"""Read-only Cloudflare Worker shape report for Mini App integration.

Never saves or logs source, request details, or secrets.
Output is deliberately limited to pre-approved structural booleans and names.
"""
from __future__ import annotations

import os
import re
import urllib.request
import urllib.error

SCRIPT="ngo-grants-instant-bot"
KNOWN_ROUTES=(
    "/health","/internal/sync","/internal/pending","/internal/activate",
    "/internal/deactivate","/api/mini-app/order",
)
FUNCTION_HINTS=("queue","order","member","draft","submit","save",
                "fetch","message","handle","request","verify","check",
                "topic","user","limit","record","process")
MAX_SOURCE=8_000_000


def inspect(raw: bytes) -> dict:
    if not raw or len(raw)>MAX_SOURCE:
        raise ValueError("Unexpected Worker source size")
    # Cloudflare may return JavaScript or multipart source, both kept in RAM.
    content=raw.decode("utf-8","replace")
    names=re.findall(r"\b(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(",
                     content)
    candidate=sorted(set(
        name for name in names
        if len(name)<=70 and any(w in name.lower() for w in FUNCTION_HINTS)
    ))
    # Function names, not function bodies or snippets.
    candidate=candidate[:70]
    return {
        "worker_export_default":bool(re.search(r"\bexport\s+default\b",content)),
        "fetch_handler":bool(re.search(r"\basync\s+fetch\s*\(",content)),
        "webhook_handler":("/webhook" in content or "X-Telegram-Bot-Api-Secret-Token" in content),
        "membership_check":("getChatMember" in content),
        "d1_prepared_statement":(".prepare(" in content),
        "d1_insert":bool(re.search(r"\bINSERT\s+(?:OR\s+\w+\s+)?INTO\s+",content,re.I)),
        "queue_mention":("queue" in content),
        "known_routes":{route:route in content for route in KNOWN_ROUTES},
        "function_name_hints":candidate,
    }


def main() -> int:
    aid=(os.getenv("CF_WORKER_ACCOUNT_ID") or os.getenv("CF_ACCOUNT_ID") or "").strip()
    token=(os.getenv("CF_WORKER_API_TOKEN") or "").strip()
    if not aid or not token:
        print("MINI_APP_WORKER_SHAPE=NOT_CONFIGURED")
        return 2
    req=urllib.request.Request(
        f"https://api.cloudflare.com/client/v4/accounts/{aid}/workers/scripts/{SCRIPT}",
        headers={"Authorization":"Bearer "+token,"Accept":"*/*"},
        method="GET"
    )
    try:
        with urllib.request.urlopen(req,timeout=30) as response:
            raw=response.read(MAX_SOURCE+1)
    except urllib.error.HTTPError as error:
        print(f"MINI_APP_WORKER_SHAPE=HTTP_{error.code}")
        return 2
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        print(f"MINI_APP_WORKER_SHAPE=NETWORK_{type(error).__name__}")
        return 2
    try:
        report=inspect(raw)
    except ValueError:
        print("MINI_APP_WORKER_SHAPE=UNEXPECTED_SOURCE_SIZE")
        return 2
    for field in ("worker_export_default","fetch_handler","webhook_handler",
                  "membership_check","d1_prepared_statement","d1_insert","queue_mention"):
        print("STRUCTURE_"+field.upper()+"="+str(report[field]))
    for route,present in report["known_routes"].items():
        print("ROUTE_"+route.replace("/","_").upper()+"="+str(present))
    print("FUNCTION_NAMES="+",".join(report["function_name_hints"]))
    print("MINI_APP_WORKER_SHAPE=READ_ONLY_COMPLETE")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
