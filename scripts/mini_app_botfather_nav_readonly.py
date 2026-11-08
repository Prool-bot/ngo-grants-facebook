"""Read-only BotFather navigation up to 'Configure Mini App' menu.

Clicks only owner-verified existing @ngogratsAI_bot and 'Bot Settings'.
No configuration is changed, no URL sent, no new bot created.
No private conversation text, usernames besides known target, callback data,
Telegram account IDs, or other bot names are logged.
"""
from __future__ import annotations
import asyncio,os,re,sys

BOT="ngogratsAI_bot"
FATHER="BotFather"

def buttons_of(message):
    return [b for row in (getattr(message,"buttons",None) or []) for b in row]

def matching_buttons(messages,matcher,min_id=0):
    found=[]
    for msg in messages:
        if getattr(msg,"out",False) or (getattr(msg,"id",0) or 0)<min_id:
            continue
        for button in buttons_of(msg):
            label=getattr(button,"text","")
            if matcher(label):found.append((msg,button))
    return found

def is_target(label):
    return isinstance(label,str) and (
       BOT.lower() in label.lower() or "ngo grants ai" in label.lower()
    )
def is_settings(label):
    return isinstance(label,str) and bool(re.search(r"bot\s+settings",label,re.I))
def is_mini(label):
    return isinstance(label,str) and bool(re.search(r"configure\s+mini\s+app",label,re.I))

async def menu(client,father,matcher,min_id=0):
    for attempt in range(15):
        messages=await client.get_messages(father,limit=8)
        matches=matching_buttons(messages,matcher,min_id)
        if len(matches)==1:return matches[0]
        if len(matches)>1:raise RuntimeError("Ambiguous BotFather menu target")
        await asyncio.sleep(.65)
    raise RuntimeError("Expected BotFather submenu unavailable")

async def main():
    if (os.getenv("GITHUB_ACTIONS")!="true" or
        os.getenv("GITHUB_REF")!="refs/heads/main" or
        os.getenv("NGO_BOTFATHER_NAV_PREVIEW_APPROVED")!="YES_NAVIGATE_NO_SETTINGS"):
        raise RuntimeError("Explicit BotFather navigation-only gate missing")
    from telethon import TelegramClient
    from telethon.sessions import StringSession
    if any(not os.environ.get(x) for x in
           ("TELEGRAM_API_ID","TELEGRAM_API_HASH","TELEGRAM_SESSION")):
        raise RuntimeError("Owner session not configured")
    async with TelegramClient(
        StringSession(os.environ["TELEGRAM_SESSION"].strip()),
        int(os.environ["TELEGRAM_API_ID"]),
        os.environ["TELEGRAM_API_HASH"].strip(),
        receive_updates=False
    ) as client:
        if not await client.is_user_authorized():
            raise RuntimeError("Telegram owner session authorization absent")
        target=await client.get_entity(BOT)
        if (getattr(target,"bot",False) is not True or
            getattr(target,"bot_can_edit",False) is not True or
            getattr(target,"username","").lower()!=BOT.lower()):
            raise RuntimeError("Target bot not editable by connected account")
        father=await client.get_entity(FATHER)
        if (getattr(father,"bot",False) is not True or
            getattr(father,"username","").lower()!="botfather"):
            raise RuntimeError("Not official BotFather")
        existing,bot_button=await menu(client,father,is_target)
        anchor=existing.id
        await bot_button.click()
        settings,settings_button=await menu(client,father,is_settings,anchor)
        await settings_button.click()
        mini,mini_button=await menu(client,father,is_mini,anchor)
        print("BOTFATHER_EXACT_OWNED_BOT_SELECTED=True")
        print("BOTFATHER_BOT_SETTINGS_MENU_ACCESSIBLE=True")
        print("BOTFATHER_CONFIGURE_MINI_APP_MENU_ACCESSIBLE=True")
        print("MAIN_APP_CONFIGURATION_NOT_CHANGED=True")
        print("NEW_BOTS_CREATED=0;CHANNEL_POSTS_SENT=0")
        return True
if __name__=="__main__":
    try:asyncio.run(main())
    except Exception as exc:
        print("BOTFATHER_NAV_PREVIEW_UNAVAILABLE="+type(exc).__name__,file=sys.stderr)
        raise SystemExit(1)
