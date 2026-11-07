"""One-time PUBLIC Telegram Mini App invitation through the EXISTING NGO Grants AI bot.

This release has two intentional Telegram writes:
 (1) append /assistant to the default command list without removing anything;
 (2) send one announcement to @ngo_grants.

A GitHub contents API *pre-send attempt lock* makes reruns fail closed. If a
network request has an unknown outcome, do not retry automatically. No test
catalogs, Telegram user DMs, D1 changes or new bots are created.
"""
from __future__ import annotations

import base64
from datetime import datetime, timezone
import json
import os
import re
import urllib.error
import urllib.request

from mini_app_public_preflight import CHANNEL, inspect, telegram

REPO="Prool-bot/ngo-grants-facebook"
RECORD_PATH="launches/mini_app_public_2026-11-07.json"
BOT_DESC="Грантовий помічник із роботом"
MAX_BYTES=60000

POST_TEMPLATE="""<b>🤖 NGO Grants AI: ВІДКРИВАЄМО ПУБЛІЧНЕ ТЕСТУВАННЯ ГРАНТОВОГО ПОМІЧНИКА</b>

У нашому Telegram-боті з’явився новий інтерактивний помічник із дружнім анімованим роботом. Він допомагає покроково сформувати запит на тематичну добірку грантів і можливостей фінансування.

<b>🔎 ЯК СПРОБУВАТИ</b>
1️⃣ Відкрийте бота @{username}.
2️⃣ Надішліть команду <code>/assistant</code>.
3️⃣ Натисніть «🤖 Відкрити грантового помічника».
4️⃣ Заповніть анкету: тип заявника, напрями діяльності, географія, роль і форма фінансування.
5️⃣ Перевірте підсумок і, якщо хочете замовити добірку, натисніть «Замовити каталог».

<b>📄 ЩО ДАЛІ?</b>
Запит потрапить до чинної системи NGO Grants AI. Вона перевіряє можливості, опубліковані в архіві @ngo_grants, і за наявності відповідних оголошень формує тематичний PDF-каталог. Результати публікуються в каналі. Діють правила підписки та обмеження кількості запитів.

<b>🧪 ДОПОМОЖІТЬ ПЕРЕВІРИТИ</b>
Спробуйте різні реальні теми. Якщо знайшли незрозумілу кнопку, збій, непотрібний або відсутній результат — залиште коментар під цим дописом: на якому кроці й що сталося. Не публікуйте особисті дані.

Це <b>публічне тестування нового інтерфейсу в уже наявному боті</b>, а не запуск окремого нового бота. Ваші відгуки допоможуть удосконалити пошук. 🇺🇦"""


def announcement_text(username: str)->str:
    if re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{4,31}",username) is None:
        raise ValueError("Bot link not verified")
    text=POST_TEMPLATE.format(username=username)
    if len(text)>3900:
        raise ValueError("Post too long for Telegram")
    return text


def bot_write(method: str, payload:dict,*,token:str):
    if method not in ("setMyCommands","sendMessage"):
        raise ValueError("Telegram write method not allowed")
    request=urllib.request.Request(
        f"https://api.telegram.org/bot{token}/{method}",
        method="POST",
        headers={"Content-Type":"application/json","User-Agent":"NGOGrantsMiniAppPublicLaunch/1.0"},
        data=json.dumps(payload,ensure_ascii=False).encode("utf-8")
    )
    try:
        with urllib.request.urlopen(request,timeout=25) as resp:
            decoded=json.loads(resp.read(MAX_BYTES).decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Telegram {method} HTTP {exc.code} (no automatic retry)") from None
    except (OSError,urllib.error.URLError,TimeoutError) as exc:
        raise RuntimeError(f"Telegram {method} outcome unknown: {type(exc).__name__}; do not retry without checking channel") from None
    if decoded.get("ok") is not True:
        raise RuntimeError(f"Telegram {method} API refused (no automatic retry)")
    return decoded.get("result")


def github_api(method:str,path:str,payload:dict|None=None):
    token=os.getenv("GITHUB_TOKEN","").strip()
    if not token:
        raise RuntimeError("GitHub release lock token missing")
    url=f"https://api.github.com/repos/{REPO}/{path}"
    data=None if payload is None else json.dumps(payload).encode("utf-8")
    headers={"Authorization":"Bearer "+token,"Accept":"application/vnd.github+json",
             "X-GitHub-Api-Version":"2022-11-28",
             "Content-Type":"application/json",
             "User-Agent":"NGOGrantsMiniAppLaunch/1.0"}
    req=urllib.request.Request(url,method=method,data=data,headers=headers)
    try:
        with urllib.request.urlopen(req,timeout=30) as resp:
            content=resp.read(MAX_BYTES)
            return resp.status,json.loads(content) if content else {}
    except urllib.error.HTTPError as exc:
        if method=="GET" and exc.code==404:
            return 404,{}
        if method=="PUT" and exc.code in (409,422):
            raise RuntimeError("GitHub launch lock already exists or branch changed; no post sent") from None
        raise RuntimeError(f"GitHub release lock HTTP {exc.code}; no post sent") from None
    except (urllib.error.URLError,OSError,TimeoutError) as exc:
        raise RuntimeError(f"GitHub release lock outcome unknown: {type(exc).__name__}") from None


def validate_environment():
    if os.getenv("GITHUB_ACTIONS")!="true" or os.getenv("GITHUB_REF")!="refs/heads/main":
        raise RuntimeError("One-time public launch requires main GitHub Actions")
    if os.getenv("NGO_MINI_APP_PUBLIC_LAUNCH_APPROVED")!="YES_EXISTING_BOT_PUBLIC_TEST":
        raise RuntimeError("Explicit launch authorization missing")
    if os.getenv("GITHUB_REPOSITORY")!=REPO:
        raise RuntimeError("Wrong GitHub repo")


def lock_attempt(username:str):
    status,_=github_api("GET",f"contents/{RECORD_PATH}?ref=main")
    if status!=404:
        raise RuntimeError("PUBLIC_ANNOUNCEMENT_ALREADY_ATTEMPTED — inspect recorded channel post; no repost")
    rec={"status":"attempted","kind":"existing_bot_mini_app_public_test",
         "channel":CHANNEL,"bot":"@"+username,
         "created_at":datetime.now(timezone.utc).isoformat(),
         "github_run":os.getenv("GITHUB_RUN_ID","")}
    status,response=github_api("PUT",f"contents/{RECORD_PATH}",{
      "message":"Reserve one-time NGO Grants AI Mini App announcement before Telegram send",
      "branch":"main",
      "content":base64.b64encode(json.dumps(rec,ensure_ascii=False,indent=2).encode("utf-8")).decode("ascii")
    })
    sha=(response.get("content") or {}).get("sha")
    if status!=201 or not sha:
        raise RuntimeError("Public launch lock not confirmed; no Telegram post sent")
    print("PUBLIC_ANNOUNCEMENT_ONE_SHOT_LOCKED")
    return sha,rec


def mark_published(sha,rec,message_id):
    if not isinstance(message_id,int) or message_id<=0:
        raise RuntimeError("Invalid Telegram message id; release outcome unknown")
    rec.update({"status":"posted","message_id":message_id,
        "url":f"https://t.me/ngo_grants/{message_id}",
        "published_at":datetime.now(timezone.utc).isoformat()})
    status,_=github_api("PUT",f"contents/{RECORD_PATH}",{
        "message":"Confirm NGO Grants Mini App public invitation Telegram message id",
        "branch":"main","sha":sha,
        "content":base64.b64encode(json.dumps(rec,ensure_ascii=False,indent=2).encode("utf-8")).decode("ascii")
    })
    if status!=200:
        raise RuntimeError("Telegram was sent but receipt update failed — do not repost")
    return rec["url"]


def main():
    validate_environment()
    token=os.getenv("NGO_GRANTS_AI_BOT_TOKEN","").strip()
    if not token:
        raise RuntimeError("Existing bot token missing")
    identity=telegram("getMe",token=token)
    channel=telegram("getChat",{"chat_id":CHANNEL},token=token)
    member=telegram("getChatMember",{"chat_id":CHANNEL,"user_id":identity["id"]},token=token)
    commands=telegram("getMyCommands",token=token)
    details=inspect(identity,channel,member,commands)
    if not details["channel_can_post"]:
        raise RuntimeError("Existing bot cannot publish to @ngo_grants — stop")
    # Read-only production Mini App smoke has already passed. Do not create a bot.
    username=details["bot_username"]
    current=[{"command":x["command"],"description":x["description"]} for x in commands]
    if not details["assistant_already_in_commands"]:
        if len(current)>=100:raise RuntimeError("Telegram command slots exhausted")
        updated=current+[{"command":"assistant","description":BOT_DESC}]
        if bot_write("setMyCommands",{"commands":updated},token=token) is not True:
            raise RuntimeError("Telegram refused assistant command installation")
        confirmed=telegram("getMyCommands",token=token)
        if not all(cmd in confirmed for cmd in updated):
            raise RuntimeError("Telegram assistant command verification failed")
        print("BOT_ASSISTANT_COMMAND_ADDED_PRESERVING_OTHERS=True")
    else:
        print("BOT_ASSISTANT_COMMAND_ALREADY_VISIBLE=True")
    sha,rec=lock_attempt(username)
    # A single sendMessage. NO automatic retry on any exception/unknown outcome.
    data={"chat_id":CHANNEL,"text":announcement_text(username),
          "parse_mode":"HTML","disable_web_page_preview":True,
          "reply_markup":{"inline_keyboard":[[{
             "text":"🤖 Спробувати грантового помічника",
             "url":"https://t.me/"+username
          }]]}}
    posted=bot_write("sendMessage",data,token=token)
    message_id=posted.get("message_id") if isinstance(posted,dict) else None
    if(not isinstance(posted,dict) or
       (posted.get("chat") or {}).get("username")!="ngo_grants" or
       not isinstance(message_id,int) or message_id<=0):
        raise RuntimeError("Telegram send outcome not verified; do not repost")
    print("ANNOUNCEMENT_SENT="+f"https://t.me/ngo_grants/{message_id}")
    link=mark_published(sha,rec,message_id)
    print("ONE_TIME_ANNOUNCEMENT_CONFIRMED="+link)
    print("EXISTING_BOT_USERNAME=@"+username)
    print("NO_NEW_TELEGRAM_BOT_CREATED")
    print("NO_CATALOG_ORDERS_CREATED")
    return link


if __name__=="__main__":
    try:main()
    except RuntimeError as exc:raise SystemExit(str(exc)) from None
