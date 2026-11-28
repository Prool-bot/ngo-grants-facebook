"""Add one support row to the existing pinned post; never publish or repin."""
from __future__ import annotations
import json
import os
from pathlib import Path
from datetime import datetime, timezone
from base64 import b64encode
import urllib.request
import urllib.error
from mini_app_pinned_shortcut_v05 import preflight, POST_ID, CHANNEL, MAIN_LINK, LABEL
from mini_app_public_preflight import telegram
from mini_app_public_launch import github_api

SUPPORT_URL="https://donatello.to/NGO_Grants"
SUPPORT_LABEL="❤️ Підтримати NGO Grants"
RECEIPT="launches/pinned_donatello_support_2026-11-28.json"

def expected_markup():
    return {"inline_keyboard":[[{"text":LABEL,"url":MAIN_LINK}],
                                [{"text":SUPPORT_LABEL,"url":SUPPORT_URL}]]}

def validate_post(message, *, after=False):
    if (message.get("message_id")!=POST_ID or message.get("text")!=LABEL or
        not any(e.get("type")=="text_link" and e.get("url")==MAIN_LINK for e in message.get("entities",[]))):
        raise RuntimeError("Pinned post text or launch link changed; no edit")
    markup=message.get("reply_markup")
    allowed=[expected_markup()] if after else [{"inline_keyboard":[[{"text":LABEL,"url":MAIN_LINK}]]},expected_markup()]
    if markup is not None and markup not in allowed:
        raise RuntimeError("Unexpected pinned buttons; no overwrite")
    return markup==expected_markup()

def edit(token):
    payload={"chat_id":CHANNEL,"message_id":POST_ID,"reply_markup":expected_markup()}
    req=urllib.request.Request("https://api.telegram.org/bot"+token+"/editMessageReplyMarkup",
        data=json.dumps(payload,ensure_ascii=False).encode("utf-8"),method="POST",
        headers={"Content-Type":"application/json","User-Agent":"NGOGrantsPinnedSupport/1.0"})
    try:
        with urllib.request.urlopen(req,timeout=25) as resp:
            result=json.loads(resp.read(60000))
    except urllib.error.HTTPError as exc:
        raise RuntimeError("Pinned markup HTTP "+str(exc.code)+"; inspect before retry") from None
    except (OSError,urllib.error.URLError,TimeoutError):
        raise RuntimeError("Pinned markup status unknown; inspect before retry") from None
    if result.get("ok") is not True or not isinstance(result.get("result"),dict):
        raise RuntimeError("Pinned edit unconfirmed")
    msg=result["result"]
    if (msg.get("chat",{}).get("username")!="ngo_grants" or not validate_post(msg,after=True)):
        raise RuntimeError("Telegram did not confirm both buttons")

def main():
    if os.getenv("NGO_PINNED_SUPPORT_APPROVED")!="YES_ADD_SUPPORT_ROW_3813":
        raise RuntimeError("Explicit pinned support approval missing")
    os.environ["NGO_MINI_APP_PINNED_SHORTCUT_APPROVED"]="YES_MINIMAL_EDIT_PINNED_3813_ONCE"
    token=preflight()
    receipt=json.loads(Path("launches/mini_app_pinned_shortcut_v05_2026-11-08.json").read_text("utf-8"))
    if receipt.get("status")!="verified_pinned_single_button" or receipt.get("message_id")!=POST_ID:
        raise RuntimeError("Original pinned receipt missing")
    status,_=github_api("GET","contents/"+RECEIPT+"?ref=main")
    if status==200:
        print("Pinned support receipt already exists; no repeat edit")
        return
    if status!=404:raise RuntimeError("Cannot read support receipt")
    chat=telegram("getChat",{"chat_id":CHANNEL},token=token)
    before=chat.get("pinned_message") or {}
    already=validate_post(before)
    if not already:
        edit(token)
    chat=telegram("getChat",{"chat_id":CHANNEL},token=token)
    validate_post(chat.get("pinned_message") or {},after=True)
    record={"status":"verified_pinned_two_buttons","operation":"editMessageReplyMarkup",
            "channel":CHANNEL,"message_id":POST_ID,"buttons":expected_markup(),
            "verified_at":datetime.now(timezone.utc).isoformat(),"run_id":os.getenv("GITHUB_RUN_ID")}
    status,_=github_api("PUT","contents/"+RECEIPT,{"branch":"main","message":"Verify existing pinned post support row",
        "content":b64encode(json.dumps(record,ensure_ascii=False,indent=2).encode()).decode()})
    if status!=201:raise RuntimeError("Pinned edit verified but receipt write failed")
    print("PINNED_3813_TWO_BUTTONS_VERIFIED=True;NO_NEW_POSTS=True;NO_PIN_CHANGES=True")

if __name__=="__main__":
    try:main()
    except RuntimeError as exc:raise SystemExit(str(exc)) from None
