"""Offline guards for Mini App v0.5.4 HTML-only production patch."""
import json
from base64 import b64encode
from pathlib import Path
import sys
from unittest import TestCase

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"worker"))
from patch_live_worker_mini_app_direct_v05 import direct_html
from patch_mini_app_v054_ui import patch
from patch_mini_app_real_session_dryrun import ROUTE as VERIFIED_DRYRUN_ROUTE
from mini_app_expected_worker_version import expected_version
from read_live_mini_app_v05_diagnosis import extract_active_module

MARKERS=(
 "NGO_GRANTS_NATIVE_MINI_APP_V01",
 "NGO_MINI_APP_DIRECT_API_DORMANT_V05",
 "NGO_MINIAPP_V053_TELEGRAM_MEMBER_POST_REDIRECT_FIX",
 "const __ngoMiniAppDirectRouteEnabled=true;",
 "menu_version:'5.8'",
)
OLD='<!doctype html><html><head></head><body>Legacy public direct form</body></html>'


def original():
    return "\n".join(MARKERS)+(
       "\nconst __ngoMiniAppDirectHTML="+
       json.dumps(OLD,ensure_ascii=True)+";\n"
       "async function checkChannelMembership(){return true;}\n"
       "export default {async fetch(request,env){return new Response('ok')}};\n"
    )


class V054Tests(TestCase):
    def test_surgical_embedded_html_only_and_version_fallback(self):
        template=direct_html(ROOT/"mini-app/direct-preview.html")
        self.assertIn('data-direct-send="true"',template)
        self.assertIn('id="robotFigure"',template)
        self.assertNotIn('id="greet"',template)
        self.assertIn('id="robotArm"',template)
        src=original()
        result=patch(src,old_live_html=OLD,new_html=template)
        changed=result.replace(json.dumps(template,ensure_ascii=True),
                               json.dumps(OLD,ensure_ascii=True),1)
        self.assertEqual(changed,src)
        self.assertIn('async function checkChannelMembership()',result)
        self.assertTrue(expected_version())
    def test_stale_cloudflare_latest_upload_rejected(self):
        template=direct_html(ROOT/"mini-app/direct-preview.html")
        with self.assertRaisesRegex(RuntimeError,"differs from active"):
            patch(original(),old_live_html=OLD+"CHANGED",new_html=template)
    def test_temporary_debug_route_is_never_carried_to_production(self):
        template=direct_html(ROOT/"mini-app/direct-preview.html")
        with self.assertRaises(RuntimeError):
            patch(original()+"\n// NGO_MINIAPP_STAGE_TELEGRAM_UPSTREAM_METHODS_V053",
                  old_live_html=OLD,new_html=template)
    def test_missing_signed_or_D1_baseline_refuses_rollout(self):
        template=direct_html(ROOT/"mini-app/direct-preview.html")
        for marker in MARKERS:
            with self.subTest(marker=marker),self.assertRaises(RuntimeError):
                patch(original().replace(marker,"DELETED",1),
                      old_live_html=OLD,new_html=template)

    def test_known_staged_dryrun_route_is_exactly_removed_before_patch(self):
        template=direct_html(ROOT/"mini-app/direct-preview.html")
        clean=patch(original(),old_live_html=OLD,new_html=template)
        # Cloudflare may return latest staged script, not live version.
        # That staging route is exactly the known authored probe.
        staged=original().replace(
            "export default {async fetch(request,env){",
            "export default {async fetch(request,env){"+VERIFIED_DRYRUN_ROUTE)
        restored=patch(staged,old_live_html=OLD,new_html=template)
        self.assertEqual(restored,clean)
        self.assertNotIn("NGO_MINIAPP_V052_STAGE_ONLY_AUTH_DRYRUN",restored)
    def test_each_action_hops_and_waves_and_semantic_form_gates(self):
        js=(ROOT/"mini-app/app.js").read_text("utf8")
        css=(ROOT/"mini-app/styles.css").read_text("utf8")
        self.assertIn("function needsDetail()",js)
        self.assertIn("robotFigure.classList.add('hop')",js)
        self.assertIn("robotArm.classList.add('wave')",js)
        self.assertIn("@keyframes arm-wave",css)
        self.assertIn("@keyframes robot-hop",css)
        self.assertIn("translateY(-11px)",css)

    def test_versioned_cloudflare_read_uses_only_approved_active_module(self):
        version="12345678-1234-1234-1234-1234567890ab"
        payload={"id":version,"main_module":"worker.mjs","modules":[{
            "name":"worker.mjs",
            "content_type":"application/javascript+module",
            "content_base64":b64encode(original().encode("utf-8")).decode("ascii"),
        }]}
        self.assertEqual(extract_active_module(payload,version),original())
        for modified in (
            {**payload,"id":"99999999-1234-1234-1234-1234567890ab"},
            {**payload,"main_module":"other.mjs"},
            {**payload,"modules":[]},
            {**payload,"modules":payload["modules"]*2},
            {**payload,"modules":[{**payload["modules"][0],"content_base64":"bad-!"}]},
            {**payload,"modules":[{**payload["modules"][0],"name":"other.mjs"}]},
        ):
            with self.subTest(modified=modified),self.assertRaises(RuntimeError):
                extract_active_module(modified,version)
