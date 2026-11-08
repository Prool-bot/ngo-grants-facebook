"""Read-only fetch of approved *currently deployed* Mini App Worker source.

The source is put exclusively under GitHub Actions RUNNER_TEMP (0600), then
deleted by the caller's EXIT trap. No source or private D1 data are logged.
"""
from __future__ import annotations
from pathlib import Path
import json
import os
import re
import sys
import urllib.request
import urllib.error

from build_mini_app_candidate import extract_js, MAX_BYTES

SCRIPT="ngo-grants-instant-bot"
LIVE_VERSION="d891323d-c8ca-4898-8ff4-ce5bc7e4b053"
REQUIRED={"BOT_TOKEN":"secret_text","WEBHOOK_SECRET":"secret_text",
          "SYNC_SECRET":"secret_text","DB":"d1","AI":"ai"}


def call(url,token,limit,structured=False):
    req=urllib.request.Request(url,method="GET",headers={
      "Authorization":"Bearer "+token,
      "Accept":"application/json,application/javascript,multipart/form-data",
      "User-Agent":"NGOGrantsMiniAppContractAudit/1.0"
    })
    try:
        with urllib.request.urlopen(req,timeout=35) as response:
            ct=response.headers.get("Content-Type","")
            raw=response.read(limit+1)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Cloudflare read-only request HTTP {exc.code}") from None
    except (urllib.error.URLError,OSError,TimeoutError) as exc:
        raise RuntimeError(f"Cloudflare read-only request failed ({type(exc).__name__})") from None
    if len(raw)>limit:raise RuntimeError("Cloudflare response exceeds limit")
    if not structured:return ct,raw
    obj=json.loads(raw)
    if obj.get("success") is not True:raise RuntimeError("Cloudflare metadata denied")
    return obj.get("result") or {}


def main():
    if (len(sys.argv)!=2 or os.getenv("GITHUB_ACTIONS")!="true" or
        os.getenv("GITHUB_REF")!="refs/heads/main"):
        raise RuntimeError("Read-only contract audit must run from GitHub main")
    target=Path(sys.argv[1]).resolve()
    temp=Path(os.environ.get("RUNNER_TEMP","/tmp")).resolve()
    if not str(target).startswith(str(temp)+"/"):
        raise RuntimeError("Private Worker source path outside runner temporary directory")
    account=(os.getenv("CF_WORKER_ACCOUNT_ID") or os.getenv("CF_ACCOUNT_ID") or "").strip()
    token=(os.getenv("CF_WORKER_API_TOKEN") or "").strip()
    if not account or not token:raise RuntimeError("Cloudflare read-only credentials absent")
    base="https://api.cloudflare.com/client/v4/accounts/"+account+"/workers/scripts/"+SCRIPT
    deps=call(base+"/deployments",token,100000,structured=True).get("deployments") or []
    if not deps:raise RuntimeError("No Cloudflare deployment")
    active=deps[0].get("versions") or []
    if len(active)!=1 or active[0].get("percentage")!=100 or active[0].get("version_id")!=LIVE_VERSION:
        raise RuntimeError("Live Worker changed since approved v0.4")
    meta=call(base+"/versions/"+LIVE_VERSION,token,100000,structured=True)
    observed={item.get("name"):item.get("type")
              for item in (meta.get("resources") or {}).get("bindings") or []}
    if observed!=REQUIRED:raise RuntimeError("Production binding inventory changed")
    ctype,raw=call(base,token,MAX_BYTES)
    module=extract_js(ctype,raw)
    if (module.count("NGO_GRANTS_NATIVE_MINI_APP_V01")!=1 or
        module.count("NGO_MINI_APP_FOP_STATUS_HINT_V04")!=1 or
        "menu_version:'5.8'" not in module):
        raise RuntimeError("Unexpected Worker source fingerprint")
    fd=os.open(target,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    with os.fdopen(fd,"w",encoding="utf-8") as stream:stream.write(module)
    print("LIVE_WORKER_V04_VERIFIED_READ_ONLY")
    print("PRODUCTION_BINDINGS_VERIFIED",len(observed))
    print("PRIVATE_WORKER_READY_ONLY_IN_EPHEMERAL_RUNNER")
    return 0

if __name__=="__main__":
    try:raise SystemExit(main())
    except RuntimeError as error:raise SystemExit(str(error)) from None
