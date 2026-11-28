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

    def test_catalog_caption_has_quiet_invitation_and_link(self):
        order="https://t.me/ngogratsAI_bot?startapp=ngo_grants"
        with patch.object(ai,"verified_order_url",return_value=order):
            caption=ai._catalog_caption("Тест", "Відбудова громад", None, 29, 0, 29)
            self.assertIn("Якщо наші матеріали корисні для вас, підтримайте розвиток NGO Grants.",caption)
            self.assertTrue(caption.endswith(ai.SUPPORT_URL))
            self.assertEqual(caption.count(ai.SUPPORT_URL),1)
            self.assertIn(order,caption)
            self.assertIn("Можливостей: 29 (прямі: 0; умовні: 29).",caption)
            self.assertIn("Перевіряйте актуальні правила й дедлайни.",caption)
            # Near-limit descriptions must never be truncated by the new invitation.
            base_len=len(ai._catalog_caption("Тест", "", None, 29, 0, 29).split("\n\n❤️")[0])
            detail="X"*(990-base_len)
            long_caption=ai._catalog_caption("Тест", detail, None, 29, 0, 29)
            self.assertIn(detail,long_caption)
            self.assertLessEqual(len(long_caption),1000)
            self.assertNotIn(ai.SUPPORT_URL,long_caption)

    def test_no_results_public_message_support_and_existing_link(self):
        order="https://t.me/ngogratsAI_bot?startapp=ngo_grants"
        item={"topic":"На розвиток кіно","checked_on":"2026-11-28"}
        with patch.object(ai,"verified_order_url",return_value=order):
            msg=ai.public_no_results_text(item)
            self.assertIn("Відповідних актуальних можливостей не знайдено.",msg)
            self.assertTrue(msg.endswith(ai.SUPPORT_INVITATION))
            self.assertEqual(msg.count(ai.SUPPORT_INVITATION),1)
            self.assertIn(order,msg)
            self.assertEqual(ai.no_results_public_markup()["inline_keyboard"],[
                [{"text":"🤖 Знайти гранти","url":order}],
                [{"text":"❤️ Підтримати NGO Grants","url":ai.SUPPORT_URL}]])
        with patch.object(ai,"verified_order_url",return_value=None):
            self.assertEqual(len(ai.no_results_public_markup()["inline_keyboard"]),1)
