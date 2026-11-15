"""Minimal production fix for live Telegram getChatMember transport.

Real signed-user Cloudflare canary proved POST with redirect:'error' throws
NETWORK_EXCEPTION, while ordinary POST and GET return HTTP 200 with matching
member. The called Telegram Bot API hostname and endpoint are constants.
Remove the explicitly rejecting redirect mode from exactly one *production*
membership call; do not touch any other validation, queue, or endpoint.
"""
from __future__ import annotations
import os,sys
from pathlib import Path
from patch_mini_app_telegram_upstream_probe_v053 import ROUTE as METHOD_PROBE
from patch_mini_app_real_session_dryrun import ROUTE as DRYRUN_PROBE

MARKER="NGO_MINIAPP_V053_TELEGRAM_MEMBER_POST_REDIRECT_FIX"
OLD='''        redirect:"error"
      });'''
NEW='''      });'''

def patch(src:str)->str:
    if not src or len(src)>8_000_000:return fail("empty")
    for marker,body in [
      ("NGO_MINIAPP_STAGE_TELEGRAM_UPSTREAM_METHODS_V053",METHOD_PROBE),
      ("NGO_MINIAPP_V052_STAGE_ONLY_AUTH_DRYRUN",DRYRUN_PROBE),
    ]:
        if marker in src:
            if src.count(body)!=1:fail("unrecognized staged diagnostic route")
            src=src.replace(body,"",1)
    required=(
      "NGO_MINI_APP_V052_503_CATEGORY_DIAGNOSTIC",
      "NGO_MINI_APP_V051_D1_READBACK_STATUS_COMPATIBILITY",
      "NGO_MINI_APP_DIRECT_API_DORMANT_V05",
      "NGO_GRANTS_NATIVE_MINI_APP_V01",
      "NGO_MINI_APP_NAV_FIX_V02",
      "NGO_MINI_APP_DIRECT_START_V03",
      "NGO_MINI_APP_FOP_STATUS_HINT_V04",
      'const __ngoMiniAppDirectRouteEnabled=true;',
      'if(env&&env.__miniAppHttpOrderMode===true)',
      "menu_version:'5.8'"
    )
    if (MARKER in src or any(src.count(x)!=1 for x in required) or
        "NGO_MINIAPP_STAGE_TELEGRAM_UPSTREAM_METHODS_V053" in src or
        "NGO_MINIAPP_V052_STAGE_ONLY_AUTH_DRYRUN" in src or
        src.count(OLD)!=1):
        fail("unexpected deployed v0.5.2 Worker fingerprint")
    # Prefix verification: only the dedicated getChatMember function is touched.
    start=src.index("async function checkChannelMembership(")
    stop=src.index("/** Select only the receipt metadata;",start)
    segment=src[start:stop]
    if (segment.count(OLD)!=1 or
        segment.count('method:"POST"')!=1 or
        segment.count('https://api.telegram.org/bot')!=1 or
        segment.count('"/getChatMember"')!=1):
        fail("unexpected live Telegram membership function")
    segment=segment.replace(OLD,NEW,1)
    out=src[:start]+segment+src[stop:]
    gate='const __ngoMiniAppDirectRouteEnabled=true;'
    out=out.replace(gate,"// "+MARKER+"\n"+gate,1)
    if out.count(MARKER)!=1 or OLD in out or out.count(gate)!=1:
        fail("output fingerprint invalid")
    return out

def fail(message):
    raise RuntimeError("Refusing unsafe Telegram redirect hotfix: "+message)

def main():
    if len(sys.argv)!=3 or os.getenv("GITHUB_ACTIONS")!="true" or os.getenv("GITHUB_REF")!="refs/heads/main":
        fail("main GitHub runner required")
    temp=Path(os.getenv("RUNNER_TEMP","/tmp")).resolve()
    src,dst=[Path(x).resolve() for x in sys.argv[1:]]
    if any(not str(p).startswith(str(temp)+"/") for p in [src,dst]):fail("ephemeral paths required")
    corrected=patch(src.read_text("utf8"))
    fd=os.open(dst,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    with os.fdopen(fd,"w",encoding="utf8") as f:f.write(corrected)
    print("ONLY_TELEGRAM_MEMBER_REDIRECT_ERROR_REMOVED=True")
    print("TEMP_READONLY_PROBE_ROUTES_NOT_DEPLOYED=True")
if __name__=="__main__":
    try:main()
    except RuntimeError as exc:raise SystemExit(str(exc)) from None
