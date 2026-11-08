"""Stage-only read-only Worker D1 schema route, never deployed to production.

The live Worker source is processed inside a private GitHub Actions runner.
Only four PRAGMA table_info/index_list statements per existing table may run,
and only with valid SYNC_SECRET bearer token on a staged version override.
"""
from __future__ import annotations
import re

MARKER="NGO_MINI_APP_STAGE_SCHEMA_READ_ONLY_V01"
ROUTE="/_internal/miniapp/d1-schema-audit"
ANCHOR=r"(\basync\s+fetch\s*\(\s*request\s*,\s*env\s*\)\s*\{)"

ROUTE_BODY="""
  // NGO_MINI_APP_STAGE_SCHEMA_READ_ONLY_V01
  if(new URL(request.url).pathname==="/_internal/miniapp/d1-schema-audit"){
    if(request.method!=="GET")
      return new Response("Method Not Allowed",{status:405,headers:{allow:"GET"}});
    const token=env.SYNC_SECRET;
    if(!token || request.headers.get("authorization")!=="Bearer "+token)
      return new Response("Forbidden",{status:403,headers:{"cache-control":"no-store"}});
    const tables=["requests","legacy_limits","settings","catalogs"];
    const inspected={};
    for(const table of tables){
      // Table names are compile-time constants; no user-supplied SQL.
      const cols=await env.DB.prepare("PRAGMA table_info("+table+")").all();
      const indexes=await env.DB.prepare("PRAGMA index_list("+table+")").all();
      if(!cols || !cols.success || !Array.isArray(cols.results)||
         !indexes || !indexes.success || !Array.isArray(indexes.results))
        return new Response("Schema unavailable",{status:503});
      inspected[table]={
        columns:cols.results.map(c=>({
          name:String(c.name||""),type:String(c.type||""),
          pk:Number(c.pk||0),notnull:Boolean(c.notnull)
        })),
        unique_indexes:indexes.results.filter(i=>Number(i.unique)===1).length,
        index_count:indexes.results.length
      };
    }
    return new Response(JSON.stringify({ok:true,schema:inspected}),{
      status:200,headers:{
        "content-type":"application/json; charset=utf-8",
        "cache-control":"no-store",
        "x-content-type-options":"nosniff",
        "x-miniapp-schema-stage":"1"
      }
    });
  }
"""

def patch(source:str)->str:
    if not source or len(source)>8_000_000 or MARKER in source:
        raise RuntimeError("Unexpected or already-patched Worker source")
    for req in ("NGO_GRANTS_NATIVE_MINI_APP_V01",
                "NGO_MINI_APP_NAV_FIX_V02",
                "NGO_MINI_APP_DIRECT_START_V03",
                "NGO_MINI_APP_FOP_STATUS_HINT_V04",
                "menu_version:'5.8'"):
        if source.count(req)!=1:
            raise RuntimeError("Live Worker baseline did not match approved v0.4")
    matches=list(re.finditer(ANCHOR,source))
    if len(matches)!=1:
        raise RuntimeError("Expected exactly one Worker fetch handler")
    m=matches[0]
    result=source[:m.end()]+"\n"+ROUTE_BODY+source[m.end():]
    if result.count(MARKER)!=1 or result.count(ROUTE)!=1:
        raise RuntimeError("Staged schema-only route could not be verified")
    return result
