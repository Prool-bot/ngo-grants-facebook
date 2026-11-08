from pathlib import Path
import importlib.util
from unittest import TestCase,main
ROOT=Path(__file__).resolve().parents[1]
sp=importlib.util.spec_from_file_location("miniapp_sanitized_schema",ROOT/"scripts"/"mini_app_d1_schema_sanitized.py")
mod=importlib.util.module_from_spec(sp);sp.loader.exec_module(mod)
class Tests(TestCase):
 def test_extracts_only_column_identifiers_not_insert_values(self):
  private='''const secret="FAKE_TOKEN_NOT_FOR_LOGS";
  CREATE TABLE IF NOT EXISTS requests (id INTEGER PRIMARY KEY, created_at TEXT, user_hash TEXT, topic TEXT, facets TEXT);
  INSERT INTO requests VALUES (?,?,?,?,?);'''
  got=mod.analyze(private)
  self.assertEqual(got["requests"]["column_names"],
    ["id","created_at","user_hash","topic","facets"])
  self.assertEqual(got["requests"]["insert_statement_count"],1)
  self.assertNotIn("FAKE_TOKEN",repr(got))
 def test_missing_ddl_fails_informatively_not_with_invented_names(self):
  got=mod.analyze("INSERT INTO requests VALUES (?,?,?,?,?)")
  self.assertFalse(got["requests"]["schema_in_worker"])
  self.assertEqual(got["requests"]["column_names"],[])
if __name__=="__main__":main()
