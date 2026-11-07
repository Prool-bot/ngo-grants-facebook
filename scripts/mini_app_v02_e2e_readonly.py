"""Read-only acceptance of the running NGO Grants Mini App and actual D1 queue.

No chat messages, Telegram updates, D1 changes or PDF publication.
Cloudflare's private JS is fetched in-memory and only written to runner temp
(0600), never into the repository or upload artifacts. Do not print user data.
"""
from __future__ import annotations
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

SCRIPT="ngo-grants-instant-bot"
APPROVED_VERSION="fa75cc54-47eb-41c9-b0f1-7522b62ff59a"
REQUIRED_BINDINGS={
    "AI":"ai","BOT_TOKEN":"secret_text","DB":"d1",
    "SYNC_SECRET":"secret_text","WEBHOOK_SECRET":"secret_text"
}

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"worker"))
from build_mini_app_candidate import extract_js,MAX_BYTES


def get(url, headers, max_bytes=100000):
    req=urllib.request.Request(url,method="GET",headers=headers)
    try:
        with urllib.request.urlopen(req,timeout=35) as resp:
            body=resp.read(max_bytes+1)
            if len(body)>max_bytes:
                raise RuntimeError("Unexpected API response size")
            return resp.status,resp.headers,body
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Read-only GET HTTP {e.code}") from None
    except (urllib.error.URLError,OSError,TimeoutError) as e:
        raise RuntimeError(f"Read-only GET failed ({type(e).__name__})") from None


def cf_result(url,token):
    status,headers,body=get(url,{
        "Authorization":"Bearer "+token,"Accept":"application/json",
        "User-Agent":"NGO-Grants-MiniApp-E2E-ReadOnly/1.0"
    })
    parsed=json.loads(body)
    if status!=200 or parsed.get("success") is not True:
        raise RuntimeError("Invalid Cloudflare metadata response")
    return parsed.get("result") or {}


def main():
    if len(sys.argv)!=2:
        raise RuntimeError("Expected runner-temp output path")
    if os.getenv("GITHUB_ACTIONS")!="true" or os.getenv("GITHUB_REF")!="refs/heads/main":
        raise RuntimeError("Read-only E2E audit allowed on GitHub main only")
    gateway=os.getenv("NGO_BOT_GATEWAY_URL","").rstrip("/")
    secret=os.getenv("NGO_BOT_SYNC_SECRET","")
    account=(os.getenv("CF_WORKER_ACCOUNT_ID") or os.getenv("CF_ACCOUNT_ID") or "").strip()
    cf_token=os.getenv("CF_WORKER_API_TOKEN","")
    if (not gateway.startswith("https://") or ".workers.dev" not in gateway or
        not secret or not account or not cf_token):
        raise RuntimeError("Read-only audit credentials not configured")

    status,header,body=get(gateway+"/health",{
        "Accept":"application/json","User-Agent":"NGO-Grants-MiniApp-E2E-ReadOnly/1.0"
    })
    health=json.loads(body)
    if status!=200 or health.get("ok") is not True or health.get("menu_version")!="5.8":
        raise RuntimeError("Legacy v5.8 health smoke failed")
    print("LIVE_MENU_HEALTH_OK=5.8")

    status,header,body=get(gateway+"/mini-app",{
        "Accept":"text/html","User-Agent":"NGO-Grants-MiniApp-E2E-ReadOnly/1.0"
    })
    html=body.decode("utf-8")
    if (status!=200 or header.get("X-Ngo-Mini-App-Version")!="0.2" or
        "data-native-send=\"true\"" not in html or
        "const explicitNext=" not in html or
        "ngo-grants-miniapp-v1" not in html):
        raise RuntimeError("Live Mini App v0.2 lacks required form/submit path")
    print("LIVE_MINI_APP_GET_OK=0.2")

    status,header,body=get(gateway+"/internal/pending",{
        "Authorization":"Bearer "+secret,
        "User-Agent":"NGO-Grants-Healthcheck/1.0",
        "Accept":"application/json"
    })
    pending=json.loads(body)
    queue=pending.get("requests")
    if status!=200 or not isinstance(queue,list):
        raise RuntimeError("Private pending read-only endpoint mismatch")
    # NEVER print the requests, topics, Telegram users, timestamps or IDs.
    print("REAL_PENDING_QUEUE_COUNT="+str(len(queue)))

    state_path=Path("ai_catalogs/state.json")
    if state_path.exists():
        state=json.loads(state_path.read_text("utf-8"))
        print("GITHUB_QUEUE_COUNT="+str(len(state.get("queue") or [])))
        print("GITHUB_PUBLISHED_COUNT="+str(len(state.get("published") or [])))

    base="https://api.cloudflare.com/client/v4/accounts/"+account
    d=cf_result(base+"/workers/scripts/"+SCRIPT+"/deployments",cf_token)
    active=(d.get("deployments") or [None])[0]
    versions=active.get("versions") if active else []
    if (len(versions or [])!=1 or versions[0].get("percentage")!=100 or
        versions[0].get("version_id")!=APPROVED_VERSION):
        raise RuntimeError("Current active Worker is not approved Mini App v0.2 version")
    metadata=cf_result(base+"/workers/scripts/"+SCRIPT+"/versions/"+APPROVED_VERSION,cf_token)
    actual={b.get("name"):b.get("type")
            for b in (metadata.get("resources") or {}).get("bindings") or []}
    if actual!=REQUIRED_BINDINGS:
        raise RuntimeError("Live Worker bindings drifted")
    print("LIVE_CLOUDFLARE_DEPLOYMENT_OK")
    print("LIVE_BINDINGS_MATCH_KNOWN_FIVE=True")

    status,headers,body=get(base+"/workers/scripts/"+SCRIPT,{
        "Authorization":"Bearer "+cf_token,
        "Accept":"application/javascript,multipart/form-data",
        "User-Agent":"NGO-Grants-MiniApp-E2E-ReadOnly/1.0"
    },MAX_BYTES)
    source=extract_js(headers.get("Content-Type",""),body)
    if not all(marker in source for marker in (
       "NGO_GRANTS_NATIVE_MINI_APP_V01","NGO_MINI_APP_NAV_FIX_V02",
       "menu_version:'5.8'","async function handleTelegram")):
        raise RuntimeError("Cloudflare script does not match active v0.2 bridge")
    target=Path(sys.argv[1]).resolve()
    temp=Path(os.getenv("RUNNER_TEMP","/tmp")).resolve()
    if not str(target).startswith(str(temp)+"/"):
        raise RuntimeError("Private Worker candidate outside runner temp")
    fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,"w",encoding="utf-8") as file:
        file.write(source)
    print("WORKER_PRIVATE_SOURCE_AVAILABLE_FOR_OFFLINE_SIMULATION_ONLY")
    return 0


if __name__=="__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from None
