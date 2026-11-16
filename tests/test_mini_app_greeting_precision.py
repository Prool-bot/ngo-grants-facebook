"""Mini App request precision and robot gesture behavior regression."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class RobotAndFormTests(unittest.TestCase):
    def test_greeting_only_triggers_arm_wave(self):
        js = (ROOT / "mini-app/app.js").read_text("utf-8")
        css = (ROOT / "mini-app/styles.css").read_text("utf-8")
        self.assertIn("if(kind!=='wave'||!robotArm||reduced.matches)return;", js)
        self.assertIn("()=>trigger('wave')", js)
        self.assertNotIn("robot.classList.add('react')", js)
        self.assertNotIn(".robot.react{animation:", css)
        self.assertIn(".robot-arm.wave{opacity:1;animation:arm-wave", css)

    def test_broad_selections_require_a_concrete_request(self):
        js = (ROOT / "mini-app/app.js").read_text("utf-8")
        self.assertIn("return draft.sectors.includes('all') || draft.audience==='all'", js)
        self.assertIn("draft.detail.trim().length<12", js)
        self.assertIn("фах чи кваліфікацію", js)

    def test_production_safety_preserved(self):
        js = (ROOT / "mini-app/app.js").read_text("utf-8")
        self.assertIn("const result=await directController.submit(draft)", js)
        self.assertIn("if(!directController)", js)
        self.assertIn("submit(draft)", js)


if __name__ == "__main__":
    unittest.main()
