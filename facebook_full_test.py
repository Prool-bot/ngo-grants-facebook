import asyncio
import base64
import io
import json
import os
import re
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from PIL import Image, ImageDraw, ImageFont, ImageOps
from telethon import TelegramClient
from telethon.sessions import StringSession

OUTPUT = Path("output")
OUTPUT.mkdir(exist_ok=True)

REQUIRED = (
    "TELEGRAM_API_ID",
    "TELEGRAM_API_HASH",
    "TELEGRAM_SESSION",
    "CLOUDFLARE_ACCOUNT_ID",
    "CLOUDFLARE_API_TOKEN",
)

for name in REQUIRED:
    if not os.environ.get(name, "").strip():
        raise SystemExit(f"Відсутній секрет: {name}")

ACCOUNT_ID = os.environ["CLOUDFLARE_ACCOUNT_ID"].strip()
TOKEN = os.environ["CLOUDFLARE_API_TOKEN"].strip()

if not re.fullmatch(r"[a-fA-F0-9]{32}", ACCOUNT_ID):
    raise SystemExit("Некоректний CLOUDFLARE_ACCOUNT_ID")

MODEL = "@cf/black-forest-labs/flux-1-schnell"

def save_json(path, value):
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

def full_text(message):
    text = (message.raw_text or "").strip()
    urls = []

    for entity in message.entities or []:
        url = getattr(entity, "url", None)
        if (
            url
            and url.startswith(("https://", "http://"))
            and url not in text
            and url not in urls
        ):
            urls.append(url)

    if urls:
        text += "\n\nПосилання:\n" + "\n".join(urls)

    return text

def get_title(text):
    for line in text.splitlines():
        if line.strip():
            return line.strip()
    return "Грантові можливості"

def generate_image(title):
    subject = title.lower()
    if "djerassi" in subject or "резиденц" in subject:
        scene = "An artist studio with brushes, canvas and notebooks overlooking wooded hills, daylight."
    elif "стипенд" in subject or "магістр" in subject:
        scene = "Students studying together in a contemporary university library, books and notebooks."
    elif "огс" in subject or "інституц" in subject:
        scene = "Civil society colleagues planning a community project around a table with blank folders."
    else:
        scene = "A diverse project team collaborating in a bright modern workspace."
    prompt = scene + " Editorial illustration, teal and warm gold. Blank surfaces, no text, no numbers, no logos."

    endpoint = (
        "https://api.cloudflare.com/client/v4/accounts/"
        + ACCOUNT_ID
        + "/ai/run/"
        + MODEL
    )

    request = urllib.request.Request(
        endpoint,
        data=json.dumps(
            {"prompt": prompt, "steps": 4}
        ).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(
            request, timeout=180
        ) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as error:
        raise RuntimeError(
            f"Cloudflare повернув HTTP {error.code}"
        ) from None
    except urllib.error.URLError:
        raise RuntimeError(
            "Не вдалося підключитися до Cloudflare"
        ) from None

    if payload.get("success") is False:
        codes = [
            str(item.get("code", "unknown"))
            for item in payload.get("errors", [])
        ]
        raise RuntimeError(
            "Помилка Cloudflare: " + ", ".join(codes)
        )

    encoded = (payload.get("result") or {}).get("image")
    if not encoded:
        raise RuntimeError(
            "Cloudflare не повернув зображення"
        )

    if encoded.startswith("data:"):
        encoded = encoded.split(",", 1)[1]

    with Image.open(
        io.BytesIO(base64.b64decode(encoded))
    ) as source:
        source.load()
        return ImageOps.fit(
            source.convert("RGB"),
            (1080, 1080),
        )

def load_font(size, bold=False):
    filename = (
        "DejaVuSans-Bold.ttf"
        if bold
        else "DejaVuSans.ttf"
    )
    path = (
        "/usr/share/fonts/truetype/dejavu/"
        + filename
    )
    return ImageFont.truetype(path, size)

def wrap_title(draw, text, font, width):
    lines = []
    current = ""

    for word in text.split():
        candidate = (
            current + " " + word
        ).strip()

        if (
            current
            and draw.textlength(
                candidate, font=font
            ) > width
        ):
            lines.append(current)
            current = word
        else:
            current = candidate

    if current:
        lines.append(current)

    return lines

def brand_image(image, title, destination):
    draw = ImageDraw.Draw(image)

    # Залишаємо українські літери, прибираємо
    # емодзі, які цей шрифт може не підтримувати.
    clean_title = re.sub(
        r"[^\w\s.,:;!?()'’«»/—–+\-]",
        "",
        title,
        flags=re.UNICODE,
    ).strip()

    clean_title = clean_title or "Грантові можливості"

    for size in range(46, 23, -2):
        font = load_font(size, bold=True)
        lines = wrap_title(
            draw, clean_title, font, 960
        )
        if len(lines) <= 5:
            break

    line_height = size + 12
    panel_height = (
        110 + len(lines) * line_height
    )
    panel_top = 1080 - panel_height

    draw.rectangle(
        (0, panel_top, 1080, 1080),
        fill=(13, 48, 53),
    )

    draw.text(
        (60, panel_top + 25),
        "NGO Grants",
        font=load_font(30, bold=True),
        fill=(244, 197, 92),
    )

    y = panel_top + 80
    for line in lines:
        draw.text(
            (60, y),
            line,
            font=font,
            fill="white",
        )
        y += line_height

    image.save(destination, quality=95)

async def select_posts():
    kyiv = ZoneInfo("Europe/Kyiv")
    today = datetime.now(kyiv).date()
    yesterday = today - timedelta(days=1)

    start = datetime.combine(
        yesterday,
        datetime.min.time(),
        tzinfo=kyiv,
    ).astimezone(timezone.utc)

    end = datetime.combine(
        today,
        datetime.min.time(),
        tzinfo=kyiv,
    ).astimezone(timezone.utc)

    client = TelegramClient(
        StringSession(
            os.environ["TELEGRAM_SESSION"].strip()
        ),
        int(os.environ["TELEGRAM_API_ID"].strip()),
        os.environ["TELEGRAM_API_HASH"].strip(),
        receive_updates=False,
    )

    candidates = []

    try:
        await client.connect()

        if not await client.is_user_authorized():
            raise RuntimeError(
                "Сесія Telegram не авторизована"
            )

        channel = await client.get_entity("ngo_grants")

        async for message in client.iter_messages(
            channel, offset_date=end
        ):
            if message.date < start:
                break
            if message.date >= end:
                continue
            if not (message.raw_text or "").strip():
                continue
            if message.views is None:
                continue

            candidates.append(message)

        candidates.sort(
            key=lambda item: (item.views, item.id),
            reverse=True,
        )

        posts = []

        for rank, message in enumerate(
            candidates[:3], start=1
        ):
            text = full_text(message)
            posts.append({
                "rank": rank,
                "telegram_message_id": message.id,
                "telegram_url": (
                    f"https://t.me/ngo_grants/{message.id}"
                ),
                "views": message.views,
                "title": get_title(text),
                "text": text,
                "image_file": f"post-{rank}.jpg",
            })

        return yesterday, len(candidates), posts

    finally:
        await client.disconnect()

import subprocess
import time
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup

REPORT = {"posts": [], "reel": None}
PAGE = os.environ.get("FACEBOOK_PAGE_ID", "").strip()
FB_TOKEN = os.environ.get("FACEBOOK_PAGE_ACCESS_TOKEN", "").strip()
GRAPH = "https://graph.facebook.com/v26.0/"
if not PAGE or not FB_TOKEN:
    raise SystemExit("Відсутні секрети Facebook")

def checkpoint():
    save_json(OUTPUT / "publication-report.json", REPORT)

def api_result(response, service):
    try:
        result = response.json()
    except ValueError:
        raise RuntimeError(f"{service}: HTTP {response.status_code}, відповідь не JSON") from None
    if not response.ok or result.get("error"):
        error = result.get("error") or {}
        raise RuntimeError(
            f"{service}: HTTP {response.status_code}; код {error.get('code', 'unknown')}; "
            f"підкод {error.get('error_subcode', 'none')}; "
            + str(error.get("message", "")).replace(FB_TOKEN, "[redacted]")
        )
    return result

def graph(method, path, data=None, files=None):
    response = requests.request(
        method, GRAPH + path,
        headers={"Authorization": f"Bearer {FB_TOKEN}"},
        params=data if method == "GET" else None,
        data=data if method != "GET" else None,
        files=files, timeout=180, allow_redirects=False,
    )
    return api_result(response, "Meta " + method + " /" + path)

def download_image(url):
    if urlparse(url).scheme not in ("http", "https"):
        raise ValueError("Некоректна адреса зображення")
    response = requests.get(
        url, headers={"User-Agent": "NGOGrantsPublisher/1.0"},
        timeout=25, stream=True,
    )
    try:
        response.raise_for_status()
        content = bytearray()
        for chunk in response.iter_content(65536):
            content.extend(chunk)
            if len(content) > 15_000_000:
                raise ValueError("Зображення завелике")
    finally:
        response.close()
    with Image.open(io.BytesIO(content)) as image:
        image.load()
        if image.width < 400 or image.height < 200:
            raise ValueError("Зображення замале")
        return image.convert("RGB")

def website_banner(text):
    urls = re.findall(r"https?://[^\s<>]+", text)
    for url in dict.fromkeys(urls):
        url = url.rstrip(".,;)")
        host = (urlparse(url).hostname or "").lower()
        if host in {
            "t.me", "telegram.me", "www.t.me",
            "www2.fundsforngos.org", "fundsforngos.org",
        }:
            continue
        try:
            response = requests.get(
                url, headers={"User-Agent": "NGOGrantsPublisher/1.0"}, timeout=25
            )
            response.raise_for_status()
            if len(response.content) > 5_000_000:
                continue
            soup = BeautifulSoup(response.content, "html.parser")
            for selector in ('meta[property="og:image"]', 'meta[name="twitter:image"]'):
                tag = soup.select_one(selector)
                if not tag or not tag.get("content"):
                    continue
                candidate = urljoin(response.url, tag["content"])
                if any(word in candidate.lower() for word in ("logo", "favicon", "avatar", "sprite")):
                    continue
                return download_image(candidate), {
                    "type": "website", "page_url": response.url, "image_url": candidate
                }
        except Exception:
            continue
    return None, None

async def telegram_images(posts):
    client = TelegramClient(
        StringSession(os.environ["TELEGRAM_SESSION"].strip()),
        int(os.environ["TELEGRAM_API_ID"]),
        os.environ["TELEGRAM_API_HASH"].strip(), receive_updates=False,
    )
    images = {}
    try:
        await client.connect()
        if not await client.is_user_authorized():
            raise RuntimeError("Сесія Telegram не авторизована")
        channel = await client.get_entity("ngo_grants")
        for post in posts:
            message = await client.get_messages(channel, ids=post["telegram_message_id"])
            if message and message.photo:
                content = await client.download_media(message, file=bytes)
                with Image.open(io.BytesIO(content)) as image:
                    image.load()
                    images[post["rank"]] = image.convert("RGB")
    finally:
        await client.disconnect()
    return images

def preserve_banner(image, path):
    canvas = Image.new("RGB", (1080, 1080), (13, 48, 53))
    fitted = ImageOps.contain(image, (1040, 950))
    canvas.paste(fitted, ((1080 - fitted.width) // 2, (950 - fitted.height) // 2))
    ImageDraw.Draw(canvas).text(
        (50, 995), "NGO Grants", font=load_font(36, True), fill=(244, 197, 92)
    )
    canvas.save(path, quality=95)

def short_reel_title(title):
    title = re.sub(r"[^\w\s.,:;!?()'’«»/—–+\-€$]", "", title).strip()
    words = title.split()
    result = " ".join(words[:18])
    return result + ("…" if len(words) > 18 else "")

def reel_description(post):
    # Copy source facts only; never infer a missing amount or deadline.
    lines = [line.strip() for line in post["text"].splitlines() if line.strip()]
    selected = [short_reel_title(post["title"])]
    for line in lines[1:]:
        if (not line.startswith(("#", "http", "•", "🔗", "📲"))
                and len(line) <= 260 and "дедлайн: заявок" not in line.lower()):
            selected.append(line)
            break
    for keyword in ("фінансування:", "дедлайн:", "хто може", "українці можуть", "українські фотографи"):
        for line in lines[1:]:
            if keyword in line.lower() and len(line) <= 180 and line not in selected:
                if "дедлайн: заявок" not in line.lower():
                    selected.append(line)
                break
    body = "\n\n".join(selected)
    if len(body) > 650:
        body = body[:647].rsplit(" ", 1)[0] + "…"
    return (body + "\n\n📖 Деталі та умови: " + post["telegram_url"]
            + "\n\n📲 Більше можливостей у Telegram:\nhttps://t.me/ngo_grants")

REEL_TELEGRAM_BANNER = "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"

def make_reel(post):
    frame = Image.new("RGB", (720, 1280), (13, 48, 53))
    draw = ImageDraw.Draw(frame)
    title = short_reel_title(post["title"])
    for size in range(36, 23, -2):
        font = load_font(size, True)
        lines = wrap_title(draw, title, font, 600)
        if len(lines) <= 4:
            break
    y = 100
    for line in lines:
        draw.text((40, y), line, font=font, fill="white")
        y += size + 10
    image_top = max(y + 30, 300)
    # Reserve a fixed footer area so a long headline cannot overlap the banner.
    with Image.open(OUTPUT / post["image_file"]) as source:
        fitted = ImageOps.contain(source.convert("RGB"), (620, 960 - image_top))
    frame.paste(fitted, ((720 - fitted.width) // 2, image_top))
    with Image.open(io.BytesIO(base64.b64decode(REEL_TELEGRAM_BANNER))) as source:
        banner = ImageOps.contain(source.convert("RGB"), (560, 255))
    frame.paste(banner, (40, 980))
    (OUTPUT / "reel-description.txt").write_text(reel_description(post), encoding="utf-8")
    frame.save(OUTPUT / "reel-frame.jpg", quality=95)
    video = OUTPUT / "reel.mp4"
    subprocess.run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-loop", "1", "-framerate", "30", "-i", str(OUTPUT / "reel-frame.jpg"),
        "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-t", "12",
        "-vf", "fade=t=in:st=0:d=0.5,fade=t=out:st=11.5:d=0.5",
        "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-movflags", "+faststart", "-shortest", str(video),
    ], check=True)
    return video

def recent_items(edge, fields):
    # Read-only preflight. Abort if it fails instead of risking duplicate posts.
    result = graph("GET", PAGE + "/" + edge, {"fields": fields, "limit": "100"})
    return result.get("data", [])

def publish_reel(video, post):
    result = graph("POST", PAGE + "/video_reels", {"upload_phase": "start"})
    video_id = str(result["video_id"])
    upload_url = result["upload_url"]
    parsed = urlparse(upload_url)
    if parsed.scheme != "https" or parsed.hostname != "rupload.facebook.com":
        raise RuntimeError("Неочікувана адреса завантаження Meta")
    REPORT["reel"] = {"video_id": video_id, "stage": "created"}
    checkpoint()
    with video.open("rb") as stream:
        response = requests.post(
            upload_url, headers={
                "Authorization": f"OAuth {FB_TOKEN}", "offset": "0",
                "file_size": str(video.stat().st_size),
                "Content-Type": "application/octet-stream",
            }, data=stream, timeout=180, allow_redirects=False,
        )
    if not api_result(response, "Meta upload").get("success"):
        raise RuntimeError("Meta не підтвердила завантаження рілз")
    REPORT["reel"]["stage"] = "uploaded"
    checkpoint()
    finished = graph("POST", PAGE + "/video_reels", {
        "upload_phase": "finish", "video_id": video_id,
        "video_state": "PUBLISHED", "title": post["title"][:200],
        "description": reel_description(post),
    })
    if not finished.get("success"):
        raise RuntimeError("Meta не підтвердила запит публікації рілз")
    REPORT["reel"]["stage"] = "publication_requested"
    checkpoint()
    print(f"Запит публікації рілз прийнято. ID: {video_id}", flush=True)
    for attempt in range(18):
        status = graph("GET", video_id, {"fields": "status"}).get("status") or {}
        REPORT["reel"]["status"] = status
        checkpoint()
        print("Стан рілз:", json.dumps(status, ensure_ascii=False), flush=True)
        if (status.get("publishing_phase") or {}).get("status") == "complete":
            REPORT["reel"]["stage"] = "published"
            checkpoint()
            print("Рілз опубліковано")
            return
        if status.get("video_status") == "error" or any(
            (status.get(phase) or {}).get("status") == "error"
            for phase in ("uploading_phase", "processing_phase", "publishing_phase")
        ):
            raise RuntimeError("Meta повідомила про помилку обробки рілз")
        time.sleep(10)
    raise RuntimeError("Meta не підтвердила завершення публікації рілз за 3 хвилини; перевірте статус перед повторним запуском")

def main():
    checkpoint()
    page = graph("GET", "me", {"fields": "id,name"})
    if str(page.get("id")) != PAGE:
        raise RuntimeError("Токен належить іншій сторінці")
    print("Сторінка:", page.get("name"), flush=True)
    day, count, posts = asyncio.run(select_posts())
    if not posts:
        REPORT["stage"] = "no_posts"
        checkpoint()
        print("За попередній день немає дописів; публікацію пропущено")
        return
    REPORT["selection_date"] = str(day)
    REPORT["candidate_count"] = count
    print(f"Дата: {day}; кандидатів: {count}; відібрано: {len(posts)}", flush=True)

    existing_posts = recent_items("posts", "id,message")
    existing_videos = recent_items("videos", "id,description")
    if os.environ.get("PUBLISH_TO_FACEBOOK", "true").lower() == "true" and all(
        any(post["telegram_url"] in (item.get("message") or "") for item in existing_posts)
        for post in posts
    ) and any(posts[0]["telegram_url"] in (item.get("description") or "") for item in existing_videos):
        REPORT["stage"] = "already_published"
        checkpoint()
        print("Усі дописи та рілз уже опубліковані; повторний запуск пропущено", flush=True)
        return
    photos = asyncio.run(telegram_images(posts))
    for post in posts:
        print(f"Підготовка зображення {post['rank']}", flush=True)
        image, source = website_banner(post["text"])
        if image is None and post["rank"] in photos:
            image = photos[post["rank"]]
            source = {"type": "telegram"}
        path = OUTPUT / post["image_file"]
        if image is None:
            image = generate_image(post["title"])
            source = {"type": "generated"}
            brand_image(image, post["title"], path)
        else:
            preserve_banner(image, path)
        post["image_source"] = source
        (OUTPUT / f"post-{post['rank']}.txt").write_text(post["text"], encoding="utf-8")
        print("Джерело зображення:", source["type"], flush=True)
    save_json(OUTPUT / "manifest.json", {"selection_date": str(day), "posts": posts})
    video = make_reel(posts[0])
    if os.environ.get("PUBLISH_TO_FACEBOOK", "true").lower() != "true":
        REPORT["stage"] = "preview_ready"
        REPORT["duplicate_posts"] = sum(any(post["telegram_url"] in (item.get("message") or "") for item in existing_posts) for post in posts)
        REPORT["duplicate_reel"] = any(posts[0]["telegram_url"] in (item.get("description") or "") for item in existing_videos)
        checkpoint()
        print("Перевірку завершено. У Facebook нічого не опубліковано.")
        print("Уже існує дописів:", REPORT["duplicate_posts"], "рілз:", REPORT["duplicate_reel"])
        return
    for post in posts:
        old = next((item for item in existing_posts
                    if post["telegram_url"] in (item.get("message") or "")), None)
        if old:
            entry = {"rank": post["rank"], "post_id": old["id"], "stage": "already_exists"}
        else:
            with (OUTPUT / post["image_file"]).open("rb") as stream:
                result = graph("POST", PAGE + "/photos", {
                    "caption": post["text"] + "\n\n" + post["telegram_url"],
                    "published": "true",
                }, files={"source": (post["image_file"], stream, "image/jpeg")})
            if not result.get("id"):
                raise RuntimeError("Meta не повернула ID публікації")
            entry = {"rank": post["rank"], "photo_id": result["id"],
                     "post_id": result.get("post_id"), "stage": "created"}
        REPORT["posts"].append(entry)
        checkpoint()
        print("Допис:", json.dumps(entry, ensure_ascii=False), flush=True)
    old_reel = next((item for item in existing_videos
                     if posts[0]["telegram_url"] in (item.get("description") or "")), None)
    if old_reel:
        REPORT["reel"] = {"video_id": old_reel["id"], "stage": "already_exists"}
        checkpoint()
        print("Відео з цього допису вже існує, повторну публікацію пропущено")
    else:
        publish_reel(video, posts[0])
    print("Повний запуск завершено. Перевірте видимість дописів і рілз у Facebook.")

if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        REPORT["error_type"] = type(error).__name__
        checkpoint()
        print(str(error) if isinstance(error, RuntimeError) else type(error).__name__, flush=True)
        raise SystemExit(1)
