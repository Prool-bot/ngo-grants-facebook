"""Create stage-only schema audit Worker candidate from ephemeral approved JS."""
from __future__ import annotations
from pathlib import Path
import os,sys

from patch_staged_readonly_schema_route import patch

def main():
    if len(sys.argv)!=3:raise RuntimeError("Expected original/candidate runner-temp paths")
    base=Path(os.getenv("RUNNER_TEMP","/tmp")).resolve()
    old,new=(Path(x).resolve() for x in sys.argv[1:])
    for item in (old,new):
        if not str(item).startswith(str(base)+"/"):
            raise RuntimeError("Private Worker must remain within ephemeral runner path")
    content=old.read_text("utf-8")
    patched=patch(content)
    fd=os.open(new,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    with os.fdopen(fd,"w",encoding="utf-8") as stream:stream.write(patched)
    print("STAGED_READ_ONLY_D1_SCHEMA_ROUTE_CANDIDATE_READY")
    return 0

if __name__=="__main__":
    try:raise SystemExit(main())
    except RuntimeError as exc:raise SystemExit(str(exc)) from None
