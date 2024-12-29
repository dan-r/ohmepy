"""Ohme API library."""

import logging
import json
from time import time
from enum import Enum
from typing import Any
from dataclasses import dataclass
import datetime
import aiohttp
from .utils import time_next_occurs, ChargeSlot, slot_list
from .const import VERSION, GOOGLE_API_KEY

_LOGGER = logging.getLogger(__name__)


class ChargerStatus(Enum):
    """Charger state enum."""

    UNPLUGGED = "unplugged"
    PENDING_APPROVAL = "pending_approval"
    CHARGING = "charging"
    PLUGGED_IN = "plugged_in"
    PAUSED = "paused"


@dataclass
class ChargerPower:
    """Dataclass for reporting power status of charger."""

    watts: float
    amps: float
    volts: int | None
    ct_amps: float


class OhmeApiClient:
    """API client for Ohme EV chargers."""

    def __init__(self, email: str, password: str) -> None:
        if email is None or password is None:
            raise AuthException("Credentials not provided")

        # Credentials from configuration
        self.email = email
        self._password = password

        # Charger and its capabilities
        self.device_info: dict[str, Any] = {}
        self._charge_session: dict[str, Any] = {}
        self._advanced_settings: dict[str, Any] = {}
        self.schedules: list[dict[str, Any]] = []
        self.energy: float = 0.0
        self.battery: int = 0

        self._capabilities: dict[str, bool | str | list[str]] = {}
        self.ct_connected: bool = False
        self.cap_available: bool = True
        self.solar_capable: bool = False

        # Authentication
        self._token_birth: float = 0.0
        self._token: str | None = None
        self._refresh_token: str | None = None

        # User info
        self.serial = ""

        # Sessions
        self._timeout = aiohttp.ClientTimeout(total=10)
        self._last_rule: dict[str, Any] = {}

    # Auth methods

    async def async_login(self) -> bool:
        """Refresh the user auth token from the stored credentials."""
        async with aiohttp.ClientSession(timeout=self._timeout) as session:
            async with session.post(
                f"https://www.googleapis.com/identitytoolkit/v3/relyingparty/verifyPassword?key={GOOGLE_API_KEY}",
                data={
                    "email": self.email,
                    "password": self._password,
                    "returnSecureToken": True,
                },
            ) as resp:
                if resp.status != 200:
                    raise AuthException("Incorrect credentials")

                resp_json = await resp.json()
                self._token_birth = time()
                self._token = resp_json["idToken"]
                self._refresh_token = resp_json["refreshToken"]
                return True
        raise AuthException("Incorrect credentials")

    async def _async_refresh_session(self) -> bool:
        """Refresh auth token if needed."""
        if self._token is None:
            return await self.async_login()

        # Don't refresh token unless its over 45 mins old
        if time() - self._token_birth < 2700:
            return True

        async with aiohttp.ClientSession(timeout=self._timeout) as session:
            async with session.post(
                f"https://securetoken.googleapis.com/v1/token?key={GOOGLE_API_KEY}",
                data={
                    "grantType": "refresh_token",
                    "refreshToken": self._refresh_token,
                },
            ) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    msg = f"Ohme auth refresh error: {text}"
                    _LOGGER.error(msg)
                    raise AuthException(msg)

                resp_json = await resp.json()
                self._token_birth = time()
                self._token = resp_json["id_token"]
                self._refresh_token = resp_json["refresh_token"]
                return True

    # Internal methods

    async def _handle_api_error(self, url, resp):
        """Raise an exception if API response failed."""
        if resp.status != 200:
            text = await resp.text()
            msg = f"Ohme API response error: {url}, {resp.status}; {text}"
            _LOGGER.error(msg)
            raise ApiException(msg)

    async def _make_request(self, method, url, data=None, skip_json=False):
        """Make an HTTP request."""
        await self._async_refresh_session()

        async with aiohttp.ClientSession(
            base_url="https://api.ohme.io", timeout=self._timeout
        ) as session:
            async with session.request(
                method=method,
                url=url,
                data=json.dumps(data) if data and method in {"PUT", "POST"} else data,
                headers={
                    "Authorization": f"Firebase {self._token}",
                    "Content-Type": "application/json",
                    "User-Agent": f"ohmepy/{VERSION}",
                },
            ) as resp:
                _LOGGER.debug(
                    "%s request to %s, status code %s", method, url, resp.status
                )
                await self._handle_api_error(url, resp)

                if skip_json and method == "POST":
                    return await resp.text()

                return await resp.json() if method != "PUT" else True

    # Simple getters

    def is_capable(self, capability) -> bool:
        """Return whether or not this model has a given capability."""
        return bool(self._capabilities[capability])

    @property
    def status(self) -> ChargerStatus:
        """Return status from enum."""
        if self._charge_session["mode"] == "PENDING_APPROVAL":
            return ChargerStatus.PENDING_APPROVAL
        elif self._charge_session["mode"] == "DISCONNECTED":
            return ChargerStatus.UNPLUGGED
        elif self._charge_session["mode"] == "STOPPED":
            return ChargerStatus.PAUSED
        elif (
            self._charge_session.get("power")
            and self._charge_session["power"].get("watt", 0) > 0
        ):
            return ChargerStatus.CHARGING
        else:
            return ChargerStatus.PLUGGED_IN

    @property
    def available(self) -> bool:
        """CT reading."""
        return self._advanced_settings.get("online", False)

    @property
    def power(self) -> ChargerPower:
        """Return all power readings."""

        charge_power = self._charge_session.get("power") or {}
        return ChargerPower(
            watts=charge_power.get("watt", 0),
            amps=charge_power.get("amp", 0),
            volts=charge_power.get("volt", None),
            ct_amps=self._advanced_settings.get("clampAmps", 0),
        )

    @property
    def slots(self) -> list[ChargeSlot]:
        """Slot list."""
        return slot_list(self._charge_session)

    @property
    def next_slot_start(self) -> datetime.datetime | None:
        """Next slot start."""
        return min(
            (
                slot.start
                for slot in self.slots
                if slot.start > datetime.datetime.now().astimezone()
            ),
            default=None,
        )

    @property
    def next_slot_end(self) -> datetime.datetime | None:
        """Next slot start."""
        return min(
            (
                slot.end
                for slot in self.slots
                if slot.end > datetime.datetime.now().astimezone()
            ),
            default=None,
        )

    # Push methods

    async def async_pause_charge(self) -> bool:
        """Pause an ongoing charge"""
        result = await self._make_request(
            "POST", f"/v1/chargeSessions/{self.serial}/stop", skip_json=True
        )
        return bool(result)

    async def async_resume_charge(self) -> bool:
        """Resume a paused charge"""
        result = await self._make_request(
            "POST", f"/v1/chargeSessions/{self.serial}/resume", skip_json=True
        )
        return bool(result)

    async def async_approve_charge(self) -> bool:
        """Approve a charge"""
        result = await self._make_request(
            "PUT", f"/v1/chargeSessions/{self.serial}/approve?approve=true"
        )
        return bool(result)

    async def async_max_charge(self, state=True) -> bool:
        """Enable max charge"""
        result = await self._make_request(
            "PUT",
            f"/v1/chargeSessions/{self.serial}/rule?maxCharge=" + str(state).lower(),
        )
        return bool(result)

    async def async_apply_session_rule(
        self,
        max_price=None,
        target_time=None,
        target_percent=None,
        pre_condition=None,
        pre_condition_length=None,
    ) -> bool:
        """Apply rule to ongoing charge/stop max charge."""
        # Check every property. If we've provided it, use that. If not, use the existing.
        if max_price is None:
            if (
                "settings" in self._last_rule
                and self._last_rule["settings"] is not None
                and len(self._last_rule["settings"]) > 1
            ):
                max_price = self._last_rule["settings"][0]["enabled"]
            else:
                max_price = False

        if target_percent is None:
            target_percent = (
                self._last_rule["targetPercent"]
                if "targetPercent" in self._last_rule
                else 80
            )

        if pre_condition is None:
            pre_condition = (
                self._last_rule["preconditioningEnabled"]
                if "preconditioningEnabled" in self._last_rule
                else False
            )

        if pre_condition_length is None:
            pre_condition_length = (
                self._last_rule["preconditionLengthMins"]
                if (
                    "preconditionLengthMins" in self._last_rule
                    and self._last_rule["preconditionLengthMins"] is not None
                )
                else 30
            )

        if target_time is None:
            # Default to 9am
            target_time = (
                self._last_rule["targetTime"]
                if "targetTime" in self._last_rule
                else 32400
            )
            target_time = (target_time // 3600, (target_time % 3600) // 60)

        target_ts = int(
            time_next_occurs(target_time[0], target_time[1]).timestamp() * 1000
        )

        # Convert these to string form
        max_price = "true" if max_price else "false"
        pre_condition = "true" if pre_condition else "false"

        result = await self._make_request(
            "PUT",
            f"/v1/chargeSessions/{self.serial}/rule?enableMaxPrice={max_price}&targetTs={target_ts}&enablePreconditioning={pre_condition}&toPercent={target_percent}&preconditionLengthMins={pre_condition_length}",
        )
        return bool(result)

    async def async_change_price_cap(self, enabled=None, cap=None) -> bool:
        """Change price cap settings."""
        settings = await self._make_request("PUT", "/v1/users/me/settings")
        if enabled is not None:
            settings["chargeSettings"][0]["enabled"] = enabled

        if cap is not None:
            settings["chargeSettings"][0]["value"] = cap

        result = await self._make_request("PUT", "/v1/users/me/settings", data=settings)
        return bool(result)

    async def async_update_schedule(
        self,
        target_percent=None,
        target_time=None,
        pre_condition=None,
        pre_condition_length=None,
    ) -> bool:
        """Update the first listed schedule."""
        await self.async_get_schedules()

        rule = self.schedules[0]

        # Account for user having no rules
        if not rule:
            return False

        # Update percent and time if provided
        if target_percent is not None:
            rule["targetPercent"] = target_percent
        if target_time is not None:
            rule["targetTime"] = (target_time[0] * 3600) + (target_time[1] * 60)

        # Update pre-conditioning if provided
        if pre_condition is not None:
            rule["preconditioningEnabled"] = pre_condition
        if pre_condition_length is not None:
            rule["preconditionLengthMins"] = pre_condition_length

        await self._make_request("PUT", f"/v1/chargeRules/{rule['id']}", data=rule)
        return True

    async def async_set_configuration_value(self, values) -> bool:
        """Set a configuration value or values."""
        result = await self._make_request(
            "PUT", f"/v1/chargeDevices/{self.serial}/appSettings", data=values
        )
        return bool(result)

    # Pull methods

    async def async_get_charge_session(self) -> None:
        """Fetch charge sessions endpoint."""
        resp = await self._make_request("GET", "/v1/chargeSessions")
        resp = resp[0]

        self._charge_session = resp

        # Store last rule
        if resp["mode"] == "SMART_CHARGE" and "appliedRule" in resp:
            self._last_rule = resp["appliedRule"]

        # Calculate energy
        new_energy = (resp.get("chargeGraph", {}).get("now", {}) or {}).get("y", 0)
        if self.energy is None or new_energy <= 0:
            self.energy = new_energy
        elif (
            self.energy > 0 and new_energy > 0 and (new_energy / self.energy) < 0.1
        ):  # Allow a significant (90%+) drop, even if we dont hit exactly 0
            self.energy = new_energy
        else:
            self.energy = max(0, self.energy or 0, new_energy)

        self.battery = resp.get("car", {}).get("batterySoc", {}).get("percent", 0)
        self.battery = self.battery or resp.get("batterySoc", {}).get("percent", 0)

    async def async_get_advanced_settings(self) -> None:
        """Get advanced settings (mainly for CT clamp reading)"""
        resp = await self._make_request(
            "GET", f"/v1/chargeDevices/{self.serial}/advancedSettings"
        )

        self._advanced_settings = resp

        # clampConnected is not reliable, so check clampAmps being > 0 as an alternative
        if resp["clampConnected"] or (
            isinstance(resp.get("clampAmps"), float) and resp.get("clampAmps") > 0
        ):
            self.ct_connected = True

    async def async_get_schedules(self) -> None:
        """Get charge schedules."""
        schedules = await self._make_request("GET", "/v1/chargeRules")

        self.schedules = schedules

    async def async_update_device_info(self) -> bool:
        """Update _device_info with our charger model."""
        resp = await self._make_request("GET", "/v1/users/me/account")

        device = resp["chargeDevices"][0]

        self._capabilities = device["modelCapabilities"]
        self.serial = device["id"]

        self.device_info = {
            "name": device["modelTypeDisplayName"],
            "model": device["modelTypeDisplayName"].replace("Ohme ", ""),
            "sw_version": device["firmwareVersionLabel"],
        }

        if resp["tariff"] is not None and resp["tariff"]["dsrTariff"]:
            self.cap_available = False

        solar_modes = device["modelCapabilities"]["solarModes"]
        if isinstance(solar_modes, list) and len(solar_modes) == 1:
            self.solar_capable = True

        return True


# Exceptions
class ApiException(Exception): ...


class AuthException(ApiException): ...
