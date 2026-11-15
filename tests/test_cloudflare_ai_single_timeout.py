"""A slow but valid Cloudflare AI response must not be cut off at 35 s.

Preserves one request per attempt; no automatic POST replay that might burn
additional free Worker AI tokens. Network/API are fully mocked.
"""
import os
from unittest import TestCase
from unittest.mock import patch
import ngo_grants_ai as mod

class SingleCloudflareAIRequestTests(TestCase):
 def test_one_call_allows_60_seconds_without_retry(self):
  response={"success":True,"result":{"response":"{}"}}
  with patch.dict(os.environ,{"CF_ACCOUNT_ID":"test-account","CF_API_TOKEN":"test-secret"}),\
       patch.object(mod,"http_json",return_value=response) as call,\
       patch.object(mod,"_parse_ai_json",return_value={"direct_ids":[]}) as parser:
    answer=mod.cf_ai("check",{"safe":"topic"},max_tokens=150,
                     required_keys=("direct_ids",))
  self.assertEqual(answer,{"direct_ids":[]})
  call.assert_called_once()
  self.assertEqual(call.call_args.kwargs["timeout"],60)
  self.assertEqual(call.call_args.kwargs["data"]["max_tokens"],150)
  self.assertEqual(call.call_args.kwargs["data"]["temperature"],0.0)
  parser.assert_called_once()
 def test_timeout_has_no_automatic_post_replay(self):
  with patch.dict(os.environ,{"CF_ACCOUNT_ID":"test-account","CF_API_TOKEN":"test-secret"}),\
       patch.object(mod,"http_json",side_effect=TimeoutError("read timed out")) as call:
    with self.assertRaises(TimeoutError):
     mod.cf_ai("test",{"safe":"topic"})
  call.assert_called_once()
