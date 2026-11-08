"""Read-only 0.01% canary verification of staged, *hard-disabled* v0.5 API.

Temporary deployment split is ALWAYS restored to the previously approved
v0.4 Worker. No catalog orders, D1 writes, Telegram messages or DM delivery.
"""
from __future__ import annotations
import json
import os
import sys
import time
import urllib.error
import urllib.request

from deploy_worker_mini_app_fop_v04 import api,deploy,health,forbidden,mini_app_smoke,SCRIPT

OLD="d891323d-c8ca-4898-8ff4-ce5bc7e4b053"
CANDIDATE="c9dbb626-4f6c-4c31-96a7-73332bbf7e08"
EXPECTED={"AI":"ai","BOT_TOKEN":"secret_text","DB":"d1",
          "SYNC_SECRET":"secret_text","WEBHOOK_SECRET":"secret_text"}
APP_URL="/mini-app/direct"
POST_PATH="/api/mini-app/order"

def request(gateway,path,version=None,method="GET",payload=None):
    if method not in ("GET","POST"):raise RuntimeError("Unknown safe canary verb")
    headers={"accept":"text/html,application/json",
             "user-agent":"NGOGrantsDirectMiniAppCanary/1.0",
             "cache-control":"no-store"}
    if version:
        headers["Cloudflare-Workers-Version-Overrides"]=f'{SCRIPT}="{version}"'
    if method=="POST":
        if path!=POST_PATH or payload!=b"{}":
            raise RuntimeError("Only one inert disabled-API POST is allowed")
        headers["content-type"]="application/json"
    req=urllib.request.Request(gateway.rstrip("/")+path,method=method,
                               headers=headers,data=payload)
    try:
        with urllib.request.urlopen(req,timeout=25) as response:
            return response.status,response.headers,response.read(250000)
    except urllib.error.HTTPError as exc:
        # 503 expected for the disabled route, 404 for old route.
        if exc.code not in (404,503):
            raise RuntimeError("Unanticipated canary HTTP "+str(exc.code)) from None
        return exc.code,exc.headers,exc.read(250000)
    except (OSError,urllib.error.URLError,TimeoutError) as exc:
        raise RuntimeError("Read-only canary request failed ("+type(exc).__name__+")") from None

def inspect_version(gateway,version):
    status,headers,body=request(gateway,APP_URL,version)
    html=body.decode("utf-8","replace")
    if (status!=200 or headers.get("x-ngo-mini-app-direct-version")!="0.5-stage" or
        'data-native-send="false" data-direct-send="true"' not in html or
        "telegram-web-app.js" not in html or
        "ngo-grants-miniapp" not in html.lower()):
        raise RuntimeError("Staged v0.5 direct UI missing or not enabled for Telegram")
    status,headers,body=request(gateway,POST_PATH,version,"POST",b"{}")
    if status!=503:
        raise RuntimeError("Dormant v0.5 API unexpectedly accepts public writes")
    try:result=json.loads(body)
    except ValueError:raise RuntimeError("Dormant v0.5 refusal was not JSON") from None
    if result.get("ok") is not False or result.get("error")!="Not enabled":
        raise RuntimeError("Dormant v0.5 API refusal contract changed")
    print("STAGED_DIRECT_MINI_APP_HTML_OK")
    print("STAGED_DIRECT_ORDER_POST_HARD_DISABLED_503")
    return True

def main():
    if (os.getenv("GITHUB_ACTIONS")!="true" or
        os.getenv("GITHUB_REF")!="refs/heads/main" or
        os.getenv("MINI_APP_V05_CANARY_APPROVED")!="YES_DISABLED_001_WITH_ROLLBACK"):
        raise RuntimeError("Strict read-only canary authorization missing")
    gateway=os.getenv("NGO_BOT_GATEWAY_URL","").rstrip("/")
    if not gateway.startswith("https://") or ".workers.dev" not in gateway:
        raise RuntimeError("Verified production Worker origin missing")
    current=api("/workers/scripts/"+SCRIPT+"/deployments")
    deployments=current.get("deployments") or []
    old=deployments[0].get("versions") if deployments else []
    if (len(old or [])!=1 or old[0].get("percentage")!=100 or
        old[0].get("version_id")!=OLD):
        raise RuntimeError("Active production version drifted; canary aborted")
    check=api("/workers/scripts/"+SCRIPT+"/versions/"+CANDIDATE)
    actual={b.get("name"):b.get("type")
            for b in (check.get("resources") or {}).get("bindings") or []}
    if actual!=EXPECTED:
        raise RuntimeError("Staged v0.5 must inherit exactly five existing bindings")
    if health(gateway).get("menu_version")!="5.8" or not forbidden(gateway):
        raise RuntimeError("Original Worker baseline failed")
    print("PRE_CANARY_ACTIVE_V04_AND_FIVE_BINDINGS_VERIFIED")

    traffic_attempted=False
    try:
        traffic_attempted=True
        deploy([(OLD,99.99),(CANDIDATE,0.01)],
               "One-time disabled direct Mini App v0.5 0.01% GET/503 smoke only")
        time.sleep(3)
        if health(gateway,CANDIDATE).get("menu_version")!="5.8" or not forbidden(gateway,CANDIDATE):
            raise RuntimeError("Candidate regression in legacy menu or auth")
        mini_app_smoke(gateway,CANDIDATE)  # Original keyboard UI remains v0.4.
        inspect_version(gateway,CANDIDATE)
    finally:
        if traffic_attempted:
            try:
                deploy([(OLD,100)],
                       "Restore original v0.4 after read-only direct Mini App 0.01% smoke")
                print("RESTORED_PREVIOUS_PRODUCTION_VERSION_100_PERCENT")
            except BaseException:
                print("CRITICAL_ROLLBACK_FAILED_CHECK_CLOUDFLARE_IMMEDIATELY")
                raise
    time.sleep(2)
    if health(gateway).get("menu_version")!="5.8" or not forbidden(gateway):
        raise RuntimeError("Original Worker failed after mandatory rollback")
    mini_app_smoke(gateway)
    status,_,_=request(gateway,APP_URL)
    if status!=404:
        raise RuntimeError("Production accidentally exposed dormant direct Mini App")
    print("PRODUCTION_V04_100_PERCENT_RESTORED_CONFIRMED")
    print("NO_REAL_D1_WRITES;NO_REAL_TELEGRAM_SENDS;NO_CATALOG_ORDERS")
    return 0

if __name__=="__main__":
    try:raise SystemExit(main())
    except RuntimeError as error:raise SystemExit(str(error)) from None
