"""Read-only acceptance of the already-staged Mini App Worker version.

Never modifies Cloudflare. Never logs or commits Worker source. The latest
script body is inspected in runner temp only and deleted at workflow end.
"""
from __future__ import annotations
import json,os,sys,urllib.request,urllib.error
from pathlib import Path
from build_mini_app_candidate import extract_js,MAX_BYTES

SCRIPT="ngo-grants-instant-bot"
STAGED="4e3f1f6c-0e30-47f1-bbd3-1003f1a73391"
EXPECTED={"BOT_TOKEN":"secret_text","SYNC_SECRET":"secret_text",
          "WEBHOOK_SECRET":"secret_text","DB":"d1","AI":"ai"}

def main():
    if len(sys.argv)!=2:raise RuntimeError("Runner temp candidate path required")
    account=(os.getenv("CF_WORKER_ACCOUNT_ID") or os.getenv("CF_ACCOUNT_ID") or "").strip()
    token=os.getenv("CF_WORKER_API_TOKEN","").strip()
    if not account or not token:raise RuntimeError("Scoped Cloudflare credentials required")
    base=f"https://api.cloudflare.com/client/v4/accounts/{account}"
    def get(path,*,binary=False):
        req=urllib.request.Request(base+path,method="GET",headers={
            "Authorization":"Bearer "+token,
            "Accept":"application/javascript,multipart/form-data,application/json"
        })
        try:
            with urllib.request.urlopen(req,timeout=35) as response:
                body=response.read(MAX_BYTES+1 if binary else 100000)
                ct=response.headers.get("Content-Type","")
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"Read-only Cloudflare GET HTTP {e.code}") from None
        except (urllib.error.URLError,TimeoutError,OSError) as e:
            raise RuntimeError(f"Read-only Cloudflare GET failed {type(e).__name__}") from None
        if binary:return ct,body
        payload=json.loads(body)
        if payload.get("success") is not True:raise RuntimeError("Cloudflare API metadata refused")
        return payload.get("result") or {}
    deployments=get(f"/workers/scripts/{SCRIPT}/deployments")
    latest=(deployments.get("deployments") or [None])[0]
    if not latest:raise RuntimeError("No active production Worker")
    active=latest.get("versions") or []
    if len(active)!=1 or active[0].get("percentage")!=100:
        raise RuntimeError("Unexpected live traffic split")
    if active[0].get("version_id")==STAGED:
        raise RuntimeError("Staged Mini App unexpectedly already deployed")
    staged=get(f"/workers/scripts/{SCRIPT}/versions/{STAGED}")
    bindings=(staged.get("resources") or {}).get("bindings") or []
    observed={b.get("name"):b.get("type") for b in bindings}
    if observed!=EXPECTED:raise RuntimeError("Staged Worker bindings drifted")
    ct,raw=get(f"/workers/scripts/{SCRIPT}",binary=True)
    source=extract_js(ct,raw)
    if source.count("NGO_GRANTS_NATIVE_MINI_APP_V01")!=1:
        raise RuntimeError("Latest script is not our guarded Mini App candidate")
    if "menu_version:'5.8'" not in source or "data-native-send" not in source:
        raise RuntimeError("Unexpected staged Worker version")
    path=Path(sys.argv[1]).resolve()
    temp=Path(os.getenv("RUNNER_TEMP","/tmp")).resolve()
    if not str(path).startswith(str(temp)+"/"):
        raise RuntimeError("Candidate script may exist only in runner temp")
    fd=os.open(path,os.O_WRONLY|os.O_EXCL|os.O_CREAT,0o600)
    with os.fdopen(fd,"w",encoding="utf-8") as file:file.write(source)
    print("STAGED_MINI_APP_VERSION_CONFIRMED",STAGED)
    print("PRODUCTION_UNCHANGED",active[0].get("version_id")!=STAGED)
    print("EXACT_STAGED_BINDINGS_CONFIRMED",sorted(EXPECTED))
    print("IN_MEMORY_CANDIDATE_READY_FOR_OFFLINE_MOCK")
    return 0

if __name__=="__main__":
    try:raise SystemExit(main())
    except RuntimeError as err:raise SystemExit(str(err)) from None
