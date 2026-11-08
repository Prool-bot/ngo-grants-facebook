import importlib.util
import io
import json
from pathlib import Path
from unittest import TestCase,main
from unittest.mock import patch
from urllib.parse import quote
import urllib.error

ROOT=Path(__file__).resolve().parents[1]
SP=importlib.util.spec_from_file_location(
  "main_channel_webview",ROOT/"scripts"/"mini_app_main_channel_webview_no_order.py")
MOD=importlib.util.module_from_spec(SP);SP.loader.exec_module(MOD)
BASE="https://"+MOD.EXPECTED_HOST+MOD.EXPECTED_PATH
SIGNED="auth_date=1794120000&user=%7B%22id%22%3A145%7D&hash="+("a"*64)

class ChannelWebViewTests(TestCase):
 def test_only_exact_worker_origin_and_signed_main_app_data(self):
    link=BASE+"?tgWebAppData="+quote(SIGNED,safe="")
    self.assertEqual(MOD.validate_webview_link(link),SIGNED)
    with self.assertRaises(RuntimeError):
       MOD.validate_webview_link("https://unrelated.example"+MOD.EXPECTED_PATH+"?tgWebAppData="+quote(SIGNED))
    with self.assertRaises(RuntimeError):
       MOD.validate_webview_link(BASE)
 def test_valid_telegram_signature_gate_probe_is_never_a_real_catalog_order(self):
    requests=[]
    def reject(req,timeout):
      requests.append(req)
      body=json.loads(req.data)
      self.assertEqual(body["facets"],{})
      self.assertEqual(body["initData"],SIGNED)
      self.assertEqual(req.get_method(),"POST")
      self.assertTrue(req.full_url.endswith(MOD.ORDER_PATH))
      raise urllib.error.HTTPError(req.full_url,400,"Bad Request",{},io.BytesIO(b'{"ok":false}'))
    with patch.object(MOD.urllib.request,"urlopen",side_effect=reject):
      self.assertTrue(MOD.reject_invalid_facets_with_valid_session(SIGNED))
    self.assertEqual(len(requests),1)
 def test_server_must_refuse_invalid_facets_after_valid_signature(self):
    def fake(req,timeout):
      raise urllib.error.HTTPError(req.full_url,401,"Unauthorized",{},io.BytesIO(b'{"ok":false}'))
    with patch.object(MOD.urllib.request,"urlopen",side_effect=fake):
      with self.assertRaisesRegex(RuntimeError,"auth gate not reached"):
        MOD.reject_invalid_facets_with_valid_session(SIGNED)

if __name__=="__main__":main()
