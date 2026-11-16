"""Patch only the embedded public Mini App HTML in the *approved live* Worker.

No D1/API/bot logic changes. Fail closed if Cloudflare's last-uploaded script
is not the exact HTML served by the currently deployed production version.
Never store Worker source in GitHub, logs or artifacts.
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

from patch_live_worker_mini_app_direct_v05 import direct_html

PREFIX="const __ngoMiniAppDirectHTML="
SENTINEL="NGO_MINIAPP_V053_TELEGRAM_MEMBER_POST_REDIRECT_FIX"
STAGING_MARKERS=(
    "NGO_MINIAPP_STAGE_TELEGRAM_UPSTREAM_METHODS_V053",
    "NGO_MINIAPP_V052_STAGE_ONLY_AUTH_DRYRUN",
    "NGO_MINI_APP_READONLY_D1_AGG_V052",
    "NGO_MINIAPP_STAGE_D1",
)


def patch(source: str, *, old_live_html: str, new_html: str) -> str:
    if (not source or len(source) > 8_000_000 or
        source.count(PREFIX) != 1 or
        source.count(SENTINEL) != 1 or
        source.count("const __ngoMiniAppDirectRouteEnabled=true;") != 1 or
        source.count("NGO_MINI_APP_DIRECT_API_DORMANT_V05") != 1 or
        source.count("NGO_GRANTS_NATIVE_MINI_APP_V01") != 1 or
        "menu_version:'5.8'" not in source or
        any(marker in source for marker in STAGING_MARKERS)):
        raise RuntimeError("Unrecognized approved Worker script; refuse UI update")
    index=source.index(PREFIX)+len(PREFIX)
    try:
        stored_html,used=json.JSONDecoder().raw_decode(source[index:])
    except ValueError:
        raise RuntimeError("Invalid embedded Mini App HTML literal") from None
    if not isinstance(stored_html,str) or source[index+used:index+used+1]!=";":
        raise RuntimeError("Embedded Mini App HTML boundary changed")
    if old_live_html != stored_html:
        raise RuntimeError("Last-uploaded Worker differs from active served HTML")
    required=(
        'data-native-send="false" data-direct-send="true"',
        'telegram-web-app.js',
        'id="greet"',
        'id="robotArm"',
        "function needsDetail(){",
        "@keyframes arm-wave",
        "NgoGrantsDirectClient",
    )
    if any(piece not in new_html for piece in required):
        raise RuntimeError("Updated Mini App missing required UI/security elements")
    if ("const __ngoMiniAppDirectRouteEnabled=true;" in new_html or
        "<script src=\"./" in new_html or
        new_html==stored_html):
        raise RuntimeError("Updated embedded UI is invalid or unchanged")
    replacement=json.dumps(new_html,ensure_ascii=True)
    updated=source[:index]+replacement+source[index+used:]
    # Entire backend script — including membership, queue, auth and D1 —
    # must remain byte-for-byte identical except the one JS string literal.
    assert updated.replace(replacement,json.dumps(stored_html,ensure_ascii=True),1)==source
    return updated


def current_public_html(gateway: str) -> str:
    if not gateway.startswith("https://") or ".workers.dev" not in gateway:
        raise RuntimeError("Approved production Worker origin required")
    request=urllib.request.Request(
        gateway.rstrip("/")+"/mini-app/direct",
        method="GET",headers={"cache-control":"no-store",
                             "user-agent":"NGOGrantsV054UIGuard/1.0"})
    try:
        with urllib.request.urlopen(request,timeout=30) as response:
            raw=response.read(120_000)
            if (response.status!=200 or
                "text/html" not in response.headers.get("Content-Type","")):
                raise RuntimeError("Live Mini App route unhealthy")
    except (urllib.error.HTTPError,urllib.error.URLError,OSError) as exc:
        raise RuntimeError("Cannot validate deployed public Mini App") from None
    return raw.decode("utf-8")


def main():
    if (len(sys.argv)!=3 or os.environ.get("GITHUB_ACTIONS")!="true" or
        os.environ.get("GITHUB_REF")!="refs/heads/main"):
        raise RuntimeError("Approved main-only Worker stage required")
    temp=Path(os.environ.get("RUNNER_TEMP","/tmp")).resolve()
    old,new=[Path(p).resolve() for p in sys.argv[1:]]
    if any(not p.is_relative_to(temp) for p in (old,new)) or old==new:
        raise RuntimeError("Private Worker paths must be in runner temp")
    live=current_public_html(os.environ.get("NGO_BOT_GATEWAY_URL",""))
    template=Path(__file__).resolve().parents[1]/"mini-app/direct-preview.html"
    latest=direct_html(template)
    candidate=patch(old.read_text("utf-8"),old_live_html=live,new_html=latest)
    fd=os.open(new,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,"w",encoding="utf-8") as f:
        f.write(candidate)
    print("MINIAPP_V054_UI_ONLY_PATCH_VERIFIED=True")
    print("LIVE_WORKER_HTML_FINGERPRINT_MATCHED=True")
    print("D1_BOT_API_AUTH_BINDINGS_AND_QUEUE_UNCHANGED=True")
    print("NO_WORKER_SOURCE_EXPORTED=True")


if __name__=="__main__":
    try:raise SystemExit(main())
    except RuntimeError as exc:raise SystemExit(str(exc)) from None
