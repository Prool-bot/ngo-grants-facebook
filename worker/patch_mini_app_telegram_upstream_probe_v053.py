"""Temporary protected GET/POST Telegram API method comparison from Cloudflare.

Only authentic signed Main WebApp user is probed. Never log identity, token
or Telegram response body; the route returns safe method/status booleans only.
Restored via canary wrapper; no D1 write or order.
"""
from __future__ import annotations
import os,re,sys
from pathlib import Path
from patch_mini_app_real_session_dryrun import ROUTE as PRIOR_DRYRUN_ROUTE

MARKER="NGO_MINIAPP_STAGE_TELEGRAM_UPSTREAM_METHODS_V053"
ANCHOR=r"\bexport\s+default\s*\{\s*async\s+fetch\s*\(\s*request\s*,\s*env\s*\)\s*\{"
ROUTE='''
  // NGO_MINIAPP_STAGE_TELEGRAM_UPSTREAM_METHODS_V053
  if(new URL(request.url).pathname==="/_internal/miniapp/telegram-upstream-probe"){
    if(request.method!=="POST")return new Response("Method not allowed",{status:405});
    if(!env.SYNC_SECRET||request.headers.get("authorization")!=="Bearer "+env.SYNC_SECRET)
      return new Response("Forbidden",{status:403});
    let input;
    try{
      const raw=await request.text();
      if(raw.length>8192)throw Error("size");
      input=JSON.parse(raw);
      if(Object.keys(input).length!==1||typeof input.initData!=="string")throw Error("shape");
    }catch(_){return new Response("Bad request",{status:400});}
    let auth;
    try{auth=await __ngoDirectAuth.validateTelegramInitData(input.initData,env.BOT_TOKEN,
      {maxAgeSeconds:3600});}
    catch(_){return new Response("Invalid Telegram HMAC",{status:401});}
    const url="https://api.telegram.org/bot"+env.BOT_TOKEN+"/getChatMember";
    const payload=JSON.stringify({chat_id:"@ngo_grants",user_id:auth.userId});
    const configs=[
      {kind:"POST_REDIRECT_ERROR",method:"POST",redirect:"error"},
      {kind:"POST_DEFAULT",method:"POST"},
      {kind:"GET_QUERY",method:"GET"}
    ];
    const result=[];
    for(const config of configs){
      let response;
      try{
        let address=url;
        if(config.kind==="GET_QUERY"){
          const qp=new URLSearchParams({chat_id:"@ngo_grants",user_id:String(auth.userId)});
          address+="?"+qp;
        }
        const init={method:config.method,headers:{"accept":"application/json"}};
        if(config.method==="POST"){
          init.headers["content-type"]="application/json";
          init.body=payload;
        }
        if(config.redirect)init.redirect=config.redirect;
        response=await fetch(address,init);
      }catch(_){
        result.push({kind:config.kind,stage:"NETWORK_EXCEPTION"});continue;
      }
      let body=null;
      try{body=await response.json()}catch(_){}
      const member=body&&typeof body==="object"?body.result:null;
      const status=member&&typeof member==="object"?member.status:null;
      const match=member&&member.user&&member.user.id===auth.userId;
      const allowed=["creator","administrator","member","restricted","left","kicked"];
      const category=response.ok && body?.ok===true && allowed.includes(status) && match===true
        ?"MEMBER_VALID":response.ok && body?.ok===true?"BODY_OR_USER_MISMATCH":
        body?.ok===false?"BOT_API_DENIAL":"UNEXPECTED";
      // Sanitized HTTP/status categories only. Error description and user
      // identity are never returned, retained or logged.
      result.push({kind:config.kind,stage:category,http:response.status,
        bot_error_code:Number.isSafeInteger(body?.error_code)?body.error_code:null,
        status:allowed.includes(status)?status:null});
    }
    return new Response(JSON.stringify({ok:true,kind:"telegram-methods",results:result}),{
      status:200,headers:{"content-type":"application/json","cache-control":"no-store",
       "x-miniapp-telegram-methods":"read-only","x-content-type-options":"nosniff"}});
  }
'''
def patch(src:str)->str:
    if 'NGO_MINIAPP_V052_STAGE_ONLY_AUTH_DRYRUN' in src:
        if src.count(PRIOR_DRYRUN_ROUTE)!=1:
            raise RuntimeError("Cannot remove exact prior temporary preflight route")
        src=src.replace(PRIOR_DRYRUN_ROUTE,"",1)
    if (not src or len(src)>8_000_000 or MARKER in src or
        "NGO_MINIAPP_V052_STAGE_ONLY_AUTH_DRYRUN" in src or
        src.count("NGO_MINI_APP_V052_503_CATEGORY_DIAGNOSTIC")!=1 or
        src.count('const __ngoMiniAppDirectRouteEnabled=true;')!=1):
        raise RuntimeError("Unexpected approved deployed v0.5.2 Worker fingerprint")
    found=list(re.finditer(ANCHOR,src))
    if len(found)!=1:raise RuntimeError("Worker fetch anchor ambiguous")
    m=found[0]
    result=src[:m.end()]+ROUTE+src[m.end():]
    if result.count(MARKER)!=1:raise RuntimeError("Only one read-only route permitted")
    return result
def main():
    if (len(sys.argv)!=3 or os.getenv("GITHUB_ACTIONS")!="true" or
        os.getenv("GITHUB_REF")!="refs/heads/main"):
        raise RuntimeError("Only approved Actions may stage Worker")
    temp=Path(os.environ.get("RUNNER_TEMP","/tmp")).resolve()
    src,dest=[Path(x).resolve() for x in sys.argv[1:]]
    if any(not str(x).startswith(str(temp)+"/") for x in (src,dest)):
        raise RuntimeError("Private Worker must stay in temp")
    new=patch(src.read_text("utf-8"))
    fd=os.open(dest,os.O_EXCL|os.O_CREAT|os.O_WRONLY,0o600)
    with os.fdopen(fd,"w",encoding="utf-8") as file:file.write(new)
    print("PRIVATE_TELEGRAM_API_METHOD_DIAGNOSE_STAGE_READY=True")
if __name__=="__main__":
    try:main()
    except RuntimeError as e:raise SystemExit(str(e)) from None
