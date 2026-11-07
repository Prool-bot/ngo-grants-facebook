"""The scheduled bot must recover the existing outbox before AI and quota."""
import os
import sys
import unittest
from unittest.mock import patch
import ngo_grants_ai as app

class ScheduledRecoveryTests(unittest.TestCase):
    def test_runner_recovers_when_ai_secrets_missing_and_quota_full(self):
        state={"schema_version":1,"queue":[{"id":555,"topic":"Соціальні послуги"}],
               "published":[{"id":1,"published_on":"2026-11-07","v59_document_count":3}],
               "no_results":[],"v59_deliveries":{"555":{"documents":[]}}}
        env={"NGO_AI_AUTOPUBLISH":"true",
             "NGO_GRANTS_AI_BOT_TOKEN":"fake-test-token",
             "NGO_BOT_GATEWAY_URL":"https://example.invalid",
             "NGO_GRANTS_V59_LIVE_DELIVERY":"true"}
        with patch.dict(os.environ,env,clear=True), \
             patch.object(sys,"argv",["ngo_grants_ai.py"]), \
             patch.object(app,"load_state",return_value=state), \
             patch.object(app,"refresh_bot_identity"), \
             patch.object(app,"configure_bot_profile"), \
             patch.object(app,"import_gateway_requests"), \
             patch.object(app,"save_state") as saver, \
             patch.object(app,"publish_pending_no_results",return_value=False), \
             patch.object(app,"can_publish",return_value=False), \
             patch.object(app,"resume_v59_delivery",return_value=True) as resume, \
             patch.object(app,"read_archive") as archive:
            app.main()
        resume.assert_called_once()
        archive.assert_not_called()
        self.assertGreaterEqual(saver.call_count,2)

if __name__=="__main__":
    unittest.main()
