"""Read-only pinned NGO Grants AI channel post audit, no account identifiers."""
from __future__ import annotations
import asyncio
import os
from mini_app_public_preflight import telegram, CHANNEL

POST=3813
EXPECTED="https://t.me/ngogratsAI_bot?startapp=ngo_grants"

async def main():
    token=os.environ.get("NGO_GRANTS_AI_BOT_TOKEN","").strip()
    bot=telegram("getMe",token=token)
    channel=telegram("getChat",{"chat_id":CHANNEL},token=token)
    right=telegram("getChatMember",{"chat_id":CHANNEL,"user_id":bot["id"]},token=token)
    if (bot.get("username")!="ngogratsAI_bot" or
        channel.get("type")!="channel" or channel.get("username")!="ngo_grants"):
        raise RuntimeError("Wrong bot/channel identity")
    pin=channel.get("pinned_message") or {}
    print("PIN_AUDIT_BOT_CHANNEL_STATUS="+str(right.get("status")))
    print("PIN_AUDIT_BOT_CAN_EDIT_MESSAGES="+str(right.get("can_edit_messages") is True))
    print("PIN_AUDIT_TOP_PIN="+str(pin.get("message_id") or "none"))
    from telethon import TelegramClient
    from telethon.sessions import StringSession
    from telethon.tl.types import ChannelParticipantCreator
    async with TelegramClient(
        StringSession(os.environ["TELEGRAM_SESSION"].strip()),
        int(os.environ["TELEGRAM_API_ID"]),
        os.environ["TELEGRAM_API_HASH"].strip(),receive_updates=False
    ) as client:
        if not await client.is_user_authorized():
            raise RuntimeError("Telegram session not authorized")
        message=await client.get_messages("ngo_grants",ids=POST)
        if not message or message.id!=POST:
            raise RuntimeError("Pilot message not found")
        buttons=getattr(getattr(message,"reply_markup",None),"rows",[]) or []
        urls=[getattr(b,"url",None) for row in buttons for b in row.buttons]
        print("PIN_AUDIT_PILOT_POST_PRESENT=True")
        print("PIN_AUDIT_PILOT_POST_IS_PINNED="+str(message.pinned is True))
        print("PIN_AUDIT_PILOT_POST_BUTTON_COUNT="+str(len(urls)))
        print("PIN_AUDIT_PILOT_POST_MAIN_LINK="+str(EXPECTED in urls))
        print("PIN_AUDIT_PILOT_POST_TEXT_LENGTH="+str(len(message.text or "")))
        try:
            participant=await client.get_permissions("ngo_grants","me")
            owner_can_pin=(getattr(participant,"is_creator",False) is True or
                          getattr(participant,"edit_messages",False) is True)
            print("PIN_AUDIT_CONNECTED_SESSION_CAN_PIN="+str(owner_can_pin))
        except Exception:
            print("PIN_AUDIT_CONNECTED_SESSION_CAN_PIN=unavailable")
    print("PIN_AUDIT_READ_ONLY_COMPLETE=True")
if __name__=="__main__":
    asyncio.run(main())
