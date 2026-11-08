"""Surgical v0.4 Mini App applicant-status advisory patch; NO backend changes.

The real Cloudflare Worker JS remains in GitHub Actions runner memory. Only
the embedded HTML string and its public version header are changed.
"""
from __future__ import annotations

import json
import re

OLD_VERSION="0.3"
NEW_VERSION="0.4"
MARKERS=("NGO_GRANTS_NATIVE_MINI_APP_V01","NGO_MINI_APP_NAV_FIX_V02",
         "NGO_MINI_APP_DIRECT_START_V03")
NEW_MARKER="NGO_MINI_APP_FOP_STATUS_HINT_V04"
NEW_FEATURE="businessApplicantNeedsReview"
SCRIPT_ANCHOR=r'(const __ngoMiniAppHTML=)([^\n]+)(;\n)'


def patch(source:str,preview:str)->str:
    if not source or len(source)>8_000_000:
        raise RuntimeError("Unexpected Worker size")
    if "menu_version:'5.8'" not in source or NEW_MARKER in source:
        raise RuntimeError("Mini App Worker v0.3 baseline changed")
    if any(source.count(x)!=1 for x in MARKERS):
        raise RuntimeError("Existing Mini App v0.1/v0.2/v0.3 markers not unique")
    items=list(re.finditer(SCRIPT_ANCHOR,source))
    if len(items)!=1:
        raise RuntimeError("Embedded Mini App HTML constant not unique")
    m=items[0]
    try:old_html=json.loads(m.group(2))
    except (TypeError,ValueError):
        raise RuntimeError("Existing HTML is not a JSON-encoded string") from None
    if (not isinstance(old_html,str) or
        'data-native-send="true"' not in old_html or
        'telegram-web-app.js' not in old_html or
        'const explicitNext=' not in old_html or
        NEW_FEATURE in old_html):
        raise RuntimeError("Expected deployed v0.3 HTML is absent")
    if (preview.count('data-native-send="false"')!=1 or
        NEW_FEATURE not in preview or
        "зареєстровані як ФОП" not in preview or
        "telegram-web-app.js" in preview):
        raise RuntimeError("New v0.4 offline preview invalid or send-enabled")
    served=preview.replace('data-native-send="false"',
        'data-native-send="true"',1).replace("</head>",
        '<script src="https://telegram.org/js/telegram-web-app.js"></script>\n</head>',1)
    parsed=json.dumps(served,ensure_ascii=True)
    changed=source[:m.start(2)]+parsed+source[m.end(2):]
    old_header='"x-ngo-mini-app-version":"'+OLD_VERSION+'"'
    new_header='"x-ngo-mini-app-version":"'+NEW_VERSION+'"'
    if changed.count(old_header)!=1:
        raise RuntimeError("Old Worker route version header not unique")
    changed=changed.replace(old_header,new_header,1)
    marker_anchor=";\n// NGO_MINI_APP_NAV_FIX_V02"
    if changed.count(marker_anchor)!=1:
        raise RuntimeError("Mini App bridge marker moved")
    changed=changed.replace(marker_anchor,
        ";\n// "+NEW_MARKER+"\n// NGO_MINI_APP_NAV_FIX_V02",1)
    if (changed.count(NEW_MARKER)!=1 or changed.count(new_header)!=1 or
        any(changed.count(x)!=1 for x in MARKERS)):
        raise RuntimeError("Final Worker v0.4 verification failed")
    return changed
