"""Temporarily route 0.01% to an identical Worker with an auth-only D1 PRAGMA probe.

Critical property: always revert traffic to the exact pre-existing v0.4
version, even after successful read-only schema introspection or any failure.
There is NO full promotion and NO Telegram or catalog operation here.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import sys
import time

from deploy_worker_mini_app_fop_v04 import (
    api,deploy,health,forbidden,mini_app_smoke,SCRIPT
)
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from mini_app_staged_d1_schema_check import main as read_schema

OLD="d891323d-c8ca-4898-8ff4-ce5bc7e4b053"
BINDINGS={"AI":"ai","BOT_TOKEN":"secret_text","DB":"d1",
          "SYNC_SECRET":"secret_text","WEBHOOK_SECRET":"secret_text"}


def main():
    if (os.getenv("GITHUB_ACTIONS")!="true" or
        os.getenv("GITHUB_REF")!="refs/heads/main" or
        os.getenv("MINI_APP_SCHEMA_CANARY_APPROVED")!="YES_READONLY_001_WITH_ROLLBACK"):
        raise RuntimeError("Strict staged schema canary authorization missing")
    manifest=Path(os.getenv("RUNNER_TEMP","/tmp"))/"ngo-worker-miniapp-stage.json"
    doc=json.loads(manifest.read_text("utf-8"))
    version=doc.get("version_id")
    if (doc.get("staged_only") is not True or doc.get("script")!=SCRIPT or
        not isinstance(version,str) or
        re.fullmatch(r"[a-f0-9-]{36}",version) is None or version==OLD):
        raise RuntimeError("Unknown dormant Worker source/ID")
    gateway=os.getenv("NGO_BOT_GATEWAY_URL","").rstrip("/")
    if not gateway.startswith("https://") or ".workers.dev" not in gateway:
        raise RuntimeError("Unexpected Worker URL")
    running=api("/workers/scripts/"+SCRIPT+"/deployments")
    active=(running.get("deployments") or [None])[0]
    versions=active.get("versions") if active else []
    if (len(versions or [])!=1 or versions[0].get("version_id")!=OLD or
        versions[0].get("percentage")!=100):
        raise RuntimeError("Live production Worker changed: refusing canary")
    staging=api("/workers/scripts/"+SCRIPT+"/versions/"+version)
    actual={b.get("name"):b.get("type")
            for b in (staging.get("resources") or {}).get("bindings") or []}
    if actual!=BINDINGS:raise RuntimeError("Dormant Worker bindings changed")
    if health(gateway).get("menu_version")!="5.8" or not forbidden(gateway):
        raise RuntimeError("Live Worker health/authorization baseline failed")
    print("PRE_CANARY_LIVE_VERSION_AND_BINDINGS_OK")
    deploy_started=False
    failed=False
    try:
        # Deployed fraction is only to enable documented version overrides
        # for the otherwise dormant Worker version. No public-facing functions
        # differ from v0.4 except the SYNC_SECRET-protected schema GET route.
        deploy_started=True
        deploy([(OLD,99.99),(version,0.01)],
               "Temporary 0.01% D1 schema metadata-only canary; automatic rollback")
        time.sleep(3)
        if health(gateway,version).get("menu_version")!="5.8" or not forbidden(gateway,version):
            raise RuntimeError("Canary inherited legacy handler or authentication drift")
        mini_app_smoke(gateway,version)
        print("SCHEMA_CANARY_LEGACY_WORKER_SMOKE_OK")
        read_schema()
        print("D1_SCHEMA_VERIFIED_IN_STAGED_CANARY")
    except BaseException:
        failed=True
        raise
    finally:
        if deploy_started:
            try:
                deploy([(OLD,100)],
                       "Restore 100% previous Worker after read-only D1 schema canary")
                print("RESTORED_PREVIOUS_PRODUCTION_VERSION_100_PERCENT")
            except BaseException:
                print("CRITICAL_ROLLBACK_FAILED_CHECK_CLOUDFLARE_IMMEDIATELY")
                raise
    time.sleep(2)
    if health(gateway).get("menu_version")!="5.8" or not forbidden(gateway):
        raise RuntimeError("Post-canary original Worker authorization smoke failed")
    mini_app_smoke(gateway)
    print("PRODUCTION_WORKER_V04_RESTORED_AND_VERIFIED")
    print("REAL_CATALOG_ORDERS=0;REAL_TELEGRAM_MESSAGES=0;D1_WRITES=0")


if __name__=="__main__":
    main()
