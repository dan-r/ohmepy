import unittest
from unittest.mock import AsyncMock, patch
from ohme import OhmeApiClient


class TestSolar(unittest.IsolatedAsyncioTestCase):
    def test_solar_enabled_property(self):
        client = OhmeApiClient("test@example.com", "password")

        # Off / IGNORE
        client._configuration = {"solarMode": "IGNORE"}
        self.assertFalse(client.solar_enabled)

        # ZERO_EXPORT
        client._configuration = {"solarMode": "ZERO_EXPORT"}
        self.assertTrue(client.solar_enabled)

        # PURE_SOLAR
        client._configuration = {"solarMode": "PURE_SOLAR"}
        self.assertTrue(client.solar_enabled)

        # None / Missing
        client._configuration = {}
        self.assertFalse(client.solar_enabled)

    async def test_solar_capability_multiple_modes(self):
        client = OhmeApiClient("test@example.com", "password")

        account_resp = {
            "user": {"id": "user123"},
            "tariff": None,
            "chargeDevices": [{
                "id": "ohme123",
                "modelTypeDisplayName": "Ohme Home Pro",
                "firmwareVersionLabel": "v1.0.0",
                "modelCapabilities": {
                    "solarModes": ["PURE_SOLAR", "ZERO_EXPORT"]
                },
                "optionalSettings": {}
            }]
        }

        with patch.object(client, "_make_request", new=AsyncMock(return_value=account_resp)):
            self.assertTrue(await client.async_update_device_info())
            self.assertTrue(client.is_capable("solar"))

    async def test_solar_capability_single_mode(self):
        client = OhmeApiClient("test@example.com", "password")

        account_resp = {
            "user": {"id": "user123"},
            "tariff": None,
            "chargeDevices": [{
                "id": "ohme123",
                "modelTypeDisplayName": "Ohme Home Pro",
                "firmwareVersionLabel": "v1.0.0",
                "modelCapabilities": {
                    "solarModes": ["ZERO_EXPORT"]
                },
                "optionalSettings": {}
            }]
        }

        with patch.object(client, "_make_request", new=AsyncMock(return_value=account_resp)):
            self.assertTrue(await client.async_update_device_info())
            self.assertTrue(client.is_capable("solar"))

    async def test_solar_capability_empty_or_missing(self):
        client = OhmeApiClient("test@example.com", "password")

        account_resp = {
            "user": {"id": "user123"},
            "tariff": None,
            "chargeDevices": [{
                "id": "ohme123",
                "modelTypeDisplayName": "Ohme Home Pro",
                "firmwareVersionLabel": "v1.0.0",
                "modelCapabilities": {
                    "solarModes": []
                },
                "optionalSettings": {}
            }]
        }

        with patch.object(client, "_make_request", new=AsyncMock(return_value=account_resp)):
            self.assertTrue(await client.async_update_device_info())
            self.assertFalse(client.is_capable("solar"))


if __name__ == "__main__":
    unittest.main()
