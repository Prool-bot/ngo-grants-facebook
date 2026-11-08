import importlib.util
from pathlib import Path
from unittest import TestCase,main
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location(
 "botfather_probe",ROOT/"scripts"/"mini_app_botfather_menu_probe.py")
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
class MenuProbeTests(TestCase):
 def test_matches_only_exact_known_existing_ngo_grants_bot(self):
    self.assertTrue(mod.is_target_button("@ngogratsAI_bot"))
    self.assertTrue(mod.is_target_button("NGO Grants AI"))
    self.assertFalse(mod.is_target_button("@another_bot"))
    self.assertFalse(mod.is_target_button("Start a new bot"))
    self.assertFalse(mod.is_target_button(None))
if __name__=="__main__":main()
