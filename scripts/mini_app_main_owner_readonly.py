"""Read-only Main Mini App ownership and registration preflight.

Uses the existing read-only Telegram user session only to check whether this
session can edit @ngogratsAI_bot, never to message @BotFather or users.
No Telegram account IDs, names, chats, session data or bot secrets are logged.
"""
from __future__ import annotations
import asyncio
import os
import sys

BOT="ngogratsAI_bot"

def assessment(bot)->dict:
    if getattr(bot,"bot",False) is not True:
        raise RuntimeError("Target Telegram entity is not a bot")
    if str(getattr(bot,"username","")).lower()!=BOT.lower():
        raise RuntimeError("Unexpected bot identity in Telegram session")
    return {
        "session_can_edit_this_bot":getattr(bot,"bot_can_edit",False) is True,
        "main_mini_app_registered":getattr(bot,"bot_has_main_app",False) is True,
    }

async def check():
    from telethon import TelegramClient
    from telethon.sessions import StringSession
    api_id=os.environ.get("TELEGRAM_API_ID","").strip()
    api_hash=os.environ.get("TELEGRAM_API_HASH","").strip()
    session=os.environ.get("TELEGRAM_SESSION","").strip()
    if not api_id.isdigit() or not api_hash or not session:
        raise RuntimeError("Read-only Telegram session credentials missing")
    async with TelegramClient(
        StringSession(session),int(api_id),api_hash,receive_updates=False
    ) as client:
        if not await client.is_user_authorized():
            raise RuntimeError("Existing Telegram session not authorized")
        bot=await client.get_entity(BOT)
        result=assessment(bot)
    print("TELEGRAM_BOT_SESSION_OWNER_PREFLIGHT_COMPLETE")
    print("CURRENT_CONNECTED_SESSION_CAN_EDIT_BOT="+str(
        result["session_can_edit_this_bot"]))
    print("MAIN_MINI_APP_REGISTERED_IN_MTPROTO="+str(
        result["main_mini_app_registered"]))
    print("BOTFATHER_MESSAGES_SENT=0")
    return result

if __name__=="__main__":
    try:asyncio.run(check())
    except Exception as exc:
        # Never print raw Telethon errors: they may include account or chat IDs.
        print("MAIN_APP_OWNER_READ_ONLY_CHECK_UNAVAILABLE="+type(exc).__name__,file=sys.stderr)
        raise SystemExit(1)
