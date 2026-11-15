"""Safe 0.01% canary + promotion for Mini App privacy-safe diagnostic codes.

The v0.5 production Worker is otherwise byte-for-byte identical. Stage source
verified by a real-SQLite E2E test before this script is invoked. On any
post-switch failure, revert precisely to the approved original version.
The version receipt is committed only after verified successful promotion.
"""
from __future__ import annotations
from base64 import b64encode
from datetime import datetime,timezone
import json,os,re,sys,time
from pathlib import Path

from deploy_worker_mini_app_fop_v04 import (
    api,deploy,health,forbidden,mini_app_smoke,SCRIPT
)
from release_mini_app_direct_v05_active import inspect,EXPECTED
from mini_app_expected_worker_version import expected_version
PREVIOUS=expected_version()
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from mini_app_public_launch import github_api

RECEIPT="launches/mini_app_v052_live_version.json"
APPROVAL="YES_RELEASE_MINI_APP_V052_SAFE_DIAGNOSTIC"

def stage_version()->str:
    manifest=Path(os.environ.get("RUNNER_TEMP","/tmp"))/"ngo-worker-miniapp-stage.json"
    doc=json.loads(manifest.read_text("utf-8"))
    version=doc.get("version_id")
    if (doc.get("script")!=SCRIPT or doc.get("staged_only") is not True or
        not isinstance(version,str) or
        re.fullmatch(r"[a-f0-9-]{36}",version) is None or version==PREVIOUS):
        raise RuntimeError("Unverified staged v0.5.2 version")
    return version

def current():
    deployments=api("/workers/scripts/"+SCRIPT+"/deployments")
    rows=(deployments.get("deployments") or [{}])[0].get("versions") or []
    if len(rows)!=1 or rows[0].get("percentage")!=100:
        raise RuntimeError("Unexpected live Worker traffic distribution")
    return rows[0].get("version_id")

def safe_write_receipt(version:str):
    status,_=github_api("GET","contents/"+RECEIPT+"?ref=main")
    if status!=404:raise RuntimeError("Worker release already recorded; stop")
    data={"status":"deployed_verified","script":SCRIPT,
          "version_id":version,"previous_version":PREVIOUS,
          "scope":"only privacy-safe 503 stage reasons and UI display; no queue changes",
          "verified_at":datetime.now(timezone.utc).isoformat(),
          "run_id":os.environ.get("GITHUB_RUN_ID","")}
    status,result=github_api("PUT","contents/"+RECEIPT,{
       "branch":"main",
       "message":"Pin validated Cloudflare Mini App v0.5.2 order status fix version",
       "content":b64encode(json.dumps(data,ensure_ascii=False,indent=2).encode()).decode()
    })
    if status!=201 or not (result.get("content") or {}).get("sha"):
        raise RuntimeError("Worker expected-version receipt not durably committed")

def main():
    if (os.getenv("GITHUB_ACTIONS")!="true" or
        os.getenv("GITHUB_REF")!="refs/heads/main" or
        os.getenv("GITHUB_REPOSITORY")!="Prool-bot/ngo-grants-facebook" or
        os.getenv("NGO_V052_DIAG_RELEASE_APPROVED")!=APPROVAL):
        raise RuntimeError("Production v0.5.2 explicit release approval missing")
    gateway=(os.getenv("NGO_BOT_GATEWAY_URL") or "").rstrip("/")
    if not gateway.startswith("https://") or ".workers.dev" not in gateway:
        raise RuntimeError("Approved production Worker URL missing")
    version=stage_version()
    if current()!=PREVIOUS:
        raise RuntimeError("Production Worker does not match approved v0.5 baseline")
    candidate=api("/workers/scripts/"+SCRIPT+"/versions/"+version)
    bindings={item.get("name"):item.get("type")
              for item in (candidate.get("resources") or {}).get("bindings") or []}
    if bindings!=EXPECTED:
        raise RuntimeError("Staged Worker bindings drifted; no deploy")
    if health(gateway).get("menu_version")!="5.8" or not forbidden(gateway):
        raise RuntimeError("Production bot health/auth not healthy")
    inspect(gateway)
    if github_api("GET","contents/"+RECEIPT+"?ref=main")[0]!=404:
        raise RuntimeError("Status fix already deployed or attempted")
    switched=False
    try:
        switched=True
        deploy([(PREVIOUS,99.99),(version,0.01)],
               "Mini App 0.5.1 request-status readback hotfix 0.01% canary")
        time.sleep(3)
        if health(gateway,version).get("menu_version")!="5.8" or not forbidden(gateway,version):
            raise RuntimeError("Canary bot health/auth regression")
        mini_app_smoke(gateway,version)
        inspect(gateway,version)
        print("V052_CANARY_SECURITY_AND_LEGACY_MENU_PASS")
        deploy([(version,100)],
               "Mini App 0.5.1 accepted live new/synced queue status; previous v0.5 retained for rollback")
        time.sleep(3)
        if current()!=version:
            raise RuntimeError("v0.5.2 full promotion unverified")
        if health(gateway).get("menu_version")!="5.8" or not forbidden(gateway):
            raise RuntimeError("Full rollout old bot health/auth regression")
        mini_app_smoke(gateway)
        inspect(gateway)
        print("V052_FULL_PRODUCTION_SECURITY_AND_UI_PASS")
        # Last fallible operation: commit exact promoted version as future
        # read-only health baseline; if this fails roll back production.
        safe_write_receipt(version)
        print("V052_PRODUCTION_VERSION_PINNED=True")
        print("NO_SYNTHETIC_REAL_USER_ORDER_OR_PRODUCTION_D1_WRITE=True")
        return 0
    except BaseException:
        if switched:
            try:
                deploy([(PREVIOUS,100)],
                       "Automatic rollback Mini App 0.5.1 status fix failure")
                print("ROLLBACK_TO_V05_PREVIOUS_100_PERCENT=True")
            except BaseException:
                print("CRITICAL_MANUAL_CLOUDFLARE_ROLLBACK_REQUIRED=True")
                raise
        raise
if __name__=="__main__":
    try:raise SystemExit(main())
    except RuntimeError as e:raise SystemExit(str(e)) from None
