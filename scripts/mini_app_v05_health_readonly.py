"""Daily read-only health & security posture audit of live Mini App v0.5.

Queries only Cloudflare deployment metadata and HTTPS routes with an invalid
HMAC (safe 401), invalid Origin (safe 403), and method rejection (405).
It NEVER submits a valid Telegram initData, creates an order, changes traffic,
messages users or modifies D1. BotFather registration is checked via getMe.
"""
from __future__ import annotations
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"worker"))
sys.path.insert(0,str(ROOT/"scripts"))

from release_mini_app_direct_v05_active import (
    api,health,forbidden,mini_app_smoke,inspect,SCRIPT,NEW
)
from mini_app_public_preflight import telegram


def assess_deployment(current:dict)->None:
    deployments=current.get("deployments") or []
    versions=deployments[0].get("versions") if deployments else []
    if (len(versions or [])!=1 or
        versions[0].get("version_id")!=NEW or
        versions[0].get("percentage")!=100):
        raise RuntimeError("Unexpected live Mini App Cloudflare Worker deployment")

def main():
    if (os.environ.get("GITHUB_ACTIONS")!="true" or
        os.environ.get("GITHUB_REF")!="refs/heads/main"):
        raise RuntimeError("Read-only health check must run on the primary branch")
    origin=(os.environ.get("NGO_BOT_GATEWAY_URL") or "").rstrip("/")
    if not origin.startswith("https://") or ".workers.dev" not in origin:
        raise RuntimeError("Approved HTTPS production gateway missing")
    assess_deployment(api("/workers/scripts/"+SCRIPT+"/deployments"))
    if health(origin).get("menu_version")!="5.8" or not forbidden(origin):
        raise RuntimeError("Legacy catalog backend health/auth regression")
    mini_app_smoke(origin)
    inspect(origin)
    bot_token=(os.environ.get("NGO_GRANTS_AI_BOT_TOKEN") or "").strip()
    identity=telegram("getMe",token=bot_token)
    if (identity.get("is_bot") is not True or
        identity.get("username")!="ngogratsAI_bot"):
        raise RuntimeError("Existing Telegram bot identity changed")
    has_main=identity.get("has_main_web_app") is True
    print("PRODUCTION_MINI_APP_V05_HEALTHY=True")
    print("LEGACY_MINI_APP_V04_AND_MENU_HEALTHY=True")
    print("UNAUTHORIZED_ORDERS_DENIED_AND_NO_D1_WRITES=True")
    print("MAIN_MINI_APP_REGISTERED="+str(has_main))
    print("DIRECT_CHANNEL_CTA_REQUIRES_REGISTRATION="+str(not has_main))
    print("NO_REAL_CATALOG_ORDERS_SUBMITTED=True")
    return has_main

if __name__=="__main__":
    try:main()
    except RuntimeError as exc:raise SystemExit(str(exc)) from None
