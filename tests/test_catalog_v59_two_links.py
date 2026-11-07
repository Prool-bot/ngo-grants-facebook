import unittest
from unittest.mock import patch
import ngo_grants_ai as app

class TwoLinksMenuTests(unittest.TestCase):
    def test_v59_published_order_shows_two_distinct_links(self):
        state={"published":[{"title":"Соціальні послуги",
                             "channel_url":"https://t.me/ngo_grants/901",
                             "channel_urls":["https://t.me/ngo_grants/901",
                                             "https://t.me/ngo_grants/902"]}]}
        with patch.object(app,"message") as messenger:
            app.show_catalogs(123,state)
        text=messenger.call_args.args[1]
        self.assertIn("https://t.me/ngo_grants/901",text)
        self.assertIn("https://t.me/ngo_grants/902",text)
        self.assertIn("Підтверджені",text)
        self.assertIn("Умовні",text)

    def test_legacy_single_link_unaffected(self):
        state={"published":[{"title":"Звичайний каталог",
                             "channel_url":"https://t.me/ngo_grants/123"}]}
        with patch.object(app,"message") as messenger:
            app.show_catalogs(123,state)
        text=messenger.call_args.args[1]
        self.assertIn("https://t.me/ngo_grants/123",text)
        self.assertNotIn("Умовні",text)

if __name__=="__main__":
    unittest.main()
