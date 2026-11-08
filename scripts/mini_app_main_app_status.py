"""Read-only official Telegram getMe check for BotFather Main Mini App.

Uses existing bot token, never prints token or owner/user data.
"""
from __future__ import annotations
import os
from mini_app_public_preflight import telegram

def main():
    token=os.getenv("NGO_GRANTS_AI_BOT_TOKEN","").strip()
    info=telegram("getMe",token=token)
    if info.get("username")!="ngogratsAI_bot" or info.get("is_bot") is not True:
        raise RuntimeError("Unexpected bot identity; no Mini App activation")
    has_main=info.get("has_main_web_app") is True
    print("EXISTING_TELEGRAM_BOT_VERIFIED=True")
    print("BOTFATHER_MAIN_MINI_APP_CONFIGURED="+str(has_main))
    print("DIRECT_CHANNEL_LINK_SAFE_TO_PUBLISH="+str(has_main and os.getenv("MINI_APP_ORDER_API_READY")=="true"))
    return has_main

if __name__=="__main__":
    try:main()
    except RuntimeError as exc:raise SystemExit(str(exc)) from None
