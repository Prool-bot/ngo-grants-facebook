import importlib.util
from pathlib import Path
from types import SimpleNamespace as Obj
from unittest import TestCase,main

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location(
    "mini_app_pilot_poll_counts",ROOT/"scripts"/"mini_app_pilot_poll_counts.py")
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)

class PollCountsTests(TestCase):
 def test_aggregates_only_option_labels_votes_without_respondent_ids(self):
    answers=[Obj(text=Obj(text="Працює"),option=b"a"),
             Obj(text="Помилка",option=b"b")]
    votes=[Obj(option=b"a",voters=4),Obj(option=b"b",voters=2)]
    media=Obj(poll=Obj(public_voters=False,answers=answers),
              results=Obj(results=votes,total_voters=6))
    summary=mod.summarize(media)
    self.assertTrue(summary["anonymous"])
    self.assertEqual(summary["total_voters"],6)
    self.assertEqual([x["votes"] for x in summary["options"]],[4,2])
    self.assertNotIn("sender_id",repr(summary))
    self.assertNotIn("user_id",repr(summary))
 def test_if_telegram_hides_breakdown_do_not_claim_zero_votes(self):
    media=Obj(poll=Obj(public_voters=False,answers=[Obj(text="Працює",option=b"a")]),
              results=Obj(results=[],total_voters=9))
    result=mod.summarize(media)
    self.assertEqual(result["total_voters"],9)
    self.assertIsNone(result["options"])
    self.assertFalse(result["breakdown_available"])
 def test_reject_nonanonymous_poll_and_invalid_data(self):
    media=Obj(poll=Obj(public_voters=True,answers=[Obj(text="Працює",option=b"a")]),
              results=Obj(results=[],total_voters=0))
    with self.assertRaises(RuntimeError):mod.summarize(media)
    with self.assertRaises(RuntimeError):mod.summarize(None)
if __name__=="__main__":main()
