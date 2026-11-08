"""One-time SAFE BotFather menu probe for existing NGO Grants AI bot.

Sends ONLY '/mybots' to the OFFICIAL @BotFather from the already-connected
owner session. Does not click any settings, configure URL, create bots,
change bot metadata, publish in the channel, or touch D1.
Logs only booleans and counts, never user/bot list or response text.
"""
from __future__ import annotations
import asyncio
import os
import sys

TARGET="ngogratsAI_bot"
BOTFATHER="BotFather"

def is_target_button(label:str)->bool:
    if not isinstance(label,str):return False
    lower=label.lower().strip()
    return TARGET.lower() in lower or "ngo grants ai" in lower

async def main():
    if (os.getenv("GITHUB_ACTIONS")!="true" or
        os.getenv("GITHUB_REF")!="refs/heads/main" or
        os.getenv("NGO_BOTFATHER_MENU_PROBE_APPROVED")!="YES_MYBOTS_READ_ONLY_MENU"):
        raise RuntimeError("Explicit one-time BotFather menu probe gate missing")
    from telethon import TelegramClient
    from telethon.sessions import StringSession
    required=("TELEGRAM_API_ID","TELEGRAM_API_HASH","TELEGRAM_SESSION")
    if any(not os.getenv(name,"").strip() for name in required):
        raise RuntimeError("Owner Telegram session is not configured")
    async with TelegramClient(
        StringSession(os.environ["TELEGRAM_SESSION"].strip()),
        int(os.environ["TELEGRAM_API_ID"]),
        os.environ["TELEGRAM_API_HASH"].strip(),
        receive_updates=False
    ) as client:
        if not await client.is_user_authorized():
            raise RuntimeError("Connected Telegram session is not authorized")
        target=await client.get_entity(TARGET)
        if (getattr(target,"bot",False) is not True or
            getattr(target,"bot_can_edit",False) is not True or
            str(getattr(target,"username","")).lower()!=TARGET.lower()):
            raise RuntimeError("Session is not authorized to edit exact existing bot")
        father=await client.get_entity(BOTFATHER)
        if (getattr(father,"bot",False) is not True or
            str(getattr(father,"username","")).lower()!="botfather"):
            raise RuntimeError("Official @BotFather identity mismatch")
        sent=await client.send_message(father,"/mybots")
        menu=None
        for attempt in range(12):
            await asyncio.sleep(.75)
            messages=await client.get_messages(father,limit=5)
            for msg in messages:
                if not msg.out and msg.id>sent.id and msg.buttons:
                    menu=msg
                    break
            if menu:break
        if menu is None:
            print("BOTFATHER_MYBOTS_INLINE_MENU_AVAILABLE=False")
            raise RuntimeError("BotFather did not return an inline owned-bots menu")
        buttons=[btn for row in (menu.buttons or []) for btn in row]
        labels=[getattr(btn,"text","") for btn in buttons]
        matching=[label for label in labels if is_target_button(label)]
        print("BOTFATHER_MYBOTS_INLINE_MENU_AVAILABLE=True")
        print("CONNECTED_SESSION_CAN_EDIT_EXISTING_BOT=True")
        print("BOTFATHER_TARGET_BOT_IN_MENU="+str(len(matching)==1))
        print("BOTFATHER_MYBOTS_BUTTON_COUNT="+str(len(buttons)))
        print("BOTFATHER_MESSAGES_SENT=1")
        print("BOTFATHER_SETTINGS_CHANGED=0")
        if len(matching)!=1:
            raise RuntimeError("Target existing bot not uniquely selectable in BotFather menu")
        return True

if __name__=="__main__":
    try:asyncio.run(main())
    except Exception as exc:
        print("BOTFATHER_MENU_PROBE_STATUS="+type(exc).__name__,file=sys.stderr)
        raise SystemExit(1)
