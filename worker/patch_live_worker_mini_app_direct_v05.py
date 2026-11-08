"""Prepare a strict, disabled-by-default v0.5 direct Mini App Worker.

The v0.4 production source is reconstructed only from the known most-recent
inactive *schema probe* by exactly removing its known inserted route.
Scripts and secrets never leave an ephemeral GitHub Actions runner.

Adds two paths: GET /mini-app/direct (UI) and a DISABLED POST order route.
The actual order code is unit-tested with fake D1 and Telegram, not activated.
"""
from __future__ import annotations
import json
from pathlib import Path
import re
from patch_staged_readonly_schema_route import ROUTE_BODY

BASE_MARKERS=(
    "NGO_GRANTS_NATIVE_MINI_APP_V01",
    "NGO_MINI_APP_NAV_FIX_V02",
    "NGO_MINI_APP_DIRECT_START_V03",
    "NGO_MINI_APP_FOP_STATUS_HINT_V04",
)
SCHEMA_MARKER="NGO_MINI_APP_STAGE_SCHEMA_READ_ONLY_V01"
DIRECT_MARKER="NGO_MINI_APP_DIRECT_API_DORMANT_V05"
TELL_ANCHOR="async function tell(env,chatId,text,markup=null,editId=null){"
FETCH_ANCHOR="export default {async fetch(request,env){"
DISABLED_FLAG="const __ngoMiniAppDirectRouteEnabled=false;"

def once(src,old,new,description):
    if src.count(old)!=1:
        raise RuntimeError("Mini App v0.5 Worker source anchor changed: "+description)
    return src.replace(old,new,1)

def reconstruct_base(source:str)->str:
    if not isinstance(source,str) or not source or len(source)>8_000_000:
        raise RuntimeError("Unknown latest private Worker content")
    if source.count(SCHEMA_MARKER)!=1 or DIRECT_MARKER in source:
        raise RuntimeError("Latest private Worker was not the verified dormant D1 schema version")
    for marker in BASE_MARKERS:
        if source.count(marker)!=1:
            raise RuntimeError("Known deployed v0.4 Worker fingerprint changed")
    # The earlier stage-only candidate was built using this exact splice.
    original=once(source,"\n"+ROUTE_BODY,"","exact stage-only D1 schema splice")
    if (SCHEMA_MARKER in original or
        "menu_version:'5.8'" not in original or
        original.count(TELL_ANCHOR)!=1 or
        original.count(FETCH_ANCHOR)!=1):
        raise RuntimeError("Original Worker could not be reconstructed exactly")
    return original

def module_body(path:Path)->str:
    src=path.read_text("utf-8")
    # All three embedded modules have ESM exports; strip only known syntax.
    src=re.sub(r"(?m)^import \{validateTelegramInitData\} from \"\./mini_app_verify_init_data.mjs\";\s*","",src)
    src=re.sub(r"(?m)^export\s+(?=(?:const|function|async|class)\b)","",src)
    if re.search(r"(?m)^\s*(?:import|export)\b",src):
        raise RuntimeError("Unexpected ESM syntax in Mini App adapter bundle")
    return src

def bundle(root:Path)->str:
    verification=module_body(root/"worker/mini_app_verify_init_data.mjs")
    endpoint=module_body(root/"worker/mini_app_order_endpoint.mjs")
    adapter=module_body(root/"worker/mini_app_live_d1_adapter.mjs")
    if any(len(x)>40000 for x in (verification,endpoint,adapter)):
        raise RuntimeError("Unexpected JS bundle size")
    return (
        "const __ngoDirectAuth=(()=>{\n"+verification+
        "\nreturn {validateTelegramInitData};})();\n"+
        "const __ngoDirectEndpoint=(({validateTelegramInitData})=>{\n"+
        endpoint+"\nreturn {handleMiniAppOrder};})(__ngoDirectAuth);\n"+
        "const __ngoDirectQueue=(()=>{\n"+adapter+
        "\nreturn {createExistingQueueAdapter};})();\n"
    )

def direct_html(path:Path)->str:
    html=path.read_text("utf-8")
    if (html.count('data-native-send="false"')!=1 or
        html.count('data-direct-send="false"')!=1 or
        "NgoGrantsDirectClient" not in html or
        "telegram-web-app.js" in html):
        raise RuntimeError("Dormant direct-preview HTML fingerprint changed")
    return (html.replace('data-direct-send="false"',
                         'data-direct-send="true"',1)
       .replace("</head>",
          '<script src="https://telegram.org/js/telegram-web-app.js"></script>\n</head>',1))

def patch(base:str,root:Path)->str:
    if (DIRECT_MARKER in base or SCHEMA_MARKER in base or
        base.count(FETCH_ANCHOR)!=1 or
        base.count(TELL_ANCHOR)!=1 or
        any(base.count(m)!=1 for m in BASE_MARKERS)):
        raise RuntimeError("Unexpected live v0.4 Worker baseline")
    content=bundle(root)
    html=direct_html(root/"mini-app/direct-preview.html")
    preamble=("\n// "+DIRECT_MARKER+"\n"+DISABLED_FLAG+"\n"+
              "const __ngoMiniAppDirectHTML="+json.dumps(html,ensure_ascii=True)+";\n"+
              content)
    base=once(base,FETCH_ANCHOR,preamble+FETCH_ANCHOR,"fetch main")
    base=once(base,TELL_ANCHOR,TELL_ANCHOR+"""
  // Only a server-verified direct Mini App request may set this private
  // per-request flag. Never allow a failed bot DM to hide a D1 commit.
  if(env&&env.__miniAppHttpOrderMode===true)return {message_id:0};
""","message delivery guard")
    route="""
  // NGO Grants Direct Mini App v0.5; production activation is SEPARATE.
  const __directPath=new URL(request.url).pathname;
  if(__directPath==="/mini-app/direct"){
    if(request.method!=="GET")
      return new Response("Method Not Allowed",{status:405,headers:{allow:"GET"}});
    return new Response(__ngoMiniAppDirectHTML,{status:200,headers:{
      "content-type":"text/html; charset=utf-8",
      "cache-control":"no-store",
      "x-content-type-options":"nosniff",
      "x-robots-tag":"noindex, nofollow",
      "x-ngo-mini-app-direct-version":"0.5-stage"
    }});
  }
  if(__directPath==="/api/mini-app/order"){
    if(!__ngoMiniAppDirectRouteEnabled)
      return new Response(JSON.stringify({ok:false,error:"Not enabled"}),{
        status:503,headers:{"content-type":"application/json",
                            "cache-control":"no-store"}});
    const __directEnv={...env,MINI_APP_ORDER_ENABLED:"true",
      __miniAppDirectSuppressDMAvailable:true};
    const __enqueue=__ngoDirectQueue.createExistingQueueAdapter({
      env:__directEnv,createRequest,defaultDraft,validatedDraft
    });
    return __ngoDirectEndpoint.handleMiniAppOrder(request,__directEnv,{
      enqueueExistingOrder:__enqueue
    });
  }
"""
    base=once(base,FETCH_ANCHOR,FETCH_ANCHOR+route,"HTTP endpoint")
    if (base.count(DIRECT_MARKER)!=1 or base.count(DISABLED_FLAG)!=1 or
        base.count("/api/mini-app/order")!=1 or
        base.count("if(env&&env.__miniAppHttpOrderMode===true)")!=1):
        raise RuntimeError("Direct Mini App staging verification failed")
    return base
