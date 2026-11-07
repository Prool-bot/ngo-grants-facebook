"""Crash-safe, fail-closed two-document Telegram delivery.

Telegram sendDocument has no caller-supplied idempotency key. Exactly-once
delivery is therefore impossible to guarantee after an unknown network failure.
We persist 'sending' before every API call and NEVER automatically retry a
'sending' document. A human must reconcile ambiguous status against the
channel before releasing that order.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable, Any

STAGES = ("prepared", "sending", "sent")


def ensure_delivery(state: dict, *, order_id: int, fingerprint: str,
                    documents: list[dict], save: Callable[[dict], None],
                    metadata: dict | None = None) -> dict:
    """Persist an immutable document manifest before any external send.

    A manifest should include ONLY complete PDFs prepared for the order.
    Re-entering the process verifies fingerprint and document identities.
    """
    key = str(int(order_id))
    deliveries = state.setdefault("v59_deliveries", {})
    existing = deliveries.get(key)
    if existing:
        if existing.get("fingerprint") != fingerprint:
            raise RuntimeError("Змінився склад документів вже розпочатої доставки.")
        expected = [(d.get("tier"), d.get("path")) for d in documents]
        actual = [(d.get("tier"), d.get("path")) for d in existing.get("documents", [])]
        if expected != actual:
            raise RuntimeError("Файли доставки змінилися під час повторного запуску.")
        if metadata is not None and existing.get("metadata") != metadata:
            raise RuntimeError("Змінилася метаінформація розпочатої доставки.")
        return existing

    if not documents:
        raise ValueError("Порожній маніфест доставки")
    if len(documents) > 2:
        raise ValueError("Надмірна кількість документів")
    tiers = [d.get("tier") for d in documents]
    if len(set(tiers)) != len(tiers) or any(t not in ("direct", "conditional") for t in tiers):
        raise ValueError("Некоректні рівні відповідності")
    prepared = []
    for doc in documents:
        if not doc.get("path") or not doc.get("caption"):
            raise ValueError("Відсутній файл або підпис документа")
        prepared.append({"tier":doc["tier"], "path":doc["path"],
                         "caption":doc["caption"], "status":"prepared",
                         "message_id":None})
    entry = {"fingerprint": fingerprint, "documents": prepared,
             "metadata": dict(metadata or {})}
    deliveries[key] = entry
    save(state)
    return entry


def deliver_documents(state: dict, *, order_id: int,
                      send: Callable[[str, str], int],
                      save: Callable[[dict], None]) -> tuple[bool, list[int]]:
    """Send remaining prepared documents, never resending uncertain ones.

    Returns (finished, message IDs). A 'sending' state always blocks.
    """
    entry = state.get("v59_deliveries", {}).get(str(int(order_id)))
    if not entry:
        raise RuntimeError("Немає підготовленого маніфесту")
    docs = entry["documents"]
    for doc in docs:
        status = doc.get("status")
        if status == "sent":
            if not isinstance(doc.get("message_id"), int) or doc["message_id"] <= 0:
                raise RuntimeError("Відправлений файл без коректного Telegram ID")
            continue
        if status == "sending":
            raise RuntimeError(
                "Невизначений результат відправлення. Повторно не надсилати: "
                "спочатку звірити повідомлення в Telegram вручну."
            )
        if status != "prepared":
            raise RuntimeError("Невідомий етап доставки")
        doc["status"] = "sending"
        doc["started_at"] = datetime.now(timezone.utc).isoformat()
        save(state)
        # This call may succeed remotely and fail locally; leave 'sending'
        # unchanged in that case. Never blindly retry.
        message_id = send(doc["path"], doc["caption"])
        if not isinstance(message_id, int) or message_id <= 0:
            raise RuntimeError("Telegram не підтвердив ID опублікованого документа")
        doc["message_id"] = message_id
        doc["status"] = "sent"
        save(state)
    return True, [d["message_id"] for d in docs]


def reconcile_document(state: dict, *, order_id: int, tier: str,
                       message_id: int, save: Callable[[dict], None]) -> None:
    """Manually confirm an ambiguous send after independently checking channel.

    This function has no automatic caller. Never infer a message ID.
    """
    if not isinstance(message_id, int) or message_id <= 0:
        raise ValueError("Потрібен перевірений Telegram message_id")
    entry = state.get("v59_deliveries", {}).get(str(int(order_id)))
    if not entry:
        raise ValueError("Не знайдено замовлення")
    doc = next((d for d in entry["documents"] if d["tier"] == tier), None)
    if not doc or doc["status"] != "sending":
        raise ValueError("Підтверджувати можна лише невизначену доставку")
    if any(x.get("message_id") == message_id for x in entry["documents"]):
        raise ValueError("Telegram ID уже використано")
    doc["message_id"] = message_id
    doc["status"] = "sent"
    save(state)
