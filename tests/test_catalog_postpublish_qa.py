"""Acceptance-monitor regression; public PDFs only, no Telegram or network."""
import json
from pathlib import Path
import unittest

from scripts.check_new_catalog_quality import (
    BASELINE_LAST_POST, ROOT, check_catalog, public_message_ids
)
from ngo_grants_ai import read_archive


class PostPublishAcceptanceTests(unittest.TestCase):
    def test_baseline_message_number_and_url_scope(self):
        self.assertEqual(3935, BASELINE_LAST_POST)
        self.assertEqual([3934, 3935], public_message_ids({
            "channel_urls": [
                "https://t.me/ngo_grants/3934",
                "https://t.me/ngo_grants/3935",
                "https://t.me/not_ngo_grants/3936"
            ]
        }))

    def test_auditor_finds_known_historical_issues_without_mutations(self):
        state = json.loads((ROOT / "ai_catalogs/state.json").read_text("utf-8"))
        item = next(
            x for x in state["published"]
            if 3934 in public_message_ids(x) and 3935 in public_message_ids(x)
        )
        public_archive = {int(p["id"]): str(p.get("text") or "")
                          for p in read_archive()}
        failures = check_catalog(item, public_archive)
        self.assertTrue(any(e.startswith("expired_mandatory_entry:2561")
                            for e in failures), failures)
        self.assertTrue(any(e.startswith("expired_mandatory_entry:2678")
                            for e in failures), failures)
        self.assertTrue(any(e.startswith("duplicate_grant_programme:")
                            and "3590" in e and "3623" in e
                            for e in failures), failures)
        self.assertFalse(any(e.startswith("missing_or_unsafe_pdf")
                             for e in failures), failures)


if __name__ == "__main__":
    unittest.main()
