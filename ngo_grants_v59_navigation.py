"""Idempotent cross-navigation for v5.9 two-tier Telegram PDFs.

The deployed v5.8 Worker still exposes a single catalog link. Its first
document remains a valid entry point: after both PDFs have been confirmed,
an inline URL button links the first document to the second.
"""
from __future__ import annotations
from typing import Callable


def companion_markup(documents: list[dict], channel: str) -> dict | None:
    if len(documents) != 2:
        return None
    if {d.get("tier") for d in documents} != {"direct", "conditional"}:
        raise RuntimeError("Некоректний набір каталогів для навігації")
    if not all(d.get("status") == "sent" and
               isinstance(d.get("message_id"), int) and d["message_id"] > 0
               for d in documents):
        raise RuntimeError("Посилання не можна створювати до публікації обох PDF")
    if documents[0]["tier"] != "direct":
        raise RuntimeError("Першим документом має бути підтверджений каталог")
    companion = documents[1]
    if channel.startswith("-100") and channel[4:].isdigit():
        # Private Telegram channel links use /c/<numeric-id> and have no @handle.
        url = f"https://t.me/c/{channel[4:]}/{companion['message_id']}"
    else:
        url = f"https://t.me/{channel.lstrip('@')}/{companion['message_id']}"
    return {"inline_keyboard": [[{
        "text": "📙 Переглянути умовні можливості",
        "url": url,
    }]]}


def ensure_companion_navigation(state: dict, *, order_id: int, channel: str,
                                edit_markup: Callable[[int, dict], object],
                                save: Callable[[dict], None]) -> bool:
    """Idempotently edit first PDF's reply markup and checkpoint the result.

    Repeating the *same* edit is safe after a response timeout: Telegram
    may report 'message is not modified', which means markup already exists.
    """
    manifest = state.get("v59_deliveries", {}).get(str(int(order_id)))
    if not manifest:
        raise RuntimeError("Не знайдено маніфест документа для навігації")
    docs = manifest.get("documents", [])
    markup = companion_markup(docs, channel)
    if markup is None:
        # A single confirmed PDF is self-sufficient for the old Worker UI.
        return True
    if manifest.get("navigation_status") == "linked":
        return True
    if manifest.get("navigation_status") not in (None, "pending"):
        raise RuntimeError("Пошкоджений стан навігації PDF")
    first_id = docs[0]["message_id"]
    try:
        edit_markup(first_id, markup)
    except RuntimeError as exc:
        # Telegram explicitly confirms the requested markup is already there.
        if "message is not modified" not in str(exc).lower():
            raise
    manifest["navigation_status"] = "linked"
    save(state)
    return True
