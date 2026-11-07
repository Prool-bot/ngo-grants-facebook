import importlib.util
from pathlib import Path
from unittest import TestCase,main

PATH=Path(__file__).resolve().parents[1]/"scripts"/"mini_app_live_worker_signature_audit.py"
spec=importlib.util.spec_from_file_location("mini_app_live_worker_signature_audit",PATH)
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)

class Tests(TestCase):
    def test_only_identifier_metadata_not_function_body_is_returned(self):
        source=(b"async function createRequest(env,hash,topic,facets){"
                b"const privateKey='secret-123'; return await env.DB.prepare("
                b"'INSERT INTO orders VALUES(1)').run();}\n"
                b"function hashUser(id){return 'secret-123';}\n")
        v=mod.shape(source)
        self.assertEqual(v["createRequest"]["args"],["env","hash","topic","facets"])
        self.assertEqual(v["tables"],["orders"])
        self.assertNotIn("secret-123",repr(v))
    def test_complex_args_are_not_echoed(self):
        source=b"function beginOrder(env,callback = 'secret-placeholder'){ return 1; }"
        result=mod.shape(source)
        self.assertEqual(result["beginOrder"]["args"],["env","<complex>"])
        self.assertNotIn("secret-placeholder",repr(result))

if __name__=="__main__":main()
