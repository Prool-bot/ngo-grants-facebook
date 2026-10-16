from datetime import datetime, timezone
from pathlib import Path
import json
import tempfile
from types import SimpleNamespace
import unittest

from telegram_comments import (comment_record, load_comments, reconcile,
                               redact, search_comments, write_comments)


def fake(mid=100, content="Цікавий грант", date=None):
    return SimpleNamespace(id=mid, raw_text=content, date=date or datetime(2026, 10, 10, tzinfo=timezone.utc),
                           edit_date=None, reply_to=SimpleNamespace(reply_to_msg_id=42), action=None)


class CommentTests(unittest.TestCase):
    def test_redacts_handles_email_phone_and_invites(self):
        content = "Напишіть @example_user на me@example.org, +380 67 123 45 67, https://t.me/+secret"
        row = comment_record(fake(content=content), 123)
        self.assertNotIn("@example_user", row["text"])
        self.assertNotIn("me@example.org", row["text"])
        self.assertNotIn("+380 67 123 45 67", row["text"])
        self.assertNotIn("t.me/+secret", row["text"])
        self.assertIn("https://t.me/ngo_grants/123?comment=100", row["comment_url"])
        self.assertNotIn("sender_id", row)
        self.assertNotIn("username", row)

    def test_edited_comments_and_deleted_threads(self):
        old = {11: [comment_record(fake(100), 11)], 22: [comment_record(fake(200), 22)]}
        new = {11: [comment_record(fake(100, "Новий дедлайн"), 11)]}
        merged = reconcile(old, new, {11, 22}, full=False)
        self.assertEqual(set(merged), {11})
        self.assertEqual(merged[11][0]["text"], "Новий дедлайн")
        self.assertEqual(reconcile(old, new, {11}, full=False)[22], old[22])

    def test_roundtrip_search_corruption_guard(self):
        first = comment_record(fake(100, "Перевірити умови", datetime(2026, 9, 30, 22, tzinfo=timezone.utc)), 123)
        second = comment_record(fake(101, "Підтримка освіти", datetime(2026, 10, 1, tzinfo=timezone.utc)), 123)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            meta = write_comments({123: [first, second]}, "public_group", root=root, full=True)
            self.assertEqual(meta["comment_count"], 2)
            loaded, _ = load_comments(root)
            self.assertEqual(loaded[123], [first, second])
            self.assertEqual(len(search_comments(loaded, "УМОВИ", post_id=123, since="2026-10-01")), 1)
            self.assertEqual(len(search_comments(loaded, post_id=999)), 0)
            write_comments({}, "public_group", root=root)
            self.assertEqual(load_comments(root)[0], {})
            self.assertFalse((root / "posts/123.json").exists())
            index_path = root / "index.json"
            bad = json.loads(index_path.read_text(encoding="utf-8"))
            bad["comment_count"] = 999
            index_path.write_text(json.dumps(bad), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_comments(root)


if __name__ == '__main__':
    unittest.main()
