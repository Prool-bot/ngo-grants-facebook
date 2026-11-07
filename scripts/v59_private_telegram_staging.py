"""Opt-in isolated Telegram v5.9 acceptance test.

Safety rules:
- Separate TEST bot and PRIVATE TEST channel only. Never use production bot.
- The private test channel must have no username and contain TEST/ТЕСТ in title.
- No production state, no Cloudflare, no archived orders or donor data.
- Preflight is GET-only; explicit typed confirmation is required to SEND.
- A network timeout after sendDocument stops the run (never retries).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import uuid
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

ROOT = Path(__file__).resolve().parents[1]
CONFIRMATION = "CONFIRM_PRIVATE_TEST_ONLY"
BLOCKED_BOT_NAMES = {"ngograntsai_bot", "ngograntsaibot"}
SAFE_TITLE = re.compile(r"test|тест", re.IGNORECASE)


def check_config(bot_id: dict, chat: dict, member: dict, chat_id: str) -> None:
    if not re.fullmatch(r"-100\d{8,16}", chat_id):
        raise RuntimeError("Only a numeric private Telegram channel ID is allowed")
    if bot_id.get("is_bot") is not True:
        raise RuntimeError("Test credentials did not identify a bot")
    username = str(bot_id.get("username") or "").lower()
    if not username or "test" not in username or username in BLOCKED_BOT_NAMES:
        raise RuntimeError("Bot username must identify a separate TEST bot")
    if chat.get("type") != "channel" or str(chat.get("id")) != chat_id:
        raise RuntimeError("Target must be the exact requested Telegram channel")
    if chat.get("username"):
        raise RuntimeError("A public channel is forbidden")
    if not SAFE_TITLE.search(str(chat.get("title") or "")):
        raise RuntimeError("Test channel title must contain TEST or ТЕСТ")
    if member.get("status") != "administrator":
        raise RuntimeError("Test bot must be channel administrator")
    if not member.get("can_post_messages") or not member.get("can_edit_messages"):
        raise RuntimeError("Test bot needs post and edit permissions")


class TelegramTestAPI:
    def __init__(self, token: str):
        self._token = token

    def call(self, method: str, data: dict, pdf: Path | None = None) -> dict:
        # Never print URL, token, chat ID, API response, or request data.
        url = "https://api.telegram.org/bot" + self._token + "/" + method
        if pdf is None:
            payload = json.dumps(data).encode("utf-8")
            request = Request(url, data=payload, method="POST",
                              headers={"Content-Type":"application/json"})
        else:
            if not pdf.is_file() or pdf.suffix != ".pdf":
                raise RuntimeError("PDF file is missing or invalid")
            boundary = "V59TEST" + uuid.uuid4().hex
            body = bytearray()
            for key,value in data.items():
                body += (f"--{boundary}\r\nContent-Disposition: form-data; "
                         f'name="{key}"\r\n\r\n{value}\r\n').encode("utf-8")
            body += (f"--{boundary}\r\nContent-Disposition: form-data; "
                     'name="document"; filename="v59-test.pdf"\r\n'
                     "Content-Type: application/pdf\r\n\r\n").encode("utf-8")
            body.extend(pdf.read_bytes())
            body.extend(("\r\n--"+boundary+"--\r\n").encode("ascii"))
            request = Request(url, data=bytes(body), method="POST",
                              headers={"Content-Type":"multipart/form-data; boundary="+boundary})
        try:
            with urlopen(request, timeout=35) as response:
                parsed = json.loads(response.read(100000))
        except HTTPError as exc:
            raise RuntimeError(f"Telegram test API {method}: HTTP {exc.code}") from None
        except (URLError, OSError, TimeoutError):
            raise RuntimeError(f"Telegram test API {method}: uncertain network outcome; STOP, DO NOT RETRY") from None
        if parsed.get("ok") is not True:
            raise RuntimeError(f"Telegram test API {method}: rejected; no retry")
        return parsed["result"]


def preflight(api: TelegramTestAPI, chat_id: str) -> None:
    # Only read-only Telegram API operations, no send/edit.
    bot = api.call("getMe", {})
    chat = api.call("getChat", {"chat_id":chat_id})
    member = api.call("getChatMember", {"chat_id":chat_id,
                                      "user_id":bot["id"]})
    check_config(bot,chat,member,chat_id)
    print("V59_PRIVATE_TEST_PREFLIGHT=PASS; NO_MESSAGES_SENT")


def execute(api: TelegramTestAPI, chat_id: str, directory: Path,
            *, token_confirm: str) -> None:
    if token_confirm != CONFIRMATION:
        raise RuntimeError("Explicit confirmation missing; no Telegram actions")
    preflight(api,chat_id)
    from ngo_grants_v59_navigation import companion_markup

    documents = []
    for tier, name in (("direct","direct.pdf"),("conditional","conditional.pdf")):
        pdf = directory / name
        if not pdf.is_file() or not pdf.read_bytes().startswith(b"%PDF"):
            raise RuntimeError("Both valid synthetic staging PDFs must exist")
        documents.append((tier,pdf))
    sent=[]
    for tier,pdf in documents:
        # Explicitly NO retry after ambiguous sendDocument outcome.
        message = api.call("sendDocument", {
            "chat_id":chat_id,
            "caption":"[TEST ONLY] NGO Grants v5.9 "+tier+" — synthetic data",
            "disable_notification":True,
        },pdf=pdf)
        msg_id=message.get("message_id")
        if not isinstance(msg_id,int) or msg_id<=0:
            raise RuntimeError("No confirmed Telegram message_id; STOP")
        sent.append({"tier":tier,"status":"sent","message_id":msg_id})
        print(f"V59_TEST_{tier.upper()}_DOCUMENT_CONFIRMED")
    markup = companion_markup(sent, "@not-used".lstrip("@"))
    # Use channel numerical ID in edit; URL must be a valid t.me link.
    # Private channels have no username: use the internal /c/<id> URL.
    private_id=chat_id.removeprefix("-100")
    markup["inline_keyboard"][0][0]["url"]=(
        f"https://t.me/c/{private_id}/{sent[1]['message_id']}")
    edited=api.call("editMessageReplyMarkup",{
        "chat_id":chat_id,
        "message_id":sent[0]["message_id"],
        "reply_markup":markup,
    })
    if edited.get("message_id") != sent[0]["message_id"]:
        raise RuntimeError("Telegram did not confirm the companion button edit")
    print("V59_PRIVATE_TEST_COMPANION_LINK_CONFIRMED")
    print("V59_PRIVATE_TEST_ACCEPTANCE=PASS; test documents remain in private channel")


def main() -> int:
    args=argparse.ArgumentParser()
    args.add_argument("--mode",choices=("preflight","send"),default="preflight")
    args.add_argument("--confirm",default="")
    options=args.parse_args()
    token=os.getenv("V59_TEST_BOT_TOKEN","").strip()
    channel=os.getenv("V59_TEST_CHANNEL_ID","").strip()
    if not token or not channel:
        print("V59_STAGING=NOT_CONFIGURED (requires separate TEST bot/channel secrets)")
        return 2
    api=TelegramTestAPI(token)
    try:
        if options.mode == "preflight":
            preflight(api,channel)
        else:
            # Confirmation must be checked BEFORE any network operation.
            if options.confirm != CONFIRMATION:
                raise RuntimeError("Confirmation mismatch, no Telegram send")
            subprocess.run([sys.executable,
                            str(ROOT/"scripts"/"v59_staging_preview.py")],
                           cwd=str(ROOT),check=True)
            execute(api,channel,ROOT/"output"/"v59-staging-preview",
                    token_confirm=options.confirm)
        return 0
    except (RuntimeError,subprocess.CalledProcessError) as exc:
        # Errors must be scrubbed of secrets, IDs and API response bodies.
        msg=str(exc).replace(token,"[REDACTED]")
        msg=msg.replace(channel,"[CHANNEL_ID]")
        print("V59_STAGING=BLOCKED: "+msg)
        return 1


if __name__=="__main__":
    raise SystemExit(main())
