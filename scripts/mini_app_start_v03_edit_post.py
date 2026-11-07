"""Update existing NGO Grants Mini App Telegram announcement after /start rollout.

Edits the ONE existing post; never sends a second announcement or a catalog.
An attempted-edit lock prevents uncontrolled retries on network uncertainty.
"""
from __future__ import annotations
import json
import os
import re
import urllib.error
import urllib.request
from datetime import datetime,timezone
from pathlib import Path

from mini_app_public_preflight import telegram,CHANNEL
from mini_app_public_launch import (
    POST_TEMPLATE,github_api,announcement_text
)

RECORD=Path("launches/mini_app_public_2026-11-07.json")
EDIT_LOCK="launches/mini_app_start_v03_announcement_edit.json"
OLD="2️⃣ Надішліть команду <code>/assistant</code>."
NEW="2️⃣ Натисніть «Розпочати» (Start) — кнопка помічника з’явиться одразу."


def updated_post(username:str)->str:
    original=announcement_text(username)
    if original.count(OLD)!=1:
        raise RuntimeError("Published announcement instructions changed")
    revised=original.replace(OLD,NEW)
    if "/assistant" in revised or len(revised)>3900:
        raise RuntimeError("Unexpected public post markup/length")
    return revised


def edit_existing(token:str,message_id:int,text:str,username:str)->dict:
    payload={"chat_id":CHANNEL,"message_id":message_id,
             "text":text,"parse_mode":"HTML",
             "disable_web_page_preview":True,
             "reply_markup":{"inline_keyboard":[[{
                  "text":"🤖 Спробувати грантового помічника",
                  "url":"https://t.me/"+username
             }]]}}
    req=urllib.request.Request(
        f"https://api.telegram.org/bot{token}/editMessageText",
        method="POST",
        headers={"Content-Type":"application/json",
                 "User-Agent":"NGOGrantsMiniAppStartEdit/1.0"},
        data=json.dumps(payload,ensure_ascii=False).encode("utf-8")
    )
    try:
        with urllib.request.urlopen(req,timeout=25) as response:
            result=json.loads(response.read(60000))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Telegram edit HTTP {exc.code}; do not retry automatically") from None
    except (OSError,urllib.error.URLError,TimeoutError) as exc:
        raise RuntimeError("Telegram edit result unknown; check post before retry") from None
    if result.get("ok") is not True:
        raise RuntimeError("Telegram edit refused; no automatic retry")
    return result.get("result") or {}


def main():
    if (os.getenv("GITHUB_ACTIONS")!="true" or
        os.getenv("GITHUB_REF")!="refs/heads/main" or
        os.getenv("GITHUB_REPOSITORY")!="Prool-bot/ngo-grants-facebook" or
        os.getenv("NGO_MINI_APP_START_POST_EDIT_APPROVED")!="YES_EDIT_EXISTING_POST_ONLY"):
        raise RuntimeError("Public edit explicit main-branch gate missing")
    if not RECORD.is_file():
        raise RuntimeError("Existing one-shot Telegram announcement receipt absent")
    record=json.loads(RECORD.read_text("utf-8"))
    message_id=record.get("message_id")
    if (record.get("status")!="posted" or record.get("channel")!=CHANNEL or
        record.get("bot")!="@ngogratsAI_bot" or message_id!=3813 or
        record.get("url")!=f"https://t.me/ngo_grants/{message_id}"):
        raise RuntimeError("Unexpected original Telegram announcement receipt")
    token=os.getenv("NGO_GRANTS_AI_BOT_TOKEN","").strip()
    identity=telegram("getMe",token=token)
    if identity.get("username")!="ngogratsAI_bot":
        raise RuntimeError("Telegram token belongs to a different bot")
    post=updated_post(identity["username"])
    status,_=github_api("GET",f"contents/{EDIT_LOCK}?ref=main")
    if status!=404:
        print("START_ANNOUNCEMENT_EDIT_ALREADY_ATTEMPTED; no repeat")
        return
    from base64 import b64encode
    locked={
        "status":"attempted","target":"https://t.me/ngo_grants/3813",
        "operation":"editMessageText","reason":"Remove /assistant entry friction",
        "created_at":datetime.now(timezone.utc).isoformat(),
        "github_run":os.getenv("GITHUB_RUN_ID","")
    }
    status,reply=github_api("PUT",f"contents/{EDIT_LOCK}",{
        "branch":"main",
        "message":"Lock one-time public post edit for direct Mini App Start",
        "content":b64encode(json.dumps(locked,ensure_ascii=False,indent=2).encode()).decode()
    })
    sha=(reply.get("content") or {}).get("sha")
    if status!=201 or not sha:
        raise RuntimeError("Post edit lock not confirmed: no Telegram edit")
    response=edit_existing(token,message_id,post,identity["username"])
    if (not isinstance(response,dict) or
        response.get("message_id")!=message_id or
        (response.get("chat") or {}).get("username")!="ngo_grants" or
        NEW.replace("<","").split(" — ")[0] not in response.get("text","")):
        raise RuntimeError("Telegram edit receipt unknown; do not retry")
    locked["status"]="edited"
    locked["edited_at"]=datetime.now(timezone.utc).isoformat()
    status,_=github_api("PUT",f"contents/{EDIT_LOCK}",{
        "branch":"main","sha":sha,
        "message":"Confirm direct-Start Mini App announcement edit",
        "content":b64encode(json.dumps(locked,ensure_ascii=False,indent=2).encode()).decode()
    })
    if status!=200:
        raise RuntimeError("Telegram post edited but GitHub receipt not committed; do not retry")
    print("EXISTING_POST_UPDATED=https://t.me/ngo_grants/3813")
    print("NEW_POSTS_SENT=0")
    print("ASSISTANT_COMMAND_NO_LONGER_REQUIRED_IN_INSTRUCTIONS=True")


if __name__=="__main__":
    try:main()
    except RuntimeError as e:raise SystemExit(str(e)) from None
