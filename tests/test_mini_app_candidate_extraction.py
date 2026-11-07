import importlib.util
import sys
from pathlib import Path
from unittest import TestCase, main

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"worker"))
spec=importlib.util.spec_from_file_location(
 "build_mini_app_candidate",ROOT/"worker"/"build_mini_app_candidate.py")
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

class ExtractionTests(TestCase):
    def test_plain_javascript(self):
        self.assertEqual(module.extract_js("application/javascript",b"export default {};"),
                         "export default {};")
    def test_multipart_worker_module(self):
        body=(
          b"--BOUNDARY\r\n"
          b'Content-Disposition: form-data; name="metadata"\r\n'
          b"Content-Type: application/json\r\n\r\n"
          b'{"bindings":[]}\r\n'
          b"--BOUNDARY\r\n"
          b'Content-Disposition: form-data; name="worker.mjs"; filename="worker.mjs"\r\n'
          b"Content-Type: application/javascript+module\r\n\r\n"
          b"export default {async fetch(){return new Response('ok')}};\r\n"
          b"--BOUNDARY--\r\n"
        )
        source=module.extract_js("multipart/form-data; boundary=BOUNDARY",body)
        self.assertTrue(source.startswith("export default"))
        self.assertNotIn("Content-Disposition",source)
        self.assertNotIn("bindings",source)
    def test_multiple_modules_fail_closed(self):
        body=(
            b"--abc\r\n"
            b'Content-Disposition: form-data; name="a.mjs"; filename="a.mjs"\r\n\r\nx\r\n'
            b"--abc\r\n"
            b'Content-Disposition: form-data; name="b.mjs"; filename="b.mjs"\r\n\r\ny\r\n'
            b"--abc--\r\n"
        )
        with self.assertRaises(RuntimeError):
            module.extract_js("multipart/form-data; boundary=abc",body)
    def test_empty_source_is_rejected(self):
        with self.assertRaises(RuntimeError):
            module.extract_js("application/javascript",b"")

if __name__=="__main__":
    main()
