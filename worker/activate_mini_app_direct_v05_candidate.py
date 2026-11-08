"""Enable only the already-tested direct Mini App API in a NEW inactive version.

The existing 100% deployed v0.4 script is never altered in-place. The
latest uploaded (inactive) v0.5 code was previously tested and verified.
This script changes ONLY its compile-time disabled direct-order flag.
"""
from __future__ import annotations
import os,sys
from pathlib import Path

LIVE="d891323d-c8ca-4898-8ff4-ce5bc7e4b053"
DORMANT="c9dbb626-4f6c-4c31-96a7-73332bbf7e08"
MARKER="NGO_MINI_APP_DIRECT_API_DORMANT_V05"
FLAG_OFF="const __ngoMiniAppDirectRouteEnabled=false;"
FLAG_ON="const __ngoMiniAppDirectRouteEnabled=true;"
REQUIRED=(
  "NGO_GRANTS_NATIVE_MINI_APP_V01",
  "NGO_MINI_APP_NAV_FIX_V02",
  "NGO_MINI_APP_DIRECT_START_V03",
  "NGO_MINI_APP_FOP_STATUS_HINT_V04",
)

def activate(source:str)->str:
    if (not source or len(source)>8_000_000 or source.count(MARKER)!=1 or
        source.count(FLAG_OFF)!=1 or FLAG_ON in source or
        "NGO_MINI_APP_STAGE_SCHEMA_READ_ONLY_V01" in source or
        any(source.count(x)!=1 for x in REQUIRED)):
        raise RuntimeError("Unexpected staged v0.5 direct Mini App Worker fingerprint")
    if (source.count('if(__directPath==="/api/mini-app/order"){')!=1 or
        'if(env&&env.__miniAppHttpOrderMode===true)' not in source or
        '"menu_version"' not in source and "menu_version:'5.8'" not in source):
        raise RuntimeError("Signed Telegram D1 adapter or legacy Worker not present")
    result=source.replace(FLAG_OFF,FLAG_ON,1)
    if result.count(FLAG_ON)!=1 or FLAG_OFF in result:
        raise RuntimeError("Cannot enable exactly one direct route flag")
    return result

def main():
    if len(sys.argv)!=3:raise RuntimeError("Two ephemeral Worker JS paths required")
    root=Path(os.getenv("RUNNER_TEMP","/tmp")).resolve()
    before,after=(Path(p).resolve() for p in sys.argv[1:])
    if any(not str(x).startswith(str(root)+"/") for x in (before,after)):
        raise RuntimeError("Private Worker source must remain in runner temp")
    activated=activate(before.read_text("utf8"))
    fd=os.open(after,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,"w",encoding="utf8") as file:file.write(activated)
    print("DIRECT_ORDER_ACTIVE_CANDIDATE_READY_IN_EPHEMERAL_RUNNER")
    print("ONLY_COMPILE_TIME_DIRECT_ORDER_FLAG_CHANGED")
    print("PREVIOUS_PRODUCTION_DEPLOYMENT_UNCHANGED")
    return 0

if __name__=="__main__":
    try:raise SystemExit(main())
    except RuntimeError as exc:raise SystemExit(str(exc)) from None
