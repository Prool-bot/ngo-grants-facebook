"""Read-only membership diagnostic for existing authorized Telegram session.

Tests the *same bot* used by Mini App getChatMember with a real session account.
Prints only status category and response type, never identity, token or topics.
"""
from __future__ import annotations
import asyncio,os
from telethon import TelegramClient
from telethon.sessions import StringSession
from mini_app_public_preflight import telegram

async def main():
    if (os.getenv("GITHUB_ACTIONS")!="true" or
        os.getenv("GITHUB_REF")!="refs/heads/main" or
        os.getenv("GITHUB_REPOSITORY")!="Prool-bot/ngo-grants-facebook"):
        raise RuntimeError("Trusted read-only diagnostic only")
    token=os.getenv("NGO_GRANTS_AI_BOT_TOKEN","")
    identity=telegram("getMe",token=token)
    if identity.get("username")!="ngogratsAI_bot" or identity.get("has_main_web_app") is not True:
        raise RuntimeError("Bot registration mismatch")
    async with TelegramClient(
        StringSession(os.environ["TELEGRAM_SESSION"].strip()),
        int(os.environ["TELEGRAM_API_ID"]),os.environ["TELEGRAM_API_HASH"].strip(),
        receive_updates=False
    ) as client:
        if not await client.is_user_authorized():
            raise RuntimeError("Authorized test session absent")
        me=await client.get_me()
        try:
            member=telegram("getChatMember",{"chat_id":"@ngo_grants","user_id":me.id},token=token)
        except Exception:
            print("TELEGRAM_CHANNEL_SUBSCRIBER_LOOKUP_STATUS=UPSTREAM_ERROR")
            raise RuntimeError("Bot cannot verify existing authorized member") from None
        state=str(member.get("status") or "missing")
        valid={"creator","administrator","member","restricted","left","kicked"}
        if state not in valid:raise RuntimeError("Unexpected Telegram membership state")
        print("TELEGRAM_CHANNEL_SUBSCRIBER_LOOKUP_STATUS="+state.upper())
        print("TELEGRAM_CHANNEL_SUBSCRIBER_LOOKUP_VALID="+str(state in ("creator","administrator","member") or (state=="restricted" and member.get("is_member") is True)))
        print("MEMBERSHIP_CHECK_PRIVATE_IDS_NOT_LOGGED=True")
if __name__=="__main__":
    try:asyncio.run(main())
    except RuntimeError as e:raise SystemExit(str(e)) from None
