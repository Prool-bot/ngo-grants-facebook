"""Add one support row to the existing pinned post; never publish or repin."""
from __future__ import annotations
import asyncio
import json
import os
from pathlib import Path
from datetime import datetime, timezone
from base64 import b64encode
import urllib.request
import urllib.error
from urllib.parse import urlparse, parse_qs
from mini_app_pinned_shortcut_v05 import preflight, POST_ID, CHANNEL, MAIN_LINK, LABEL
from mini_app_public_preflight import telegram
from mini_app_public_launch import github_api

SUPPORT_URL="https://donatello.to/NGO_Grants"
SUPPORT_LABEL="❤️ Підтримати NGO Grants"
RECEIPT="launches/pinned_donatello_support_2026-11-28.json"

def expected_markup():
    return {"inline_keyboard":[[{"text":LABEL,"url":MAIN_LINK}],
                                [{"text":SUPPORT_LABEL,"url":SUPPORT_URL}]]}

def plan_markup(message, *, post_id=POST_ID):
    if (message.get("message_id")!=post_id or message.get("text")!=LABEL or
        not any(e.get("type")=="text_link" and e.get("url")==MAIN_LINK for e in message.get("entities",[]))):
        raise RuntimeError("Pinned post text or launch link changed; no edit")
    rows=(message.get("reply_markup") or {}).get("inline_keyboard",[])
    if not isinstance(rows,list) or any(not isinstance(r,list) or not r for r in rows):
        raise RuntimeError("Invalid current pinned markup")
    if any(set(b)!={"text","url"} or not isinstance(b["text"],str) or not isinstance(b["url"],str)
           or not b["url"].startswith(("https://","tg://")) for r in rows for b in r):
        raise RuntimeError("Unsupported existing button type; no overwrite")
    rows=[list(r) for r in rows]
    def is_launch(url):
        if url==MAIN_LINK:return True
        parsed=urlparse(url)
        args=parse_qs(parsed.query)
        return (parsed.scheme=="tg" and parsed.netloc=="resolve" and
                [x.lower() for x in args.get("domain",[])]==["ngogratsai_bot"] and
                args.get("startapp")==["ngo_grants"])
    if not any(is_launch(b["url"]) for r in rows for b in r):
        rows.insert(0,[{"text":LABEL,"url":MAIN_LINK}])
    if not any(b["url"]==SUPPORT_URL for r in rows for b in r):
        rows.append([{"text":SUPPORT_LABEL,"url":SUPPORT_URL}])
    return {"inline_keyboard":rows}

def validate_post(message, *, after=False, post_id=POST_ID):
    return message.get("reply_markup")==plan_markup(message,post_id=post_id)

def edit(token, post_id, markup):
    payload={"chat_id":CHANNEL,"message_id":post_id,"reply_markup":markup}
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
    if (msg.get("chat",{}).get("username")!="ngo_grants" or not validate_post(msg,after=True,post_id=post_id)
        or msg.get("reply_markup")!=markup):
        raise RuntimeError("Telegram did not confirm preserved buttons and support")

def bot_token():
    if (os.getenv("GITHUB_ACTIONS")!="true" or os.getenv("GITHUB_REF")!="refs/heads/main" or
        os.getenv("GITHUB_REPOSITORY")!="Prool-bot/ngo-grants-facebook"):
        raise RuntimeError("Approved production runner required")
    token=os.environ["NGO_GRANTS_AI_BOT_TOKEN"].strip()
    identity=telegram("getMe",token=token)
    chat=telegram("getChat",{"chat_id":CHANNEL},token=token)
    if (identity.get("username")!="ngogratsAI_bot" or identity.get("is_bot") is not True or
        identity.get("has_main_web_app") is not True or chat.get("username")!="ngo_grants" or
        chat.get("type")!="channel"):
        raise RuntimeError("Bot or channel identity changed")
    member=telegram("getChatMember",{"chat_id":CHANNEL,"user_id":identity["id"]},token=token)
    if member.get("status") not in ("administrator","creator"):
        raise RuntimeError("Bot not authorized for channel edit")
    print("CURRENT_TOP_PIN_ID="+str((chat.get("pinned_message") or {}).get("message_id")))
    return token

def snapshot(message):
    rows=getattr(getattr(message,"reply_markup",None),"rows",[]) or []
    return {"message_id":message.id,"text":message.message,
            "entities":[{"type":"text_link","url":e.url} for e in (message.entities or []) if getattr(e,"url",None)],
            "reply_markup":{"inline_keyboard":[[{"text":b.text,"url":getattr(b,"url",None)} for b in r.buttons] for r in rows]}}

async def inspect_and_edit(token):
    from telethon import TelegramClient
    from telethon.sessions import StringSession
    from telethon.tl.types import InputMessagesFilterPinned
    async with TelegramClient(StringSession(os.environ["TELEGRAM_SESSION"].strip()),
        int(os.environ["TELEGRAM_API_ID"]),os.environ["TELEGRAM_API_HASH"].strip(),receive_updates=False) as client:
        if not await client.is_user_authorized():
            raise RuntimeError("Telegram read-only inspection session unavailable")
        old=await client.get_messages("ngo_grants",ids=POST_ID)
        candidates=[]
        if old and old.pinned is True:
            candidates=[old]
        else:
            async for msg in client.iter_messages("ngo_grants",filter=InputMessagesFilterPinned(),limit=30):
                if msg.pinned and msg.message==LABEL and any(getattr(e,"url",None)==MAIN_LINK for e in (msg.entities or [])):
                    candidates.append(msg)
        if len(candidates)!=1:
            raise RuntimeError("No unique pinned Find Grants shortcut; no Telegram write")
        msg=candidates[0]
        post_id=msg.id
        original=snapshot(msg)
        raw_rows=getattr(getattr(msg,"reply_markup",None),"rows",[]) or []
        print("PINNED_BUTTON_TYPES="+str([[type(b).__name__ for b in row.buttons] for row in raw_rows]))
        print("PINNED_BUTTON_SCHEMES="+str([[urlparse(str(getattr(b,"url","") or "")).scheme for b in row.buttons] for row in raw_rows]))
        markup=plan_markup(original,post_id=post_id)
        already=original["reply_markup"]==markup
        print("EXACT_PINNED_SHORTCUT_VERIFIED="+str(post_id))
        if not already:
            edit(token,post_id,markup)
        confirmed=await client.get_messages("ngo_grants",ids=post_id)
        if not confirmed or not confirmed.pinned or not validate_post(snapshot(confirmed),after=True,post_id=post_id):
            raise RuntimeError("Independent pinned markup verification failed")
        if snapshot(confirmed)["reply_markup"]!=markup:
            raise RuntimeError("Existing buttons not preserved")
        return post_id,markup

def main():
    if os.getenv("NGO_PINNED_SUPPORT_APPROVED")!="YES_ADD_SUPPORT_ROW_3813":
        raise RuntimeError("Explicit pinned support approval missing")
    token=bot_token()
    receipt=json.loads(Path("launches/mini_app_pinned_shortcut_v05_2026-11-08.json").read_text("utf-8"))
    if receipt.get("status")!="verified_pinned_single_button" or receipt.get("message_id")!=POST_ID:
        raise RuntimeError("Original pinned receipt missing")
    status,_=github_api("GET","contents/"+RECEIPT+"?ref=main")
    if status==200:
        print("Pinned support receipt already exists; no repeat edit")
        return
    if status!=404:raise RuntimeError("Cannot read support receipt")
    post_id,markup=asyncio.run(inspect_and_edit(token))
    record={"status":"verified_pinned_two_buttons","operation":"editMessageReplyMarkup",
            "channel":CHANNEL,"message_id":post_id,"buttons":markup,
            "verified_at":datetime.now(timezone.utc).isoformat(),"run_id":os.getenv("GITHUB_RUN_ID")}
    status,_=github_api("PUT","contents/"+RECEIPT,{"branch":"main","message":"Verify existing pinned post support row",
        "content":b64encode(json.dumps(record,ensure_ascii=False,indent=2).encode()).decode()})
    if status!=201:raise RuntimeError("Pinned edit verified but receipt write failed")
    print("PINNED_TWO_BUTTONS_VERIFIED="+str(post_id)+";NO_NEW_POSTS=True;NO_PIN_CHANGES=True")

if __name__=="__main__":
    try:main()
    except RuntimeError as exc:raise SystemExit(str(exc)) from None
