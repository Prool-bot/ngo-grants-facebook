"""Exercise the opt-in preview path without AI requests, publishing or state writes."""
import copy
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import ngo_grants_ai as app

def post(i):
    return dict(
        id=i,
        text=(f"📚 Соціальний грант №{i}\n"
              "👥 ХТО МОЖЕ ПОДАВАТИСЯ: громадські організації.\n"
              "🎯 ЩО ПІДТРИМУЄТЬСЯ: соціальні послуги.\n"
              f"🔗 https://t.me/ngo_grants/{i}"),
        _title=f"Соціальний грант №{i}", _score=10-i,
        _deadline="2026-12-01", _rolling=False, link=f"https://t.me/ngo_grants/{i}")

class PreviewSafetyTests(unittest.TestCase):
    def test_dry_run_produces_two_separate_calls_and_never_sends_or_saves(self):
        state = {"queue":[{"id":101,"topic":"Соціальні послуги"}],
                 "published":[], "no_results":[]}
        before=copy.deepcopy(state)
        ranked=[post(11),post(12)]
        with tempfile.TemporaryDirectory() as dirname, \
             patch.dict(os.environ, {"NGO_GRANTS_V59_PREVIEW":"1"}), \
             patch.object(app,"PDF_DIR",Path(dirname)), \
             patch.object(app,"can_publish",return_value=True), \
             patch.object(app,"recent_no_result",return_value=None), \
             patch.object(app,"ai_expand",return_value=("Тест",{"version":0})), \
             patch.object(app,"rank_posts",return_value=ranked), \
             patch.object(app,"ai_classify",return_value={11:"direct",12:"conditional"}), \
             patch.object(app,"pdf_catalog") as pdf, \
             patch.object(app,"upload_pdf") as upload, \
             patch.object(app,"save_state") as save:
            result=app.make_one_catalog(state,ranked,dry_run=True)
            self.assertFalse(result)
            self.assertEqual(state,before)
            self.assertEqual(pdf.call_count,2)
            self.assertEqual([len(c.args[3]) for c in pdf.call_args_list],[1,1])
            self.assertEqual([c.args[3][0]["id"] for c in pdf.call_args_list],[11,12])
            self.assertEqual(pdf.call_args_list[0].args[3][0]["_relevance"],"direct")
            self.assertEqual(pdf.call_args_list[1].args[3][0]["_relevance"],"conditional")
            upload.assert_not_called()
            save.assert_not_called()

if __name__ == "__main__":
    unittest.main()
