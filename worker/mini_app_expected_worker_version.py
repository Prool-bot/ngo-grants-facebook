"""Fail-closed pin for the approved active Mini App Worker release.

Before the v0.5.1 status compatibility fix, the original v0.5 version is
approved. After a successful production deployment, its receipt is committed.
The public GitHub receipt contains only a Cloudflare version ID, never secrets.
"""
from __future__ import annotations
import json
from pathlib import Path
import re

ORIGINAL="4b0b8562-d2af-46a5-aa87-8acfb69b2151"
RECEIPT=Path(__file__).resolve().parents[1]/"launches/mini_app_v051_live_version.json"

def expected_version()->str:
    if not RECEIPT.is_file():return ORIGINAL
    doc=json.loads(RECEIPT.read_text("utf-8"))
    version=doc.get("version_id")
    if (doc.get("status")!="deployed_verified" or
        doc.get("previous_version")!=ORIGINAL or
        not isinstance(version,str) or
        not re.fullmatch(r"[a-f0-9-]{36}",version) or version==ORIGINAL):
        raise RuntimeError("Unexpected approved Worker version receipt")
    return version
