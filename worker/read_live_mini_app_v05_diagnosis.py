"""Read deployed v0.5 Worker source for PRIVATE offline E2E diagnosis.

Read-only Cloudflare API; never logs, commits or uploads source. Restricts source
to 0600 RUNNER_TEMP, checks active version exactly as approved, rejects drift.
"""
from __future__ import annotations
from pathlib import Path
import os
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"worker"))
from read_live_mini_app_v04_contract import call,SCRIPT,REQUIRED
from build_mini_app_candidate import extract_js,MAX_BYTES
from release_mini_app_direct_v05_active import NEW

def main():
    if (len(sys.argv)!=2 or os.getenv("GITHUB_ACTIONS")!="true" or
        os.getenv("GITHUB_REF")!="refs/heads/main"):
        raise RuntimeError("Approved main-branch private read-only probe only")
    dest=Path(sys.argv[1]).resolve()
    temp=Path(os.environ.get("RUNNER_TEMP","/tmp")).resolve()
    if not str(dest).startswith(str(temp)+"/"):
        raise RuntimeError("Worker code must stay in ephemeral runner temp")
    account=(os.getenv("CF_WORKER_ACCOUNT_ID") or
             os.getenv("CF_ACCOUNT_ID") or "").strip()
    token=os.getenv("CF_WORKER_API_TOKEN","").strip()
    if not account or not token:raise RuntimeError("Cloudflare read token missing")
    base=f"https://api.cloudflare.com/client/v4/accounts/{account}/workers/scripts/{SCRIPT}"
    deployments=call(base+"/deployments",token,100000,structured=True).get("deployments") or []
    versions=(deployments[0].get("versions") or []) if deployments else []
    if (len(versions)!=1 or versions[0].get("version_id")!=NEW or
        versions[0].get("percentage")!=100):
        raise RuntimeError("Unexpected current Worker; abort diagnostic")
    resources=call(base+"/versions/"+NEW,token,100000,structured=True)
    actual={x.get("name"):x.get("type") for x in
            (resources.get("resources") or {}).get("bindings") or []}
    if actual!=REQUIRED:raise RuntimeError("Worker bindings changed")
    ctype,raw=call(base,token,MAX_BYTES)
    src=extract_js(ctype,raw)
    if (src.count("NGO_MINI_APP_DIRECT_API_DORMANT_V05")!=1 or
        src.count("const __ngoMiniAppDirectRouteEnabled=true;")!=1 or
        src.count('if(env&&env.__miniAppHttpOrderMode===true)')!=1):
        raise RuntimeError("Unexpected enabled direct API source")
    fd=os.open(dest,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    with os.fdopen(fd,"w",encoding="utf8") as f:f.write(src)
    print("PRIVATE_V05_SOURCE_TEMP_READY=True")
    print("LIVE_DEPLOYMENT_AND_EXISTING_D1_BINDING_VERIFIED=True")
    print("NO_LIVE_USER_DATA_READ=True")
if __name__=="__main__":
    try:main()
    except RuntimeError as err:raise SystemExit(str(err)) from None
