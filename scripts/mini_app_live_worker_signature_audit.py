"""Read-only function signature metadata, never Worker source/code/logs.

Reports only parameter IDENTIFIER names, call-site counts and known operation flags.
Cloudflare production code exists only in memory of the GitHub Actions runner.
"""
from __future__ import annotations
import os
import re
import urllib.request
import urllib.error

SCRIPT="ngo-grants-instant-bot"
FUNCTIONS=("createRequest","previouslyRequested","hashUser","beginOrder",
           "handleTelegram","validatedDraft","textForQueue","saveDraft")
IDENT=re.compile(r"^[A-Za-z_$][A-Za-z_$0-9]*$")

def shape(raw: bytes) -> dict:
    if not raw or len(raw)>8_000_000:raise ValueError("source size")
    s=raw.decode("utf-8","replace")
    result={}
    for name in FUNCTIONS:
        pattern=r"\b(?:async\s+)?function\s+"+re.escape(name)+r"\s*\(([^)]{0,400})\)"
        match=re.search(pattern,s)
        if match:
            args=[v.strip() for v in match.group(1).split(",")]
            args=[arg if IDENT.fullmatch(arg) else "<complex>" for arg in args]
        else:
            args=[]
        calls=re.findall(r"\b"+re.escape(name)+r"\s*\(",s)
        result[name]={"exists":bool(match),"args":args,"calls":len(calls)-int(bool(match))}
    result["ops"]={
        "telegram_get_chat_member":"getChatMember" in s,
        "telegram_chat_id":"chat_id" in s,
        "sqlite_unique":"UNIQUE" in s.upper(),
        "sqlite_insert_ignore":"INSERT OR IGNORE" in s.upper(),
        "sqlite_batch":".batch(" in s,
        "sqlite_first":".first(" in s,
        "sqlite_run":".run(" in s,
        "kyiv_timezone":"Europe/Kyiv" in s,
        "secret_header":"x-telegram-bot-api-secret-token" in s.casefold(),
    }
    tables=sorted(set(re.findall(
        r"\bINSERT\s+(?:OR\s+\w+\s+)?INTO\s+([A-Za-z_][A-Za-z_0-9]{0,50})",
        s,re.I
    )))
    # Table names are schema metadata, not D1 rows or SQL bodies.
    result["tables"]=tables[:20]
    return result


def main():
    account=(os.getenv("CF_WORKER_ACCOUNT_ID") or os.getenv("CF_ACCOUNT_ID") or "").strip()
    token=(os.getenv("CF_WORKER_API_TOKEN") or "").strip()
    if not account or not token:
        print("WORKER_SIGNATURE_AUDIT=NO_CREDENTIALS")
        return 2
    req=urllib.request.Request(
        f"https://api.cloudflare.com/client/v4/accounts/{account}/workers/scripts/{SCRIPT}",
        method="GET",headers={"Authorization":"Bearer "+token,"Accept":"*/*"})
    try:
        with urllib.request.urlopen(req,timeout=30) as r:
            data=r.read(8_000_001)
    except urllib.error.HTTPError as exc:
        print("WORKER_SIGNATURE_AUDIT=HTTP_"+str(exc.code));return 2
    except (urllib.error.URLError,OSError,TimeoutError) as exc:
        print("WORKER_SIGNATURE_AUDIT=NETWORK_"+type(exc).__name__);return 2
    try:info=shape(data)
    except ValueError:
        print("WORKER_SIGNATURE_AUDIT=INVALID_SIZE");return 2
    for name,entry in info.items():
        if name in ("ops","tables"):continue
        print("SIGNATURE_"+name.upper()+"="+
              (",".join(entry["args"]) if entry["exists"] else "NOT_FOUND")+
              ";CALLS="+str(entry["calls"]))
    for op,value in info["ops"].items():
        print("OP_"+op.upper()+"="+str(value))
    print("D1_INSERT_TABLES="+",".join(info["tables"]))
    print("WORKER_SIGNATURE_AUDIT=COMPLETE_READ_ONLY")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
