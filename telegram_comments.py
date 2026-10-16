"""Read public channel comments and archive them WITHOUT commenter identities."""
import argparse
import asyncio
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import sys
from zoneinfo import ZoneInfo

CHANNEL = "ngo_grants"
ROOT = Path("archive/telegram/comments")


def redact(text):
    """Minimize direct identifiers before placing public comments on public GitHub."""
    text = re.sub(r"https?://t\.me/(?:joinchat/|\+)[^\s<>]+", "[приватне запрошення]", text, flags=re.I)
    text = re.sub(r"(?<![\w.+-])[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}(?![\w.-])", "[електронна адреса]", text)
    text = re.sub(r"(?<!\w)@[A-Za-z][A-Za-z0-9_]{4,31}\b", "[ім'я користувача]", text)
    def phone(match):
        value = match.group(0)
        return "[номер телефону]" if sum(c.isdigit() for c in value) >= 10 else value
    return re.sub(r"(?<!\w)\+?\d[\d ()-]{7,}\d(?!\w)", phone, text)


def comment_record(msg, post_id):
    if getattr(msg, "action", None):
        return None
    text = redact(msg.raw_text or "").strip()
    if not text:
        return None
    return {
        "id": msg.id,
        "date": msg.date.astimezone(timezone.utc).isoformat(),
        "edit_date": msg.edit_date.astimezone(timezone.utc).isoformat() if msg.edit_date else None,
        "text": text,
        "reply_to_id": getattr(getattr(msg, "reply_to", None), "reply_to_msg_id", None),
        "comment_url": f"https://t.me/{CHANNEL}/{post_id}?comment={msg.id}",
    }


def atomic_text(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)


def load_comments(root=ROOT):
    manifest = root / "index.json"
    if not manifest.exists():
        if any((root / "posts").glob("*.json")):
            raise ValueError("Index missing for existing comments")
        return {}, {}
    meta = json.loads(manifest.read_text(encoding="utf-8"))
    if meta.get("schema_version") != 1 or meta.get("channel") != CHANNEL:
        raise ValueError("Unexpected archive schema")
    rows, seen = {}, set()
    for entry in meta.get("posts", []):
        pid = entry["post_id"]
        if not isinstance(pid, int) or pid in rows or entry["file"] != f"posts/{pid}.json":
            raise ValueError("Unexpected post entry")
        comments = json.loads((root / "posts" / f"{pid}.json").read_text(encoding="utf-8"))
        if len(comments) != entry["count"]:
            raise ValueError("Comment count mismatch")
        for item in comments:
            if not isinstance(item["id"], int) or item["id"] in seen:
                raise ValueError("Duplicate comment")
            seen.add(item["id"])
        rows[pid] = comments
    if len(rows) != meta.get("post_count") or len(seen) != meta.get("comment_count"):
        raise ValueError("Archive integrity check failed")
    return rows, meta


def reconcile(old, fetched, scanned, full=False):
    """Replace re-scanned threads, including comments since deleted."""
    output = {} if full else {pid: value for pid, value in old.items() if pid not in scanned}
    output.update({pid: value for pid, value in fetched.items() if value})
    return output


def write_comments(rows, discussion_username, *, full=False, days=45, now=None, root=ROOT):
    now = now or datetime.now(timezone.utc)
    old_path = root / "index.json"
    old = json.loads(old_path.read_text(encoding="utf-8")) if old_path.exists() else {}
    if old.get("discussion_username") and old["discussion_username"].casefold() != discussion_username.casefold():
        raise ValueError("Linked discussion group changed")
    posts = []
    for pid, comments in sorted(rows.items()):
        if not comments:
            continue
        comments = sorted(comments, key=lambda r: r["id"])
        atomic_text(root / "posts" / f"{pid}.json", json.dumps(comments, ensure_ascii=False, indent=2) + "\n")
        posts.append({
            "post_id": pid, "post_url": f"https://t.me/{CHANNEL}/{pid}",
            "count": len(comments), "latest_date": max(r["date"] for r in comments),
            "file": f"posts/{pid}.json",
        })
    for path in (root / "posts").glob("*.json"):
        if path.stem.isdigit() and int(path.stem) not in rows:
            path.unlink()
    meta = {
        "schema_version": 1, "channel": CHANNEL,
        "channel_url": f"https://t.me/{CHANNEL}",
        "discussion_username": discussion_username,
        "updated_at": now.isoformat(),
        "last_full_sync": now.isoformat() if full else old.get("last_full_sync"),
        "lookback_days": None if full else days,
        "comment_count": sum(p["count"] for p in posts),
        "post_count": len(posts), "posts": posts,
    }
    atomic_text(old_path, json.dumps(meta, ensure_ascii=False, indent=2) + "\n")
    return meta


def search_comments(rows, query="", post_id=None, since=None):
    terms = [next(part for part in match if part).casefold()
             for match in re.findall(r'"([^"]+)"|(\S+)', query)]
    result = []
    for pid, comments in rows.items():
        if post_id is not None and post_id != pid:
            continue
        for row in comments:
            local = datetime.fromisoformat(row["date"]).astimezone(ZoneInfo("Europe/Kyiv")).date().isoformat()
            if (since and local < since) or not all(term in row["text"].casefold() for term in terms):
                continue
            result.append({"post_id": pid, **row})
    return sorted(result, key=lambda row: (row["date"], row["id"]), reverse=True)


async def sync_comments(days=45, full=False):
    from telethon import TelegramClient
    from telethon.sessions import StringSession
    from telethon.tl.functions.channels import GetFullChannelRequest
    from telethon.tl.types import Channel

    for name in ("TELEGRAM_API_ID", "TELEGRAM_API_HASH", "TELEGRAM_SESSION"):
        if not os.environ.get(name, "").strip():
            raise RuntimeError(f"Missing secret: {name}")
    old, old_meta = load_comments()
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days)
    client = TelegramClient(
        StringSession(os.environ["TELEGRAM_SESSION"].strip()),
        int(os.environ["TELEGRAM_API_ID"]),
        os.environ["TELEGRAM_API_HASH"].strip(),
        receive_updates=False, flood_sleep_threshold=60,
    )
    fetched, scanned = {}, set()
    try:
        print("Перевірка: підключення до Telegram...", flush=True)
        await client.connect()
        if not await client.is_user_authorized():
            raise RuntimeError("Telegram session not authorized")
        print("Перевірка: Telegram-авторизація підтверджена.", flush=True)
        channel = await client.get_entity(CHANNEL)
        if not isinstance(channel, Channel) or not channel.broadcast or (channel.username or "").casefold() != CHANNEL:
            raise RuntimeError("Unexpected channel")
        print("Перевірка: канал знайдено. Шукаю прив'язану групу обговорень...", flush=True)
        info = await client(GetFullChannelRequest(channel))
        group_id = getattr(info.full_chat, "linked_chat_id", None)
        group = next((chat for chat in info.chats if chat.id == group_id), None)
        if not group_id or not isinstance(group, Channel) or not group.megagroup:
            raise RuntimeError("No linked discussion megagroup")
        print("Перевірка: групу обговорень знайдено.", flush=True)
        discussion_username = getattr(group, "username", None)
        if not discussion_username:
            raise RuntimeError("Private discussion group: public GitHub archive disabled")
        if old_meta.get("discussion_username") and old_meta["discussion_username"].casefold() != discussion_username.casefold():
            raise RuntimeError("Linked discussion group changed")
        print("Перевірка: група публічна. Починаю читання коментарів...", flush=True)
        async for post in client.iter_messages(channel, limit=None, wait_time=1):
            if not full and post.date < cutoff:
                break
            if getattr(post, "action", None):
                continue
            scanned.add(post.id)
            reply_count = getattr(getattr(post, "replies", None), "replies", 0) or 0
            if reply_count == 0 and post.id not in old:
                continue
            comments = []
            async for msg in client.iter_messages(channel, reply_to=post.id, limit=None, wait_time=1):
                record = comment_record(msg, post.id)
                if record:
                    comments.append(record)
            if comments:
                fetched[post.id] = comments
        # A Telegram read error propagates; nothing is saved partially.
    finally:
        await client.disconnect()
    meta = write_comments(reconcile(old, fetched, scanned, full=full),
                          discussion_username, days=days, full=full, now=now)
    print(f"Коментарів: {meta['comment_count']}; дописів з коментарями: "
          f"{meta['post_count']}; перевірено дописів: {len(scanned)}")
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as summary:
            summary.write(f"## Архів коментарів NGO Grants\n\n"
                          f"Коментарів: **{meta['comment_count']}**; дописів: **{meta['post_count']}**; "
                          f"перевірено: **{len(scanned)}**.\n"
                          "Особисті ідентифікатори авторів не зберігаються.\n")


def main():
    parser = argparse.ArgumentParser(description="Архів і пошук публічних коментарів NGO Grants")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sync = sub.add_parser("sync")
    sync.add_argument("--days", type=int, default=45)
    sync.add_argument("--full", action="store_true")
    search = sub.add_parser("search")
    search.add_argument("query", nargs="?", default="")
    search.add_argument("--post-id", type=int)
    search.add_argument("--since")
    search.add_argument("--limit", type=int, default=30)
    search.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.cmd == "sync":
        if not 1 <= args.days <= 3650:
            parser.error("Invalid days")
        asyncio.run(sync_comments(args.days, args.full))
    else:
        if args.limit < 1 or (args.post_id is not None and args.post_id < 1):
            parser.error("Invalid limit or post ID")
        if args.since:
            datetime.strptime(args.since, "%Y-%m-%d")
        rows, _ = load_comments()
        result = search_comments(rows, args.query, args.post_id, args.since)
        if args.output:
            atomic_text(args.output, json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        print(f"Знайдено: {len(result)}; показано: {min(len(result), args.limit)}")
        for item in result[:args.limit]:
            print(f"{item['date']} | {item['comment_url']}\n{item['text']}\n")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        # Do not expose Telegram responses, identities or credentials in public logs.
        # Only explicitly known constant error messages may enter public Actions logs.
        # Never print raw API responses, Telegram identities, or secret values.
        safe_reasons = {
            "Telegram session not authorized": "Telegram-сесія потребує повторної авторизації.",
            "Unexpected channel": "Отриманий канал не збігається з @ngo_grants.",
            "No linked discussion megagroup": "Telegram не повернув пов'язану групу обговорень.",
            "Private discussion group: public GitHub archive disabled":
                "Прив'язана група приватна. Публічний GitHub-архів коментарів заборонений.",
            "Linked discussion group changed": "Змінилася прив'язана група обговорень.",
        }
        for env_name in ("TELEGRAM_API_ID", "TELEGRAM_API_HASH", "TELEGRAM_SESSION"):
            safe_reasons[f"Missing secret: {env_name}"] = f"Відсутній секрет GitHub: {env_name}."
        reason = safe_reasons.get(str(exc)) if isinstance(exc, RuntimeError) else None
        print("Помилка читання коментарів: " + (reason or type(exc).__name__),
              file=sys.stderr)
        sys.exit(1)
