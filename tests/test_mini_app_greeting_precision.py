"""Mini App request precision and robot gesture behavior regression."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class RobotAndFormTests(unittest.TestCase):
    def test_greeting_only_triggers_arm_wave(self):
        js = (ROOT / "mini-app/app.js").read_text("utf-8")
        css = (ROOT / "mini-app/styles.css").read_text("utf-8")
        self.assertIn("if(!robotArm)return;", js)
        self.assertIn("if(kind==='ack'){", js)
        self.assertIn("if(greetedDuringForm)return;", js)
        self.assertIn("greetedDuringForm=true;", js)
        self.assertNotIn("reduced.matches", js)
        self.assertIn("()=>trigger('wave')", js)
        self.assertNotIn("robot.classList.add('react')", js)
        self.assertNotIn(".robot.react{animation:", css)
        self.assertIn(".robot-arm.wave{opacity:1;animation:arm-wave", css)
        self.assertIn("transform:rotate(53deg)", css)
        self.assertIn(".robot-arm.wave{animation:arm-wave .55s", css)

    def test_embedded_telegram_html_has_the_exact_new_wave_behavior(self):
        html=(ROOT / "mini-app/direct-preview.html").read_text("utf-8")
        self.assertIn("let greetedDuringForm=false;",html)
        self.assertIn("if(kind==='ack'){",html)
        self.assertIn("if(greetedDuringForm)return;",html)
        self.assertIn("transform:rotate(53deg)",html)
        self.assertIn(".robot-arm.wave{animation:arm-wave .55s",html)
        self.assertNotIn("reduced.matches",html)

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
