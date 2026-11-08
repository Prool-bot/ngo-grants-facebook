import importlib.util
from pathlib import Path
from unittest import TestCase,main
from unittest.mock import patch
root=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("d1_inspection",root/"scripts"/"mini_app_d1_live_schema_readonly.py")
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
class Tests(TestCase):
 def test_column_identifier_filter(self):
  settings={"bindings":[{"name":"DB","type":"d1",
    "id":"123e4567-e89b-42d3-a456-426614174000"}]}
  self.assertEqual(mod.validated_db_id(settings),"123e4567-e89b-42d3-a456-426614174000")
 def test_invalid_or_missing_binding_does_not_guess_id(self):
  self.assertIsNone(mod.validated_db_id({"bindings":[{"name":"DB","type":"d1"}]}))
  with self.assertRaises(RuntimeError):mod.validated_db_id({"bindings":[]})
 def test_reject_any_mutating_query_even_if_called_with_post(self):
  with self.assertRaises(ValueError):
    mod.cloudflare("POST","/d1/database/id/query","fake","fake",
                  {"sql":"DELETE FROM requests"})
  with self.assertRaises(ValueError):
    mod.cloudflare("POST","/d1/database/id/query","fake","fake",
                  {"sql":"SELECT * FROM requests"})
 def test_response_shape_does_not_require_d1_rows(self):
  result={"success":True,"results":[{"name":"id","type":"INTEGER","pk":1}]}
  self.assertEqual(mod.result_rows([result]),result["results"])
  with self.assertRaises(RuntimeError):mod.result_rows([result,result])
if __name__=="__main__":main()
