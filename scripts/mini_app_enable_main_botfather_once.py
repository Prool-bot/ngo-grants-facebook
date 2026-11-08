"""Enable Main Mini App for ONLY the existing NGO Grants Telegram bot via BotFather.

One-shot guarded setup from a confirmed owner session. This code:
- verifies production v0.5 signed API readiness and BotFather identity;
- consumes only the exact known 'Enable Mini App' button in the already
  inspected Configure Mini App menu;
- sends one hard-coded HTTPS URL, not user input, to official BotFather;
- verifies Bot API getMe.has_main_web_app before reporting success;
- makes no channel posts, D1 writes, catalog requests or new bot accounts.

The GitHub one-shot marker is committed BEFORE any BotFather setting action.
On uncertain outcomes the attempt marker prevents automatic repeats.
"""
from __future__ import annotations
import asyncio
from base64 import b64encode
from datetime import datetime,timezone
import json
import os
import re
import sys

from mini_app_botfather_nav_readonly import menu,BOT,FATHER
from mini_app_botfather_enable_preview import is_enable
from mini_app_public_launch import github_api
from mini_app_public_preflight import telegram

URL="https://ngo-grants-instant-bot.oleh-protasoff.workers.dev/mini-app/direct"
MARKER="launches/mini_app_botfather_main_2026-11-08.json"
APPROVED="YES_ENABLE_EXISTING_NGO_GRANTS_MAIN_APP_ONCE"

def confirm_environment():
    if (os.getenv("GITHUB_ACTIONS")!="true" or
        os.getenv("GITHUB_REF")!="refs/heads/main" or
        os.getenv("GITHUB_REPOSITORY")!="Prool-bot/ngo-grants-facebook" or
        os.getenv("NGO_BOTFATHER_MAIN_APP_RELEASE_APPROVED")!=APPROVED):
        raise RuntimeError("Explicit Main Mini App owner setup gate missing")
    if URL!="https://ngo-grants-instant-bot.oleh-protasoff.workers.dev/mini-app/direct":
        raise RuntimeError("Unapproved Mini App URL")

def lock_action():
    status,_=github_api("GET",f"contents/{MARKER}?ref=main")
    if status!=404:
        raise RuntimeError("Main App setup already attempted; refuse repeat")
    rec={
      "status":"attempted","kind":"BotFather Main Mini App enable",
      "existing_bot":"@ngogratsAI_bot","target_url":URL,
      "started_at":datetime.now(timezone.utc).isoformat(),
      "run_id":os.getenv("GITHUB_RUN_ID","")
    }
    body={"branch":"main",
          "message":"Reserve one-shot existing NGO Grants Main Mini App BotFather setup",
          "content":b64encode(json.dumps(rec,ensure_ascii=False,indent=2).encode()).decode()}
    created,resp=github_api("PUT",f"contents/{MARKER}",body)
    sha=(resp.get("content") or {}).get("sha")
    if created!=201 or not sha:
        raise RuntimeError("Could not confirm BotFather one-shot lock")
    print("BOTFATHER_MAIN_MINI_APP_SETUP_ATTEMPT_LOCKED")
    return rec,sha

def mark_complete(record,sha):
    record["status"]="verified_enabled"
    record["verified_at"]=datetime.now(timezone.utc).isoformat()
    status,_=github_api("PUT",f"contents/{MARKER}",{
      "branch":"main","sha":sha,
      "message":"Verify Main Mini App enabled for existing NGO Grants AI bot",
      "content":b64encode(json.dumps(record,ensure_ascii=False,indent=2).encode()).decode()
    })
    if status!=200:
        raise RuntimeError("Main App enabled but GitHub receipt update failed; do not repeat")

async def wait_url_prompt(client,father,start_id):
    # Require a NEW BotFather message after Enable. Prior help messages
    # mentioning URLs are not authorization to send a configuration URL.
    for _ in range(20):
        await asyncio.sleep(.7)
        replies=await client.get_messages(father,limit=8)
        for msg in replies:
            if getattr(msg,"out",False) or (msg.id or 0)<=start_id:
                continue
            text=str(getattr(msg,"raw_text","") or "")
            if (re.search(r"\b(?:URL|link|website)\b",text,re.I) and
                re.search(r"\b(?:send|provide|enter|specify|paste|please)\b",text,re.I)):
                return True
    raise RuntimeError("BotFather did not explicitly request a Mini App URL")

async def wait_bot_registration(bot_token):
    for attempt in range(24):
        await asyncio.sleep(1)
        identity=telegram("getMe",token=bot_token)
        if (identity.get("username")!="ngogratsAI_bot" or
            identity.get("is_bot") is not True):
            raise RuntimeError("Bot token identity changed")
        if identity.get("has_main_web_app") is True:return True
    raise RuntimeError("BotFather URL may have been sent but Main App not confirmed; do not retry")

async def main():
    confirm_environment()
    bot_token=os.getenv("NGO_GRANTS_AI_BOT_TOKEN","").strip()
    bot=telegram("getMe",token=bot_token)
    if bot.get("is_bot") is not True or bot.get("username")!=BOT:
        raise RuntimeError("Telegram bot token belongs to unexpected bot")
    if bot.get("has_main_web_app") is True:
        print("MAIN_MINI_APP_ALREADY_ENABLED=True")
        return True
    from telethon import TelegramClient
    from telethon.sessions import StringSession
    async with TelegramClient(
        StringSession(os.environ["TELEGRAM_SESSION"].strip()),
        int(os.environ["TELEGRAM_API_ID"]),
        os.environ["TELEGRAM_API_HASH"].strip(),
        receive_updates=False
    ) as client:
        if not await client.is_user_authorized():
            raise RuntimeError("Existing owner session not authorized")
        entity=await client.get_entity(BOT)
        father=await client.get_entity(FATHER)
        if (getattr(entity,"bot",False) is not True or
            getattr(entity,"bot_can_edit",False) is not True or
            str(getattr(entity,"username","")).lower()!=BOT.lower() or
            getattr(father,"bot",False) is not True or
            str(getattr(father,"username","")).lower()!="botfather"):
            raise RuntimeError("Owner session or BotFather identity changed")
        enable_menu,enable_button=await menu(client,father,is_enable)
        rec,sha=lock_action()
        # Only now is a configuration-changing action authorized.
        await enable_button.click()
        await wait_url_prompt(client,father,enable_menu.id)
        await client.send_message(father,URL)
        print("BOTFATHER_APPROVED_URL_SENT_ONCE=True")
        await wait_bot_registration(bot_token)
        mark_complete(rec,sha)
    print("BOTFATHER_MAIN_MINI_APP_ENABLED_VERIFIED=True")
    print("EXISTING_TELEGRAM_BOT=@ngogratsAI_bot")
    print("NEW_BOTS=0;CHANNEL_POSTS=0;REAL_CATALOG_ORDERS=0")
    return True

if __name__=="__main__":
    try:asyncio.run(main())
    except Exception as exc:
        # Telethon errors may contain user IDs, secret session details or bot
        # response text; emit only exception type and no raw error message.
        print("BOTFATHER_MAIN_APP_SETUP_UNVERIFIED="+type(exc).__name__,file=sys.stderr)
        raise SystemExit(1)
