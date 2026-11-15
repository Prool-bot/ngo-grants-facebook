"""Read-only inspect real Main Mini App Telegram initData from existing session.

Only calls Telegram's requestMainWebView (no message/order/permission write) and
validates its returned initData signature locally. No URL, user ID, query ID,
hash, token or message body printed. This must never submit an order.
"""
from __future__ import annotations
import asyncio,os,urllib.parse
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.functions.messages import RequestMainWebViewRequest
from telethon.tl.types import InputPeerEmpty, InputUser
from mini_app_public_preflight import telegram

async def main():
    if (os.getenv("GITHUB_ACTIONS")!="true" or
        os.getenv("GITHUB_REF")!="refs/heads/main" or
        os.getenv("GITHUB_REPOSITORY")!="Prool-bot/ngo-grants-facebook"):
        raise RuntimeError("Read-only trusted session diagnostic only")
    mebot=telegram("getMe",token=os.environ["NGO_GRANTS_AI_BOT_TOKEN"])
    if mebot.get("username")!="ngogratsAI_bot" or mebot.get("has_main_web_app") is not True:
        raise RuntimeError("Main BotFather registration mismatch")
    async with TelegramClient(StringSession(os.environ["TELEGRAM_SESSION"]),
        int(os.environ["TELEGRAM_API_ID"]),os.environ["TELEGRAM_API_HASH"],
        receive_updates=False) as client:
        if not await client.is_user_authorized():
            raise RuntimeError("Existing session not authorized")
        bot=await client.get_input_entity("@ngogratsAI_bot")
        inp=InputUser(bot.user_id,bot.access_hash)
        view=await client(RequestMainWebViewRequest(
            peer=InputPeerEmpty(),bot=inp,platform="desktop",start_param="ngo_grants"))
        split=urllib.parse.urlsplit(view.url)
        pairs=urllib.parse.parse_qs(split.fragment or split.query)
        data=(pairs.get("tgWebAppData") or [""])[0]
        if not data:
            raise RuntimeError("Telegram returned no signed Mini App initData")
        # Protect from accidental leaks: print counts/validation status only.
        from mini_app_verify_init_data_offline import verify
        check=verify(data,os.environ["NGO_GRANTS_AI_BOT_TOKEN"])
        if check is not True:raise RuntimeError("Actual Telegram WebApp HMAC mismatch")
        print("REAL_MAIN_MINI_APP_INIT_DATA_AVAILABLE=True")
        print("AUTHENTIC_TELEGRAM_WEBAPP_HMAC_VALID=True")
        print("NO_REAL_ORDER_OR_D1_WRITE=True")
        print("NO_IDENTIFIERS_LOGGED=True")
if __name__=="__main__":
    try:asyncio.run(main())
    except RuntimeError as e:raise SystemExit(str(e)) from None
