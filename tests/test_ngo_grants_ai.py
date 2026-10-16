import os
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path
import unittest

from ngo_grants_ai import (deadline_from_post, sanitize_user_text, similarity,
                           same_in_queue, rank_posts, user_hash, pdf_catalog,
                           load_state, save_state, can_publish)


class CatalogTests(unittest.TestCase):
    def test_deadline_ukrainian_date(self):
        self.assertEqual(deadline_from_post('📅 Дедлайн: 31 жовтня 2026 року'), date(2026, 10, 31))
        self.assertEqual(deadline_from_post('Deadline: 25.12.2026'), date(2026, 12, 25))
        self.assertIsNone(deadline_from_post('Період реалізації: 12.12.2027'))

    def test_selections_only_active_and_topic(self):
        posts = [
            {'id': 11, 'text': 'Грант для документального кіно\nДедлайн: 30.11.2026', 'urls': []},
            {'id': 12, 'text': 'Грант для кіно\nДедлайн: 01.01.2025', 'urls': []},
            {'id': 13, 'text': 'Грант для аграріїв\nДедлайн: 31.12.2026', 'urls': []},
        ]
        selected = rank_posts(posts, 'гранти для кіноіндустрії', ['документальне кіно'], now=date(2026, 10, 16))
        self.assertEqual([r['id'] for r in selected], [11])

    def test_duplicate_and_private_data(self):
        self.assertGreater(similarity('гранти для документального кіно', 'документальні фільми та режисери'), 0.75)
        self.assertTrue(same_in_queue('каталог грантів для кіно', {'queue': [{'topic': 'гранти для кінематографа'}]}))
        self.assertNotIn('test@example.org', sanitize_user_text('надішліть test@example.org'))
        self.assertNotEqual(user_hash(123, 'x'), user_hash(123, 'y'))

    def test_pdf_links_and_state(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            src = [{'id': 3219, 'text': '🎬 Конкурс для кіно\n💰 Фінансування: 1000 EUR\nДедлайн: 31.12.2026',
                    '_title': 'Гранти для кіно', '_deadline': '2026-12-31'}]
            try:
                pdf_catalog(root / 'test.pdf', 'Гранти для кінопроєктів', 'кіно', src, date(2026, 10, 16))
            except RuntimeError as exc:
                if 'шрифт' in str(exc):
                    self.skipTest('Cyrillic font missing on test machine')
                raise
            import pypdf
            pdf = pypdf.PdfReader(str(root / 'test.pdf'))
            links = [a.get_object().get('/A', {}).get('/URI', '') for page in pdf.pages
                     for a in page.get('/Annots', [])]
            self.assertTrue(any('https://t.me/ngo_grants/3219' in str(link) for link in links))
            self.assertFalse(any('example.org' in str(link) for link in links))
            state = load_state(root / 'state.json')
            state['last_update_id'] = 22
            save_state(state, root / 'state.json')
            self.assertEqual(load_state(root / 'state.json')['last_update_id'], 22)

    def test_publish_limits(self):
        now = datetime(2026, 10, 16, 10, tzinfo=timezone.utc)
        state = {'published': [], 'last_post_at': None}
        self.assertTrue(can_publish(state, now))
        state['last_post_at'] = now.isoformat()
        self.assertFalse(can_publish(state, now))
        state['last_post_at'] = None
        state['published'] = [{'published_on': '2026-10-16'}] * 3
        self.assertFalse(can_publish(state, now))


if __name__ == '__main__':
    unittest.main()
