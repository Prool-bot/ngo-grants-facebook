"""Guarded, one-purpose Worker patch: open NGO Grants Mini App directly after /start.

Cloudflare Worker source remains private: fetched inside Actions runner memory,
never committed or logged. This patch changes only the initial Telegram /start
handler and the public HTML version header; the original /request, /catalogs,
web_app_data, D1, quota, and PDF logic remain unchanged.
"""
from __future__ import annotations

V01="NGO_GRANTS_NATIVE_MINI_APP_V01"
V02="NGO_MINI_APP_NAV_FIX_V02"
V03="NGO_MINI_APP_DIRECT_START_V03"
ANCHOR="  const __miniMessage=update&&update.message;\n"
VERSION_OLD='"x-ngo-mini-app-version":"0.2"'
VERSION_NEW='"x-ngo-mini-app-version":"0.3"'

ENTRY="""  // NGO_MINI_APP_DIRECT_START_V03: show the already deployed bot's
  // Telegram reply-keyboard WebApp immediately upon pressing Start.
  // /assistant remains an optional backwards-compatible command.
  if(__miniMessage && typeof __miniMessage.text==="string" &&
     /^\\/start(?:@[A-Za-z0-9_]+)?(?:\\s+[A-Za-z0-9_-]{1,64})?$/.test(__miniMessage.text.trim()) &&
     __miniMessage.chat && __miniMessage.chat.type==="private" &&
     __miniMessage.from && __miniMessage.from.id===__miniMessage.chat.id){
    const __startKeyboard=__ngoMiniAppBridge.miniAppKeyboard(__ngoMiniAppOrigin);
    __startKeyboard.keyboard=[
      __startKeyboard.keyboard[0],
      [{text:"/request"},{text:"/catalogs"}],
      [{text:"/help"},{text:"/status"}]
    ];
    await __ngoMiniAppTelegramSend(env,__miniMessage.chat.id,
      "🤖 Вітаємо в NGO Grants AI!\\n\\n"+
      "Щоб знайти грантові можливості, просто натисніть кнопку "+
      "«🤖 Відкрити грантового помічника» нижче — без додаткових команд.\\n\\n"+
      "Також доступні: /request — звичайне оформлення, "+
      "/catalogs — готові каталоги, /help — довідка.",
      __startKeyboard);
    return;
  }
"""

def patch(source: str) -> str:
    if not source or len(source)>8_000_000:
        raise RuntimeError("Unexpected Worker JS size")
    for marker in (V01,V02,"menu_version:'5.8'","async function handleTelegram",
                   "export default"):
        if source.count(marker)<1:
            raise RuntimeError("Missing known production Worker marker: "+marker)
    if source.count(V01)!=1 or source.count(V02)!=1 or V03 in source:
        raise RuntimeError("Wrong Mini App baseline version or patch already applied")
    if source.count(ANCHOR)!=1:
        raise RuntimeError("Telegram handler entry anchor changed")
    start=source.index(ANCHOR)
    adjacent=source[start:start+1000]
    if("/assistant" not in adjacent or "processMiniAppUpdate" not in adjacent):
        raise RuntimeError("Current /assistant and web_app_data bridge structure changed")
    if source.count(VERSION_OLD)!=1 or VERSION_NEW in source:
        raise RuntimeError("Expected Mini App HTML route v0.2, not another version")
    result=source.replace(ANCHOR,ANCHOR+ENTRY,1).replace(VERSION_OLD,VERSION_NEW,1)
    if(result.count(V03)!=1 or result.count(V01)!=1 or result.count(V02)!=1):
        raise RuntimeError("Patched Worker structural verification failed")
    if result.count(VERSION_NEW)!=1:
        raise RuntimeError("Mini App new version header missing")
    return result
