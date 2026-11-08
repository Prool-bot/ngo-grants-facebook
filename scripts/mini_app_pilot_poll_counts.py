"""Read aggregate anonymous Telegram poll votes for NGO Grants AI public pilot.

Uses existing Telegram read-only session. No voter identities, phones, raw
messages, groups, or respondent details are read or stored. Never sends.
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import sys

CHANNEL="ngo_grants"
RECEIPT=Path("launches/mini_app_pilot_poll_2026-11-08.json")
OUTPUT=Path("reports/mini_app_pilot_poll_3818.json")
POLL_ID=3818


def summarize(media)->dict:
    poll=getattr(media,"poll",None)
    results=getattr(media,"results",None)
    if poll is None or results is None:
        raise RuntimeError("Poll details are not available")
    if getattr(poll,"public_voters",False):
        raise RuntimeError("Poll unexpectedly reveals voters")
    answers=list(getattr(poll,"answers",[]) or [])
    if not answers or len(answers)>12:
        raise RuntimeError("Unexpected poll options")
    counts={}
    for item in (getattr(results,"results",[]) or []):
        key=getattr(item,"option",None)
        count=getattr(item,"voters",None)
        if not isinstance(key,bytes) or not isinstance(count,int) or count<0:
            raise RuntimeError("Unexpected anonymous poll counter")
        if key in counts:raise RuntimeError("Duplicate poll answer key")
        counts[key]=count
    options=[]
    for i,item in enumerate(answers):
        key=getattr(item,"option",None)
        raw_text=getattr(item,"text",None)
        text=raw_text if isinstance(raw_text,str) else getattr(raw_text,"text",None)
        if not isinstance(key,bytes) or not isinstance(text,str):
            raise RuntimeError("Unexpected option type")
        options.append({"index":i+1,"label":text,"votes":counts.get(key,0)})
    total=getattr(results,"total_voters",None)
    if total is not None and (not isinstance(total,int) or total<0):
        raise RuntimeError("Invalid total voter count")
    # Telegram can omit breakdown temporarily. Do not mistake missing
    # details for a zero-vote result when total_voters is positive.
    breakdown_available=not(total and not counts)
    return {
       "post_url":"https://t.me/ngo_grants/3818",
       "poll_id":POLL_ID,"anonymous":True,
       "total_voters":total,
       "options":options if breakdown_available else None,
       "breakdown_available":breakdown_available
    }


def refreshed_poll_media(media, updates):
    """Use only aggregate UpdateMessagePoll counters from explicit read-only RPC.

    Telegram may attach a partial (min) poll-results object to channel
    messages, showing total voters but hiding all option counts.
    """
    from types import SimpleNamespace
    poll=getattr(media,"poll",None)
    if poll is None:return media
    current=getattr(media,"results",None)
    current_count=len(getattr(current,"results",[]) or [])
    wanted=getattr(poll,"id",None)
    if wanted is None:return media
    for update in getattr(updates,"updates",[]) or []:
        if getattr(update,"poll_id",None)!=wanted:continue
        fresh=getattr(update,"results",None)
        if fresh is None:continue
        if len(getattr(fresh,"results",[]) or [])>current_count:
            return SimpleNamespace(poll=poll,results=fresh)
    return media


async def main():
    from telethon import TelegramClient
    from telethon.tl.functions.messages import GetPollResultsRequest
    from telethon.sessions import StringSession
    required=("TELEGRAM_API_ID","TELEGRAM_API_HASH","TELEGRAM_SESSION")
    for key in required:
        if not os.getenv(key,"").strip():
            raise RuntimeError("Required Telegram session credentials are missing")
    receipt=json.loads(RECEIPT.read_text("utf8"))
    if (receipt.get("status")!="poll_posted_announcement_updated" or
        receipt.get("message_id")!=POLL_ID or
        receipt.get("url")!="https://t.me/ngo_grants/3818"):
        raise RuntimeError("Poll receipt not confirmed")
    async with TelegramClient(StringSession(os.environ["TELEGRAM_SESSION"].strip()),
                              int(os.environ["TELEGRAM_API_ID"]),
                              os.environ["TELEGRAM_API_HASH"].strip(),
                              receive_updates=False) as client:
        if not await client.is_user_authorized():
            raise RuntimeError("Telegram session not authorized")
        message=await client.get_messages(CHANNEL,ids=POLL_ID)
        if not message or message.id!=POLL_ID:
            raise RuntimeError("Cannot verify official poll message")
        media=getattr(message,"media",None)
        poll=getattr(media,"poll",None)
        if poll is None or getattr(poll,"public_voters",False):
            raise RuntimeError("Unexpected poll type")
        # This returns aggregate results only; never request voter identities.
        # poll_hash=0 requests a fresh state rather than a cached no-change result.
        try:
            updates=await client(GetPollResultsRequest(
                peer=await client.get_input_entity(CHANNEL),
                msg_id=POLL_ID,poll_hash=0
            ))
        except TypeError:
            # Older Telethon layers omit poll_hash.
            updates=await client(GetPollResultsRequest(
                peer=await client.get_input_entity(CHANNEL),
                msg_id=POLL_ID
            ))
        media=refreshed_poll_media(media,updates)
        out=summarize(media)
    OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    existing=json.loads(OUTPUT.read_text("utf8")) if OUTPUT.exists() else None
    if out!=existing:
        OUTPUT.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n","utf8")
    print("ANONYMOUS_PILOT_POLL_TOTAL_VOTERS="+str(out["total_voters"]))
    print("ANONYMOUS_PILOT_POLL_BREAKDOWN_AVAILABLE="+str(out["breakdown_available"]))
    if out["options"]:
        for row in out["options"]:
            print("POLL_OPTION_"+str(row["index"])+"_VOTES="+str(row["votes"]))
    print("POLL_RESULTS_PERSONAL_IDENTIFIERS_STORED=0")


if __name__=="__main__":
    try:asyncio.run(main())
    except Exception as e:
        # Telegram exceptions may include private session material or chat IDs.
        # Do not print their raw descriptions in public CI logs.
        print("POLL_READ_ONLY_ERROR="+type(e).__name__,file=sys.stderr)
        sys.exit(1)
