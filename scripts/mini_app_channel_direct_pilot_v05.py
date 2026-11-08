"""One-time correction of existing public Mini App PILOT announcement (#3813).

The current button points only to https://t.me/ngogratsAI_bot, which opens a
private bot chat. Replace it with the *verified Main Mini App deep link* in
the SAME existing channel post, and keep a separate explicitly labelled
legacy fallback. This is a limited voluntary pilot, not a global CTA rollout.

Safety: no new messages, no fake orders, no bot setting changes. Commit a
one-shot GitHub attempt lock BEFORE any Telegram write; never retry an
uncertain Telegram edit without independent inspection.
"""
from __future__ import annotations
from base64 import b64encode
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import urllib.error
import urllib.request

from mini_app_public_preflight import telegram,CHANNEL
from mini_app_public_launch import github_api
from mini_app_start_v03_edit_post import updated_post

BOT="ngogratsAI_bot"
POST_ID=3813
ORIGINAL="launches/mini_app_start_v03_announcement_edit.json"
BOTFATHER="launches/mini_app_botfather_main_2026-11-08.json"
MARKER="launches/mini_app_channel_direct_pilot_v05_2026-11-08.json"
MAIN_LINK="https://t.me/ngogratsAI_bot?startapp=ngo_grants"
FALLBACK_LINK="https://t.me/ngogratsAI_bot"
APPROVAL="YES_EDIT_EXISTING_PILOT_POST_3813_ONLY"

OLD_INSTRUCTIONS=(
    "1️⃣ Відкрийте бота @ngogratsAI_bot.\n"
    "2️⃣ Натисніть «Розпочати» (Start) — кнопка помічника з’явиться одразу.\n"
    "3️⃣ Натисніть «🤖 Відкрити грантового помічника».\n"
    "4️⃣ Заповніть анкету: тип заявника, напрями діяльності, географія, роль і форма фінансування.\n"
    "5️⃣ Перевірте підсумок і, якщо хочете замовити добірку, натисніть «Замовити каталог»."
)
NEW_INSTRUCTIONS=(
    "1️⃣ Натисніть кнопку «🤖 Знайти гранти» під цим дописом. "
    "Вона використовує пряме посилання Main Mini App, а не перехід до чату бота.\n"
    "2️⃣ Заповніть анкету: тип заявника, напрями діяльності, географія, роль і форма фінансування.\n"
    "3️⃣ Перевірте підсумок і за бажанням натисніть «Замовити каталог». "
    "Підтвердженням прийняття буде номер замовлення на екрані.\n\n"
    "Це перевірка прямого запуску. Якщо ваш Telegram не відкрив Mini App, "
    "скористайтеся окремою кнопкою «↩️ Резервний вхід через бота» "
    "та повідомте про збій у відгуках без персональних даних."
)

def proposed_text()->str:
    old=updated_post(BOT)
    if old.count(OLD_INSTRUCTIONS)!=1:
        raise RuntimeError("Original pilot post template changed unexpectedly")
    new=old.replace(OLD_INSTRUCTIONS,NEW_INSTRUCTIONS)
    if len(new)>3900 or "1️⃣ Відкрийте бота" in new:
        raise RuntimeError("Invalid direct-link pilot copy")
    return new

def validate_preflight():
    if (os.getenv("GITHUB_ACTIONS")!="true" or
        os.getenv("GITHUB_REF")!="refs/heads/main" or
        os.getenv("GITHUB_REPOSITORY")!="Prool-bot/ngo-grants-facebook" or
        os.getenv("NGO_MINI_APP_CHANNEL_PILOT_APPROVED")!=APPROVAL):
        raise RuntimeError("One-time v0.5 pilot edit authorization missing")
    record=json.loads(Path(ORIGINAL).read_text("utf-8"))
    if (record.get("status")!="edited" or
        record.get("target")!="https://t.me/ngo_grants/3813"):
        raise RuntimeError("Existing pilot announcement edit receipt is unverified")
    main=json.loads(Path(BOTFATHER).read_text("utf-8"))
    if (main.get("status")!="verified_enabled" or
        main.get("existing_bot")!="@"+BOT or
        main.get("target_url")!=
          "https://ngo-grants-instant-bot.oleh-protasoff.workers.dev/mini-app/direct"):
        raise RuntimeError("Verified Main Mini App registration missing")

def edit_existing(token:str,text:str)->dict:
    payload={
        "chat_id":CHANNEL,"message_id":POST_ID,
        "text":text,"parse_mode":"HTML",
        "disable_web_page_preview":True,
        "reply_markup":{"inline_keyboard":[
            [{"text":"🤖 Знайти гранти","url":MAIN_LINK}],
            [{"text":"↩️ Резервний вхід через бота","url":FALLBACK_LINK}]
        ]}
    }
    req=urllib.request.Request(
        "https://api.telegram.org/bot"+token+"/editMessageText",
        method="POST",
        headers={"content-type":"application/json",
                 "User-Agent":"NGOGrantsDirectChannelPilotV05/1.0"},
        data=json.dumps(payload,ensure_ascii=False).encode("utf-8")
    )
    try:
        with urllib.request.urlopen(req,timeout=25) as response:
            result=json.loads(response.read(60000).decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError("Telegram pilot post edit rejected, HTTP "+
                           str(exc.code)+"; do not retry automatically") from None
    except (OSError,urllib.error.URLError,TimeoutError):
        raise RuntimeError("Telegram edit outcome unknown; inspect post manually") from None
    if result.get("ok") is not True or not isinstance(result.get("result"),dict):
        raise RuntimeError("Telegram edit not confirmed; do not retry")
    message=result["result"]
    buttons=(message.get("reply_markup") or {}).get("inline_keyboard") or []
    if (message.get("message_id")!=POST_ID or
        (message.get("chat") or {}).get("username")!="ngo_grants" or
        "1️⃣ Натисніть кнопку" not in message.get("text","") or
        len(buttons)!=2 or
        buttons[0][0].get("url")!=MAIN_LINK or
        buttons[1][0].get("url")!=FALLBACK_LINK):
        raise RuntimeError("Telegram edit response does not confirm exact new CTA")
    return message

def main():
    validate_preflight()
    token=os.getenv("NGO_GRANTS_AI_BOT_TOKEN","").strip()
    identity=telegram("getMe",token=token)
    if (identity.get("username")!=BOT or identity.get("is_bot") is not True or
        identity.get("has_main_web_app") is not True):
        raise RuntimeError("Telegram bot Main Mini App is not active")
    status,_=github_api("GET","contents/"+MARKER+"?ref=main")
    if status!=404:
        raise RuntimeError("The one-time channel pilot edit has already been attempted")
    _=proposed_text()
    record={
        "status":"attempted","operation":"editMessageText",
        "channel":"@ngo_grants","message_id":POST_ID,
        "target":"https://t.me/ngo_grants/3813","button_url":MAIN_LINK,
        "fallback_url":FALLBACK_LINK,
        "created_at":datetime.now(timezone.utc).isoformat(),
        "run_id":os.getenv("GITHUB_RUN_ID","")
    }
    locked,resp=github_api("PUT","contents/"+MARKER,{
        "branch":"main",
        "message":"Reserve one-shot Main Mini App pilot CTA correction on post 3813",
        "content":b64encode(json.dumps(record,ensure_ascii=False,indent=2).encode("utf-8")).decode("ascii")
    })
    sha=(resp.get("content") or {}).get("sha")
    if locked!=201 or not sha:
        raise RuntimeError("Attempt lock not durable; no Telegram edit")
    message=edit_existing(token,proposed_text())
    record["status"]="edited"
    record["confirmed_at"]=datetime.now(timezone.utc).isoformat()
    status,_=github_api("PUT","contents/"+MARKER,{
        "branch":"main","sha":sha,
        "message":"Confirm pilot post 3813 Main Mini App link and legacy fallback",
        "content":b64encode(json.dumps(record,ensure_ascii=False,indent=2).encode("utf-8")).decode("ascii")
    })
    if status!=200:
        raise RuntimeError("Telegram edit succeeded but GitHub receipt is not committed")
    print("CHANNEL_PILOT_POST_EDITED=https://t.me/ngo_grants/3813")
    print("DIRECT_MAIN_APP_BUTTON_VERIFIED="+MAIN_LINK)
    print("LEGACY_BOT_FALLBACK_RETAINED=True")
    print("NEW_CHANNEL_MESSAGES=0;CATALOG_ORDERS_CREATED=0")

if __name__=="__main__":
    try:main()
    except RuntimeError as e:raise SystemExit(str(e)) from None
