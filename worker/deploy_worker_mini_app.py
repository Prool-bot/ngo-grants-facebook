"""Release the dormant NGO Grants Mini App Worker with guarded 0.01% smoke and rollback.

No bot messages, no webhook rotation, no D1 schema changes. An override
requests the new version without routing normal traffic to it.
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request

SCRIPT = 'ngo-grants-instant-bot'
VERSION = '4e3f1f6c-0e30-47f1-bbd3-1003f1a73391'


def api(path, method='GET', payload=None):
    aid=(os.getenv('CF_WORKER_ACCOUNT_ID') or os.getenv('CF_ACCOUNT_ID') or '').strip()
    token=(os.getenv('CF_WORKER_API_TOKEN') or '').strip()
    if not aid or not token: raise RuntimeError('Cloudflare credentials missing')
    headers={'Authorization':'Bearer '+token,'Accept':'application/json'}
    data=None
    if payload is not None:
        data=json.dumps(payload).encode('utf-8')
        headers['Content-Type']='application/json'
    req=urllib.request.Request('https://api.cloudflare.com/client/v4/accounts/'+aid+path,
                               method=method,headers=headers,data=data)
    try:
        with urllib.request.urlopen(req,timeout=35) as resp:
            result=json.loads(resp.read(150000))
    except urllib.error.HTTPError as e:
        raise RuntimeError(f'Cloudflare deployment API HTTP {e.code}') from None
    if result.get('success') is not True:
        raise RuntimeError('Cloudflare deployment API error (no credentials logged)')
    return result.get('result') or {}


def deploy(versions, explanation):
    result=api('/workers/scripts/'+SCRIPT+'/deployments','POST',{
      'strategy':'percentage',
      'versions':[{'version_id':vid,'percentage':p} for vid,p in versions],
      'annotations':{'workers/message':explanation},
    })
    print('DEPLOYMENT_CREATED',result.get('id') or '[no-id]')
    return result


def health(gateway, version_override=None):
    headers={'Accept':'application/json','User-Agent':'Mozilla/5.0 NGOGrantsRelease/1.0'}
    if version_override:
        headers['Cloudflare-Workers-Version-Overrides']=f'{SCRIPT}="{version_override}"'
    req=urllib.request.Request(gateway.rstrip('/')+'/health',headers=headers)
    with urllib.request.urlopen(req,timeout=20) as resp:
        data=json.loads(resp.read(5000))
        if resp.status!=200 or data.get('ok') is not True:
            raise RuntimeError('Worker health check invalid')
    return data


def forbidden(gateway,version_override=None):
    headers={'Accept':'application/json','User-Agent':'Mozilla/5.0 NGOGrantsRelease/1.0'}
    if version_override:
        headers['Cloudflare-Workers-Version-Overrides']=f'{SCRIPT}="{version_override}"'
    req=urllib.request.Request(gateway.rstrip('/')+'/internal/pending',headers=headers)
    try:
        with urllib.request.urlopen(req,timeout=20):pass
    except urllib.error.HTTPError as e:
        return e.code == 403
    return False


def mini_app_smoke(gateway, version_override=None):
    """GET only, no Telegram, no D1 writes, no catalog requests."""
    headers={'Accept':'text/html','User-Agent':'NGOGrantsMiniAppRelease/1.0'}
    if version_override:
        headers['Cloudflare-Workers-Version-Overrides']=f'{SCRIPT}="{version_override}"'
    req=urllib.request.Request(gateway.rstrip('/')+'/mini-app',headers=headers,method='GET')
    with urllib.request.urlopen(req,timeout=20) as resp:
        html=resp.read(70000).decode('utf-8')
        if resp.status!=200 or 'text/html' not in resp.headers.get('Content-Type',''):
            raise RuntimeError('Mini App static route did not return HTML 200')
        if not all(x in html for x in (
                'data-native-send="true"', 'telegram-web-app.js',
                'ngo-grants-miniapp-v1', 'NGO Grants AI')):
            raise RuntimeError('Mini App HTML missing native Telegram integration')
        if resp.headers.get('X-Ngo-Mini-App-Version')!='0.1':
            raise RuntimeError('Mini App version response header missing')
    return True


def main():
    if os.getenv('GITHUB_ACTIONS')!='true' or os.getenv('GITHUB_REF')!='refs/heads/main':
        raise RuntimeError('Mini App release allowed only on GitHub main')
    if os.getenv('NGO_MINI_APP_RELEASE_APPROVED')!='YES_NATIVE_TELEGRAM_CANARY':
        raise RuntimeError('Explicit Mini App rollout gate missing')
    gate=(os.getenv('NGO_BOT_GATEWAY_URL') or '').strip()
    if not gate.startswith('https://') or 'workers.dev' not in gate:
        raise RuntimeError('Protected Worker URL missing')
    d=api('/workers/scripts/'+SCRIPT+'/deployments')
    latest=(d.get('deployments') or [None])[0]
    if not latest: raise RuntimeError('No active deployment')
    active=latest.get('versions') or []
    if len(active)!=1 or active[0].get('percentage')!=100:
        raise RuntimeError('Unexpected production traffic split; do not deploy')
    old=active[0].get('version_id')
    if not old or old == VERSION: raise RuntimeError('Worker already on staged version')
    baseline=health(gate)
    print('PRE_RELEASE_MENU_VERSION',baseline.get('menu_version'))
    if baseline.get('menu_version')!='5.8':
        raise RuntimeError('Production Worker changed after staging. Do not deploy.')
    staged=api('/workers/scripts/'+SCRIPT+'/versions/'+VERSION)
    bindings=(staged.get('resources') or {}).get('bindings') or []
    expected={'BOT_TOKEN':'secret_text','SYNC_SECRET':'secret_text',
              'WEBHOOK_SECRET':'secret_text','DB':'d1','AI':'ai'}
    if {x.get('name'):x.get('type') for x in bindings} != expected:
        raise RuntimeError('Staged version binding mismatch; do not deploy')
    print('SAFE_BINDINGS_VERIFIED',sorted(expected))
    had_traffic_change=False
    try:
        had_traffic_change=True
        deploy([(old,99.99),(VERSION,0.01)],'Mini App 0.01% read-only canary, legacy Worker 99.99%')
        time.sleep(3)
        v=health(gate,VERSION)
        print('CANARY_OVERRIDE_MENU_VERSION',v.get('menu_version'))
        if v.get('menu_version')!='5.8':
            raise RuntimeError('Version override smoke did not reach v5.8-compatible candidate')
        mini_app_smoke(gate,VERSION)
        print('MINI_APP_CANARY_HTML_OK')
        if not forbidden(gate,VERSION):
            raise RuntimeError('Unauthenticated pending endpoint not forbidden')
        print('CANARY_AUTHORIZATION_OK')
        deploy([(VERSION,100)],'NGO Grants Mini App keyboard integration: full release after canary')
        time.sleep(3)
        prod=health(gate)
        print('PRODUCTION_MENU_VERSION',prod.get('menu_version'))
        if prod.get('menu_version')!='5.8' or not forbidden(gate):
            raise RuntimeError('Post-deploy legacy health/auth smoke failed')
        mini_app_smoke(gate)
        print('PRODUCTION_MINI_APP_HTML_OK')
        print('PRODUCTION_MINI_APP_RELEASE_SUCCESS')
    except BaseException as e:
        if had_traffic_change:
            try:
                deploy([(old,100)],'Automatic rollback to prior NGO Grants Worker')
                print('ROLLBACK_TO_PREVIOUS_VERSION_OK')
            except BaseException:
                print('CRITICAL: automatic rollback failed; inspect Cloudflare deployments immediately')
        raise


if __name__=='__main__':
    main()