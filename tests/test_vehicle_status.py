import datetime
import unittest
from unittest.mock import AsyncMock, patch
from ohme import OhmeApiClient, ApiException

CAR_SOC = {
    "wh": None,
    "rangeKm": None,
    "percent": 20.0,
    "timestamp": 1793876671000,
    "highPrecision": None,
    "source": "API",
    "maxRangeKm": None,
}

SESSION_SOC = {
    "wh": 3480,
    "rangeKm": 12.6,
    "percent": 26.0,
    "timestamp": 1793879020449,
    "highPrecision": None,
    "source": "EXTRAPOLATION",
    "maxRangeKm": None,
}

STATUS_RESP = {
    "soc": {
        "wh": None,
        "rangeKm": None,
        "percent": 25.0,
        "timestamp": 1793878030000,
        "highPrecision": None,
        "source": "API",
        "maxRangeKm": None,
    },
    "maxSoc": None,
    "chargingStatus": "CHARGING",
    "odometerReadingKm": None,
    "timestamp": 1793879020513,
    "statusRetrievalError": None,
    "availableChargingPowerW": None,
    "rangeDisplaySelection": None,
}


class TestVehicleStatus(unittest.IsolatedAsyncioTestCase):
    def test_battery_reading_and_estimate(self):
        client = OhmeApiClient("test@example.com", "password")
        client._charge_session = {"car": {"batterySoc": CAR_SOC}, "batterySoc": SESSION_SOC}

        reading = client.battery_reading
        self.assertEqual(reading.percent, 20.0)
        self.assertEqual(reading.source, "API")
        self.assertEqual(
            reading.timestamp,
            datetime.datetime(2026, 11, 5, 11, 4, 31, tzinfo=datetime.UTC),
        )

        estimate = client.battery_estimate
        self.assertEqual(estimate.percent, 26.0)
        self.assertEqual(estimate.source, "EXTRAPOLATION")

    def test_no_estimate_without_extrapolation(self):
        client = OhmeApiClient("test@example.com", "password")

        client._charge_session = {"batterySoc": {**SESSION_SOC, "source": "API"}}
        self.assertIsNone(client.battery_estimate)

        client._charge_session = {"batterySoc": None, "car": None}
        self.assertIsNone(client.battery_estimate)
        self.assertIsNone(client.battery_reading)

    async def test_update_vehicle_battery(self):
        client = OhmeApiClient("test@example.com", "password")
        client._cars = [{"id": "car123"}]
        client.battery = 20

        with patch.object(
            client, "_make_request", new=AsyncMock(return_value=STATUS_RESP)
        ) as request:
            battery = await client.async_update_vehicle_battery()

        request.assert_awaited_once_with(
            "GET", "/v1/cars/car123/api/status?statusRetrievalErrors=true"
        )
        self.assertEqual(battery.percent, 25.0)
        self.assertEqual(client.battery, 25.0)

    async def test_update_vehicle_battery_without_car(self):
        client = OhmeApiClient("test@example.com", "password")

        with self.assertRaises(ApiException):
            await client.async_update_vehicle_battery()
