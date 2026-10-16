"""Regression tests for the Telegram-native UI (no real Telegram calls)."""
from copy import deepcopy
import unittest
from unittest.mock import patch

import ngo_grants_ai as app


def update(text, update_id=100, user_id=44):
    return {"update_id": update_id, "message": {
        "chat": {"id": user_id, "type": "private"},
        "from": {"id": user_id}, "text": text}}


class BotUITests(unittest.TestCase):
    def setUp(self):
        self.state = app.default_state()
        self.sent = []
        self.patcher = patch.object(app, "tg", side_effect=self.fake_tg)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def fake_tg(self, method, params):
        self.sent.append((method, deepcopy(params)))
        if method == "getChatMember":
            return {"ok": True, "result": {"status": "member"}}
        return {"ok": True, "result": {"message_id": 111}}

    def test_start_renders_native_keyboard_and_limits(self):
        app.handle_update(update('/start'), self.state, 'test-token')
        method, params = self.sent[-1]
        self.assertEqual(method, 'sendMessage')
        self.assertEqual(params['parse_mode'], 'HTML')
        markup = params['reply_markup']
        labels = [button['text'] for row in markup['keyboard'] for button in row]
        self.assertIn(app.UI_ORDER, labels)
        self.assertIn(app.UI_CATALOGS, labels)
        self.assertIn(app.UI_HELP, labels)
        self.assertIn(app.UI_EXAMPLES, labels)
        self.assertIn(app.UI_STATUS, labels)
        self.assertEqual(self.state['users_days'], {})
        self.assertEqual(self.state['queue'], [])

    def test_request_button_displays_native_input_hint_without_spending_quota(self):
        app.handle_update(update(app.UI_ORDER), self.state, 'test-token')
        data = self.sent[-1][1]
        self.assertTrue(data['reply_markup']['force_reply'])
        self.assertIn('input_field_placeholder', data['reply_markup'])
        self.assertEqual(self.state['queue'], [])
        self.assertEqual(self.state['users_days'], {})

    def test_navigation_is_not_mistaken_for_new_query(self):
        for cmd in ('/help', '/examples', '/catalogs', '/status', '/request',
                    app.UI_HELP, app.UI_CATALOGS, app.UI_EXAMPLES, app.UI_STATUS):
            app.handle_update(update(cmd), self.state, 'test-token')
        self.assertEqual(self.state['queue'], [])
        self.assertEqual(self.state['users_days'], {})

    def test_topic_is_queued_once_and_limit_retained(self):
        app.handle_update(update('Гранти на охорону довкілля для громад', 100), self.state, 'test-token')
        self.assertEqual(len(self.state['queue']), 1)
        self.assertEqual(len(self.state['users_days']), 1)
        app.handle_update(update('Стипендії для українських дослідників', 101), self.state, 'test-token')
        self.assertEqual(len(self.state['queue']), 1)
        self.assertIn('використали запит', self.sent[-1][1]['text'])

    def test_personal_data_rejected(self):
        app.handle_update(update('Мій проєкт звертатись до me@example.com'), self.state, 'test-token')
        self.assertEqual(self.state['queue'], [])
        self.assertEqual(self.state['users_days'], {})

    def test_catalogs_include_only_telegram_urls_and_html_escaped_title(self):
        self.state['published'] = [
            {'title': '<Мистецтво> & кіно', 'channel_url': 'https://t.me/ngo_grants/3255'},
            {'title': 'Bad link', 'channel_url': 'https://bad.site/abc'}]
        app.handle_update(update('/catalogs'), self.state, 'test-token')
        t = self.sent[-1][1]['text']
        self.assertIn('&lt;Мистецтво&gt; &amp; кіно', t)
        self.assertIn('https://t.me/ngo_grants/3255', t)
        self.assertNotIn('bad.site', t)

    def test_profile_configured_once_without_ai(self):
        app.configure_bot_profile(self.state)
        self.assertEqual([x[0] for x in self.sent],
                         ['setMyCommands', 'setMyDescription', 'setMyShortDescription'])
        self.assertEqual(self.state['bot_profile_version'], app.BOT_PROFILE_VERSION)
        self.sent.clear()
        app.configure_bot_profile(self.state)
        self.assertEqual(self.sent, [])

    def test_profile_failure_does_not_stop_bot(self):
        with patch.object(app, 'tg', side_effect=RuntimeError('simulated')):
            app.configure_bot_profile(self.state)
        self.assertNotIn('bot_profile_version', self.state)


if __name__ == '__main__':
    unittest.main()
