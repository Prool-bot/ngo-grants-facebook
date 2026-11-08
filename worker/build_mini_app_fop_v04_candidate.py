"""Build a surgical v0.4 FOP eligibility advisory on the active v0.3 Worker.

Reads Cloudflare Worker as a multipart JS module, in memory only. Requires the
deployed Worker to be the known and validated Mini App v0.1 version before
staging. No private source or secrets in logs/artifacts.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import urllib.error
import urllib.request
import sys

from build_mini_app_candidate import extract_js,MAX_BYTES
from patch_live_worker_mini_app_fop_v04 import patch

SCRIPT="ngo-grants-instant-bot"
EXPECTED_ACTIVE_VERSION="d9a894b5-8254-4bd5-8c9e-1848261cab24"


def api_account():
    account=(os.getenv("CF_WORKER_ACCOUNT_ID") or os.getenv("CF_ACCOUNT_ID") or "").strip()
    token=(os.getenv("CF_WORKER_API_TOKEN") or "").strip()
    if not account or not token:
        raise RuntimeError("Scoped Cloudflare credentials required")
    return account,token


def get(account,token,path,*,raw=False):
    url="https://api.cloudflare.com/client/v4/accounts/"+account+path
    req=urllib.request.Request(url,headers={
        "Authorization":"Bearer "+token,
        "Accept":"application/javascript,multipart/form-data,application/json"
    },method="GET")
    try:
        with urllib.request.urlopen(req,timeout=35) as resp:
            body=resp.read(MAX_BYTES+1 if raw else 100000)
            ctype=resp.headers.get("Content-Type","")
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Cloudflare read-only GET HTTP {e.code}") from None
    except (OSError,urllib.error.URLError,TimeoutError) as e:
        raise RuntimeError(f"Cloudflare GET failed ({type(e).__name__})") from None
    if raw:return ctype,body
    result=json.loads(body)
    if result.get("success") is not True:
        raise RuntimeError("Cloudflare metadata request failed")
    return result.get("result") or {}


def main():
    if len(sys.argv)!=2:raise RuntimeError("Runner-temp output path required")
    if os.getenv("GITHUB_ACTIONS")!="true" or os.getenv("GITHUB_REF")!="refs/heads/main":
        raise RuntimeError("Deploy candidate build permitted only on GitHub main")
    account,token=api_account()
    deployed=get(account,token,f"/workers/scripts/{SCRIPT}/deployments")
    deployments=deployed.get("deployments") or []
    active=deployments[0].get("versions") if deployments else []
    if (len(active or [])!=1 or active[0].get("percentage")!=100 or
        active[0].get("version_id")!=EXPECTED_ACTIVE_VERSION):
        raise RuntimeError("Production Worker changed; refuse patching")
    ctype,raw=get(account,token,f"/workers/scripts/{SCRIPT}",raw=True)
    source=extract_js(ctype,raw)
    html=Path("mini-app/preview.html").read_text("utf-8")
    patched=patch(source,html)

    target=Path(sys.argv[1]).resolve()
    run_temp=Path(os.getenv("RUNNER_TEMP","/tmp")).resolve()
    if not str(target).startswith(str(run_temp)+"/"):
        raise RuntimeError("Candidate must be written only to runner temporary directory")
    fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,"w",encoding="utf-8") as file:file.write(patched)
    print("MINI_APP_V04_FOP_GUIDANCE_CANDIDATE_READY")
    print("ACTIVE_V03_VERSION_UNCHANGED_BEFORE_STAGE")
    print("ONLY_EMBEDDED_HTML_AND_VERSION_HEADER_PATCHED")
    return 0


if __name__=="__main__":
    try:raise SystemExit(main())
    except RuntimeError as e:raise SystemExit(str(e)) from None
