"""Canary and rollback for the Mini App v0.5.7 UI-only release.

Makes NO test catalog orders or D1 writes. Existing D1 and Telegram bindings
are inherited from current Worker. A verified public version-ID receipt is
written ONLY AFTER 100% traffic and security checks pass.
"""
from __future__ import annotations

from base64 import b64encode
from datetime import datetime, timezone
import json
import os
import re
import sys
import time
from pathlib import Path

from deploy_worker_mini_app_fop_v04 import api,deploy,health,forbidden,mini_app_smoke,SCRIPT
from release_mini_app_direct_v05_active import inspect,EXPECTED,request
from mini_app_expected_worker_version import expected_version

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from mini_app_public_launch import github_api

APPROVAL="YES_RELEASE_MINI_APP_V057_QUIET_SUPPORT_CANARY"
RECEIPT="launches/mini_app_v057_live_version.json"


def get_active_version() -> str:
    result=api("/workers/scripts/"+SCRIPT+"/deployments")
    active=(result.get("deployments") or [{}])[0].get("versions") or []
    if len(active)!=1 or active[0].get("percentage")!=100:
        raise RuntimeError("Production Worker traffic is already split")
    return active[0].get("version_id")


def staged() -> str:
    temp=Path(os.environ.get("RUNNER_TEMP","/tmp"))
    manifest=json.loads((temp/"ngo-worker-miniapp-stage.json").read_text("utf-8"))
    version=manifest.get("version_id")
    if (manifest.get("script")!=SCRIPT or manifest.get("staged_only") is not True or
        not isinstance(version,str) or
        re.fullmatch(r"[a-f0-9-]{36}",version) is None):
        raise RuntimeError("Cloudflare v0.5.7 staging manifest invalid")
    return version


def check_new_html(gateway: str, version: str | None = None):
    status,headers,raw=request(gateway,"/mini-app/direct",version)
    text=raw.decode("utf-8","replace")
    if (status!=200 or "text/html" not in headers.get("content-type","") or
        not all(anchor in text for anchor in (
            'data-native-send="false" data-direct-send="true"',
            'id="robotArm"',
            'id="robotFigure"',
            'function needsDetail(){',
            "robotFigure.classList.add('hop');",
            "robotArm.classList.add('wave');",
            'translateY(-11px)',
            '@keyframes robot-hop',
            '@keyframes arm-wave',
            'telegram-web-app.js'
        )) or
        'id="greet"' in text):
        raise RuntimeError("Candidate UI must hop and wave on each choice with no greeting button")
    from patch_quiet_support import native_public_html
    for html in (text,native_public_html(gateway,version)):
        if (html.count('id="ngoQuietSupportLink"')!=1 or
            'href="https://donatello.to/NGO_Grants"' not in html):
            raise RuntimeError("Quiet support link missing from candidate UI")
    print("V057_QUIET_SUPPORT_LINK_VERIFIED=True")


def persist_receipt(version: str,previous: str):
    status,_=github_api("GET","contents/"+RECEIPT+"?ref=main")
    if status!=404:raise RuntimeError("Version receipt already exists")
    data={
        "status":"deployed_verified",
        "script":SCRIPT,
        "version_id":version,
        "previous_version":previous,
        "scope":"quiet voluntary support link in Mini App and existing bot messages; no orders, payments, D1 or new messages",
        "verified_at":datetime.now(timezone.utc).isoformat(),
        "run_id":os.environ.get("GITHUB_RUN_ID",""),
    }
    status,result=github_api("PUT","contents/"+RECEIPT,{
        "branch":"main",
        "message":"Pin verified Mini App v0.5.7 quiet support version",
        "content":b64encode(json.dumps(data,ensure_ascii=False,indent=2).encode()).decode()
    })
    if status!=201 or not (result.get("content") or {}).get("sha"):
        raise RuntimeError("Cloudflare deployment success receipt was not committed")


def main():
    if (os.environ.get("GITHUB_ACTIONS")!="true" or
        os.environ.get("GITHUB_REF")!="refs/heads/main" or
        os.environ.get("GITHUB_REPOSITORY")!="Prool-bot/ngo-grants-facebook" or
        os.environ.get("NGO_MINI_APP_V057_RELEASE_APPROVED")!=APPROVAL):
        raise RuntimeError("Production v0.5.7 release gate absent")
    origin=(os.environ.get("NGO_BOT_GATEWAY_URL") or "").rstrip("/")
    if not origin.startswith("https://") or ".workers.dev" not in origin:
        raise RuntimeError("Approved production Worker gateway missing")
    old=expected_version()
    new=staged()
    print("V057_PRECHECK_STAGING_MANIFEST_OK=True")
    current=get_active_version()
    print("V057_PRECHECK_CURRENT_DEPLOYMENT_READ=True")
    if new==old or current!=old:
        raise RuntimeError("Current active Worker version differs from approved baseline")
    # Immediately uploaded versions can take a moment to be visible to the
    # separate Cloudflare versions-metadata route. Bounded retry only here:
    # no code re-upload, no paid AI, no request or D1 write.
    resource=None
    for attempt in range(4):
        try:
            resource=api("/workers/scripts/"+SCRIPT+"/versions/"+new)
            break
        except RuntimeError as exc:
            if "HTTP 404" not in str(exc) or attempt==3:raise
            time.sleep(2)
    print("V057_PRECHECK_CANDIDATE_METADATA_READ=True")
    observed={item.get("name"):item.get("type")
              for item in (resource.get("resources") or {}).get("bindings") or []}
    if observed!=EXPECTED:
        raise RuntimeError("Staged Worker D1 / secret / AI bindings changed")
    print("V057_PRECHECK_BINDINGS_OK=True")
    if health(origin).get("menu_version")!="5.8" or not forbidden(origin):
        raise RuntimeError("Production health or unauthenticated route failed")
    inspect(origin)
    mini_app_smoke(origin)
    print("V057_PRECHECK_LIVE_BOT_AUTH_AND_UI_OK=True")
    if github_api("GET","contents/"+RECEIPT+"?ref=main")[0]!=404:
        raise RuntimeError("UI release receipt already exists")
    switched=False
    try:
        switched=True
        deploy([(old,99.99),(new,0.01)],
               "Mini App v0.5.7 quiet support 0.01% canary")
        time.sleep(3)
        if health(origin,new).get("menu_version")!="5.8" or not forbidden(origin,new):
            raise RuntimeError("v0.5.7 canary failed legacy bot security")
        mini_app_smoke(origin,new)
        inspect(origin,new)
        check_new_html(origin,new)
        print("V057_CANARY_PASS_WITH_NO_USER_ORDERS=True")
        deploy([(new,100)],
               "Mini App v0.5.7 quiet support links")
        time.sleep(3)
        if (get_active_version()!=new or
            health(origin).get("menu_version")!="5.8" or
            not forbidden(origin)):
            raise RuntimeError("Production traffic or legacy bot health incorrect")
        mini_app_smoke(origin)
        inspect(origin)
        check_new_html(origin)
        persist_receipt(new,old)
        print("V057_PRODUCTION_100_PERCENT_AND_VERSION_PINNED=True")
        print("NO_SYNTHETIC_OR_REAL_CATALOG_ORDERS_SENT=True")
        print("NO_D1_WRITES_AND_NO_TELEGRAM_MESSAGES=True")
        return 0
    except BaseException:
        if switched:
            try:
                deploy([(old,100)],
                       "Automatic rollback after Mini App v0.5.7 UI canary failure")
                print("V057_ROLLBACK_PREVIOUS_WORKER_100_PERCENT=True")
            except BaseException:
                print("CRITICAL_V057_ROLLBACK_FAILURE_MANUAL_INSPECTION_NEEDED=True")
                raise
        raise


if __name__=="__main__":
    try:raise SystemExit(main())
    except RuntimeError as exc:raise SystemExit(str(exc)) from None
