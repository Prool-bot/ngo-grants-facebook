"""Surgical fix of proven v0.5.2 Telegram membership Cloudflare redirect failure.

Live authenticated temporary canary proved:
  POST redirect:error = NETWORK_EXCEPTION
  POST default = 200 member creator
  GET default = 200 member creator
Fix ONLY the one membership POST fetch option. Strip ONLY the exact prior
temporary method-probe route from Cloudflare's last-uploaded script source.
"""
from __future__ import annotations
import os,sys
from pathlib import Path
from patch_mini_app_telegram_upstream_probe_v053 import ROUTE as PRIOR_METHOD_PROBE

MARKER="NGO_MINIAPP_V053_TELEGRAM_FETCH_REDIRECT_FIX"
OLD='''        body:JSON.stringify({chat_id:CHANNEL,user_id:userId}),
        redirect:"error"'''
NEW='''        body:JSON.stringify({chat_id:CHANNEL,user_id:userId})'''
FLAG="const __ngoMiniAppDirectRouteEnabled=true;"

def patch(s:str)->str:
    if "NGO_MINIAPP_STAGE_TELEGRAM_UPSTREAM_METHODS_V053" in s:
        if s.count(PRIOR_METHOD_PROBE)!=1:
            raise RuntimeError("Cannot remove exact prior temporary Telegram method audit")
        s=s.replace(PRIOR_METHOD_PROBE,"",1)
    if (not s or len(s)>8_000_000 or
        "NGO_MINIAPP_STAGE_TELEGRAM_UPSTREAM_METHODS_V053" in s or
        "NGO_MINIAPP_V052_STAGE_ONLY_AUTH_DRYRUN" in s or
        "NGO_MINI_APP_READONLY_D1_AGG_V052" in s or
        MARKER in s or s.count(FLAG)!=1 or
        s.count("NGO_MINI_APP_V052_503_CATEGORY_DIAGNOSTIC")!=1 or
        s.count("NGO_MINI_APP_V051_D1_READBACK_STATUS_COMPATIBILITY")!=1 or
        s.count(OLD)!=1):
        raise RuntimeError("Active v0.5.2 source fingerprint changed; fail closed")
    out=s.replace(OLD,NEW,1).replace(FLAG,"// "+MARKER+"\n"+FLAG,1)
    if out.count(MARKER)!=1 or out.count(NEW)!=1 or OLD in out:
        raise RuntimeError("Membership redirect surgical repair incomplete")
    return out
def main():
    if (len(sys.argv)!=3 or os.getenv("GITHUB_ACTIONS")!="true" or
        os.getenv("GITHUB_REF")!="refs/heads/main"):
        raise RuntimeError("Only approved main-branch CI may patch private Worker")
    temp=Path(os.environ.get("RUNNER_TEMP","/tmp")).resolve()
    before,after=[Path(p).resolve() for p in sys.argv[1:]]
    if any(not str(x).startswith(str(temp)+"/") for x in (before,after)):
        raise RuntimeError("Worker source must remain in temp")
    src=patch(before.read_text("utf-8"))
    fd=os.open(after,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,"w",encoding="utf-8") as f:f.write(src)
    print("LIVE_TELEGRAM_MEMBERSHIP_REDIRECT_ERROR_REMOVED=True")
    print("LEGACY_BOT_AND_DB_SCHEMA_UNCHANGED=True")
if __name__=="__main__":
    try:main()
    except RuntimeError as e:raise SystemExit(str(e)) from None
