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

def make_reel(post):
    frame = Image.new("RGB", (720, 1280), (13, 48, 53))
    draw = ImageDraw.Draw(frame)
    title = re.sub(r"[^\w\s.,:;!?()'’«»/—–+\-]", "", post["title"]).strip()
    for size in range(34, 15, -2):
        font = load_font(size, True)
        lines = wrap_title(draw, title, font, 640)
        if len(lines) <= 5:
            break
    y = 100
    for line in lines:
        draw.text((40, y), line, font=font, fill="white")
        y += size + 10
    with Image.open(OUTPUT / post["image_file"]) as source:
        fitted = ImageOps.contain(source.convert("RGB"), (680, 720))
    frame.paste(fitted, ((720 - fitted.width) // 2, max(y + 30, 380)))
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
        "description": post["text"] + "\n\n" + post["telegram_url"],
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
    print("Рілз ще обробляється; перевірте його у Facebook пізніше.")

def main():
    checkpoint()
    page = graph("GET", "me", {"fields": "id,name"})
    if str(page.get("id")) != PAGE:
        raise RuntimeError("Токен належить іншій сторінці")
    print("Сторінка:", page.get("name"), flush=True)
    day, count, posts = asyncio.run(select_posts())
    if not posts:
        raise RuntimeError("За попередній день немає дописів")
    REPORT["selection_date"] = str(day)
    REPORT["candidate_count"] = count
    print(f"Дата: {day}; кандидатів: {count}; відібрано: {len(posts)}", flush=True)

    existing_posts = recent_items("posts", "id,message")
    existing_videos = recent_items("videos", "id,description")
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
