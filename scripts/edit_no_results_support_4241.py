"""Edit only the user's shown no-results post 4241; never send a new post."""
import asyncio
import json
import os
import sys
import re
import html
from pathlib import Path
from datetime import datetime, timezone
from base64 import b64encode
from unittest.mock import patch
import urllib.request
import urllib.error
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import ngo_grants_ai as ai
from add_pinned_support import bot_token, snapshot
from mini_app_public_launch import github_api
from mini_app_pinned_shortcut_v05 import MAIN_LINK
from telethon import TelegramClient
from telethon.sessions import StringSession

POST_ID=4241
URL="https://t.me/ngo_grants/4241"
RECORD="launches/no_results_support_4241_2026-11-28.json"

def planned():
    state=json.loads(Path("ai_catalogs/state.json").read_text("utf-8"))
    matches=[x for x in state.get("no_results",[]) if x.get("channel_url")==URL and x.get("status")=="published" and x.get("checked_on")=="2026-11-28"]
    if len(matches)!=1 or not matches[0]["topic"].startswith("На розвиток кіно;"):
        raise RuntimeError("Exact shown post not found in state")
    with patch.object(ai,"verified_order_url",return_value=MAIN_LINK):
        text=ai.public_no_results_text(matches[0])
        markup=ai.no_results_public_markup()
    plain=html.unescape(re.sub(r"</?b>","",text))
    old=plain.removesuffix("\n\n"+ai.SUPPORT_INVITATION)
    if old==plain:
        raise RuntimeError("Support suffix absent")
    return text,markup,plain,old

def edit(token,text,markup,plain):
    data={"chat_id":"@ngo_grants","message_id":POST_ID,"text":text,"parse_mode":"HTML",
          "link_preview_options":{"is_disabled":True},"reply_markup":markup}
    req=urllib.request.Request("https://api.telegram.org/bot"+token+"/editMessageText",
        method="POST",data=json.dumps(data,ensure_ascii=False).encode(),
        headers={"Content-Type":"application/json","User-Agent":"NGOGrantsNoResultsSupport/1.0"})
    try:
        with urllib.request.urlopen(req,timeout=25) as resp:
            result=json.loads(resp.read(60000))
    except urllib.error.HTTPError as exc:
        raise RuntimeError("Telegram edit HTTP "+str(exc.code)+"; no automatic retry") from None
    except (OSError,urllib.error.URLError,TimeoutError):
        raise RuntimeError("Telegram edit outcome unknown; no automatic retry") from None
    msg=result.get("result") or {}
    if not result.get("ok") or msg.get("message_id")!=POST_ID or msg.get("chat",{}).get("username")!="ngo_grants" or msg.get("text")!=plain or msg.get("reply_markup")!=markup:
        raise RuntimeError("Telegram edit result not verified")
    return sum(e.get("type")=="bold" for e in msg.get("entities",[]))

async def run(token):
    text,markup,plain,old=planned()
    async with TelegramClient(StringSession(os.environ["TELEGRAM_SESSION"].strip()),int(os.environ["TELEGRAM_API_ID"]),
            os.environ["TELEGRAM_API_HASH"].strip(),receive_updates=False) as client:
        if not await client.is_user_authorized():raise RuntimeError("Read-only session unavailable")
        msg=await client.get_messages("ngo_grants",ids=POST_ID)
        if not msg or msg.id!=POST_ID or msg.message not in (plain,old):
            raise RuntimeError("Live post text differs from shown post; do not edit")
        original=snapshot(msg)
        if original["reply_markup"] not in ({"inline_keyboard":markup["inline_keyboard"][:1]},markup):
            raise RuntimeError("Live post buttons differ; do not overwrite")
        bold=sum(type(e).__name__=="MessageEntityBold" for e in (msg.entities or []))
        if bold!=text.count("<b>"):
            raise RuntimeError("Original bold formatting differs")
        if msg.message!=plain or original["reply_markup"]!=markup:
            if edit(token,text,markup,plain)!=bold:
                raise RuntimeError("Edited bold formatting not verified")
        confirmed=await client.get_messages("ngo_grants",ids=POST_ID)
        if not confirmed or confirmed.message!=plain or snapshot(confirmed)["reply_markup"]!=markup:
            raise RuntimeError("Read-back verification failed")
        rec={"status":"verified_edited","message_id":POST_ID,"url":URL,"buttons":markup,"text_verified":True,
             "bold_entities":bold,"verified_at":datetime.now(timezone.utc).isoformat(),"run_id":os.getenv("GITHUB_RUN_ID")}
        status,_=github_api("PUT","contents/"+RECORD,{"branch":"main","message":"Verify support added to shown no-results post 4241",
            "content":b64encode(json.dumps(rec,ensure_ascii=False,indent=2).encode()).decode()})
        if status!=201:raise RuntimeError("Edit verified but receipt failed")
        print("NO_RESULTS_POST_UPDATED_AND_VERIFIED="+URL)

def main():
    if os.getenv("NGO_NO_RESULTS_SUPPORT_APPROVED")!="YES_EDIT_SHOWN_POST_4241_ONLY":
        raise RuntimeError("Approval absent")
    token=bot_token()
    if github_api("GET","contents/"+RECORD+"?ref=main")[0]!=404:
        raise RuntimeError("Existing receipt; no repeated edit")
    asyncio.run(run(token))

if __name__=="__main__":
    try:main()
    except RuntimeError as exc:raise SystemExit(str(exc)) from None
