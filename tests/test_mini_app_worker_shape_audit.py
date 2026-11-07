import importlib.util
import io
from contextlib import redirect_stdout
from pathlib import Path
from unittest import TestCase, main
from unittest.mock import patch

PATH=Path(__file__).resolve().parents[1]/"scripts"/"mini_app_worker_shape_audit.py"
SPEC=importlib.util.spec_from_file_location("mini_app_worker_shape_audit",PATH)
AUDIT=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


class WorkerShapeAuditTests(TestCase):
    def test_reports_only_function_names_and_structure_not_bodies(self):
        source=(b"export default {async fetch(request,env){"
                b" await env.DB.prepare('INSERT INTO orders VALUES (?)').run();"
                b" await getChatMember();"
                b"}}\nfunction saveDraft(){const secret='private-value-123';}\n"
                b"async function submitOrder(){return 'private-value-123';}\n")
        report=AUDIT.inspect(source)
        self.assertTrue(report["worker_export_default"])
        self.assertTrue(report["fetch_handler"])
        self.assertTrue(report["membership_check"])
        self.assertTrue(report["d1_prepared_statement"])
        self.assertTrue(report["d1_insert"])
        self.assertIn("saveDraft",report["function_name_hints"])
        self.assertIn("submitOrder",report["function_name_hints"])
        self.assertNotIn("private-value-123",repr(report))

    def test_missing_credentials_no_network_or_source_output(self):
        with patch.dict("os.environ",{},clear=True), \
             patch.object(AUDIT.urllib.request,"urlopen") as network, \
             redirect_stdout(io.StringIO()) as stream:
            self.assertEqual(AUDIT.main(),2)
        network.assert_not_called()
        self.assertEqual(stream.getvalue().strip(),"MINI_APP_WORKER_SHAPE=NOT_CONFIGURED")

    def test_invalid_or_excessive_size_rejected(self):
        for blob in (b"",b"x"*(AUDIT.MAX_SOURCE+1)):
            with self.assertRaises(ValueError):
                AUDIT.inspect(blob)


if __name__=="__main__":
    main()
