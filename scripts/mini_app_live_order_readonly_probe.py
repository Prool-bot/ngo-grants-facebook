"""Read-only, privacy-safe confirmation of genuine Mini App orders.

Reads ONLY existing authenticated /internal/pending and the committed public
catalog state. Never submits/retries orders, changes quotas, D1, Git state or
Telegram messages. Neither user IDs, order IDs, topics nor auth are printed.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import urllib.error
import urllib.parse
import urllib.request

BASE = 2**51
END = BASE + 2**48
STATE = Path("ai_catalogs/state.json")

def is_direct_id(value):
    return type(value) is int and BASE <= value < END

def audit(pending: dict, state: dict)->dict:
    items=pending.get("requests")
    if not isinstance(items,list):
        raise RuntimeError("Gateway pending requests are not a list")
    if not isinstance(state,dict):
        raise RuntimeError("Catalog Git state malformed")
    pub=state.get("published") or []
    empty=state.get("no_results") or []
    queue=state.get("queue") or []
    for collection in (pub,empty,queue):
        if not isinstance(collection,list):
            raise RuntimeError("Catalog state collection is not a list")
    def count(rows,key="id"):
        return sum(isinstance(x,dict) and is_direct_id(x.get(key)) for x in rows)
    # print *counts only*, never any identifying request metadata
    return {
        "gateway_pending_total":len(items),
        "gateway_pending_direct":count(items),
        "github_direct_queued":count(queue),
        "github_direct_published":count(pub),
        "github_direct_no_results":count(empty),
        "gateway_pending_limit_may_truncate":len(items)>=100,
        "direct_order_seen":any((count(items),count(queue),count(pub),count(empty))),
    }

def read_gateway()->dict:
    base=(os.getenv("NGO_BOT_GATEWAY_URL") or "").rstrip("/")
    secret=(os.getenv("NGO_BOT_SYNC_SECRET") or "").strip()
    parts=urllib.parse.urlparse(base)
    if not (parts.scheme=="https" and parts.hostname and
            parts.hostname.endswith(".workers.dev") and
            not parts.username and not parts.password and secret):
        raise RuntimeError("Approved protected gateway missing")
    request=urllib.request.Request(base+"/internal/pending",method="GET",
        headers={
          "Authorization":"Bearer "+secret,
          "Accept":"application/json",
          "User-Agent":"NGO-Grants-Healthcheck/1.0",
          "Cache-Control":"no-store"
        })
    try:
        with urllib.request.urlopen(request,timeout=25) as response:
            if response.status!=200:
                raise RuntimeError("Protected pending endpoint did not succeed")
            raw=response.read(2_000_000)
    except urllib.error.HTTPError as e:
        raise RuntimeError("Protected pending GET failed HTTP "+str(e.code)) from None
    except (OSError,urllib.error.URLError,TimeoutError) as e:
        raise RuntimeError("Protected pending GET failed: "+type(e).__name__) from None
    try:
        return json.loads(raw)
    except ValueError:
        raise RuntimeError("Protected pending GET returned invalid JSON") from None

def main():
    if (os.getenv("GITHUB_ACTIONS")!="true" or
        os.getenv("GITHUB_REF")!="refs/heads/main" or
        os.getenv("GITHUB_REPOSITORY")!="Prool-bot/ngo-grants-facebook"):
        raise RuntimeError("Only approved GitHub main read-only audit")
    state=json.loads(STATE.read_text(encoding="utf-8"))
    results=audit(read_gateway(),state)
    print("NGO_GRANTS_V053_FIRST_REAL_ORDER_PRIVATE_SAFE_AUDIT")
    for key,value in results.items():
        print(key.upper()+"="+str(value))
    print("READ_ONLY_NO_USER_IDENTIFIERS_AND_NO_DB_WRITES=True")
if __name__=="__main__":
    try:main()
    except RuntimeError as e:raise SystemExit(str(e)) from None
