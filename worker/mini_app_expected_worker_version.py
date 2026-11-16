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
V054_RECEIPT=Path(__file__).resolve().parents[1]/"launches/mini_app_v054_live_version.json"
V055_RECEIPT=Path(__file__).resolve().parents[1]/"launches/mini_app_v055_live_version.json"

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
    v053=json.loads(V053_RECEIPT.read_text("utf-8"))
    current=v053.get("version_id")
    if (v053.get("status")!="deployed_verified" or
        v053.get("previous_version")!=successor or
        not isinstance(current,str) or
        not re.fullmatch(r"[a-f0-9-]{36}",current) or current==successor):
        raise RuntimeError("Unexpected v0.5.3 Telegram upstream fix receipt")
    if not V054_RECEIPT.is_file():return current
    upgrade=json.loads(V054_RECEIPT.read_text("utf-8"))
    upgraded=upgrade.get("version_id")
    if (upgrade.get("status")!="deployed_verified" or
        upgrade.get("previous_version")!=current or
        upgrade.get("script")!="ngo-grants-instant-bot" or
        not isinstance(upgraded,str) or
        not re.fullmatch(r"[a-f0-9-]{36}",upgraded) or upgraded==current):
        raise RuntimeError("Unexpected v0.5.4 request guidance release receipt")
    if not V055_RECEIPT.is_file():return upgraded
    wave=json.loads(V055_RECEIPT.read_text("utf-8"))
    waving=wave.get("version_id")
    if (wave.get("status")!="deployed_verified" or
        wave.get("previous_version")!=upgraded or
        wave.get("script")!="ngo-grants-instant-bot" or
        not isinstance(waving,str) or
        not re.fullmatch(r"[a-f0-9-]{36}",waving) or waving==upgraded):
        raise RuntimeError("Unexpected v0.5.5 visible robot wave release receipt")
    return waving
