from datetime import datetime, timezone
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from telegram_archive import canonical_url, load_archive, message_record, reconcile, refresh_floor, search_rows, write_archive


def message(mid=1, text='📰 Цифрова безпека медіа', date=None):
    return SimpleNamespace(id=mid, raw_text=text, date=date or datetime(2026, 10, 1, tzinfo=timezone.utc),
                           edit_date=None, entities=[], views=42, grouped_id=None, reply_markup=None)


class ArchiveTests(unittest.TestCase):
    def test_hidden_links_with_emoji_and_buttons(self):
        msg = message(text='📰 Посилання https://example.org/a).')
        msg.entities = [SimpleNamespace(url='https://donor.org/call?utm_source=tg')]
        msg.reply_markup = SimpleNamespace(rows=[SimpleNamespace(buttons=[SimpleNamespace(url='https://donor.org/apply')])])
        row = message_record(msg)
        self.assertIn('https://donor.org/call', row['canonical_urls'])
        self.assertIn('https://donor.org/apply', row['urls'])
        self.assertIn('https://example.org/a', row['urls'])

    def test_url_duplicate_ignores_tracking_but_keeps_call_id(self):
        self.assertEqual(canonical_url('http://Donor.org/call/?id=1&utm_source=tg#x'), 'https://donor.org/call?id=1')
        self.assertNotEqual(canonical_url('https://donor.org/call?id=1'), canonical_url('https://donor.org/call?id=2'))

    def test_search_ukrainian_phrases_dates_and_url(self):
        rows = {1: message_record(message())}
        rows[1]['urls'] = ['https://donor.org/call?utm_source=tg']
        rows[1]['canonical_urls'] = ['https://donor.org/call']
        self.assertEqual(len(search_rows(rows, 'ЦИФРОВА "безпека медіа"')), 1)
        self.assertEqual(len(search_rows(rows, 'безпека освіта', 'any')), 1)
        self.assertEqual(len(search_rows(rows, 'безпека освіта', 'all')), 0)
        self.assertEqual(len(search_rows(rows, since='2026-10-02')), 0)
        self.assertEqual(len(search_rows(rows, url='http://donor.org/call/?utm_source=fb')), 1)

    def test_kyiv_month_boundary_roundtrip_and_corruption_guard(self):
        row = message_record(message(date=datetime(2026, 9, 30, 22, tzinfo=timezone.utc)))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            meta = write_archive({1: row}, full=True, root=root)
            self.assertEqual(meta['months'][0]['month'], '2026-10')
            self.assertEqual(load_archive(root), {1: row})
            (root / 'months/2026-10.json').write_text('[]')
            with self.assertRaises(ValueError):
                load_archive(root)

    def test_refresh_preserves_old_removes_deleted_and_updates_edited(self):
        old = message_record(message(1, date=datetime(2026, 8, 1, tzinfo=timezone.utc)))
        current = message_record(message(2))
        deleted = message_record(message(3))
        edited = message_record(message(2, text='Виправлений дедлайн'))
        added = message_record(message(4))
        rows = {1: old, 2: current, 3: deleted}
        floor = refresh_floor(rows, datetime(2026, 10, 9, tzinfo=timezone.utc))
        self.assertEqual(floor, 1)
        merged = reconcile(rows, {2: edited, 4: added}, floor)
        self.assertEqual(set(merged), {1, 2, 4})
        self.assertEqual(merged[2]['text'], 'Виправлений дедлайн')
        self.assertEqual(set(reconcile(rows, {2: edited}, 0)), {2})


if __name__ == '__main__':
    unittest.main()
