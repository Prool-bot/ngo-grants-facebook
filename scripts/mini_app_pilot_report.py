"""Anonymized NGO Grants AI public pilot quality snapshot.

Reads committed state.json and public comments archive (if available).
Never prints Telegram IDs, raw search topics, private user or update data.
No writes and no user-facing catalog publications.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime,timezone,timedelta
from pathlib import Path
import json

STATE=Path("ai_catalogs/state.json")
COMMENTS=Path("archive/telegram/comments/index.json")
PILOT_POST=3813

def parse_state(data:dict, since="2026-11-07")->dict:
    if not isinstance(data,dict):raise ValueError("Invalid catalog state")
    published=data.get("published") or []
    no_results=data.get("no_results") or []
    queue=data.get("queue") or []
    if not all(isinstance(v,list) for v in (published,no_results,queue)):
        raise ValueError("Unexpected state schema")
    new_published=[x for x in published
        if isinstance(x,dict) and str(x.get("published_on") or "")>=since]
    new_empty=[x for x in no_results
        if isinstance(x,dict) and str(x.get("checked_on") or "")>=since]
    count_facet=lambda rows,key:dict(sorted(Counter(
       (x.get("facets") or {}).get(key,"unspecified") for x in rows
    ).items()))
    business_individual_empty=sum(
        (x.get("facets") or {}).get("audience")=="individual" and
        "business" in ((x.get("facets") or {}).get("sectors") or [])
        for x in new_empty
    )
    multi_tier=sum(
        (x.get("v59_document_count") or 0)>=2 for x in new_published
    )
    return {
      "published_total":len(published),
      "no_results_total":len(no_results),
      "pending_git_queue":len(queue),
      "new_published_since_cutoff":len(new_published),
      "new_no_results_since_cutoff":len(new_empty),
      "new_v59_two_tier_catalogs":multi_tier,
      "new_published_by_audience":count_facet(new_published,"audience"),
      "new_no_results_by_audience":count_facet(new_empty,"audience"),
      "new_no_results_individual_business":business_individual_empty,
      "attribution_to_mini_app":"unknown"
    }

def comment_summary(meta:dict|None)->dict:
    if meta is None:return {"status":"archive_not_yet_synced"}
    if meta.get("channel")!="ngo_grants":raise ValueError("Wrong comment archive")
    matches=[x for x in meta.get("posts",[]) if x.get("post_id")==PILOT_POST]
    if len(matches)>1:raise ValueError("Duplicate pilot thread")
    return {"status":"indexed",
            "pilot_post_comment_count":matches[0]["count"] if matches else 0,
            "all_archived_comments":meta.get("comment_count",0),
            "archive_updated_at":meta.get("updated_at")}

def main():
    state=json.loads(STATE.read_text("utf-8"))
    comments=json.loads(COMMENTS.read_text("utf-8")) if COMMENTS.exists() else None
    summary={"pilot_post":"https://t.me/ngo_grants/3813",
             "catalog":parse_state(state),
             "comments":comment_summary(comments)}
    print("NGO_GRANTS_PILOT_PUBLIC_AGGREGATES")
    print(json.dumps(summary,ensure_ascii=False,indent=2,sort_keys=True))
    if summary["catalog"]["new_no_results_individual_business"]>0:
        print("QA_WARNING=Individual applicant selected a business area; "
              "check whether applicant is an FOP before rerunning the search.")
    return summary

if __name__=="__main__":main()
