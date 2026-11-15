"""Authenticated, stage-only, write-free real Telegram Mini App preflight.

Deploy only as a temporary 0.01% Worker canary; the preflight route checks
HMAC, live member lookup, D1 read, facet validation but short-circuits BEFORE
any createRequest or D1 insert. Result is a safe enum, no user data.
"""
from __future__ import annotations
import os,re,sys
from pathlib import Path
MARKER="NGO_MINIAPP_V052_STAGE_ONLY_AUTH_DRYRUN"
ANCHOR=r"\bexport\s+default\s*\{\s*async\s+fetch\s*\(\s*request\s*,\s*env\s*\)\s*\{"
ROUTE='''
  // NGO_MINIAPP_V052_STAGE_ONLY_AUTH_DRYRUN
  if(new URL(request.url).pathname==="/_internal/miniapp/signed-dryrun"){
    if(request.method!=="POST")return new Response("Method not allowed",{status:405});
    if(!env.SYNC_SECRET||request.headers.get("authorization")!=="Bearer "+env.SYNC_SECRET)
      return new Response("Forbidden",{status:403});
    let input;
    try{
      const raw=await request.text();
      if(raw.length>16384)throw Error("size");
      input=JSON.parse(raw);
    }catch(_){return new Response("Bad request",{status:400});}
    if(!input||typeof input!=="object"||Array.isArray(input)||
       Object.keys(input).some(k=>!["initData","facets","idempotencyKey"].includes(k)))
      return new Response("Bad request",{status:400});
    // This adapter CANNOT write. The actual legacy transaction is replaced
    // with a hard stop before createRequest is entered. All other guards
    // (auth, form, member, initial D1 SELECT) run unmodified.
    const guarded={...env,MINI_APP_ORDER_ENABLED:"true",
                   __miniAppDirectSuppressDMAvailable:true};
    const safeQueue=__ngoDirectQueue.createExistingQueueAdapter({
      env:guarded,
      defaultDraft,validatedDraft,
      createRequest:async()=>{throw Error("DRY_RUN_WRITE_NEVER_CALLED");}
    });
    const internal=new Request(new URL("/api/mini-app/order",request.url),{
      method:"POST",headers:{"content-type":"application/json"},
      body:JSON.stringify(input)
    });
    const response=await __ngoDirectEndpoint.handleMiniAppOrder(
      internal,guarded,{enqueueExistingOrder:safeQueue});
    const outcome=await response.json();
    const allowed=["CONFIG","D1_READ","QUEUE_NO_COMMIT","TELEGRAM_UPSTREAM",
                   "NOT_SUBSCRIBED","DAILY_LIMIT","CONFLICT","UNKNOWN"];
    const stage=allowed.includes(outcome.error_code)?outcome.error_code:
                response.status===401?"AUTH":
                response.status===400?"FACETS":
                response.status===403?"NOT_SUBSCRIBED":
                response.status===429?"DAILY_LIMIT":
                response.status===409?"CONFLICT":
                response.status===200?"EXISTING":"UNKNOWN";
    return new Response(JSON.stringify({ok:true,kind:"dryrun-no-writes",
      phase:stage,http_status:response.status}),{status:200,headers:{
        "content-type":"application/json","cache-control":"no-store",
        "x-ngo-miniapp-dryrun":"no-writes","x-content-type-options":"nosniff"}});
  }
'''
def patch(src:str)->str:
    if (not src or len(src)>8_000_000 or MARKER in src or
        src.count("NGO_MINI_APP_V052_503_CATEGORY_DIAGNOSTIC")!=1 or
        'NGO_MINI_APP_READONLY_D1_AGG_V052' in src or
        src.count('const __ngoMiniAppDirectRouteEnabled=true;')!=1):
        raise RuntimeError("Unexpected current production v0.5.2 fingerprint")
    matches=list(re.finditer(ANCHOR,src))
    if len(matches)!=1:raise RuntimeError("No exact Worker fetch entry")
    m=matches[0]
    output=src[:m.end()]+ROUTE+src[m.end():]
    if output.count(MARKER)!=1:raise RuntimeError("Wrong staging route")
    return output
def main():
    if (len(sys.argv)!=3 or os.getenv("GITHUB_ACTIONS")!="true" or
        os.getenv("GITHUB_REF")!="refs/heads/main"):
        raise RuntimeError("Only main GitHub Actions may stage private Worker")
    temp=Path(os.environ.get("RUNNER_TEMP","/tmp")).resolve()
    original,after=(Path(x).resolve() for x in sys.argv[1:])
    if any(not str(x).startswith(str(temp)+"/") for x in (original,after)):
        raise RuntimeError("All private source must remain in runner temp")
    raw=patch(original.read_text("utf-8"))
    fd=os.open(after,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,"w",encoding="utf8") as f:f.write(raw)
    print("TEMPORARY_SIGNED_MAIN_MINI_APP_DRY_RUN_STAGED=True")
    print("REAL_ORDER_CREATION_REPLACED_WITH_THROW_BEFORE_ENTRY=True")
if __name__=="__main__":
    try:main()
    except RuntimeError as e:raise SystemExit(str(e)) from None
