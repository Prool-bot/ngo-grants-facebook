"""Check BotFather Enable Mini App option; NEVER click the enable action.

Starts from the previously verified official 'Configure Mini App' inline
button for existing editable @ngogratsAI_bot. Reads only submenu controls.
No configuration, URL submission, channel post or D1 data change.
"""
from __future__ import annotations
import asyncio,os,re,sys
from mini_app_botfather_nav_readonly import menu,is_mini,BOT,FATHER

def is_enable(label):
    return isinstance(label,str) and bool(re.search(
        r"\benable\s+(?:main\s+)?mini\s+app\b",label,re.I
    ))

async def main():
    if (os.getenv("GITHUB_ACTIONS")!="true" or
        os.getenv("GITHUB_REF")!="refs/heads/main" or
        os.getenv("NGO_BOTFATHER_ENABLE_PREVIEW_APPROVED")!="YES_INSPECT_ENABLE_ONLY"):
        raise RuntimeError("BotFather enable-menu preview gate missing")
    from telethon import TelegramClient
    from telethon.sessions import StringSession
    async with TelegramClient(
        StringSession(os.environ["TELEGRAM_SESSION"].strip()),
        int(os.environ["TELEGRAM_API_ID"]),
        os.environ["TELEGRAM_API_HASH"].strip(),
        receive_updates=False
    ) as client:
        if not await client.is_user_authorized():
            raise RuntimeError("Telegram owner session is unauthorized")
        target=await client.get_entity(BOT)
        father=await client.get_entity(FATHER)
        if (getattr(target,"bot",False) is not True or
            getattr(target,"bot_can_edit",False) is not True or
            str(getattr(target,"username","")).lower()!=BOT.lower() or
            getattr(father,"bot",False) is not True or
            str(getattr(father,"username","")).lower()!="botfather"):
            raise RuntimeError("Existing BotFather or owned bot identity changed")
        configure,button=await menu(client,father,is_mini)
        await button.click()
        prompt,enable=await menu(client,father,is_enable,configure.id)
        print("BOTFATHER_MAIN_APP_ENABLE_BUTTON_AVAILABLE=True")
        print("CONNECTED_SESSION_CAN_CONFIGURE_EXISTING_BOT=True")
        print("BOTFATHER_ENABLE_BUTTON_NOT_CLICKED=True")
        print("BOTFATHER_URLS_SENT=0;CONFIGURATION_CHANGED=0")
        return True
if __name__=="__main__":
    try:asyncio.run(main())
    except Exception as exc:
        print("BOTFATHER_ENABLE_MENU_PROBE_FAILED="+type(exc).__name__,file=sys.stderr)
        raise SystemExit(1)
