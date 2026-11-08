"""Build a disabled direct-link Worker candidate from the verified live version.

The last uploaded script is the previous isolated schema-probe version.
Reconstruct the exact pre-probe v0.4 source with strict splice verification,
then attach direct UI + authenticated order adapter. No cloud writes here.
"""
from __future__ import annotations
import os
import sys
from pathlib import Path

from patch_live_worker_mini_app_direct_v05 import reconstruct_base,patch

def main():
    if len(sys.argv)!=3:raise RuntimeError("Original/candidate temp paths required")
    parent=Path(os.getenv("RUNNER_TEMP","/tmp")).resolve()
    before,after=(Path(p).resolve() for p in sys.argv[1:])
    if any(not str(p).startswith(str(parent)+"/") for p in (before,after)):
        raise RuntimeError("Private Worker source must stay inside runner temp")
    original=before.read_text("utf-8")
    approved=reconstruct_base(original)
    candidate=patch(approved,Path.cwd())
    fd=os.open(after,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    with os.fdopen(fd,"w",encoding="utf-8") as handle:
        handle.write(candidate)
    print("APPROVED_LIVE_V04_RECONSTRUCTED_FROM_VERIFIED_DORMANT_SCHEMA_PATCH")
    print("MINI_APP_V05_DIRECT_WORKER_CANDIDATE_IN_RUNNER_TEMP")
    print("DIRECT_ORDER_ENDPOINT_HARD_DISABLED_FOR_STAGING=True")
    print("ACTIVE_PRODUCTION_WORKER_UNCHANGED")
    return 0

if __name__=="__main__":
    try:raise SystemExit(main())
    except RuntimeError as error:raise SystemExit(str(error)) from None
