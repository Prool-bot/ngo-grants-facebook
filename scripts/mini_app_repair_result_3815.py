"""One-shot repair of the already published no-results post #3815 only.

Replace the old private-bot chat link with verified Main Mini App URL and one
inline launch button. Never send a message, repin, or rewrite unrelated posts.
Only edit if a live, read-only Telegram check matches the exact old template.
GitHub attempt lock is durable BEFORE the Telegram edit.
"""
from __future__ import annotations
from base64 import b64encode
from datetime import datetime,timezone
from html import unescape
import asyncio
import json
import os
from pathlib import Path
import re
import urllib.error
import urllib.request

import ngo_grants_ai as app
from mini_app_public_preflight import telegram, CHANNEL
from mini_app_public_launch import github_api

MESSAGE_ID=3815
TARGET="https://t.me/ngo_grants/3815"
MARKER="launches/mini_app_result_3815_direct_link_2026-11-08.json"
APPROVED="YES_REPAIR_EXISTING_RESULT_3815_ONCE"
OLD_LINK="https://t.me/ngogratsAI_bot"
NEW_LINK="https://t.me/ngogratsAI_bot?startapp=ngo_grants"

def find_target(state:dict)->dict:
    rows=[r for r in state.get("no_results",[]) if
          r.get("status")=="published" and r.get("channel_url")==TARGET]
    if (len(rows)!=1 or rows[0].get("reason")!="no_candidate" or
        rows[0].get("checked_on")!="2026-11-08"):
        raise RuntimeError("Unique published result #3815 not verified in Git state")
    return rows[0]

def current_and_legacy_text(item:dict)->tuple[str,str]:
    direct=app.public_no_results_text(item)
    if direct.count(NEW_LINK)!=1 or direct.count("🤖 Знайти гранти:")!=1:
        raise RuntimeError("Unverified direct result template")
    # The original public message used exactly the same template except
    # for the previous private chat URL and call-to-action label.
    legacy=direct.replace("🤖 Знайти гранти: "+NEW_LINK,
                          "🤖 Замовити добірку: "+OLD_LINK)
    if legacy==direct:
        raise RuntimeError("Legacy template reconstruction failed")
    return direct,legacy

def visible_text(html:str)->str:
    return unescape(re.sub(r"<[^>]+>","",html)).strip()

async def read_only_verify_existing(expected_legacy:str)->None:
    from telethon import TelegramClient
    from telethon.sessions import StringSession
    async with TelegramClient(
        StringSession(os.environ["TELEGRAM_SESSION"].strip()),
        int(os.environ["TELEGRAM_API_ID"]),
        os.environ["TELEGRAM_API_HASH"].strip(),
        receive_updates=False
    ) as client:
        if not await client.is_user_authorized():
            raise RuntimeError("Telegram read-only session not authenticated")
        msg=await client.get_messages("ngo_grants",ids=MESSAGE_ID)
        if not msg or msg.id!=MESSAGE_ID or
           (msg.raw_text or "").strip()!=visible_text(expected_legacy):
            raise RuntimeError("Real Telegram post does not match expected original text")
    print("OLD_PUBLIC_RESULT_3815_TEMPLATE_VERIFIED=True")

def submit_once(token:str,html:str)->None:
    payload={
        "chat_id":CHANNEL,"message_id":MESSAGE_ID,
        "text":html,"parse_mode":"HTML","disable_web_page_preview":True,
        "reply_markup":{"inline_keyboard":[[{
            "text":"🤖 Знайти гранти","url":NEW_LINK
        }]]}
    }
    req=urllib.request.Request(
       "https://api.telegram.org/bot"+token+"/editMessageText",
       method="POST",data=json.dumps(payload,ensure_ascii=False).encode("utf-8"),
       headers={"Content-Type":"application/json",
                "User-Agent":"NGOGrantsResultLinkRepair/1.0"}
    )
    try:
        with urllib.request.urlopen(req,timeout=25) as response:
            reply=json.loads(response.read(60000).decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError("Result edit rejected HTTP "+str(exc.code)+
                           "; do not retry automatically") from None
    except (OSError,urllib.error.URLError,TimeoutError):
        raise RuntimeError("Result edit outcome uncertain; inspect before retry") from None
    if reply.get("ok") is not True or not isinstance(reply.get("result"),dict):
        raise RuntimeError("Result message edit not confirmed")
    msg=reply["result"]
    buttons=(msg.get("reply_markup") or {}).get("inline_keyboard") or []
    if (msg.get("message_id")!=MESSAGE_ID or
        (msg.get("chat") or {}).get("username")!="ngo_grants" or
        NEW_LINK not in msg.get("text","") or
        OLD_LINK in msg.get("text","").replace(NEW_LINK,"") or
        buttons!=[[{"text":"🤖 Знайти гранти","url":NEW_LINK}]]):
        raise RuntimeError("Result edit receipt is not the exact expected message")

async def main()->None:
    if (os.environ.get("GITHUB_ACTIONS")!="true" or
        os.environ.get("GITHUB_REF")!="refs/heads/main" or
        os.environ.get("GITHUB_REPOSITORY")!="Prool-bot/ngo-grants-facebook" or
        os.environ.get("NGO_GRANTS_RESULT_LINK_REPAIR_APPROVED")!=APPROVED):
        raise RuntimeError("One-shot result edit authorization missing")
    state=json.loads(Path("ai_catalogs/state.json").read_text("utf-8"))
    item=find_target(state)
    token=os.environ.get("NGO_GRANTS_AI_BOT_TOKEN","").strip()
    identity=telegram("getMe",token=token)
    if (identity.get("is_bot") is not True or
        identity.get("username")!="ngogratsAI_bot" or
        identity.get("has_main_web_app") is not True):
        raise RuntimeError("Existing Telegram Main Mini App is not available")
    app.VERIFIED_BOT_USERNAME=identity["username"]
    app.VERIFIED_MAIN_MINI_APP=True
    direct,legacy=current_and_legacy_text(item)
    # Check the historic message before any write or creating a lock.
    await read_only_verify_existing(legacy)
    status,_=github_api("GET","contents/"+MARKER+"?ref=main")
    if status!=404:
        raise RuntimeError("Repair already attempted; do not repeat")
    rec={
        "status":"attempted","operation":"editMessageText","target":TARGET,
        "message_id":MESSAGE_ID,"direct_link":NEW_LINK,
        "started_at":datetime.now(timezone.utc).isoformat(),
        "run_id":os.environ.get("GITHUB_RUN_ID","")
    }
    locked,reply=github_api("PUT","contents/"+MARKER,{
        "branch":"main",
        "message":"Reserve one-time repair of old bot chat link in result 3815",
        "content":b64encode(json.dumps(rec,ensure_ascii=False,indent=2).encode()).decode()
    })
    sha=(reply.get("content") or {}).get("sha")
    if locked!=201 or not sha:
        raise RuntimeError("Repair lock not durable; no Telegram write")
    submit_once(token,direct)
    rec["status"]="verified_updated"
    rec["verified_at"]=datetime.now(timezone.utc).isoformat()
    status,_=github_api("PUT","contents/"+MARKER,{
        "branch":"main","sha":sha,
        "message":"Confirm no-results post 3815 links directly to Main Mini App",
        "content":b64encode(json.dumps(rec,ensure_ascii=False,indent=2).encode()).decode()
    })
    if status!=200:
        raise RuntimeError("Telegram edited but receipt not committed; do not retry")
    print("RESULT_3815_DIRECT_MINI_APP_LINK_VERIFIED=True")
    print("OLD_RESULT_CONTENT_PRESERVED=True")
    print("NO_NEW_MESSAGES_OR_CATALOG_ORDERS=True")

if __name__=="__main__":
    try:asyncio.run(main())
    except RuntimeError as exc:raise SystemExit(str(exc)) from None
