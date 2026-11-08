"""Make existing pinned NGO Grants AI post #3813 a one-button Mini App shortcut.

No new post, no pin/unpin operations, no other channel changes. The Telegram
client displays the *text* preview in the pinned banner; inline buttons appear
on the actual pinned message only. Keep the preview text itself minimal and
clickable and render exactly one inline Main Mini App launch button.
"""
from __future__ import annotations
from base64 import b64encode
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import urllib.error
import urllib.request

from mini_app_public_preflight import telegram, CHANNEL
from mini_app_public_launch import github_api
from mini_app_channel_direct_pilot_v05 import MAIN_LINK, BOTFATHER, MARKER as PRIOR

BOT="ngogratsAI_bot"
POST_ID=3813
MARKER="launches/mini_app_pinned_shortcut_v05_2026-11-08.json"
LABEL="🤖 Знайти гранти"
APPROVAL="YES_MINIMAL_EDIT_PINNED_3813_ONCE"

def post_markup()->dict:
    # The hyperlink remains usable when the client does not render inline buttons.
    return {
        "chat_id":CHANNEL,
        "message_id":POST_ID,
        "text":'<a href="'+MAIN_LINK+'">'+LABEL+"</a>",
        "parse_mode":"HTML",
        "disable_web_page_preview":True,
        "reply_markup":{"inline_keyboard":[[
            {"text":LABEL,"url":MAIN_LINK}
        ]]}
    }

def preflight()->str:
    if (os.environ.get("GITHUB_ACTIONS")!="true" or
        os.environ.get("GITHUB_REF")!="refs/heads/main" or
        os.environ.get("GITHUB_REPOSITORY")!="Prool-bot/ngo-grants-facebook" or
        os.environ.get("NGO_MINI_APP_PINNED_SHORTCUT_APPROVED")!=APPROVAL):
        raise RuntimeError("Explicit existing pinned post edit approval missing")
    previous=json.loads(Path(PRIOR).read_text("utf-8"))
    botfather=json.loads(Path(BOTFATHER).read_text("utf-8"))
    if (previous.get("status")!="edited" or
        previous.get("message_id")!=POST_ID or
        previous.get("button_url")!=MAIN_LINK or
        botfather.get("status")!="verified_enabled" or
        botfather.get("existing_bot")!="@"+BOT):
        raise RuntimeError("Prerequisite Main Mini App edit or BotFather receipt missing")
    token=os.environ.get("NGO_GRANTS_AI_BOT_TOKEN","").strip()
    identity=telegram("getMe",token=token)
    if (identity.get("username")!=BOT or identity.get("is_bot") is not True or
        identity.get("has_main_web_app") is not True):
        raise RuntimeError("Telegram Main Mini App is not registered")
    chat=telegram("getChat",{"chat_id":CHANNEL},token=token)
    if (chat.get("username")!="ngo_grants" or chat.get("type")!="channel" or
        (chat.get("pinned_message") or {}).get("message_id")!=POST_ID):
        raise RuntimeError("Pilot post is not current pinned message; do not edit")
    member=telegram("getChatMember",
                    {"chat_id":CHANNEL,"user_id":identity["id"]},token=token)
    if member.get("status") not in ("administrator","creator"):
        raise RuntimeError("Telegram bot no longer administers the channel")
    return token

def edit_pinned(token:str)->None:
    req=urllib.request.Request(
        "https://api.telegram.org/bot"+token+"/editMessageText",
        method="POST",
        data=json.dumps(post_markup(),ensure_ascii=False).encode("utf-8"),
        headers={"content-type":"application/json",
                 "User-Agent":"NGOGrantsPinnedShortcutV05/1.0"}
    )
    try:
        with urllib.request.urlopen(req,timeout=25) as response:
            result=json.loads(response.read(60000).decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError("Telegram pinned edit rejected HTTP "+str(exc.code)+
                           "; do not retry automatically") from None
    except (OSError,urllib.error.URLError,TimeoutError):
        raise RuntimeError("Telegram pinned edit status unknown; inspect before retry") from None
    if result.get("ok") is not True or not isinstance(result.get("result"),dict):
        raise RuntimeError("Telegram pinned message edit unconfirmed")
    message=result["result"]
    buttons=(message.get("reply_markup") or {}).get("inline_keyboard") or []
    entities=message.get("entities") or []
    has_link=any(x.get("type")=="text_link" and x.get("url")==MAIN_LINK
                 for x in entities)
    if (message.get("message_id")!=POST_ID or
        (message.get("chat") or {}).get("username")!="ngo_grants" or
        message.get("text")!=LABEL or
        len(buttons)!=1 or len(buttons[0])!=1 or
        buttons[0][0].get("text")!=LABEL or
        buttons[0][0].get("url")!=MAIN_LINK or
        not has_link):
        raise RuntimeError("Telegram response not the precise clickable single-button shortcut")

def main():
    token=preflight()
    status,_=github_api("GET","contents/"+MARKER+"?ref=main")
    if status!=404:
        raise RuntimeError("Pinned shortcut edit already attempted; no automatic replay")
    record={
        "status":"attempted","operation":"editMessageText","channel":CHANNEL,
        "message_id":POST_ID,"target":"https://t.me/ngo_grants/3813",
        "label":LABEL,"main_url":MAIN_LINK,
        "pinned_before":True,
        "started_at":datetime.now(timezone.utc).isoformat(),
        "run_id":os.environ.get("GITHUB_RUN_ID","")
    }
    locked,resp=github_api("PUT","contents/"+MARKER,{
        "branch":"main",
        "message":"Reserve one-shot minimal pinned Mini App shortcut post 3813",
        "content":b64encode(json.dumps(record,ensure_ascii=False,indent=2).encode()).decode()
    })
    sha=(resp.get("content") or {}).get("sha")
    if locked!=201 or not sha:
        raise RuntimeError("Pinned shortcut edit lock failed; no Telegram write")
    edit_pinned(token)
    # Read-only check: the message remains pinned; pin/unpin never called.
    chat=telegram("getChat",{"chat_id":CHANNEL},token=token)
    if (chat.get("username")!="ngo_grants" or
        (chat.get("pinned_message") or {}).get("message_id")!=POST_ID):
        raise RuntimeError("Edited post could not be confirmed as still pinned")
    record["status"]="verified_pinned_single_button"
    record["verified_at"]=datetime.now(timezone.utc).isoformat()
    status,_=github_api("PUT","contents/"+MARKER,{
        "branch":"main","sha":sha,
        "message":"Confirm pinned post 3813 shows only Find Grants launch",
        "content":b64encode(json.dumps(record,ensure_ascii=False,indent=2).encode()).decode()
    })
    if status!=200:
        raise RuntimeError("Telegram changed but GitHub receipt was not updated")
    print("PINNED_MINI_APP_SHORTCUT_VERIFIED=https://t.me/ngo_grants/3813")
    print("PINNED_TEXT="+LABEL)
    print("PINNED_SINGLE_BUTTON=True")
    print("OTHER_PINNED_MESSAGES_UNTOUCHED=True")
    print("NO_NEW_POSTS=TRUE;NO_CATALOG_ORDERS=TRUE")

if __name__=="__main__":
    try:main()
    except RuntimeError as exc:raise SystemExit(str(exc)) from None
