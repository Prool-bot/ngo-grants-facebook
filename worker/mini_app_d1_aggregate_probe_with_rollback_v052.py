"""Brief, authenticated read-only count endpoint canary on inactive Worker.

Strictly restore previous 100% production version even when a check fails.
Never echo the secret or any identifying data. No live D1 writes or orders.
"""
from __future__ import annotations
import json,os,re,time,urllib.error,urllib.request
from pathlib import Path
from deploy_worker_mini_app_fop_v04 import api,deploy,health,forbidden,mini_app_smoke,SCRIPT
from release_mini_app_direct_v05_active import inspect,EXPECTED
from mini_app_expected_worker_version import expected_version

PATH="/_internal/miniapp/order-count-health"
def run():
    if (os.getenv("GITHUB_ACTIONS")!="true" or
        os.getenv("GITHUB_REF")!="refs/heads/main" or
        os.getenv("NGO_D1_AGGREGATE_PROBE_APPROVED")!="YES_READONLY_001_WITH_ROLLBACK"):
        raise RuntimeError("Read-only canary authorization missing")
    gate=(os.getenv("NGO_BOT_GATEWAY_URL") or "").rstrip("/")
    secret=os.getenv("NGO_BOT_SYNC_SECRET") or ""
    if not gate.startswith("https://") or ".workers.dev" not in gate or not secret:
        raise RuntimeError("Approved Worker gateway credentials missing")
    receipt=Path(os.getenv("RUNNER_TEMP","/tmp"))/"ngo-worker-miniapp-stage.json"
    stage=json.loads(receipt.read_text("utf-8"))
    version=stage.get("version_id")
    baseline=expected_version()
    if (stage.get("staged_only") is not True or stage.get("script")!=SCRIPT or
        not isinstance(version,str) or not re.fullmatch(r"[a-f0-9-]{36}",version) or
        version==baseline):
        raise RuntimeError("No expected dormant candidate")
    live=(api("/workers/scripts/"+SCRIPT+"/deployments").get("deployments") or [{}])[0]
    versions=live.get("versions") or []
    if len(versions)!=1 or versions[0].get("version_id")!=baseline or versions[0].get("percentage")!=100:
        raise RuntimeError("Expected production version was replaced")
    binds=api("/workers/scripts/"+SCRIPT+"/versions/"+version)
    actual={x.get("name"):x.get("type") for x in (binds.get("resources") or {}).get("bindings") or []}
    if actual!=EXPECTED:raise RuntimeError("Dormant Worker binding mismatch")
    if health(gate).get("menu_version")!="5.8" or not forbidden(gate):
        raise RuntimeError("Old bot health failed")
    inspect(gate)
    switched=False
    try:
        switched=True
        deploy([(baseline,99.99),(version,0.01)],
               "Temporary 0.01% authenticated read-only D1 aggregate diagnosis")
        time.sleep(3)
        if health(gate,version).get("menu_version")!="5.8" or not forbidden(gate,version):
            raise RuntimeError("Canary legacy bot regression")
        inspect(gate,version)
        req=urllib.request.Request(gate+PATH,method="GET",headers={
          "Authorization":"Bearer "+secret,
          "Cloudflare-Workers-Version-Overrides":f'{SCRIPT}="{version}"',
          "Accept":"application/json","Cache-Control":"no-store",
          "User-Agent":"NGOGrantsD1AggregateV052/1.0"
        })
        try:
            with urllib.request.urlopen(req,timeout=25) as response:
                if response.status!=200 or response.headers.get("x-ngo-miniapp-order-count")!="read-only":
                    raise RuntimeError("Read-only Worker version override failed")
                result=json.loads(response.read(10000))
        except urllib.error.HTTPError as e:
            raise RuntimeError("Read-only D1 aggregate HTTP "+str(e.code)) from None
        if result.get("ok") is not True or result.get("kind")!="aggregate_only" or not isinstance(result.get("total"),int):
            raise RuntimeError("Aggregate schema verification failed")
        count=result["status_counts"]
        if not isinstance(count,dict) or sum(count.values())!=result["total"]:
            raise RuntimeError("Aggregate counts incoherent")
        print("LIVE_D1_MINI_APP_ORDER_AGGREGATES_READ_ONLY=True")
        print("LIVE_D1_MINI_APP_TOTAL="+str(result["total"]))
        for key in ("new","synced","pending","processing","published","no_candidate","done","completed"):
            if not isinstance(count.get(key),int):raise RuntimeError("Missing status count")
            print("LIVE_D1_MINI_APP_"+key.upper()+"="+str(count[key]))
        print("NO_USER_IDS_TOPICS_OR_ORDER_IDS_READ=True")
    finally:
        if switched:
            deploy([(baseline,100)],
                   "Restore 100% approved v0.5.1 after read-only aggregate D1 probe")
            print("PRODUCTION_V051_RESTORED_100_PERCENT=True")
    time.sleep(2)
    if health(gate).get("menu_version")!="5.8" or not forbidden(gate):
        raise RuntimeError("Post-probe legacy health failed")
    inspect(gate)
    print("NO_D1_WRITES_OR_LIVE_ORDERS=True")
if __name__=="__main__":
    try:run()
    except RuntimeError as e:raise SystemExit(str(e)) from None
