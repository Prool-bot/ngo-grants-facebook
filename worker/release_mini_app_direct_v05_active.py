"""Safely release approved NGO Grants Mini App v0.5 direct API.

0.01% active canary validates signed-session refusals without *ever* creating
test orders. On success, promote to 100% and recheck old + new routes.
Always restore v0.4 if any post-deploy smoke fails.
"""
from __future__ import annotations
import json
import os
import re
import time
import urllib.error
import urllib.request
from deploy_worker_mini_app_fop_v04 import api,deploy,health,forbidden,mini_app_smoke,SCRIPT

OLD="d891323d-c8ca-4898-8ff4-ce5bc7e4b053"
NEW="4b0b8562-d2af-46a5-aa87-8acfb69b2151"
EXPECTED={"AI":"ai","BOT_TOKEN":"secret_text","DB":"d1",
          "SYNC_SECRET":"secret_text","WEBHOOK_SECRET":"secret_text"}
APP_PATH="/mini-app/direct"
ORDER_PATH="/api/mini-app/order"
FAKE_UUID="123e4567-e89b-42d3-a456-426614174000"

def request(gateway,path,version=None,method="GET",body=None,foreign=False):
    if method not in ("GET","POST"):raise RuntimeError("Unsupported release-smoke verb")
    if method=="POST" and path!=ORDER_PATH:
        raise RuntimeError("Unsafe release smoke path")
    headers={"accept":"text/html,application/json",
             "user-agent":"NGOGrantsDirectV05ReleaseSmoke/1.0",
             "cache-control":"no-store"}
    if version:
        headers["Cloudflare-Workers-Version-Overrides"]=f'{SCRIPT}="{version}"'
    if foreign:headers["origin"]="https://unauthorized.invalid"
    if method=="POST":headers["content-type"]="application/json"
    req=urllib.request.Request(gateway.rstrip("/")+path,
        method=method,headers=headers,data=body)
    try:
        with urllib.request.urlopen(req,timeout=25) as response:
            return response.status,response.headers,response.read(250000)
    except urllib.error.HTTPError as exc:
        if exc.code not in (400,401,403,404,405,503):
            raise RuntimeError("Unexpected smoke HTTP "+str(exc.code)) from None
        return exc.code,exc.headers,exc.read(250000)
    except (urllib.error.URLError,TimeoutError,OSError) as exc:
        raise RuntimeError("HTTP smoke network "+type(exc).__name__) from None

def inspect(gateway,version=None):
    status,headers,body=request(gateway,APP_PATH,version)
    page=body.decode("utf-8","replace")
    if (status!=200 or headers.get("x-ngo-mini-app-direct-version")!="0.5-stage" or
        'data-native-send="false" data-direct-send="true"' not in page or
        "telegram-web-app.js" not in page or
        "NGO Grants AI" not in page):
        raise RuntimeError("Active Mini App direct page failed HTML smoke")
    # A valid-looking JSON envelope with INVALID Telegram HMAC is guaranteed
    # to stop before membership or any D1 write. Never sign a real user.
    invalid={
        "initData":"auth_date=1794120000&user=%7B%22id%22%3A23456%7D&hash="+("0"*64),
        "facets":{"audience":"nonprofit","sectors":["social"],"custom_sector":"",
                  "geo":"ukraine","region":"","detail":"synthetic test",
                  "applicant_role":"lead","funding_format":"grant_only"},
        "idempotencyKey":FAKE_UUID
    }
    payload=json.dumps(invalid,ensure_ascii=False).encode("utf-8")
    code,head,raw=request(gateway,ORDER_PATH,version,"POST",payload)
    if code!=401:
        raise RuntimeError("Active direct API did not reject invalid Telegram HMAC")
    try:parsed=json.loads(raw)
    except ValueError:raise RuntimeError("Invalid auth response is not JSON") from None
    if parsed.get("ok") is not False:
        raise RuntimeError("Invalid Telegram session falsely acknowledged as order")
    code,_,_=request(gateway,ORDER_PATH,version,"POST",payload,foreign=True)
    if code!=403:
        raise RuntimeError("Direct order endpoint did not reject cross-origin POST")
    code,_,_=request(gateway,ORDER_PATH,version,"GET")
    if code!=405:
        raise RuntimeError("Direct order endpoint did not enforce POST method")
    print("DIRECT_V05_HTML_OK_SIGNED_HMAC_ENFORCED_401")
    print("DIRECT_V05_CROSS_ORIGIN_DENIED_403_GET_DENIED_405")
    print("REAL_CATALOG_ORDERS_CREATED_IN_CANARY=0")
    return True

def main():
    if (os.getenv("GITHUB_ACTIONS")!="true" or
        os.getenv("GITHUB_REF")!="refs/heads/main" or
        os.getenv("MINI_APP_DIRECT_V05_RELEASE_APPROVED")!="YES_ACTIVATE_SIGNED_V05_CANARY"):
        raise RuntimeError("Explicit signed Mini App v0.5 release gate missing")
    gateway=os.getenv("NGO_BOT_GATEWAY_URL","").rstrip("/")
    if not gateway.startswith("https://") or ".workers.dev" not in gateway:
        raise RuntimeError("Worker HTTPS origin missing")
    current=api("/workers/scripts/"+SCRIPT+"/deployments")
    versions=(current.get("deployments") or [{}])[0].get("versions") or []
    if (len(versions)!=1 or versions[0].get("version_id")!=OLD or
        versions[0].get("percentage")!=100):
        raise RuntimeError("Production Worker changed from approved v0.4")
    candidate=api("/workers/scripts/"+SCRIPT+"/versions/"+NEW)
    actual={b.get("name"):b.get("type")
            for b in (candidate.get("resources") or {}).get("bindings") or []}
    if actual!=EXPECTED:
        raise RuntimeError("Activation candidate D1/secrets bindings drifted")
    if health(gateway).get("menu_version")!="5.8" or not forbidden(gateway):
        raise RuntimeError("Existing Worker auth/menu baseline failed")
    print("V05_RELEASE_BASELINE_V04_AND_BINDINGS_OK")
    switched=False
    try:
        switched=True
        deploy([(OLD,99.99),(NEW,0.01)],
               "Signed Telegram Mini App v0.5 0.01% canary, legacy v0.4 99.99%")
        time.sleep(3)
        if health(gateway,NEW).get("menu_version")!="5.8" or not forbidden(gateway,NEW):
            raise RuntimeError("v0.5 canary broke existing bot health/auth")
        mini_app_smoke(gateway,NEW)
        inspect(gateway,NEW)
        print("DIRECT_V05_CANARY_PASSED")
        deploy([(NEW,100)],
               "Signed direct Mini App v0.5 live; existing Telegram keyboard preserved")
        time.sleep(3)
        if health(gateway).get("menu_version")!="5.8" or not forbidden(gateway):
            raise RuntimeError("v0.5 full release legacy health/auth failed")
        mini_app_smoke(gateway)
        inspect(gateway)
        deployed=api("/workers/scripts/"+SCRIPT+"/deployments")
        check=(deployed.get("deployments") or [{}])[0].get("versions") or []
        if len(check)!=1 or check[0].get("version_id")!=NEW or check[0].get("percentage")!=100:
            raise RuntimeError("Cloudflare full v0.5 traffic share not confirmed")
        print("PRODUCTION_V05_DIRECT_API_100_PERCENT_VERIFIED")
        print("NO_REAL_TELEGRAM_MESSAGES_OR_CATALOG_ORDERS_SENT")
        return 0
    except BaseException:
        if switched:
            try:
                deploy([(OLD,100)],"Automatic rollback to prior NGO Grants v0.4 after v0.5 smoke failure")
                print("PRODUCTION_V04_ROLLBACK_100_PERCENT")
            except BaseException:
                print("CRITICAL_ROLLBACK_FAILURE_MANUAL_CLOUDFLARE_CHECK_REQUIRED")
                raise
        raise

if __name__=="__main__":
    try:raise SystemExit(main())
    except RuntimeError as error:raise SystemExit(str(error)) from None
