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
LATEST_RECEIPT=Path(__file__).resolve().parents[1]/"launches/mini_app_v052_live_version.json"
V053_RECEIPT=Path(__file__).resolve().parents[1]/"launches/mini_app_v053_live_version.json"

def expected_version()->str:
    if not RECEIPT.is_file():return ORIGINAL
    doc=json.loads(RECEIPT.read_text("utf-8"))
    version=doc.get("version_id")
    if (doc.get("status")!="deployed_verified" or
        doc.get("previous_version")!=ORIGINAL or
        not isinstance(version,str) or
        not re.fullmatch(r"[a-f0-9-]{36}",version) or version==ORIGINAL):
        raise RuntimeError("Unexpected approved Worker version receipt")
    if not LATEST_RECEIPT.is_file():return version
    latest=json.loads(LATEST_RECEIPT.read_text("utf-8"))
    successor=latest.get("version_id")
    if (latest.get("status")!="deployed_verified" or
        latest.get("previous_version")!=version or
        not isinstance(successor,str) or
        not re.fullmatch(r"[a-f0-9-]{36}",successor) or successor==version):
        raise RuntimeError("Unexpected new approved Worker diagnostic version receipt")
    if not V053_RECEIPT.is_file():return successor
    hotfix=json.loads(V053_RECEIPT.read_text("utf-8"))
    fixed=hotfix.get("version_id")
    if (hotfix.get("status")!="deployed_verified" or
        hotfix.get("previous_version")!=successor or
        not isinstance(fixed,str) or
        not re.fullmatch(r"[a-f0-9-]{36}",fixed) or fixed==successor):
        raise RuntimeError("Unexpected approved Telegram upstream hotfix version")
    return fixed
