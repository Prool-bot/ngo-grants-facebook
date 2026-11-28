import json
import sys
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"worker"))
from patch_quiet_support import add_link, DIRECT, NATIVE, MARKER, URL
from patch_support_header import move_link, patch, check_header, HEADER_LINK

class SupportHeaderTest(unittest.TestCase):
    def test_both_templates(self):
        for name in ("direct-preview.html","preview.html"):
            html=(ROOT/"mini-app"/name).read_text("utf-8")
            old=add_link(html)
            moved=move_link(old)
            check_header(moved)
            self.assertLess(moved.index(HEADER_LINK),moved.index('id="progressFill"'))
            self.assertEqual(moved.count(URL),1)
            # Reconstruct exact old HTML to prove no other content changed.
            restored=moved.replace(HEADER_LINK+'\n','',1).replace('id="mode" style="display:none"','id="mode"',1)
            from patch_quiet_support import BLOCK
            restored=restored.replace("</main>",BLOCK+"\n</main>",1)
            self.assertEqual(restored,old)
            source="// "+MARKER+"\n"+DIRECT+json.dumps(old)+";\n"+NATIVE+json.dumps(old)+";\nconst unchanged=42;"
            result=patch(source,old,old)
            self.assertTrue(result.endswith("const unchanged=42;"))
            with self.assertRaises(RuntimeError):patch(source,old+"x",old)
            with self.assertRaises(RuntimeError):move_link(moved)
