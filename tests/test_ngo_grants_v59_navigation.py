import unittest
from unittest.mock import Mock
from ngo_grants_v59_navigation import companion_markup, ensure_companion_navigation

def docs():
    return [{"tier":"direct","status":"sent","message_id":8121},
            {"tier":"conditional","status":"sent","message_id":8122}]

class NavigationTests(unittest.TestCase):
    def setUp(self):
        self.state={"v59_deliveries":{"333":{"documents":docs()}}}

    def test_first_pdf_links_second(self):
        markup=companion_markup(docs(),"ngo_grants")
        self.assertEqual("https://t.me/ngo_grants/8122",
                         markup["inline_keyboard"][0][0]["url"])
        self.assertIn("умовні",markup["inline_keyboard"][0][0]["text"].lower())

    def test_private_channel_numeric_link(self):
        markup=companion_markup(docs(),"-1001234567890")
        self.assertEqual("https://t.me/c/1234567890/8122",
                         markup["inline_keyboard"][0][0]["url"])

    def test_link_once_and_persist_confirmation(self):
        edit=Mock();save=Mock()
        self.assertTrue(ensure_companion_navigation(
            self.state,order_id=333,channel="ngo_grants",
            edit_markup=edit,save=save))
        self.assertEqual(8121,edit.call_args.args[0])
        save.assert_called_once()
        self.assertTrue(ensure_companion_navigation(
            self.state,order_id=333,channel="ngo_grants",
            edit_markup=edit,save=save))
        edit.assert_called_once()

    def test_unknown_response_is_safe_to_retry_same_markup(self):
        edit=Mock(side_effect=[TimeoutError("response lost"),
                               RuntimeError("message is not modified")])
        save=Mock()
        with self.assertRaises(TimeoutError):
            ensure_companion_navigation(self.state,order_id=333,
              channel="ngo_grants",edit_markup=edit,save=save)
        save.assert_not_called()
        self.assertTrue(ensure_companion_navigation(
            self.state,order_id=333,channel="ngo_grants",
            edit_markup=edit,save=save))
        self.assertEqual("linked",self.state["v59_deliveries"]["333"]["navigation_status"])
        self.assertEqual(2,edit.call_count)
        self.assertEqual(edit.call_args_list[0].args,edit.call_args_list[1].args)

    def test_only_conditional_document_needs_no_markup(self):
        self.state["v59_deliveries"]["333"]["documents"]=docs()[1:]
        edit=Mock();save=Mock()
        self.assertTrue(ensure_companion_navigation(
            self.state,order_id=333,channel="ngo_grants",
            edit_markup=edit,save=save))
        edit.assert_not_called();save.assert_not_called()

    def test_unconfirmed_document_cannot_be_linked(self):
        self.state["v59_deliveries"]["333"]["documents"][1]["status"]="sending"
        with self.assertRaisesRegex(RuntimeError,"публікації"):
            ensure_companion_navigation(self.state,order_id=333,
               channel="ngo_grants",edit_markup=Mock(),save=Mock())

if __name__=="__main__":
    unittest.main()
