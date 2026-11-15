"""Workers-Free Gemma 4 REST migration contract tests; network fully mocked."""
from __future__ import annotations
import os
from unittest import TestCase
from unittest.mock import patch
import ngo_grants_ai as app

ENV={"CF_ACCOUNT_ID":"test-account","CF_API_TOKEN":"test-token"}
MODEL="@cf/google/gemma-4-26b-a4b-it"

class GemmaFreeMigrationTests(TestCase):
 def test_pinned_to_live_verified_free_model(self):
  self.assertEqual(app.CF_MODEL,MODEL)
  self.assertIn(app.CF_MODEL,app.CF_FREE_MODEL_ALLOWLIST)
  self.assertNotIn("@cf/meta/llama-3.1-8b-instruct-fp8",app.CF_FREE_MODEL_ALLOWLIST)

 def test_real_gemma_api_response_shape_and_exact_one_call(self):
  json_text='{"title":"Гранти для неформальних молодіжних груп","subject":"молодь","topic_groups":[["молодіжні ініціативи"]]}'
  result={"success":True,"result":{
   "id":"test","model":MODEL,
   "choices":[{"index":0,"message":{"role":"assistant","content":json_text},"finish_reason":"stop"}],
   "usage":{"prompt_tokens":20,"completion_tokens":40}}}
  with patch.dict(os.environ,ENV),patch.object(app,"http_json",return_value=result) as sent:
   info=app.cf_ai("Return JSON",{"topic":"молодь"},max_tokens=350,
                  required_keys=("title","subject","topic_groups"))
  self.assertEqual(info["subject"],"молодь")
  sent.assert_called_once()
  opts=sent.call_args.kwargs
  self.assertEqual(opts["data"]["chat_template_kwargs"],{"enable_thinking":False})
  self.assertEqual(opts["data"]["response_format"],{"type":"json_object"})
  self.assertEqual(opts["data"]["max_tokens"],350)
  self.assertEqual(opts["data"]["temperature"],0.0)
  self.assertEqual(opts["timeout"],60)
  self.assertEqual(opts["headers"]["Authorization"],"Bearer test-token")
  self.assertTrue(opts["url"].endswith("/run/"+MODEL))

 def test_classification_direct_only_from_json_content(self):
  obj={"success":True,"result":{"choices":[
   {"message":{"content":'{"direct_ids":[11],"conditional_ids":[]}'}}]}}
  with patch.dict(os.environ,ENV),patch.object(app,"http_json",return_value=obj):
   res=app.cf_ai("Only JSON",{"candidates":[11,22]},
                 required_keys=("direct_ids","conditional_ids"))
  self.assertEqual(res,{"direct_ids":[11],"conditional_ids":[]})

 def test_malformed_model_result_never_fabricates_relevance(self):
  for malformed in ({},{'result':{'choices':[]}},
                    {'result':{'choices':[{'message':{'content':''}}]}},
                    {'result':{'choices':[{'message':{'content':'{"direct_ids":[1]'}}]}}):
   with self.subTest(body=str(malformed)[:36]),patch.dict(os.environ,ENV),\
        patch.object(app,"http_json",return_value=malformed) as sent:
    with self.assertRaises(app.AIResponseFormatError):
     app.cf_ai("classify",{"topic":"test"},required_keys=("direct_ids",))
    sent.assert_called_once()

 def test_paid_model_cannot_be_selected_or_called(self):
  with patch.dict(os.environ,ENV),\
       patch.object(app,"CF_MODEL","@cf/zai-org/glm-5.3"),\
       patch.object(app,"http_json") as sent:
   with self.assertRaisesRegex(RuntimeError,"Workers-Free"):
    app.cf_ai("fake",{"topic":"x"})
   sent.assert_not_called()
