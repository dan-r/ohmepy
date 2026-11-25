import unittest
from ohme import OhmeApiClient


class TestChargeSessionId(unittest.IsolatedAsyncioTestCase):
    def _client(self, session):
        client = OhmeApiClient("test@example.com", "password")
        client.serial = "ohme123"
        self.calls = []

        async def make_request(method, url, data=None, skip_json=False):
            self.calls.append(f"{method} {url}")
            if url == "/v1/chargeSessions":
                return [session]
            if url == "/v1/chargeSessions/nextSessionInfo":
                return {"rule": {}}
            return "" if method == "POST" else True

        client._make_request = make_request
        return client

    async def _actions(self, client):
        self.calls.clear()
        await client.async_approve_charge()
        await client.async_pause_charge()
        await client.async_resume_charge()
        return self.calls

    async def test_actions_use_session_id(self):
        client = self._client({"mode": "PENDING_APPROVAL", "sessionId": "ohme123-20261008-130652-1"})
        await client.async_get_charge_session()

        self.assertEqual(await self._actions(client), [
            "PUT /v1/chargeSessions/ohme123-20261008-130652-1/approve?approve=true",
            "POST /v1/chargeSessions/ohme123-20261008-130652-1/stop",
            "POST /v1/chargeSessions/ohme123-20261008-130652-1/resume",
        ])

    async def test_actions_fall_back_to_serial_without_session_id(self):
        client = self._client({"mode": "DISCONNECTED"})
        await client.async_get_charge_session()

        self.assertEqual(await self._actions(client), [
            "PUT /v1/chargeSessions/ohme123/approve?approve=true",
            "POST /v1/chargeSessions/ohme123/stop",
            "POST /v1/chargeSessions/ohme123/resume",
        ])

    async def test_actions_fall_back_to_serial_before_first_fetch(self):
        client = self._client({})

        self.assertEqual(await self._actions(client), [
            "PUT /v1/chargeSessions/ohme123/approve?approve=true",
            "POST /v1/chargeSessions/ohme123/stop",
            "POST /v1/chargeSessions/ohme123/resume",
        ])


if __name__ == "__main__":
    unittest.main()
