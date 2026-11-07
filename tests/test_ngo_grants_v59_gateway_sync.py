"""Verify that v5.9 dual links survive Python gateway sync serialization."""
import os
import unittest
from unittest.mock import patch
import ngo_grants_ai as app

class GatewayV59Tests(unittest.TestCase):
    def test_both_tier_urls_are_sent_to_worker(self):
        order={"id":81,"title":"Соціальні гранти",
               "channel_url":"https://t.me/ngo_grants/701",
               "channel_urls":["https://t.me/ngo_grants/701",
                               "https://t.me/ngo_grants/702"],
               "channel_tiers":["direct","conditional"],
               "published_on":"2026-11-07"}
        state={"published":[order],"gateway_seen_ids":[81],
               "queue":[],"users_days":{}}
        with patch.dict(os.environ,{"NGO_BOT_GATEWAY_URL":"https://example.invalid"}), \
             patch.object(app,"gateway_api",return_value={
                 "published":1,"acknowledged":1}) as request:
            app.notify_gateway(state)
        route,payload=request.call_args.args
        self.assertEqual("/internal/sync",route)
        self.assertEqual(order["channel_urls"],payload["published"][0]["channel_urls"])
        self.assertEqual(order["channel_tiers"],payload["published"][0]["channel_tiers"])
        self.assertNotIn("chat_id",payload["published"][0])

if __name__=="__main__":
    unittest.main()
