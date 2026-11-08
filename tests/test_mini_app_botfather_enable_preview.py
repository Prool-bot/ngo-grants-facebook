import importlib.util
from pathlib import Path
from unittest import TestCase,main
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
spec=importlib.util.spec_from_file_location("enable_preview",
 ROOT/"scripts"/"mini_app_botfather_enable_preview.py")
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
class MenuTests(TestCase):
 def test_only_enable_mini_app_is_selected(self):
  self.assertTrue(mod.is_enable("Enable Mini App"))
  self.assertTrue(mod.is_enable("Enable Main Mini App"))
  self.assertFalse(mod.is_enable("Configure Splash Screen"))
  self.assertFalse(mod.is_enable("Disable Mini App"))
  self.assertFalse(mod.is_enable("Enable Inline Mode"))
if __name__=="__main__":main()
