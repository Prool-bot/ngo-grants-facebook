"""Read-only semantic audit of deployed queue code. Never logs Worker source."""
from __future__ import annotations
import os,re,urllib.request,urllib.error

TARGETS=("createRequest","beginOrder","previouslyRequested","validatedDraft","textForQueue")
TOKENS={
    "uses_get_chat_member":r"getChatMember",
    "uses_hash_user":r"hashUser\s*\(",
    "uses_previous_request":r"previouslyRequested\s*\(",
    "uses_legacy_limit":r"legacy_limits",
    "uses_user_days":r"user_days",
    "uses_insert_request":r"INSERT\s+(?:OR\s+\w+\s+)?INTO\s+requests",
    "uses_insert_ignore":r"INSERT\s+OR\s+IGNORE",
    "uses_db_batch":r"\.batch\s*\(",
    "uses_db_first":r"\.first\s*\(",
    "uses_db_run":r"\.run\s*\(",
    "uses_telegram_message":r"sendMessage|sendTelegram|telegramApi",
    "uses_chat":r"\bchat\b",
    "uses_user_id":r"\buserId\b",
    "uses_update_id":r"\bupdateId\b",
    "uses_tg_keyboard":r"reply_markup",
    "uses_date":r"kyiv|Kyiv|today",
    "calls_save_draft":r"saveDraft\s*\(",
    "returns_value":r"\breturn\s+[^;}\s]",
}
def inspect(raw:bytes)->dict:
    if not raw or len(raw)>8_000_000:raise ValueError("size")
    text=raw.decode("utf-8","replace")
    out={}
    for name in TARGETS:
        m=re.search(r"\b(?:async\s+)?function\s+"+re.escape(name)+r"\s*\(",text)
        if not m:
            out[name]=None;continue
        # All bounded slices below are processed only in memory; no source output.
        after=text[m.end():]
        end=re.search(r"\n(?:async\s+)?function\s+[\w$]+\s*\(",after)
        body=after[:min(end.start() if end else len(after),12000)]
        out[name]={k:bool(re.search(v,body,re.I)) for k,v in TOKENS.items()}
    fetch=re.search(r"\basync\s+fetch\s*\(([^)]{0,200})\)",text)
    out["fetch_params"]=(["<complex>" if not re.fullmatch(r"[A-Za-z_$][\w$]*",x.strip()) else x.strip()
                           for x in fetch.group(1).split(",")] if fetch else [])
    return out

def main():
    account=(os.getenv("CF_WORKER_ACCOUNT_ID") or os.getenv("CF_ACCOUNT_ID") or "").strip()
    token=os.getenv("CF_WORKER_API_TOKEN","").strip()
    if not account or not token:
        print("MINI_APP_QUEUE_AUDIT=NO_CREDENTIALS");return 2
    url=f"https://api.cloudflare.com/client/v4/accounts/{account}/workers/scripts/ngo-grants-instant-bot"
    req=urllib.request.Request(url,method="GET",headers={"Authorization":"Bearer "+token,"Accept":"*/*"})
    try:
        with urllib.request.urlopen(req,timeout=30) as response:raw=response.read(8_000_001)
    except urllib.error.HTTPError as exc:
        print("MINI_APP_QUEUE_AUDIT=HTTP_"+str(exc.code));return 2
    except (OSError,TimeoutError,urllib.error.URLError) as exc:
        print("MINI_APP_QUEUE_AUDIT=NETWORK_"+type(exc).__name__);return 2
    try:result=inspect(raw)
    except ValueError:
        print("MINI_APP_QUEUE_AUDIT=INVALID_SIZE");return 2
    for name in TARGETS:
        marks=result[name]
        if marks is None:print("FUNCTION_"+name.upper()+"=MISSING");continue
        print("FUNCTION_"+name.upper()+"="+",".join(k for k,v in marks.items() if v))
    print("FETCH_PARAM_NAMES="+",".join(result["fetch_params"]))
    print("MINI_APP_QUEUE_AUDIT=COMPLETE_READ_ONLY")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
