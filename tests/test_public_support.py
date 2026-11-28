import sys
import unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import add_pinned_support as pinned
import ngo_grants_ai as ai

class PublicSupportTests(unittest.TestCase):
    def test_pinned_preserves_original_link(self):
        old={"inline_keyboard":[[{"text":pinned.LABEL,"url":pinned.MAIN_LINK}]]}
        message={"message_id":pinned.POST_ID,"text":pinned.LABEL,
                 "entities":[{"type":"text_link","url":pinned.MAIN_LINK}],"reply_markup":old}
        self.assertFalse(pinned.validate_post(message))
        self.assertEqual(pinned.expected_markup()["inline_keyboard"][:1],old["inline_keyboard"])
        message["reply_markup"]=pinned.expected_markup()
        self.assertTrue(pinned.validate_post(message,after=True))
        message["reply_markup"]={"inline_keyboard":[[{"text":"Інша назва","url":pinned.MAIN_LINK}],[{"text":"Додатково","url":"https://t.me/ngo_grants"}]]}
        planned=pinned.plan_markup(message)
        self.assertEqual(planned["inline_keyboard"][:-1],message["reply_markup"]["inline_keyboard"])
        self.assertEqual(planned["inline_keyboard"][-1][0]["url"],pinned.SUPPORT_URL)
        message["message_id"]=0
        with self.assertRaises(RuntimeError):pinned.validate_post(message)

    def test_pdf_buttons_and_companion_preserved(self):
        order="https://t.me/ngogratsAI_bot?startapp=ngo_grants"
        companion={"inline_keyboard":[[{"text":"Умовні","url":"https://t.me/ngo_grants/42"}]]}
        with patch.object(ai,"verified_order_url",return_value=order):
            markup=ai.catalog_public_markup()
            self.assertEqual([row[0]["url"] for row in markup["inline_keyboard"]],[order,ai.SUPPORT_URL])
            both=ai.catalog_public_markup(companion)
            self.assertEqual(both["inline_keyboard"][0],companion["inline_keyboard"][0])
            self.assertEqual(ai.catalog_public_markup(both),both)
        with patch.object(ai,"verified_order_url",return_value=None):
            self.assertEqual(ai.catalog_public_markup()["inline_keyboard"][0][0]["url"],ai.SUPPORT_URL)
