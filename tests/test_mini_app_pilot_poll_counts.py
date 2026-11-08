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
 def test_explicit_aggregate_poll_results_refreshes_partial_message(self):
    poll=Obj(id=778899,public_voters=False,
      answers=[Obj(text="Все працює",option=b"a"),
               Obj(text="Не працює",option=b"b")])
    old=Obj(poll=poll,results=Obj(results=[],total_voters=2))
    fresh=Obj(updates=[Obj(poll_id=778899,
       results=Obj(results=[Obj(option=b"a",voters=1),
                            Obj(option=b"b",voters=1)],
                   total_voters=2))])
    combined=mod.refreshed_poll_media(old,fresh)
    summary=mod.summarize(combined)
    self.assertTrue(summary["breakdown_available"])
    self.assertEqual([x["votes"] for x in summary["options"]],[1,1])
 def test_unrelated_update_cannot_override_poll_counters(self):
    original=Obj(poll=Obj(id=99),results=Obj(results=[],total_voters=2))
    unrelated=Obj(updates=[Obj(poll_id=100,
      results=Obj(results=[Obj(option=b"a",voters=999)],total_voters=999))])
    self.assertIs(mod.refreshed_poll_media(original,unrelated),original)
 def test_reject_nonanonymous_poll_and_invalid_data(self):
    media=Obj(poll=Obj(public_voters=True,answers=[Obj(text="Працює",option=b"a")]),
              results=Obj(results=[],total_voters=0))
    with self.assertRaises(RuntimeError):mod.summarize(media)
    with self.assertRaises(RuntimeError):mod.summarize(None)
if __name__=="__main__":main()
