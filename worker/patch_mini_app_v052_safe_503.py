"""Surgical v0.5.2 safe 503 stage diagnostics and embedded Telegram UI.

Only exact deployed v0.5.1 source may be modified. Compare embedded HTML
byte-for-byte with pre-upgrade repository template before rewriting it.
No user data, Worker source or API tokens appear in stdout/artifacts.
"""
from __future__ import annotations
import json,os,re,sys
from pathlib import Path
from patch_live_worker_mini_app_direct_v05 import direct_html
from patch_mini_app_d1_aggregate_probe_v052 import ROUTE as PREVIOUS_TEMP_READONLY_ROUTE

MARKER="NGO_MINI_APP_V052_503_CATEGORY_DIAGNOSTIC"
OLD_HTML_FN=""" function jsonError(response){
   return new Error(ERRORS[response?.status]||'Не вдалося підтвердити замовлення.');
 }
"""
NEW_HTML_FN=""" async function jsonError(response){
   let message=ERRORS[response?.status]||'Не вдалося підтвердити замовлення.';
   if(response?.status===503){
     let code='UNKNOWN';
     try{
       const body=await response.json();
       const known=['CONFIG','D1_READ','QUEUE_NO_COMMIT','TELEGRAM_UPSTREAM'];
       if(known.includes(body?.error_code))code=body.error_code;
     }catch(_){/* Do not log private server errors or request parameters. */}
     message+=' (код: '+code+')';
   }
   return new Error(message);
 }
"""
HTML_OLD_A="         throw jsonError(response);"
HTML_NEW_A="         throw await jsonError(response);"
OLD_READ='''  const row=await DB.prepare(
    "SELECT update_id, day, status FROM requests WHERE update_id = ? LIMIT 1"
  ).bind(updateId).first();'''
NEW_READ='''  let row;
  try{
    row=await DB.prepare(
      "SELECT update_id, day, status FROM requests WHERE update_id = ? LIMIT 1"
    ).bind(updateId).first();
  }catch(_){fail("D1_READ");}'''
OLD_LAST='''    return json(503,{ok:false,error:"Не вдалося підтвердити замовлення. Спробуйте перевірити стан черги у боті."});'''
NEW_LAST='''    const known=["CONFIG","D1_READ","QUEUE_NO_COMMIT","TELEGRAM_UPSTREAM"];
    return json(503,{ok:false,error:"Не вдалося підтвердити замовлення.",
      error_code:known.includes(code)?code:"UNKNOWN"});'''
def replace_one(raw:str,old:str,new:str,why:str)->str:
    if raw.count(old)!=1:
        raise RuntimeError("Unexpected active Worker fingerprint: "+why)
    return raw.replace(old,new,1)

def patch(src:str,root:Path)->str:
    # Cloudflare's raw script download may return the last staged source
    # rather than the 100%-deployed source. Our prior read-only diagnostic
    # created one exact temporary route. Strip it ONLY with byte-for-byte
    # equality to the known audited route; never carry a debug endpoint into
    # production accidentally.
    if 'NGO_MINI_APP_READONLY_D1_AGG_V052' in src:
        if src.count(PREVIOUS_TEMP_READONLY_ROUTE)!=1:
            raise RuntimeError('Unknown previously staged Worker diagnostic source')
        src=src.replace(PREVIOUS_TEMP_READONLY_ROUTE,'',1)
    if 'NGO_MINI_APP_READONLY_D1_AGG_V052' in src:
        raise RuntimeError('Temporary internal audit route still present')
    required=("NGO_MINI_APP_V051_D1_READBACK_STATUS_COMPATIBILITY",
              "NGO_MINI_APP_DIRECT_API_DORMANT_V05",
              "NGO_GRANTS_NATIVE_MINI_APP_V01","NGO_MINI_APP_NAV_FIX_V02",
              "NGO_MINI_APP_DIRECT_START_V03","NGO_MINI_APP_FOP_STATUS_HINT_V04",
              "menu_version:'5.8'",'const __ngoMiniAppDirectRouteEnabled=true;')
    if (not src or len(src)>8_000_000 or MARKER in src or
        any(src.count(x)!=1 for x in required)):
        raise RuntimeError("Unexpected approved production Worker; no patch")
    prefix="const __ngoMiniAppDirectHTML="
    if src.count(prefix)!=1:raise RuntimeError("Embedded app HTML anchor changed")
    idx=src.index(prefix)+len(prefix)
    try:
        live_html,consumed=json.JSONDecoder().raw_decode(src[idx:])
    except ValueError:
        raise RuntimeError("Embedded HTML malformed") from None
    if not isinstance(live_html,str) or src[idx+consumed:idx+consumed+1]!=";":
        raise RuntimeError("Embedded HTML assignment changed")
    # Repo template was already upgraded; reverse ONLY the new JS fragments
    # and compare to the EXACT embedded live v0.5.1 HTML.
    new_html=direct_html(root/"mini-app/direct-preview.html")
    if (new_html.count(NEW_HTML_FN)!=1 or new_html.count(HTML_NEW_A)!=1 or
        OLD_HTML_FN in new_html or HTML_OLD_A in new_html):
        raise RuntimeError("Expected proposed direct-client upgrade missing")
    old_html=new_html.replace(NEW_HTML_FN,OLD_HTML_FN,1).replace(HTML_NEW_A,HTML_OLD_A,1)
    if live_html!=old_html:raise RuntimeError("Current live Mini App HTML differs from approved template")
    src=src[:idx]+json.dumps(new_html,ensure_ascii=True)+src[idx+consumed:]
    start=re.search(r"\basync\s+function\s+checkChannelMembership\s*\(",src)
    end=src.find("/** Select only the receipt",start.end() if start else 0)
    if not start or end<0:raise RuntimeError("Membership function boundary unknown")
    member=src[start.start():end]
    cnt=member.count('fail("UPSTREAM_UNAVAILABLE")')
    if not 4<=cnt<=8:raise RuntimeError("Unexpected membership error branches")
    src=src[:start.start()]+member.replace('fail("UPSTREAM_UNAVAILABLE")',
                                         'fail("TELEGRAM_UPSTREAM")')+src[end:]
    src=replace_one(src,OLD_READ,NEW_READ,"D1 lookup failure category")
    src=replace_one(src,'if(legacyError)fail("UPSTREAM_UNAVAILABLE");',
                   'if(legacyError)fail("QUEUE_NO_COMMIT");',"legacy queue failure category")
    src=replace_one(src,OLD_LAST,NEW_LAST,"final endpoint 503 classification")
    gate="const __ngoMiniAppDirectRouteEnabled=true;"
    src=replace_one(src,gate,"// "+MARKER+"\n"+gate,"single diagnostic marker")
    if (src.count(MARKER)!=1 or src.count("TELEGRAM_UPSTREAM")<4 or
        src.count("D1_READ")<1 or src.count("QUEUE_NO_COMMIT")<2 or
        src.count("error_code:known.includes(code)?code:")==0):
        raise RuntimeError("Diagnostic instrumentation incomplete")
    return src

def main():
    if (len(sys.argv)!=3 or os.getenv("GITHUB_ACTIONS")!="true" or
        os.getenv("GITHUB_REF")!="refs/heads/main"):
        raise RuntimeError("Trusted main release only")
    temp=Path(os.environ.get("RUNNER_TEMP","/tmp")).resolve()
    before,after=[Path(p).resolve() for p in sys.argv[1:]]
    if any(not str(x).startswith(str(temp)+"/") for x in (before,after)):
        raise RuntimeError("Ephemeral source files required")
    patched=patch(before.read_text("utf-8"),Path(__file__).resolve().parents[1])
    fd=os.open(after,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,"w",encoding="utf-8") as fp:fp.write(patched)
    print("V052_PRIVACY_SAFE_503_DIAGNOSTIC_PATCHED=True")
    print("WORKER_SOURCE_PRIVATE=True")
if __name__=="__main__":
    try:main()
    except RuntimeError as e:raise SystemExit(str(e)) from None
