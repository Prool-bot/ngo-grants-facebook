"""Verify Main Mini App opens in @ngo_grants context without a bot chat.

Uses official Telegram MTProto messages.requestMainWebView in the already
authorized owner account. The returned signed initData is used ONLY in one
POST with deliberately invalid (empty) facets: success is HTTP 400 after
auth, never a real catalog order. No Telegram messages or D1 writes.

Never print/store raw webView URL, initData, user ID, bot token, session,
contact information, or BotFather conversation text.
"""
from __future__ import annotations
import asyncio
import json
import os
import sys
from urllib.parse import urlsplit,parse_qs
import urllib.request
import urllib.error

BOT="ngogratsAI_bot"
CHANNEL="ngo_grants"
EXPECTED_HOST="ngo-grants-instant-bot.oleh-protasoff.workers.dev"
EXPECTED_PATH="/mini-app/direct"
ORDER_PATH="/api/mini-app/order"

def validate_webview_link(raw:str)->str:
    if not isinstance(raw,str) or len(raw)>16000:
        raise RuntimeError("Unexpected Main Mini App view URL")
    url=urlsplit(raw)
    if url.scheme!="https" or url.hostname!=EXPECTED_HOST or url.path!=EXPECTED_PATH:
        raise RuntimeError("Main Mini App points at the wrong origin/path")
    params=parse_qs(url.query,keep_blank_values=True)
    if "tgWebAppData" not in params and url.fragment:
        params=parse_qs(url.fragment,keep_blank_values=True)
    signed=params.get("tgWebAppData",[])
    if len(signed)!=1 or not signed[0] or len(signed[0])>8192:
        raise RuntimeError("Main Mini App did not receive a single signed initData")
    initData=signed[0]
    fields=parse_qs(initData,keep_blank_values=True)
    if (len(fields.get("hash",[]))!=1 or len(fields.get("auth_date",[]))!=1
        or len(fields.get("user",[]))!=1):
        raise RuntimeError("Main Mini App initData signature fields missing")
    return initData

def reject_invalid_facets_with_valid_session(signed:str):
    endpoint="https://"+EXPECTED_HOST+ORDER_PATH
    # Empty facets MUST be rejected *after* the server validates Telegram
    # initData, but BEFORE membership checks, DB writes or daily limits.
    envelope={
      "initData":signed,"facets":{},
      "idempotencyKey":"123e4567-e89b-42d3-a456-426614174000"
    }
    req=urllib.request.Request(endpoint,method="POST",
      data=json.dumps(envelope).encode("utf-8"),
      headers={
        "Content-Type":"application/json",
        "Origin":"https://"+EXPECTED_HOST,
        "User-Agent":"NGOGrantsMainMiniAppAuthGateProbe/1.0"
      })
    try:
        with urllib.request.urlopen(req,timeout=20) as resp:
            status=resp.status
            raw=resp.read(4096)
    except urllib.error.HTTPError as exc:
        status=exc.code
        raw=exc.read(4096)
    except (urllib.error.URLError,TimeoutError,OSError) as exc:
        raise RuntimeError("Network failed for Main Mini App signed session check") from None
    if status!=400:
        raise RuntimeError("Signed Main Mini App auth gate not reached or invalid facets accepted")
    try:body=json.loads(raw)
    except ValueError:raise RuntimeError("Non-JSON auth gate response") from None
    if body.get("ok") is not False:
        raise RuntimeError("Invalid form was falsely acknowledged")
    return True

async def main():
    if (os.getenv("GITHUB_ACTIONS")!="true" or
        os.getenv("GITHUB_REF")!="refs/heads/main" or
        os.getenv("NGO_MAIN_WEBVIEW_SAFE_PROBE_APPROVED")!="YES_CHANNEL_WEBVIEW_NO_ORDER"):
        raise RuntimeError("Channel Main Mini App no-order probe gate missing")
    from telethon import TelegramClient,utils
    from telethon.sessions import StringSession
    from telethon.tl.functions.messages import RequestMainWebViewRequest
    async with TelegramClient(
       StringSession(os.environ["TELEGRAM_SESSION"].strip()),
       int(os.environ["TELEGRAM_API_ID"]),
       os.environ["TELEGRAM_API_HASH"].strip(),
       receive_updates=False
    ) as client:
        if not await client.is_user_authorized():
            raise RuntimeError("Owner Telegram session no longer authorized")
        bot=await client.get_entity(BOT)
        if (getattr(bot,"bot",False) is not True or
            str(getattr(bot,"username","")).lower()!=BOT.lower() or
            getattr(bot,"bot_has_main_app",False) is not True):
            raise RuntimeError("Existing Telegram bot Main Mini App not registered")
        channel=await client.get_input_entity(CHANNEL)
        result=await client(RequestMainWebViewRequest(
          peer=channel,bot=utils.get_input_user(bot),platform="android"
        ))
        signed=validate_webview_link(getattr(result,"url",None))
    print("TELEGRAM_MAIN_APP_CHANNEL_WEBVIEW_REQUEST_SUCCESS=True")
    print("MAIN_APP_URL_AND_SIGNED_INITDATA_PRESENT=True")
    reject_invalid_facets_with_valid_session(signed)
    print("SERVER_VALIDATED_REAL_TELEGRAM_INITDATA_REJECTED_INVALID_FORM_400=True")
    print("BOT_CHAT_OPENED=0;TELEGRAM_MESSAGES_SENT=0;D1_WRITES=0;REAL_ORDERS=0")

if __name__=="__main__":
    try:asyncio.run(main())
    except Exception as exc:
        print("MAIN_APP_CHANNEL_NO_ORDER_PROBE_FAILED="+type(exc).__name__,file=sys.stderr)
        raise SystemExit(1)
