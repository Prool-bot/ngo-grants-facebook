"""One-literal fix against the exact active private Worker source.

Actual live createRequest inserts request status 'new'. Existing v0.5 D1
readback rejected both live statuses 'new' and 'synced' as CONFLICT, even
after a durable commit. Correct only this status allowlist, preserving API,
auth, quotas, idempotency, D1 schema and all legacy bot handlers.
"""
from __future__ import annotations
from pathlib import Path
import os,sys

OLD='["pending","processing","published","no_candidate","done","completed"]'
NEW='["new","synced","pending","processing","published","no_candidate","done","completed"]'
MARKER="NGO_MINI_APP_V051_D1_READBACK_STATUS_COMPATIBILITY"
FLAG="const __ngoMiniAppDirectRouteEnabled=true;"

def patch(source:str)->str:
    required=("NGO_MINI_APP_DIRECT_API_DORMANT_V05",
              "NGO_GRANTS_NATIVE_MINI_APP_V01","NGO_MINI_APP_NAV_FIX_V02",
              "NGO_MINI_APP_DIRECT_START_V03","NGO_MINI_APP_FOP_STATUS_HINT_V04",
              FLAG,'if(env&&env.__miniAppHttpOrderMode===true)',"menu_version:'5.8'")
    if (not source or len(source)>8_000_000 or
        MARKER in source or NEW in source or
        source.count(OLD)!=1 or
        any(source.count(x)!=1 for x in required)):
        raise RuntimeError("Unexpected existing v0.5 Worker or status allowlist: abort")
    new=source.replace(OLD,NEW,1).replace(FLAG,"// "+MARKER+"\n"+FLAG,1)
    if (new.count(MARKER)!=1 or new.count(NEW)!=1 or
        new.count(OLD)>0 or new.count(FLAG)!=1):
        raise RuntimeError("v0.5.1 surgical patch validation failed")
    return new

def main():
    if (len(sys.argv)!=3 or os.getenv("GITHUB_ACTIONS")!="true" or
        os.getenv("GITHUB_REF")!="refs/heads/main"):
        raise RuntimeError("One-time Worker repair permitted only from main")
    temp=Path(os.environ.get("RUNNER_TEMP","/tmp")).resolve()
    inp,out=(Path(p).resolve() for p in sys.argv[1:])
    if any(not str(p).startswith(str(temp)+"/") for p in (inp,out)):
        raise RuntimeError("Worker source must remain in ephemeral runner directory")
    fixed=patch(inp.read_text("utf-8"))
    fd=os.open(out,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,"w",encoding="utf-8") as f:f.write(fixed)
    print("V051_PATCHED_ONLY_LIVE_D1_STATUS_ALLOWLIST=True")
    print("PRIVATE_WORKER_SOURCE_NOT_LOGGED=True")
if __name__=="__main__":
    try:main()
    except RuntimeError as exc:raise SystemExit(str(exc)) from None
