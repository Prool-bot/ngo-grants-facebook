"""Prepare authenticated read-only aggregate probe for existing v0.5.1 D1.

The exact current deployed private Worker is patched in ephemeral runner memory,
staged as an inactive version, exposed under 0.01% canary *briefly* for version-
override GET, then the original version restored in finally. This probe NEVER
reads topics, user hashes, orders or any individual row; only grouped counts.
"""
from __future__ import annotations
import os,re,sys
from pathlib import Path

MARKER="NGO_MINI_APP_READONLY_D1_AGG_V052"
ANCHOR="export default {async fetch(request,env){"
ROUTE='''
  // NGO_MINI_APP_READONLY_D1_AGG_V052 (temporary, authorized, count-only)
  if(new URL(request.url).pathname==="/_internal/miniapp/order-count-health"){
    if(request.method!=="GET")return new Response("Method not allowed",{status:405});
    if(!env.SYNC_SECRET||request.headers.get("authorization")!=="Bearer "+env.SYNC_SECRET)
      return new Response("Forbidden",{status:403});
    const lower=2**51,upper=2**51+2**48;
    try{
      const rows=await env.DB.prepare(
        "SELECT status, COUNT(*) AS n FROM requests WHERE update_id >= ? AND update_id < ? GROUP BY status"
      ).bind(lower,upper).all();
      if(!rows||!rows.success||!Array.isArray(rows.results))throw Error("D1");
      const statuses=["new","synced","pending","processing","published","no_candidate","done","completed"];
      const totals={};
      for(const s of statuses)totals[s]=0;
      for(const row of rows.results){
        const status=String(row.status||"");
        if(!Object.hasOwn(totals,status))throw Error("UNKNOWN_STATUS");
        const count=Number(row.n);
        if(!Number.isSafeInteger(count)||count<0)throw Error("COUNT");
        totals[status]+=count;
      }
      const count=Object.values(totals).reduce((a,b)=>a+b,0);
      return new Response(JSON.stringify({ok:true,kind:"aggregate_only",total:count,status_counts:totals}),{
        status:200,headers:{"content-type":"application/json; charset=utf-8",
          "cache-control":"no-store","x-ngo-miniapp-order-count":"read-only",
          "x-content-type-options":"nosniff"}
      });
    }catch(_){
      return new Response(JSON.stringify({ok:false,kind:"aggregate_only",error:"D1_AGG_UNAVAILABLE"}),{
        status:503,headers:{"content-type":"application/json","cache-control":"no-store"}
      });
    }
  }
'''
def patch(s:str)->str:
    if (not s or len(s)>8_000_000 or s.count(ANCHOR)!=1 or
        MARKER in s or s.count("NGO_MINI_APP_V051_D1_READBACK_STATUS_COMPATIBILITY")!=1 or
        s.count('const __ngoMiniAppDirectRouteEnabled=true;')!=1):
        raise RuntimeError("Current live v0.5.1 fingerprint missing, abort")
    out=s.replace(ANCHOR,ANCHOR+ROUTE,1)
    if out.count(MARKER)!=1:return_error=1
    else:return_error=0
    if return_error:raise RuntimeError("Read-only aggregate probe patch incorrect")
    return out
def main():
    if (len(sys.argv)!=3 or os.getenv("GITHUB_ACTIONS")!="true" or
        os.getenv("GITHUB_REF")!="refs/heads/main"):
        raise RuntimeError("Trusted main CI only")
    temp=Path(os.environ.get("RUNNER_TEMP","/tmp")).resolve()
    inp,out=(Path(p).resolve() for p in sys.argv[1:])
    if any(not str(p).startswith(str(temp)+"/") for p in (inp,out)):
        raise RuntimeError("Private JS confined to ephemeral runner temp")
    raw=patch(inp.read_text("utf-8"))
    fd=os.open(out,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,"w",encoding="utf-8") as fp:fp.write(raw)
    print("READONLY_D1_AGGREGATE_PROBE_PATCHED=True")
if __name__=="__main__":
    try:main()
    except RuntimeError as e:raise SystemExit(str(e)) from None
