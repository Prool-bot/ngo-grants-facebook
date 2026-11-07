import importlib.util
import subprocess
from pathlib import Path
from unittest import TestCase, main

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location(
    "patch_live_worker_mini_app",ROOT/"worker"/"patch_live_worker_mini_app.py")
mod=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)

SYNTHETIC = """
// guided Telegram menu v5.8
// x-telegram-bot-api-secret-token
async function getChatMember(){return true;}
async function createRequest(env,chat,userId,d,updateId){return true;}
function defaultDraft(){return {session:'test',stage:'audience'};}
function validatedDraft(d){return !!d;}
async function handleTelegram(env,update){return null;}
export default {async fetch(request,env){return Response.json({ok:true,menu_version:'5.8'});}};
"""

class Tests(TestCase):
    def test_patch_compiles_without_any_real_worker_source(self):
        html=(ROOT/"mini-app"/"preview.html").read_text("utf-8")
        bridge=(ROOT/"worker"/"mini_app_keyboard_bridge.mjs").read_text("utf-8")
        patched=mod.patch_worker(SYNTHETIC,html,bridge)
        self.assertIn('data-native-send=\\\"true\\\"',patched)
        self.assertIn('https://telegram.org/js/telegram-web-app.js',patched)
        self.assertIn('NGO_GRANTS_NATIVE_MINI_APP_V01',patched)
        self.assertIn('/mini-app',patched)
        result=subprocess.run(["node","--input-type=module","--check"],
            input=patched,text=True,capture_output=True)
        self.assertEqual(result.returncode,0,"Patched synthetic Worker must compile")
    def test_unknown_worker_version_fails_closed(self):
        html=(ROOT/"mini-app"/"preview.html").read_text("utf-8")
        bridge=(ROOT/"worker"/"mini_app_keyboard_bridge.mjs").read_text("utf-8")
        with self.assertRaises(RuntimeError):
            mod.patch_worker(SYNTHETIC.replace("5.8","5.7"),html,bridge)
    def test_missing_webhook_signature_fails_closed(self):
        html=(ROOT/"mini-app"/"preview.html").read_text("utf-8")
        bridge=(ROOT/"worker"/"mini_app_keyboard_bridge.mjs").read_text("utf-8")
        with self.assertRaises(RuntimeError):
            mod.patch_worker(SYNTHETIC.replace("x-telegram-bot-api-secret-token","gone"),html,bridge)
    def test_cannot_patch_twice(self):
        html=(ROOT/"mini-app"/"preview.html").read_text("utf-8")
        bridge=(ROOT/"worker"/"mini_app_keyboard_bridge.mjs").read_text("utf-8")
        once=mod.patch_worker(SYNTHETIC,html,bridge)
        with self.assertRaises(RuntimeError):
            mod.patch_worker(once,html,bridge)

if __name__=="__main__":main()
