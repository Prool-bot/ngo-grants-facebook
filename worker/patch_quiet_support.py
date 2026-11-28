"""Minimal, opt-in Donatello links for the existing live Worker.
No payment processing, new messages, database changes, or order-flow changes.
Run only on an exact approved active version in the ephemeral runner.
"""
from __future__ import annotations
import json
import os
import re
import sys
from pathlib import Path

URL = "https://donatello.to/NGO_Grants"
LABEL = "❤️ Підтримати проєкт"
MARKER = "NGO_QUIET_SUPPORT_V01"
DIRECT = "const __ngoMiniAppDirectHTML="
NATIVE = "const __ngoMiniAppHTML="
TELL = "async function tell(env,chatId,text,markup=null,editId=null){"
NATIVE_TELL = "async function __ngoMiniAppTelegramSend(env,chatId,text,keyboard=null){"
HANDLER = r"(\basync\s+function\s+handleTelegram\s*\(\s*env\s*,\s*update\s*\)\s*\{)"
BLOCK = (
    '<div id="ngoQuietSupport" style="text-align:center;margin:18px 0 4px">'
    '<a id="ngoQuietSupportLink" href="' + URL + '" target="_blank" rel="noopener noreferrer"'
    ' style="display:inline-block;color:#576e86;font-size:13px;text-decoration:none;'
    'padding:8px 12px;border:1px solid #dce6f3;border-radius:12px">'
    + LABEL + '</a></div>'
)
SCRIPT = (
    '<script>(function(){var a=document.getElementById("ngoQuietSupportLink");'
    'if(!a)return;a.addEventListener("click",function(e){'
    'var w=window.Telegram&&window.Telegram.WebApp;'
    'if(w&&typeof w.openLink==="function"){try{w.openLink(a.href);e.preventDefault();}catch(_){}}'
    '});})();</script>'
)
def add_link(html: str) -> str:
    if html.count("</main>") != 1 or html.count("</body>") != 1 or URL in html:
        raise RuntimeError("Unexpected or already updated Mini App HTML")
    return html.replace("</main>", BLOCK + "\n</main>", 1).replace("</body>", SCRIPT + "\n</body>", 1)

def splice_html(source: str, prefix: str, served: str | None = None) -> str:
    if source.count(prefix) != 1:
        raise RuntimeError("Embedded HTML literal is not unique")
    at = source.index(prefix) + len(prefix)
    old, used = json.JSONDecoder().raw_decode(source[at:])
    if not isinstance(old, str) or source[at+used:at+used+1] != ";":
        raise RuntimeError("Embedded HTML boundary changed")
    if served is not None and old != served:
        raise RuntimeError("Active served HTML differs from source")
    return source[:at] + json.dumps(add_link(old), ensure_ascii=True) + source[at+used:]

# The existing tell() handles outgoing user messages. Only the known menu
# or a singular positive ready message with a catalog link is eligible.
# Preserve all existing rows and parse mode; never create an additional DM.
HELPER = r'''
// NGO_QUIET_SUPPORT_V01
function __ngoQuietSupportDecorate(chatId,text,markup){
  if(!Number.isSafeInteger(Number(chatId))||Number(chatId)<=0||typeof text!=="string")
    return {text,markup};
  if(text.includes("https://donatello.to/NGO_Grants"))return {text,markup};
  const label="❤️ Підтримати проєкт", url="https://donatello.to/NGO_Grants";
  const inline=Array.isArray(markup?.inline_keyboard), reply=Array.isArray(markup?.keyboard);
  const key=inline?"inline_keyboard":reply?"keyboard":null;
  const rows=key?markup[key]:[];
  const names=rows.flat().map(b=>typeof b==="string"?b:b?.text||"").join(" ").toLowerCase();
  if(names.includes("підтримати проєкт"))return {text,markup};
  const menu=key&&(((names.includes("замовити каталог")||names.includes("знайти гранти"))&&names.includes("каталоги"))||
    (reply&&rows.flat().some(b=>b?.web_app&&b.text?.includes("грантового помічника"))&&names.includes("/start")));
  const plain=text.replace(/<[^>]*>/g," ").replace(/\s+/g," ").toLowerCase();
  const ready=/(?:каталог\s+(?:вже\s+)?готовий|каталог\s+(?:вже\s+)?опубліковано|готовий\s+каталог|каталоги\s+(?:вже\s+)?(?:готові|опубліковано)|добірка\s+(?:вже\s+)?готова)/u.test(plain)
      && !/(?:не\s+готовий|ще\s+не|немає|не\s+знайдено)/u.test(plain)
      && (/(?:https?:\/\/t\.me\/(?:ngo_grants\/\d+|c\/\d+\/\d+))/i.test(text)||
          rows.flat().some(b=>typeof b?.url==="string"&&/^https:\/\/t\.me\/(?:ngo_grants\/\d+|c\/\d+\/\d+)/i.test(b.url)));
  if(menu){
    return {text,markup:{...markup,[key]:[...rows,[inline?{text:label,url}:{text:label}]]}};
  }
  if(ready){
    if(inline||!markup){
      return {text:text+"\n\nЗа бажанням — підтримайте розвиток проєкту.",
        markup:{...(markup||{}),inline_keyboard:[...(inline?rows:[]),[{text:label,url}]]}};
    }
    return {text:text+"\n\nЗа бажанням — підтримайте проєкт: "+url,markup};
  }
  return {text,markup};
}
'''
IN_TELL = '''
  ({text,markup}=__ngoQuietSupportDecorate(chatId,text,markup));
'''
IN_HANDLER = '''
  const __supportMessage=update&&update.message;
  if(__supportMessage&&__supportMessage.chat?.type==="private"&&
     __supportMessage.from?.id===__supportMessage.chat.id&&
     typeof __supportMessage.text==="string"&&
     (/^\\/support(?:@[A-Za-z0-9_]+)?$/.test(__supportMessage.text.trim())||
      __supportMessage.text.trim()==="❤️ Підтримати проєкт")){
    await __ngoMiniAppTelegramSend(env,__supportMessage.chat.id,
      "За бажанням підтримайте розвиток NGO Grants AI. Доступ залишається безкоштовним.",
      {inline_keyboard:[[{text:"❤️ Підтримати проєкт",url:"https://donatello.to/NGO_Grants"}]]});
    return;
  }
'''

def patch(source: str, direct_live: str, native_live: str) -> str:
    if (MARKER in source or not source or len(source)>8_000_000
        or source.count(TELL)!=1 or source.count(NATIVE_TELL)!=1 or len(re.findall(HANDLER,source))!=1
        or source.count("export default")!=1
        or "NGO_MINI_APP_DIRECT_API_DORMANT_V05" not in source
        or "NGO_GRANTS_NATIVE_MINI_APP_V01" not in source
        or "async function __ngoMiniAppTelegramSend" not in source):
        raise RuntimeError("Approved Worker fingerprint changed")
    out=splice_html(source,DIRECT,direct_live)
    out=splice_html(out,NATIVE,native_live)
    out=out.replace(TELL,TELL+IN_TELL,1)
    out=out.replace(NATIVE_TELL,NATIVE_TELL+"\n  const __decorated=__ngoQuietSupportDecorate(chatId,text,keyboard);\n  text=__decorated.text; keyboard=__decorated.markup;\n",1)
    out=re.sub(HANDLER,lambda m:m.group(1)+IN_HANDLER,out,count=1)
    out=out.replace("export default",HELPER+"\nexport default",1)
    if out.count(MARKER)!=1:
        raise RuntimeError("Quiet support patch not unique")
    return out

def native_public_html(gateway: str, version: str | None = None) -> str:
    """Use the existing successful native Mini App smoke request headers."""
    import urllib.request
    import urllib.error
    from deploy_worker_mini_app_fop_v04 import SCRIPT
    if not gateway.startswith("https://") or ".workers.dev" not in gateway:
        raise RuntimeError("Approved production Worker origin required")
    headers={"Accept":"text/html","User-Agent":"NGOGrantsMiniAppRelease/1.0"}
    if version:
        headers["Cloudflare-Workers-Version-Overrides"]=f'{SCRIPT}="{version}"'
    request=urllib.request.Request(gateway.rstrip("/")+"/mini-app",headers=headers,method="GET")
    try:
        with urllib.request.urlopen(request,timeout=20) as response:
            if response.status!=200 or "text/html" not in response.headers.get("Content-Type",""):
                raise RuntimeError("Native Mini App route unhealthy")
            return response.read(120000).decode("utf-8")
    except urllib.error.HTTPError as exc:
        raise RuntimeError("Native Mini App smoke HTTP "+str(exc.code)) from None

def main():
    from patch_mini_app_v054_ui import current_public_html
    if len(sys.argv)!=3 or os.getenv("GITHUB_ACTIONS")!="true" or os.getenv("GITHUB_REF")!="refs/heads/main":
        raise RuntimeError("Main-only approved Worker staging")
    root=Path(os.environ["RUNNER_TEMP"]).resolve()
    before,after=map(lambda p:Path(p).resolve(),sys.argv[1:])
    if before==after or not before.is_relative_to(root) or not after.is_relative_to(root):
        raise RuntimeError("Worker files must stay in runner temp")
    gateway=os.environ["NGO_BOT_GATEWAY_URL"].rstrip("/")
    direct=current_public_html(gateway)
    native=native_public_html(gateway)
    result=patch(before.read_text("utf-8"),direct,native)
    fd=os.open(after,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,"w",encoding="utf-8") as f:f.write(result)
    print("QUIET_SUPPORT_PATCH_VERIFIED=True")

if __name__=="__main__":
    try:main()
    except RuntimeError as e:raise SystemExit(str(e)) from None
