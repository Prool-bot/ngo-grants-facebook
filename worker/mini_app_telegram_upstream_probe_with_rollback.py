"""Real Telegram-signed Main Mini App, write-free Cloudflare preflight canary.

Uses existing authorized Telethon session to generate *genuine* Telegram initData.
No sends, bot settings edits, order creation, D1 mutation, identifying output,
or requests to public order endpoint. Stage worker injects hard stop before
createRequest. 0.01% temporary canary is always rolled back in finally.
"""
from __future__ import annotations
import asyncio,json,os,re,time,urllib.error,urllib.parse,urllib.request,uuid
from pathlib import Path
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.functions.messages import RequestMainWebViewRequest
from telethon.tl.types import InputPeerEmpty,InputUser

from deploy_worker_mini_app_fop_v04 import api,deploy,health,forbidden,mini_app_smoke,SCRIPT
from release_mini_app_direct_v05_active import inspect,EXPECTED
from mini_app_expected_worker_version import expected_version
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from mini_app_verify_init_data_offline import verify
from mini_app_public_preflight import telegram

PATH="/_internal/miniapp/telegram-upstream-probe"

async def real_signed_init_data()->str:
    token=os.environ["NGO_GRANTS_AI_BOT_TOKEN"].strip()
    ident=telegram("getMe",token=token)
    if ident.get("username")!="ngogratsAI_bot" or ident.get("has_main_web_app") is not True:
        raise RuntimeError("Verified Telegram Main Mini App not available")
    async with TelegramClient(StringSession(os.environ["TELEGRAM_SESSION"].strip()),
           int(os.environ["TELEGRAM_API_ID"]),os.environ["TELEGRAM_API_HASH"].strip(),
           receive_updates=False) as client:
        if not await client.is_user_authorized():
            raise RuntimeError("Authorized session absent")
        bot=await client.get_input_entity("@ngogratsAI_bot")
        result=await client(RequestMainWebViewRequest(peer=InputPeerEmpty(),
                  bot=InputUser(bot.user_id,bot.access_hash),
                  platform="desktop",start_param="ngo_grants"))
        url=urllib.parse.urlsplit(result.url)
        fields=urllib.parse.parse_qs(url.fragment or url.query)
        data=(fields.get("tgWebAppData") or [""])[0]
        if not data or not verify(data,token):
            raise RuntimeError("Genuine signed Telegram data failed verification")
        return data

def get_stage_version():
    staged=json.loads((Path(os.environ["RUNNER_TEMP"])/"ngo-worker-miniapp-stage.json").read_text("utf-8"))
    version=staged.get("version_id")
    if (staged.get("script")!=SCRIPT or staged.get("staged_only") is not True or
        not isinstance(version,str) or not re.fullmatch(r"[a-f0-9-]{36}",version)):
        raise RuntimeError("Unknown staged Worker source")
    return version

def invoke(gateway,version,init_data):
    secret=os.environ["NGO_BOT_SYNC_SECRET"]
    packet={"initData":init_data}
    request=urllib.request.Request(gateway+PATH,method="POST",headers={
      "authorization":"Bearer "+secret,
      "Cloudflare-Workers-Version-Overrides":f'{SCRIPT}="{version}"',
      "content-type":"application/json","accept":"application/json",
      "user-agent":"NGOGrantsTelegramUpstreamSafeProbe/1.0",
      "cache-control":"no-store"
    },data=json.dumps(packet).encode("utf-8"))
    try:
        with urllib.request.urlopen(request,timeout=30) as response:
            if response.status!=200 or response.headers.get("x-miniapp-telegram-methods")!="read-only":
                raise RuntimeError("Authenticated temporary method probe override failed")
            result=json.loads(response.read(3200).decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError("Temporary method probe refused HTTP "+str(exc.code)) from None
    if result.get("ok") is not True or result.get("kind")!="telegram-methods":
        raise RuntimeError("Unexpected safe Bot API probe response")
    entries=result.get("results")
    if not isinstance(entries,list) or len(entries)!=3:
        raise RuntimeError("Missing Telegram API method observations")
    valid={"MEMBER_VALID","NETWORK_EXCEPTION","BODY_OR_USER_MISMATCH",
           "BOT_API_DENIAL","UNEXPECTED"}
    for item in entries:
        method=item.get("kind");state=item.get("stage")
        if method not in {"POST_REDIRECT_ERROR","POST_DEFAULT","GET_QUERY"} or state not in valid:
            raise RuntimeError("Unexpected sanitized Telegram probe state")
        print("WORKER_TELEGRAM_METHOD_"+method+"="+state)
        if isinstance(item.get("http"),int):
            print("WORKER_TELEGRAM_HTTP_"+method+"="+str(item["http"]))
        if isinstance(item.get("bot_error_code"),int):
            print("WORKER_TELEGRAM_API_ERROR_"+method+"="+str(item["bot_error_code"]))
        if item.get("status") in {"creator","administrator","member","restricted","left","kicked"}:
            print("WORKER_TELEGRAM_MEMBERSHIP_"+method+"="+item["status"])
    print("NO_USER_ID_AUTH_DATA_OR_BOT_TOKEN_LOGGED=True")
    print("NO_CLOUD_DB_WRITES_OR_NEW_CATALOG_ORDERS=True")

async def main():
    if (os.getenv("GITHUB_ACTIONS")!="true" or
        os.getenv("GITHUB_REF")!="refs/heads/main" or
        os.getenv("GITHUB_REPOSITORY")!="Prool-bot/ngo-grants-facebook" or
        os.getenv("NGO_TELEGRAM_UPSTREAM_METHOD_PROBE_APPROVED")!="YES_TRIPLE_READONLY_MEMBER_METHODS"):
        raise RuntimeError("Safe Main Mini App preflight not approved")
    gateway=(os.environ.get("NGO_BOT_GATEWAY_URL") or "").rstrip("/")
    if not gateway.startswith("https://") or ".workers.dev" not in gateway:
        raise RuntimeError("Approved Worker URL missing")
    original=expected_version()
    version=get_stage_version()
    if version==original:raise RuntimeError("Preflight stage cannot equal production")
    live=(api("/workers/scripts/"+SCRIPT+"/deployments").get("deployments") or [{}])[0].get("versions") or []
    if len(live)!=1 or live[0].get("percentage")!=100 or live[0].get("version_id")!=original:
        raise RuntimeError("Live Worker not on approved baseline")
    config=api("/workers/scripts/"+SCRIPT+"/versions/"+version)
    bind={x.get("name"):x.get("type") for x in (config.get("resources") or {}).get("bindings") or []}
    if bind!=EXPECTED:raise RuntimeError("Staged bindings mismatch")
    if health(gateway).get("menu_version")!="5.8" or not forbidden(gateway):
        raise RuntimeError("Existing production bot health failed")
    inspect(gateway)
    init_data=await real_signed_init_data() # read-only user-authorized Telegram call
    switched=False
    try:
        switched=True
        deploy([(original,99.99),(version,0.01)],
               "Temporary 0.01% read-only Telegram Bot API method check with rollback")
        time.sleep(3)
        if health(gateway,version).get("menu_version")!="5.8" or not forbidden(gateway,version):
            raise RuntimeError("Canary old bot regression")
        inspect(gateway,version)
        invoke(gateway,version,init_data)
    finally:
        if switched:
            deploy([(original,100)],
                   "Restore exact 100% v0.5.2 Worker after read-only Telegram API method probe")
            print("RESTORED_MAIN_MINI_APP_PRODUCTION_100_PERCENT=True")
    time.sleep(2)
    if health(gateway).get("menu_version")!="5.8" or not forbidden(gateway):
        raise RuntimeError("Post-preflight bot regression")
    inspect(gateway)
    print("SAFE_TELEGRAM_METHOD_PROBE_COMPLETE_NO_REAL_ORDERS=True")
if __name__=="__main__":
    try:asyncio.run(main())
    except RuntimeError as e:raise SystemExit(str(e)) from None
