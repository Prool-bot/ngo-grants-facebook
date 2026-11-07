"""Read-only launch preflight for existing NGO Grants AI Telegram bot.

Never creates a new Telegram bot, never posts, and never changes commands.
Shows only current bot username, own channel posting right, command names
and mini-app version. Bot token stays exclusively in GitHub Actions secrets.
"""
from __future__ import annotations
import json
import os
import re
import urllib.error
import urllib.request

CHANNEL="@ngo_grants"
MAX_BYTES=40000

def telegram(method: str, data: dict | None = None, *, token: str) -> dict:
    if method not in ("getMe","getChat","getChatMember","getMyCommands"):
        raise ValueError("Read-only API methods only")
    if not token or len(token)<15:
        raise RuntimeError("Existing Telegram bot token missing")
    body=json.dumps(data or {},ensure_ascii=False).encode("utf-8")
    request=urllib.request.Request(
        f"https://api.telegram.org/bot{token}/{method}",
        method="POST",headers={"Content-Type":"application/json",
                               "User-Agent":"NGOGrantsMiniAppLaunch/1.0"},
        data=body
    )
    try:
        with urllib.request.urlopen(request,timeout=25) as response:
            decoded=json.loads(response.read(MAX_BYTES).decode("utf-8"))
    except urllib.error.HTTPError as exc:
        # never log credential-containing urllib URL or response body
        raise RuntimeError(f"Telegram {method}: HTTP {exc.code}") from None
    except (urllib.error.URLError,TimeoutError,OSError) as exc:
        raise RuntimeError(f"Telegram {method}: network {type(exc).__name__}") from None
    if not decoded.get("ok"):
        # Telegram error description may contain internal details, suppress it.
        raise RuntimeError(f"Telegram {method}: API refused request")
    return decoded.get("result")

def inspect(identity:dict, channel:dict, membership:dict, commands:list) -> dict:
    username=identity.get("username")
    bot_id=identity.get("id")
    if(identity.get("is_bot") is not True or not isinstance(bot_id,int) or
       not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{4,31}",str(username or ""))):
        raise RuntimeError("Bot API getMe did not verify a proper bot username")
    if channel.get("type")!="channel" or channel.get("username")!="ngo_grants":
        raise RuntimeError("Target channel mismatch")
    role=membership.get("status")
    allowed=role=="creator" or (role=="administrator" and membership.get("can_post_messages") is True)
    if not isinstance(commands,list):
        raise RuntimeError("Invalid bot command list")
    names=[str(item.get("command","")) for item in commands if isinstance(item,dict)]
    if len(names)!=len(commands) or any(not re.fullmatch(r"[a-z0-9_]{1,32}",name) for name in names):
        raise RuntimeError("Invalid Telegram command names")
    return {
        "bot_username":username,"bot_id":bot_id,"channel":CHANNEL,
        "channel_bot_status":role,"channel_can_post":allowed,
        "commands":names,"assistant_already_in_commands":"assistant" in names
    }

def preflight() -> dict:
    token=os.getenv("NGO_GRANTS_AI_BOT_TOKEN","").strip()
    identity=telegram("getMe",token=token)
    channel=telegram("getChat",{"chat_id":CHANNEL},token=token)
    rights=telegram("getChatMember",{"chat_id":CHANNEL,
        "user_id":identity["id"]},token=token)
    commands=telegram("getMyCommands",token=token)
    result=inspect(identity,channel,rights,commands)
    print("EXISTING_TELEGRAM_BOT_VERIFIED=@"+result["bot_username"])
    print("CHANNEL_IDENTITY_VERIFIED="+CHANNEL)
    print("BOT_IN_CHANNEL="+str(result["channel_bot_status"]))
    print("BOT_CAN_POST_CHANNEL="+str(result["channel_can_post"]))
    print("BOT_COMMANDS="+",".join(result["commands"]))
    print("ASSISTANT_COMMAND_VISIBLE="+str(result["assistant_already_in_commands"]))
    print("TELEGRAM_PREFLIGHT_READ_ONLY_COMPLETE")
    return result

if __name__=="__main__":
    try:preflight()
    except RuntimeError as exc:raise SystemExit(str(exc)) from None
