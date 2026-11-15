"""Safe aggregate-only check of existing Cloudflare pending route.

No row text, user hashes, request IDs, access tokens or private request
details are logged or committed. GET only; no side effects.
"""
from __future__ import annotations
import os,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import ngo_grants_ai as app

ID_BASE=2**51
ID_END=ID_BASE+2**48

def inspect(response):
    if not isinstance(response,dict) or not isinstance(response.get("requests"),list):
        raise RuntimeError("Unexpected Cloudflare pending API response shape")
    records=response["requests"]
    counts={"total_pending":len(records),"mini_app_direct_pending":0,
            "mini_app_other_pending":0,"legacy_pending":0}
    for record in records:
        if not isinstance(record,dict):
            raise RuntimeError("Malformed queue record")
        raw=record.get("update_id",record.get("id"))
        try:
            n=int(raw)
        except (TypeError,ValueError):
            counts["mini_app_other_pending"]+=1
            continue
        if ID_BASE<=n<ID_END:
            counts["mini_app_direct_pending"]+=1
        else:
            counts["legacy_pending"]+=1
    return counts

def main():
    if (os.getenv("GITHUB_ACTIONS")!="true" or
        os.getenv("GITHUB_REF")!="refs/heads/main" or
        os.getenv("GITHUB_REPOSITORY")!="Prool-bot/ngo-grants-facebook"):
        raise RuntimeError("Read-only queue check permitted only in trusted main Actions")
    output=inspect(app.gateway_api("/internal/pending"))
    print("CLOUDFLARE_PENDING_AGGREGATE_ONLY=True")
    for k,v in output.items():
        print(k.upper()+"="+str(v))
    print("NO_PERSONAL_DATA_LOGGED=True;NO_WRITES=True")

if __name__=="__main__":
    try:main()
    except RuntimeError as e:raise SystemExit(str(e)) from None
