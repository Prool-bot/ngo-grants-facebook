"""Patch only the embedded HTML and version header of the deployed Mini App v0.1.

The actual Worker source stays PRIVATE and is processed only in GitHub runner
memory. No changes to webhook, D1, grant logic, secrets, routing or bindings.
"""
from __future__ import annotations

import json
import re

MARKER="NGO_GRANTS_NATIVE_MINI_APP_V01"
VERSION_MARKER="NGO_MINI_APP_NAV_FIX_V02"
OLD_HTML_TAG='data-native-send="true"'
OLD_BUG="el('next').hidden=true;el('next').disabled=false;"
NEW_FIX="const explicitNext=p.key==='applicant_role'||p.key==='funding_format';"


def patch(source: str, preview_html: str) -> str:
    if not source or len(source)>8_000_000:
        raise RuntimeError("Unexpected deployed Worker size")
    if source.count(MARKER)!=1 or VERSION_MARKER in source:
        raise RuntimeError("Expected exactly one original Mini App v0.1 Worker marker")
    if "menu_version:'5.8'" not in source:
        raise RuntimeError("Unexpected original Worker menu version")
    pattern=r'(const __ngoMiniAppHTML=)([^\n]+)(;\nconst __ngoMiniAppBridge=)'
    matches=list(re.finditer(pattern,source))
    if len(matches)!=1:
        raise RuntimeError("Embedded Mini App HTML anchor changed")
    match=matches[0]
    try: current=json.loads(match.group(2))
    except (ValueError,TypeError):
        raise RuntimeError("Previous embedded HTML is not a JSON string") from None
    if not isinstance(current,str) or OLD_HTML_TAG not in current or OLD_BUG not in current:
        raise RuntimeError("Previous Mini App version/bug fingerprint changed")
    if current.count("telegram-web-app.js")!=1:
        raise RuntimeError("Prior Telegram SDK fingerprint unexpected")
    if 'data-native-send="false"' not in preview_html or NEW_FIX not in preview_html:
        raise RuntimeError("New offline preview does not contain guarded navigation fix")
    if preview_html.count("data-native-send=\"false\"")!=1:
        raise RuntimeError("Offline preview activation gate is ambiguous")
    if "telegram-web-app.js" in preview_html:
        raise RuntimeError("Offline preview must not depend on Telegram SDK")
    served=preview_html.replace('data-native-send="false"','data-native-send="true"',1)
    served=served.replace("</head>",
        '<script src="https://telegram.org/js/telegram-web-app.js"></script>\n</head>',1)
    new_json=json.dumps(served,ensure_ascii=True)
    replaced=source[:match.start(2)]+new_json+source[match.end(2):]
    old_header='"x-ngo-mini-app-version":"0.1"'
    if replaced.count(old_header)!=1:
        raise RuntimeError("Original route response version header changed")
    replaced=replaced.replace(old_header,'"x-ngo-mini-app-version":"0.2"',1)
    # Marker is outside the HTML literal. It cannot affect functional logic.
    bridge_anchor=';\nconst __ngoMiniAppBridge='
    if replaced.count(bridge_anchor)!=1:
        raise RuntimeError("Mini App bridge anchor changed after patch")
    replaced=replaced.replace(
        bridge_anchor,';\n// '+VERSION_MARKER+'\nconst __ngoMiniAppBridge=',1)
    if (replaced.count(MARKER)!=1 or replaced.count(VERSION_MARKER)!=1
        or replaced.count('"x-ngo-mini-app-version":"0.2"')!=1):
        raise RuntimeError("Mini App nav fix final fingerprint failed")
    return replaced
