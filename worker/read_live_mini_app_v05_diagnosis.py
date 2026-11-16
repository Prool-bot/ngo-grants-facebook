"""Read deployed v0.5 Worker source for PRIVATE offline E2E diagnosis.

Read-only Cloudflare API; never logs, commits or uploads source. Restricts source
to 0600 RUNNER_TEMP, checks active version exactly as approved, rejects drift.
"""
from __future__ import annotations
from pathlib import Path
from base64 import b64decode
from binascii import Error as Base64Error
import os
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"worker"))
from read_live_mini_app_v04_contract import call,SCRIPT,REQUIRED
from build_mini_app_candidate import extract_js,MAX_BYTES
from mini_app_expected_worker_version import expected_version

# The stable /workers/scripts/{name} GET can return an INACTIVE staged upload.
# Cloudflare's versioned Workers API exposes the exact active version's modules.
MAX_VERSION_RESPONSE=4*((MAX_BYTES+2)//3)+1_500_000


def extract_active_module(version_record: dict, approved_version: str) -> str:
    if (not isinstance(version_record,dict) or
        version_record.get("id")!=approved_version or
        version_record.get("main_module")!="worker.mjs"):
        raise RuntimeError("Active Worker version identity or main module changed")
    modules=version_record.get("modules")
    if not isinstance(modules,list) or len(modules)!=1:
        raise RuntimeError("Expected one exact active Worker module")
    module=modules[0]
    if (not isinstance(module,dict) or module.get("name")!="worker.mjs" or
        module.get("content_type") not in (
            "application/javascript+module", "application/javascript", "text/javascript") or
        not isinstance(module.get("content_base64"),str)):
        raise RuntimeError("Active Worker module fingerprint changed")
    try:
        raw=b64decode(module["content_base64"],validate=True)
    except (Base64Error,ValueError):
        raise RuntimeError("Active Worker module is not valid base64") from None
    return extract_js("application/javascript",raw)

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
    if (len(versions)!=1 or versions[0].get("version_id")!=expected_version() or
        versions[0].get("percentage")!=100):
        raise RuntimeError("Unexpected current Worker; abort diagnostic")
    version=expected_version()
    resources=call(base+"/versions/"+version,token,100000,structured=True)
    actual={x.get("name"):x.get("type") for x in
            (resources.get("resources") or {}).get("bindings") or []}
    if actual!=REQUIRED:raise RuntimeError("Worker bindings changed")
    active_url=(f"https://api.cloudflare.com/client/v4/accounts/{account}"
                f"/workers/workers/{SCRIPT}/versions/{version}?include=modules")
    active=call(active_url,token,MAX_VERSION_RESPONSE,structured=True)
    src=extract_active_module(active,version)
    if (src.count("NGO_MINI_APP_DIRECT_API_DORMANT_V05")!=1 or
        src.count("const __ngoMiniAppDirectRouteEnabled=true;")!=1 or
        src.count('if(env&&env.__miniAppHttpOrderMode===true)')!=1):
        raise RuntimeError("Unexpected enabled direct API source")
    fd=os.open(dest,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    with os.fdopen(fd,"w",encoding="utf8") as f:f.write(src)
    print("PRIVATE_V05_SOURCE_TEMP_READY=True")
    print("EXACT_ACTIVE_WORKER_VERSION_MODULE_VERIFIED=True")
    print("LIVE_DEPLOYMENT_AND_EXISTING_D1_BINDING_VERIFIED=True")
    print("NO_LIVE_USER_DATA_READ=True")
if __name__=="__main__":
    try:main()
    except RuntimeError as err:raise SystemExit(str(err)) from None
