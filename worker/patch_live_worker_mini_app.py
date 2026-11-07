"""Patch deployed v5.8 Worker in memory into a staged Mini App-enabled version.

No production Worker source is committed or printed. Every insertion requires
strict single-match anchors. The staged version inherits current secrets/D1.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

DOMAIN="https://ngo-grants-instant-bot.oleh-protasoff.workers.dev"
MARKER="NGO_GRANTS_NATIVE_MINI_APP_V01"

def patch_worker(source: str, app_html: str, bridge_module: str) -> str:
    if not source or len(source)>8_000_000 or MARKER in source:
        raise RuntimeError("Unexpected or already-patched Worker source")
    for expected in ("menu_version:'5.8'","async function handleTelegram",
                     "function createRequest","function defaultDraft",
                     "function validatedDraft","getChatMember","export default"):
        if expected not in source:
            raise RuntimeError("Worker changed; refusing Mini App patch: "+expected)
    if "x-telegram-bot-api-secret-token" not in source.casefold():
        raise RuntimeError("Webhook secret header missing; Mini App bridge blocked")
    if "data-native-send=\"false\"" not in app_html:
        raise RuntimeError("Static preview was not safely send-disabled")
    if "sendData(data)" not in app_html:
        raise RuntimeError("UI lacks native sendData activation gate")
    if "MINI_APP_MARKER" not in bridge_module or "processMiniAppUpdate" not in bridge_module:
        raise RuntimeError("Native Telegram Mini App bridge not present")
    if re.search(r"^\s*import\s",bridge_module,re.M):
        raise RuntimeError("Expected self-contained bridge without imports")
    # Use a *separate in-memory copy*. Repo preview stays offline forever.
    served=app_html.replace('data-native-send="false"',
                            'data-native-send="true"',1)
    served=served.replace("</head>",
        '<script src="https://telegram.org/js/telegram-web-app.js"></script>\n</head>',1)
    bridge=re.sub(r"^export\s+","",bridge_module,flags=re.M)
    helpers=f"""
// {MARKER} BEGIN — isolated Telegram Keyboard Mini App integration.
const __ngoMiniAppHTML={json.dumps(served,ensure_ascii=True)};
const __ngoMiniAppBridge=(()=>{{
{bridge}
return {{processMiniAppUpdate,miniAppKeyboard}};
}})();
const __ngoMiniAppOrigin={json.dumps(DOMAIN)};
async function __ngoMiniAppTelegramSend(env,chatId,text,keyboard=null){{
  const data={{chat_id:chatId,text,disable_web_page_preview:true}};
  if(keyboard)data.reply_markup=keyboard;
  const response=await fetch("https://api.telegram.org/bot"+env.BOT_TOKEN+"/sendMessage",{{
    method:"POST",headers:{{"content-type":"application/json"}},
    body:JSON.stringify(data)
  }});
  if(!response.ok)throw new Error("Telegram Mini App keyboard delivery failed");
}}
"""
    # Locate the one Worker fetch handler and handleTelegram function:
    fetch_anchor=r"(\basync\s+fetch\s*\(\s*request\s*,\s*env\s*\)\s*\{)"
    handler_anchor=r"(\basync\s+function\s+handleTelegram\s*\(\s*env\s*,\s*update\s*\)\s*\{)"
    if len(re.findall(fetch_anchor,source))!=1 or len(re.findall(handler_anchor,source))!=1:
        raise RuntimeError("Unknown Worker fetch/Telegram handler signatures")
    if source.count("export default")!=1:
        raise RuntimeError("Unexpected Worker export count")
    patched=source.replace("export default",helpers+"\nexport default",1)
    fetch_body="""
  // Native Mini App static UI: no token, no user data, no D1 access.
  if(new URL(request.url).pathname==="/mini-app"){{
    if(request.method!=="GET")
      return new Response("Method Not Allowed",{{status:405,headers:{{allow:"GET"}}}});
    return new Response(__ngoMiniAppHTML,{{status:200,headers:{{
      "content-type":"text/html; charset=utf-8",
      "cache-control":"no-store",
      "x-content-type-options":"nosniff",
      "referrer-policy":"no-referrer",
      "x-ngo-mini-app-version":"0.1"
    }}}});
  }}
""".replace("{{","{").replace("}}","}")
    patched=re.sub(fetch_anchor,lambda m:m.group(1)+"\n"+fetch_body,patched,count=1)
    handler_body="""
  // Telegram WebApp.sendData is delivered as a signed webhook update.
  // Never accept direct client-supplied user IDs or JSON over a public endpoint.
  const __miniMessage=update&&update.message;
  if(__miniMessage && typeof __miniMessage.text==="string" &&
     /^\\/assistant(?:@[A-Za-z0-9_]+)?$/.test(__miniMessage.text.trim()) &&
     __miniMessage.chat && __miniMessage.chat.type==="private"){{
    const __miniKeyboard=__ngoMiniAppBridge.miniAppKeyboard(__ngoMiniAppOrigin);
    await __ngoMiniAppTelegramSend(env,__miniMessage.chat.id,
      "🤖 Відкрийте грантового помічника кнопкою нижче. Для повернення до звичайного меню натисніть /start.",
      __miniKeyboard);
    return;
  }}
  if(__miniMessage && __miniMessage.web_app_data){{
    try{{
      return await __ngoMiniAppBridge.processMiniAppUpdate(update,env,{{
        defaultDraft,validatedDraft,createRequest
      }});
    }}catch(_error){{
      if(__miniMessage.chat&&__miniMessage.chat.type==="private"){{
        await __ngoMiniAppTelegramSend(env,__miniMessage.chat.id,
          "Не вдалося прийняти анкету. Перевірте стан черги у боті перед повторним замовленням.");
      }}
      return;
    }}
  }}
""".replace("{{","{").replace("}}","}")
    patched=re.sub(handler_anchor,lambda m:m.group(1)+"\n"+handler_body,patched,count=1)
    if patched.count(MARKER)!=1 or "/mini-app" not in patched:
        raise RuntimeError("Worker patch final validation failed")
    return patched


if __name__=="__main__":
    import sys
    if len(sys.argv)!=4:
        raise RuntimeError("Usage: patch_worker.py original_worker.js preview.html native_bridge.mjs")
    original=Path(sys.argv[1]).read_text("utf-8")
    html=Path(sys.argv[2]).read_text("utf-8")
    bridge=Path(sys.argv[3]).read_text("utf-8")
    sys.stdout.write(patch_worker(original,html,bridge))
