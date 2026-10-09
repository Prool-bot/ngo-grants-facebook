"""Read-only public @ngo_grants archive and offline search. No media or sessions saved."""
import argparse
import asyncio
from collections import defaultdict
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import sys
import unicodedata
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from zoneinfo import ZoneInfo

CHANNEL = "ngo_grants"
ROOT = Path("archive/telegram")


def normalize(value):
    return unicodedata.normalize("NFKC", value).casefold().replace("’", "'").replace("ʼ", "'")


def canonical_url(url):
    try:
        parts = urlsplit(url)
        if parts.scheme.lower() not in ("http", "https") or not parts.hostname:
            return url
        query = sorted((k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
                       if not k.lower().startswith("utm_") and k.lower() not in ("fbclid", "gclid"))
        return urlunsplit(("https", parts.netloc.lower(), parts.path.rstrip("/") or "/", urlencode(query), ""))
    except ValueError:
        return url


def message_record(message):
    text = message.raw_text or ""
    urls = re.findall(r"https?://[^\s<>\"\u200b]+", text)
    urls = [url.rstrip(".,;!?)]}") for url in urls]
    # Entity offsets are UTF-16, so slicing Python text with them is unsafe.
    for entity in message.entities or []:
        if getattr(entity, "url", None):
            urls.append(entity.url)
    for row in getattr(getattr(message, "reply_markup", None), "rows", []) or []:
        for button in row.buttons:
            if getattr(button, "url", None):
                urls.append(button.url)
    urls = list(dict.fromkeys(urls))
    return {
        "id": message.id,
        "date": message.date.astimezone(timezone.utc).isoformat(),
        "edit_date": message.edit_date.astimezone(timezone.utc).isoformat() if message.edit_date else None,
        "text": text,
        "urls": urls,
        "canonical_urls": list(dict.fromkeys(map(canonical_url, urls))),
        "post_url": f"https://t.me/{CHANNEL}/{message.id}",
        "views": message.views,
        "grouped_id": getattr(message, "grouped_id", None),
    }


def load_archive(root=ROOT):
    rows = {}
    for path in sorted((root / "months").glob("*.json")):
        for row in json.loads(path.read_text(encoding="utf-8")):
            if row["id"] in rows:
                raise ValueError("Duplicate message ID in archive")
            rows[row["id"]] = row
    manifest = root / "index.json"
    if manifest.exists():
        meta = json.loads(manifest.read_text(encoding="utf-8"))
        if meta["channel"] != CHANNEL or meta["message_count"] != len(rows):
            raise ValueError("Archive integrity check failed")
    elif rows:
        raise ValueError("Archive index missing; refusing an incomplete refresh")
    return rows


def atomic_text(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)


def write_archive(rows, *, full, root=ROOT, now=None):
    now = now or datetime.now(timezone.utc)
    months = defaultdict(list)
    for row in sorted(rows.values(), key=lambda r: r["id"]):
        month = datetime.fromisoformat(row["date"]).astimezone(ZoneInfo("Europe/Kyiv")).strftime("%Y-%m")
        months[month].append(row)
    index = []
    for month, messages in sorted(months.items()):
        atomic_text(root / "months" / f"{month}.json", json.dumps(messages, ensure_ascii=False, indent=2) + "\n")
        # Plain searchable companion; message text is data, never executed.
        lines = [f"# NGO Grants — {month}\n"]
        for row in messages:
            lines.extend([f"\n## Допис {row['id']} — {row['date']}\n", row["post_url"], "\n" + row["text"]])
            lines.extend(row["urls"])
        atomic_text(root / "months" / f"{month}.md", "\n".join(lines) + "\n")
        index.append({"month": month, "message_count": len(messages), "json": f"months/{month}.json",
                      "text": f"months/{month}.md", "first_id": messages[0]["id"], "last_id": messages[-1]["id"]})
    for path in (root / "months").glob("*"):
        if path.suffix in (".json", ".md") and path.stem not in months:
            path.unlink()
    old_index = root / "index.json"
    old = json.loads(old_index.read_text(encoding="utf-8")) if old_index.exists() else {}
    meta = {"schema_version": 1, "channel": CHANNEL, "channel_url": f"https://t.me/{CHANNEL}",
            "updated_at": now.isoformat(), "last_full_sync": now.isoformat() if full else old.get("last_full_sync"),
            "message_count": len(rows), "last_message_id": max(rows, default=0), "months": index}
    atomic_text(old_index, json.dumps(meta, ensure_ascii=False, indent=2) + "\n")
    return meta


def refresh_floor(rows, now):
    cutoff = now - timedelta(days=30)
    return max((r["id"] for r in rows.values() if datetime.fromisoformat(r["date"]) < cutoff), default=0)


def reconcile(rows, fetched, floor):
    return {**{mid: row for mid, row in rows.items() if mid <= floor}, **fetched}


async def sync_archive(full=False):
    # Import only for sync: offline search/tests need no Telegram credentials.
    from telethon import TelegramClient
    from telethon.sessions import StringSession
    from telethon.tl.types import Channel
    names = ("TELEGRAM_API_ID", "TELEGRAM_API_HASH", "TELEGRAM_SESSION")
    for name in names:
        if not os.environ.get(name, "").strip():
            raise RuntimeError(f"Missing secret: {name}")
    now = datetime.now(timezone.utc)
    rows = load_archive()
    full = full or not (ROOT / "index.json").exists() or now.weekday() == 6
    floor = 0 if full else refresh_floor(rows, now)
    client = TelegramClient(StringSession(os.environ["TELEGRAM_SESSION"].strip()),
                            int(os.environ["TELEGRAM_API_ID"]), os.environ["TELEGRAM_API_HASH"].strip(),
                            receive_updates=False, flood_sleep_threshold=60)
    fetched = {}
    try:
        await client.connect()
        if not await client.is_user_authorized():
            raise RuntimeError("Telegram session is not authorized")
        channel = await client.get_entity(CHANNEL)
        if not isinstance(channel, Channel) or not channel.broadcast or channel.username.casefold() != CHANNEL:
            raise RuntimeError("Expected the public @ngo_grants broadcast channel")
        async for message in client.iter_messages(channel, limit=None, min_id=floor, wait_time=1):
            if not getattr(message, "action", None):
                fetched[message.id] = message_record(message)
            if len(fetched) and len(fetched) % 1000 == 0:
                print(f"Прочитано дописів: {len(fetched)}", flush=True)
    finally:
        await client.disconnect()
    # Never publish partial results if Telegram failed partway through a read.
    if rows and not fetched and floor == 0:
        raise RuntimeError("Unexpected empty history; existing archive preserved")
    merged = reconcile(rows, fetched, floor)
    meta = write_archive(merged, full=full, now=now)
    print(f"Архів оновлено. Дописів: {meta['message_count']}; місяців: {len(meta['months'])}")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as stream:
            stream.write(f"## Архів NGO Grants\n\nДописів: **{meta['message_count']}**. Місяців: **{len(meta['months'])}**.\n\n"
                         f"Оновлено: {meta['updated_at']}. Повна звірка: {meta['last_full_sync']}.\n")


def search_rows(rows, query="", mode="all", since=None, until=None, url=None):
    # Quoted phrases stay together, unquoted words combine in all/any mode.
    terms = [normalize(a or b) for a, b in re.findall(r'"([^"]+)"|(\S+)', query)]
    result = []
    for row in rows.values():
        date = datetime.fromisoformat(row["date"]).astimezone(ZoneInfo("Europe/Kyiv")).date().isoformat()
        if (since and date < since) or (until and date > until):
            continue
        haystack = normalize("\n".join([row["text"], *row["urls"], *row["canonical_urls"]]))
        if terms and not (all if mode == "all" else any)(term in haystack for term in terms):
            continue
        if url and canonical_url(url) not in row["canonical_urls"]:
            continue
        result.append(row)
    return sorted(result, key=lambda r: r["id"], reverse=True)


def main():
    parser = argparse.ArgumentParser(description="Архів і пошук публікацій NGO Grants")
    sub = parser.add_subparsers(dest="command", required=True)
    sync = sub.add_parser("sync")
    sync.add_argument("--full", action="store_true")
    search = sub.add_parser("search")
    search.add_argument("query", nargs="?", default="")
    search.add_argument("--mode", choices=("all", "any"), default="all")
    search.add_argument("--since")
    search.add_argument("--until")
    search.add_argument("--url")
    search.add_argument("--limit", type=int, default=30)
    search.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.command == "sync":
        asyncio.run(sync_archive(args.full))
    else:
        for value in (args.since, args.until):
            if value:
                datetime.strptime(value, "%Y-%m-%d")
        if args.limit < 1 or (args.since and args.until and args.since > args.until):
            parser.error("Invalid limit or date range")
        if not (ROOT / "index.json").exists():
            parser.error("Archive has not been created yet")
        result = search_rows(load_archive(), args.query, args.mode, args.since, args.until, args.url)
        if args.output:
            atomic_text(args.output, json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        print(f"Знайдено: {len(result)}; показано: {min(args.limit, len(result))}")
        for row in result[:args.limit]:
            print(f"\n{row['date']} | {row['post_url']}\n{row['text']}\n" + "\n".join(row["urls"]))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        # Avoid credentials or private API response data in public Actions logs.
        print(f"Помилка архівування/пошуку: {type(exc).__name__}. Перевірте налаштування та доступ.", file=sys.stderr)
        sys.exit(1)
