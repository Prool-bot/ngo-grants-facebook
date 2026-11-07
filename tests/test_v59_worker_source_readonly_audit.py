"""No-source-disclosure preflight tests for deployed Worker audit."""
import importlib.util
import io
import os
from pathlib import Path
import unittest
from unittest.mock import patch
from contextlib import redirect_stdout

PATH = Path(__file__).resolve().parents[1]/"scripts"/"v59_worker_source_readonly_audit.py"
spec=importlib.util.spec_from_file_location("v59_worker_source_readonly_audit",PATH)
audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)

class AuditTests(unittest.TestCase):
    def test_detects_dual_link_fields_without_source_output(self):
        source=b"menu_version:'5.8' channel_url channel_urls channel_tiers"
        flags=audit.inspect_source(source)
        self.assertTrue(flags["multiple_links_field"])
        self.assertTrue(flags["tiers_field"])

    def test_missing_fields_fail_closed(self):
        flags=audit.inspect_source(b"menu_version:'5.8'; channel_url")
        self.assertFalse(flags["multiple_links_field"])
        self.assertFalse(flags["tiers_field"])

    def test_missing_credentials_never_request_remote_source(self):
        with patch.dict(os.environ,{},clear=True), \
             patch.object(audit.urllib.request,"urlopen") as network:
            with redirect_stdout(io.StringIO()) as text:
                self.assertEqual(2,audit.main())
        network.assert_not_called()
        self.assertIn("UNVERIFIED",text.getvalue())

    def test_no_source_is_written_or_printed(self):
        payload=b"private-source-unique-string channel_urls channel_tiers menu_version:'5.8'"
        class Response:
            def __enter__(self):return self
            def __exit__(self,*a):return False
            def read(self,n):return payload
        with patch.dict(os.environ,{"CF_WORKER_ACCOUNT_ID":"example","CF_WORKER_API_TOKEN":"redacted"}), \
             patch.object(audit.urllib.request,"urlopen",return_value=Response()) as request, \
             redirect_stdout(io.StringIO()) as text:
            self.assertEqual(0,audit.main())
        self.assertNotIn("private-source-unique-string",text.getvalue())
        self.assertNotIn("redacted",text.getvalue())
        self.assertEqual("GET",request.call_args.args[0].get_method())

if __name__=="__main__":
    unittest.main()
