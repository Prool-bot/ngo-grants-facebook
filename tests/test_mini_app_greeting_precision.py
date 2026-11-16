"""Mini App request precision and robot gesture behavior regression."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class RobotAndFormTests(unittest.TestCase):
    def test_every_form_action_triggers_both_layers(self):
        js = (ROOT / "mini-app/app.js").read_text("utf-8")
        css = (ROOT / "mini-app/styles.css").read_text("utf-8")
        self.assertIn("if(kind!=='ack'||!robotFigure||!robotArm)return;",js)
        self.assertIn("robotFigure.classList.add('hop');",js)
        self.assertIn("robotArm.classList.add('wave');",js)
        self.assertIn("void robotFigure.offsetWidth",js)
        self.assertNotIn("greetButton",js)
        self.assertNotIn("greetedDuringForm",js)
        self.assertNotIn("setInterval",js)
        self.assertIn(".robot-figure.hop{animation:robot-hop",css)
        self.assertIn("@keyframes robot-hop",css)
        self.assertIn(".robot-arm.wave{opacity:1;animation:arm-wave",css)
        self.assertIn("@keyframes arm-wave",css)
        self.assertNotIn(".robot-greet",css)

    def test_embedded_telegram_html_has_both_gestures_and_no_greeting(self):
        html=(ROOT / "mini-app/direct-preview.html").read_text("utf-8")
        self.assertIn('id="robotFigure"',html)
        self.assertIn('id="robotArm"',html)
        self.assertIn("robotFigure.classList.add('hop');",html)
        self.assertIn("robotArm.classList.add('wave');",html)
        self.assertIn("@keyframes robot-hop",html)
        self.assertIn("@keyframes arm-wave",html)
        self.assertNotIn('id="greet"',html)
        self.assertNotIn("👋 Привіт",html)
        self.assertNotIn("greetedDuringForm",html)

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
