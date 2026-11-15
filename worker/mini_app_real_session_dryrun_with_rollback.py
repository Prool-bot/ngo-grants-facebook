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

PATH="/_internal/miniapp/signed-dryrun"

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
    base=os.environ["NGO_BOT_SYNC_SECRET"]
    facets={"audience":"nonprofit","sectors":["social","recovery"],
        "custom_sector":"","geo":"ukraine","region":"",
        "detail":"Суспільно корисні ініціативи",
        "applicant_role":"lead","funding_format":"any"}
    packet={"initData":init_data,"facets":facets,
            "idempotencyKey":str(uuid.uuid4())}
    request=urllib.request.Request(gateway+PATH,method="POST",headers={
      "authorization":"Bearer "+base,
      "Cloudflare-Workers-Version-Overrides":f'{SCRIPT}="{version}"',
      "content-type":"application/json","accept":"application/json",
      "user-agent":"NGOGrantsSafeSignedPreflight/1.0",
      "cache-control":"no-store"
    },data=json.dumps(packet,ensure_ascii=False).encode("utf-8"))
    try:
        with urllib.request.urlopen(request,timeout=25) as response:
            if response.status!=200 or response.headers.get("x-ngo-miniapp-dryrun")!="no-writes":
                raise RuntimeError("Temporary authorized Worker version override did not match")
            result=json.loads(response.read(1500).decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise RuntimeError("Authenticated dryrun endpoint HTTP "+str(e.code)) from None
    if result.get("ok") is not True or result.get("kind")!="dryrun-no-writes":
        raise RuntimeError("Unexpected preflight response shape")
    phase=result.get("phase")
    allow={"CONFIG","D1_READ","QUEUE_NO_COMMIT","TELEGRAM_UPSTREAM",
           "AUTH","FACETS","NOT_SUBSCRIBED","DAILY_LIMIT","CONFLICT",
           "UNKNOWN","EXISTING"}
    if phase not in allow:raise RuntimeError("Unexpected safe diagnostic category")
    print("REAL_TELEGRAM_SIGNED_MAIN_MINI_APP_PREFLIGHT_STAGE="+phase)
    print("REAL_TELEGRAM_SIGNED_MAIN_MINI_APP_PREFLIGHT_HTTP="+str(result.get("http_status")))
    print("REAL_USER_ACCOUNT_ID_AND_AUTH_DATA_NOT_LOGGED=True")
    print("NO_CLOUD_DB_WRITES_OR_NEW_CATALOG_ORDERS=True")

async def main():
    if (os.getenv("GITHUB_ACTIONS")!="true" or
        os.getenv("GITHUB_REF")!="refs/heads/main" or
        os.getenv("GITHUB_REPOSITORY")!="Prool-bot/ngo-grants-facebook" or
        os.getenv("NGO_SIGNED_MINI_APP_DRYRUN_APPROVED")!="YES_READ_ONLY_CANARY_AND_ROLLBACK"):
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
               "Temporary 0.01% signed Main Mini App preflight: no writes, rollback always")
        time.sleep(3)
        if health(gateway,version).get("menu_version")!="5.8" or not forbidden(gateway,version):
            raise RuntimeError("Canary old bot regression")
        inspect(gateway,version)
        invoke(gateway,version,init_data)
    finally:
        if switched:
            deploy([(original,100)],
                   "Restore exact 100% v0.5.2 Worker after no-write Main Mini App preflight")
            print("RESTORED_MAIN_MINI_APP_PRODUCTION_100_PERCENT=True")
    time.sleep(2)
    if health(gateway).get("menu_version")!="5.8" or not forbidden(gateway):
        raise RuntimeError("Post-preflight bot regression")
    inspect(gateway)
    print("SAFE_PREFLIGHT_COMPLETE_WITHOUT_REAL_ORDERS=True")
if __name__=="__main__":
    try:asyncio.run(main())
    except RuntimeError as e:raise SystemExit(str(e)) from None
