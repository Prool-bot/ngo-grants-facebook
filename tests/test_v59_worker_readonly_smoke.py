"""Pure unit tests for the public-GET-only Worker staging probe."""
import importlib.util
import io
from pathlib import Path
import unittest
from unittest.mock import patch
from contextlib import redirect_stdout

PATH = Path(__file__).resolve().parents[1]/"scripts"/"v59_worker_readonly_smoke.py"
spec = importlib.util.spec_from_file_location("v59_worker_readonly_smoke", PATH)
smoke = importlib.util.module_from_spec(spec)
spec.loader.exec_module(smoke)


class ReadonlyWorkerChecks(unittest.TestCase):
    def test_two_requests_are_explicit_public_get_only(self):
        class Result:
            status=200
            def __enter__(self): return self
            def __exit__(self, *_): return False
            def read(self, limit): return b'{"menu_version":"5.8"}'
        with patch.object(smoke,"urlopen",return_value=Result()) as opener:
            code, payload=smoke.get("/health")
        self.assertEqual(200,code)
        self.assertIn(b"5.8",payload)
        request=opener.call_args.args[0]
        self.assertEqual("GET",request.get_method())
        self.assertIsNone(request.data)
        self.assertTrue(request.full_url.endswith("/health"))
        self.assertNotIn("Authorization",request.headers)

    def test_healthy_worker_and_protected_internal_endpoint(self):
        with patch.object(smoke,"get",side_effect=[
                (200,b'{"menu_version":"5.8"}'),(403,b"Forbidden")]):
            self.assertEqual(0,smoke.main())

    def test_wrong_version_blocks_promotion(self):
        with patch.object(smoke,"get",side_effect=[
                (200,b'{"menu_version":"5.2"}'),(403,b"Forbidden")]):
            with redirect_stdout(io.StringIO()) as buf:
                self.assertEqual(1,smoke.main())
        self.assertIn("NOT_CONFIRMED",buf.getvalue())

    def test_unprotected_internal_endpoint_blocks(self):
        with patch.object(smoke,"get",side_effect=[
                (200,b'{"menu_version":"5.8"}'),(200,b"secret")]):
            self.assertEqual(1,smoke.main())

if __name__ == "__main__":
    unittest.main()
