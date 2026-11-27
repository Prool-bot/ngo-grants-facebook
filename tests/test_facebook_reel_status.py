"""Offline regression tests: no tokens, network requests, or Facebook writes."""
import ast
import asyncio
import json
import re
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

SOURCE = Path(__file__).resolve().parents[1] / "facebook_full_test.py"
NAMES = {"MetaAPIError", "verify_reel_publication", "has_source_url", "main"}
TREE = ast.parse(SOURCE.read_text(encoding="utf-8"), filename=str(SOURCE))
SELECTED = ast.Module(
    body=[node for node in TREE.body if getattr(node, "name", None) in NAMES],
    type_ignores=[],
)
assert {node.name for node in SELECTED.body} == NAMES


class NetworkError(Exception):
    pass


class ReelStatusTests(unittest.TestCase):
    def setUp(self):
        self.report = {"posts": [], "reel": {"stage": "publication_requested"}}
        self.sleep = Mock()
        self.graph = Mock()
        self.ns = {
            "REPORT": self.report,
            "time": SimpleNamespace(sleep=self.sleep),
            "requests": SimpleNamespace(RequestException=NetworkError),
            "graph": self.graph,
            "checkpoint": Mock(),
            "json": json,
            "re": re,
            "print": Mock(),
            "asyncio": asyncio,
            "os": SimpleNamespace(environ={"PUBLISH_TO_FACEBOOK": "true"}),
            "PAGE": "page",
        }
        exec(compile(SELECTED, str(SOURCE), "exec"), self.ns)

    def error(self, code, subcode=None, http=400):
        return self.ns["MetaAPIError"]("mock error", http, code, subcode)

    def poll(self):
        self.ns["verify_reel_publication"]("video")
        self.assertTrue(all(call.args[0] == "GET" for call in self.graph.call_args_list))

    def test_original_error_then_published(self):
        self.graph.side_effect = [
            self.error(100, 33),
            {"status": {"publishing_phase": {"status": "in_progress"}}},
            {"status": {"publishing_phase": {"status": "complete"}}},
        ]
        self.poll()
        self.assertEqual(self.report["reel"]["stage"], "published")
        self.assertEqual([call.args[0] for call in self.sleep.call_args_list], [10, 15, 25])
        self.assertNotIn("last_verification_error", self.report["reel"])

    def test_original_error_persists(self):
        self.graph.side_effect = self.error(100, 33)
        self.poll()
        self.assertEqual(self.report["reel"]["stage"], "publication_unconfirmed")
        self.assertEqual(self.graph.call_count, 6)

    def test_processing_never_finishes(self):
        self.graph.return_value = {"status": {"publishing_phase": {"status": "in_progress"}}}
        self.poll()
        self.assertEqual(self.report["reel"]["stage"], "publication_unconfirmed")

    def test_network_error_then_success(self):
        self.graph.side_effect = [
            NetworkError(),
            {"status": {"publishing_phase": {"status": "complete"}}},
        ]
        self.poll()
        self.assertEqual(self.report["reel"]["stage"], "published")

    def test_permission_error_is_not_publication_failure(self):
        self.graph.side_effect = self.error(200)
        self.poll()
        self.assertEqual(self.report["reel"]["stage"], "verification_unavailable")
        self.assertEqual(self.graph.call_count, 1)

    def test_meta_explicit_failure_is_fatal(self):
        self.graph.return_value = {"status": {"video_status": "error"}}
        with self.assertRaises(RuntimeError):
            self.poll()
        self.assertEqual(self.report["reel"]["stage"], "failed")

    def test_exact_source_url(self):
        match = self.ns["has_source_url"]
        url = "https://t.me/ngo_grants/123"
        self.assertTrue(match({"message": url + "\n"}, "message", url))
        self.assertFalse(match({"message": url + "4"}, "message", url))
        self.assertFalse(match({}, "message", url))

    def test_all_posts_exist_but_reel_missing_no_writes(self):
        urls = ["https://t.me/ngo_grants/" + str(i) for i in (123, 124, 125)]

        async def select():
            return "2026-11-26", 3, [
                {"rank": i, "telegram_url": url} for i, url in enumerate(urls, 1)
            ]

        self.graph.return_value = {"id": "page", "name": "Test"}
        self.ns["select_posts"] = select
        self.ns["recent_items"] = Mock(side_effect=[
            [{"id": str(i), "message": url} for i, url in enumerate(urls, 1)],
            [],
        ])
        self.ns["publish_reel"] = Mock()
        self.ns["main"]()
        self.ns["publish_reel"].assert_not_called()
        self.assertEqual(self.graph.call_count, 1)
        self.assertEqual(self.report["stage"], "manual_verification_required")
        self.assertEqual(len(self.report["posts"]), 3)


if __name__ == "__main__":
    unittest.main()
