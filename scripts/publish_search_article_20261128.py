"""One explicitly approved article. No changes to pins, commands or catalogs."""
from __future__ import annotations
import base64
import hashlib
import html
import json
import os
import re
from datetime import datetime,timezone
from pathlib import Path
from mini_app_public_preflight import telegram
from mini_app_public_launch import bot_write,github_api

RECORD="launches/how_ngo_grants_works_2026-11-28.json"
CHANNEL="@ngo_grants"
MARKUP={"inline_keyboard":[
    [{"text":"🤖 Знайти гранти в каналі","url":"https://t.me/ngogratsAI_bot?startapp=ngo_grants"}],
    [{"text":"❤️ Підтримати NGO Grants","url":"https://donatello.to/NGO_Grants"}]
]}
ARTICLE=Path(__file__).resolve().parents[1]/"launches/how_ngo_grants_works_2026-11-28.html"

def payload():
    article=ARTICLE.read_text("utf-8").strip()
    plain=html.unescape(re.sub(r"</?b>","",article))
    count=len(plain.encode("utf-16-le"))//2
    if not 1<=count<=4096 or article.count("<b>")!=article.count("</b>") or "<" in re.sub(r"</?b>","",article):
        raise RuntimeError("Invalid Telegram length or HTML")
    if not plain.startswith("ЯК ПРАЦЮЄ NGO GRANTS:") or not plain.endswith("залишався безкоштовним."):
        raise RuntimeError("Article fingerprint changed")
    print("ARTICLE_CHARACTERS="+str(len(plain))+";UTF16="+str(count))
    return {"chat_id":CHANNEL,"text":article,"parse_mode":"HTML","link_preview_options":{"is_disabled":True},
            "disable_notification":True,"reply_markup":MARKUP},plain

def main():
    if (os.getenv("GITHUB_ACTIONS")!="true" or os.getenv("GITHUB_REF")!="refs/heads/main"
        or os.getenv("GITHUB_REPOSITORY")!="Prool-bot/ngo-grants-facebook"
        or os.getenv("NGO_ARTICLE_APPROVED")!="YES_PUBLISH_APPROVED_ARTICLE_20261128_ONCE"):
        raise RuntimeError("Article publication not authorized")
    data,plain=payload()
    token=os.environ["NGO_GRANTS_AI_BOT_TOKEN"].strip()
    bot=telegram("getMe",token=token)
    chat=telegram("getChat",{"chat_id":CHANNEL},token=token)
    if bot.get("username")!="ngogratsAI_bot" or bot.get("has_main_web_app") is not True or chat.get("username")!="ngo_grants" or chat.get("type")!="channel":
        raise RuntimeError("Bot/channel mismatch")
    rights=telegram("getChatMember",{"chat_id":CHANNEL,"user_id":bot["id"]},token=token)
    if rights.get("status")!="creator" and not (rights.get("status")=="administrator" and rights.get("can_post_messages") is True):
        raise RuntimeError("Bot cannot post")
    if github_api("GET","contents/"+RECORD+"?ref=main")[0]!=404:
        raise RuntimeError("Article already attempted; no duplicate post")
    rec={"status":"attempted","channel":CHANNEL,"run_id":os.getenv("GITHUB_RUN_ID"),"characters":len(plain),
         "utf16":len(plain.encode("utf-16-le"))//2,"sha256":hashlib.sha256(plain.encode()).hexdigest(),
         "created_at":datetime.now(timezone.utc).isoformat()}
    def encoded():
        return base64.b64encode(json.dumps(rec,ensure_ascii=False,indent=2).encode()).decode()
    status,response=github_api("PUT","contents/"+RECORD,{"branch":"main","message":"Reserve one-time approved NGO Grants article","content":encoded()})
    sha=(response.get("content") or {}).get("sha")
    if status!=201 or not sha:raise RuntimeError("No durable one-shot lock")
    msg=bot_write("sendMessage",data,token=token)
    mid=msg.get("message_id") if isinstance(msg,dict) else None
    if not isinstance(mid,int) or mid<=0 or msg.get("chat",{}).get("username")!="ngo_grants":
        raise RuntimeError("Send result unverified; no retry")
    rec.update({"status":"posted","message_id":mid,"url":f"https://t.me/ngo_grants/{mid}","published_at":datetime.now(timezone.utc).isoformat(),
                "text_verified":msg.get("text")==plain,
                "buttons_verified":msg.get("reply_markup")==MARKUP,
                "bold_entities":sum(e.get("type")=="bold" for e in msg.get("entities",[]))})
    status,_=github_api("PUT","contents/"+RECORD,{"branch":"main","sha":sha,"message":"Record actual published NGO Grants article","content":encoded()})
    if status!=200:raise RuntimeError("Sent but receipt update failed; no retry")
    print("ARTICLE_PUBLISHED="+rec["url"])
    print("ARTICLE_VERIFICATION="+json.dumps({k:rec[k] for k in ("text_verified","buttons_verified","bold_entities")}))
    if not rec["text_verified"] or not rec["buttons_verified"] or rec["bold_entities"]!=data["text"].count("<b>"):
        raise RuntimeError("Article posted; formatting verification incomplete; no retry")

if __name__=="__main__":
    try:main()
    except RuntimeError as exc:raise SystemExit(str(exc)) from None
