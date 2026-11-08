"""One-shot anonymous Telegram pilot feedback poll in the existing @ngo_grants channel.

Only channel poll and edit of existing announcement #3813. NO new bot,
no catalog order, no personal reply data, no D1 changes. An atomic GitHub
receipt is written before sending, to prevent duplicate polls on retries.
"""
from __future__ import annotations

from base64 import b64encode
from datetime import datetime,timezone
import json
import os
import urllib.error
import urllib.request

from mini_app_public_launch import CHANNEL,github_api
from mini_app_public_preflight import telegram,inspect
from mini_app_start_v03_edit_post import updated_post

BOT="@ngogratsAI_bot"
LOCK="launches/mini_app_pilot_poll_2026-11-08.json"
POST_ID=3813
QUESTION="🤖 Як працює новий грантовий помічник NGO Grants AI?"
OPTIONS=[
  "✅ Анкета працює, проблем немає",
  "📄 Замовив(-ла), отримав(-ла) каталог",
  "⏳ Замовив(-ла), очікую результат",
  "⚠️ Була помилка під час оформлення",
  "🔎 Каталог не знайшов відповідних грантів",
  "👀 Лише переглянув(-ла) помічника"
]
OLD_FRAGMENT=("Якщо знайшли незрозумілу кнопку, збій, непотрібний або відсутній "
 "результат — залиште коментар під цим дописом: на якому кроці й що сталося. "
 "Не публікуйте особисті дані.")

def markup_text(poll_id:int,bot:str)->str:
    if not isinstance(poll_id,int) or poll_id<=0 or bot!="ngogratsAI_bot":
        raise ValueError("Unexpected poll or bot")
    current=updated_post(bot)
    if current.count(OLD_FRAGMENT)!=1:
        raise ValueError("Announcement changed: refuse edit")
    replacement=(
     "Коментарі до допису поки недоступні. "
     'Оцініть роботу помічника в <a href="https://t.me/ngo_grants/'
     +str(poll_id)+'">анонімному опитуванні</a>. '
     "Не публікуйте особистих даних."
    )
    out=current.replace(OLD_FRAGMENT,replacement)
    if len(out)>3900:raise ValueError("Telegram announcement too long")
    return out

def send(method,payload,token):
    if method not in ("sendPoll","editMessageText"):
        raise ValueError("Only one pilot poll and one existing-post edit allowed")
    req=urllib.request.Request(
        f"https://api.telegram.org/bot{token}/{method}",
        data=json.dumps(payload,ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type":"application/json",
                 "User-Agent":"NGOGrantsMiniAppPilotFeedback/1.0"},
        method="POST")
    try:
        with urllib.request.urlopen(req,timeout=25) as response:
            result=json.loads(response.read(80000).decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Telegram {method} HTTP {exc.code}; do not auto-retry") from None
    except (urllib.error.URLError,OSError,TimeoutError) as exc:
        raise RuntimeError(f"Telegram {method} outcome unknown; no automatic retry") from None
    if result.get("ok") is not True:
        raise RuntimeError(f"Telegram {method} refused; do not retry")
    return result.get("result") or {}

def update_record(sha,record,message):
    body={
       "branch":"main","sha":sha,
       "message":message,
       "content":b64encode(json.dumps(record,ensure_ascii=False,indent=2).encode()).decode()
    }
    status,resp=github_api("PUT",f"contents/{LOCK}",body)
    if status!=200 or not (resp.get("content") or {}).get("sha"):
        raise RuntimeError("Receipt update failed; poll may exist; never retry sending")
    return resp["content"]["sha"]

def main():
    if (os.getenv("GITHUB_ACTIONS")!="true" or
        os.getenv("GITHUB_REF")!="refs/heads/main" or
        os.getenv("GITHUB_REPOSITORY")!="Prool-bot/ngo-grants-facebook" or
        os.getenv("NGO_MINI_APP_PILOT_POLL_APPROVED")!="YES_ANONYMOUS_POLL_ONCE"):
        raise RuntimeError("Explicit pilot poll release gate required")
    token=os.getenv("NGO_GRANTS_AI_BOT_TOKEN","").strip()
    me=telegram("getMe",token=token)
    ch=telegram("getChat",{"chat_id":CHANNEL},token=token)
    member=telegram("getChatMember",{"chat_id":CHANNEL,"user_id":me["id"]},token=token)
    commands=telegram("getMyCommands",token=token)
    checked=inspect(me,ch,member,commands)
    if checked["bot_username"]!="ngogratsAI_bot" or not checked["channel_can_post"]:
        raise RuntimeError("Existing bot or channel permissions mismatch")
    status,_=github_api("GET",f"contents/{LOCK}?ref=main")
    if status!=404:
        print("PILOT_POLL_ALREADY_ATTEMPTED; no duplicate sent")
        return
    attempt={"status":"attempted","kind":"anonymous_public_miniapp_feedback",
             "channel":CHANNEL,"bot":BOT,
             "created_at":datetime.now(timezone.utc).isoformat(),
             "run_id":os.getenv("GITHUB_RUN_ID","")}
    status,result=github_api("PUT",f"contents/{LOCK}",{
       "branch":"main","message":"Reserve one-time anonymous Mini App pilot poll",
       "content":b64encode(json.dumps(attempt,ensure_ascii=False,indent=2).encode()).decode()
    })
    sha=(result.get("content") or {}).get("sha")
    if status!=201 or not sha:
        raise RuntimeError("Atomic poll attempt lock was not confirmed")
    print("PILOT_POLL_ONE_SHOT_LOCKED")
    published=send("sendPoll",{
       "chat_id":CHANNEL,"question":QUESTION,
       "options":OPTIONS,"type":"regular","is_anonymous":True,
       "allows_multiple_answers":False,"disable_notification":True
    },token)
    poll_id=published.get("message_id") if isinstance(published,dict) else None
    if (not isinstance(poll_id,int) or poll_id<=0 or
        (published.get("chat") or {}).get("username")!="ngo_grants"):
        raise RuntimeError("Poll publication uncertain; no retry")
    attempt.update({"status":"poll_posted","message_id":poll_id,
       "url":f"https://t.me/ngo_grants/{poll_id}"})
    sha=update_record(sha,attempt,"Record posted anonymous Mini App feedback poll")
    print("PILOT_POLL_LINK="+attempt["url"])
    # Replace impossible comments CTA inside the already published post;
    # do not send another announcement.
    updated=send("editMessageText",{
       "chat_id":CHANNEL,"message_id":POST_ID,
       "text":markup_text(poll_id,checked["bot_username"]),
       "parse_mode":"HTML","disable_web_page_preview":True,
       "reply_markup":{"inline_keyboard":[[{
         "text":"🤖 Спробувати грантового помічника",
         "url":"https://t.me/ngogratsAI_bot"
       }]]}
    },token)
    if (not isinstance(updated,dict) or updated.get("message_id")!=POST_ID or
        (updated.get("chat") or {}).get("username")!="ngo_grants"):
        raise RuntimeError("Existing announcement edit uncertain; do not retry automatically")
    attempt.update({"status":"poll_posted_announcement_updated",
       "announcement_updated_at":datetime.now(timezone.utc).isoformat()})
    update_record(sha,attempt,"Confirm link to anonymous pilot poll in existing post")
    print("ORIGINAL_POST_UPDATED=https://t.me/ngo_grants/3813")
    print("NEW_ANNOUNCEMENT_POSTS=0")
    print("NO_CATALOG_ORDERS_CREATED=True")

if __name__=="__main__":
    try:main()
    except RuntimeError as error:raise SystemExit(str(error)) from None
