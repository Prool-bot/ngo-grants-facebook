"""Stage NGO Grants UI 5.8 as an inactive Cloudflare Worker version.

Never touches production deployment, Telegram webhook, D1 rows or secrets.
Existing secret and database bindings are inherited strictly by name.
"""
import json
import os
import sys
import uuid
import urllib.error
import urllib.request
from pathlib import Path

SCRIPT = 'ngo-grants-instant-bot'
EXPECTED = {'BOT_TOKEN': 'secret_text', 'SYNC_SECRET': 'secret_text',
            'WEBHOOK_SECRET': 'secret_text', 'DB': 'd1'}


def api(method, path, body=None, content_type=None):
    account = (os.getenv('CF_WORKER_ACCOUNT_ID') or os.getenv('CF_ACCOUNT_ID') or '').strip()
    token = (os.getenv('CF_WORKER_API_TOKEN') or '').strip()
    if not account or not token:
        raise RuntimeError('Missing Cloudflare account or token')
    base = 'https://api.cloudflare.com/client/v4/accounts/'+account
    headers = {'Authorization':'Bearer '+token,'Accept':'application/json'}
    if content_type: headers['Content-Type'] = content_type
    req = urllib.request.Request(base+path, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req,timeout=40) as resp:
            return json.loads(resp.read(150000))
    except urllib.error.HTTPError as e:
        # Never emit headers or payload in case Cloudflare includes secrets.
        raise RuntimeError(f'Cloudflare API rejected {method} {path.split("?")[0].rsplit("/",1)[-1]}: HTTP {e.code}') from None


def multipart(parts):
    boundary = 'NGOGrantsUIv58'+uuid.uuid4().hex
    output=[]
    for name,filename,mime,value in parts:
        output.append(('--'+boundary+'\r\n').encode())
        head=f'Content-Disposition: form-data; name="{name}"'
        if filename: head+=f'; filename="{filename}"'
        output.append((head+'\r\nContent-Type: '+mime+'\r\n\r\n').encode())
        output.append(value if isinstance(value,bytes) else value.encode())
        output.append(b'\r\n')
    output.append(('--'+boundary+'--\r\n').encode())
    return b''.join(output),'multipart/form-data; boundary='+boundary


def main():
    if len(sys.argv)!=2: raise RuntimeError('Expected patched Worker script file')
    source=Path(sys.argv[1]).read_text('utf-8')
    assert "menu_version:'5.8'" in source and 'advanceAfterDetail' in source
    conf=api('GET','/workers/scripts/'+SCRIPT+'/settings')
    if conf.get('success') is not True: raise RuntimeError('Cannot inspect existing bindings')
    settings=conf.get('result') or {}
    existing={x['name']:x['type'] for x in settings.get('bindings') or []}
    if existing != EXPECTED:
        raise RuntimeError('Bindings changed since baseline: stop before upload')
    orig_date=settings.get('compatibility_date')
    if not orig_date: raise RuntimeError('Existing compatibility date not available')
    # Retain all production secrets without reading them, and the exact D1 DB.
    bindings=[{'name':n,'type':'inherit'} for n in sorted(EXPECTED)]
    bindings.append({'name':'AI','type':'ai'})
    metadata={'main_module':'worker.mjs','bindings':bindings,
              'compatibility_date':orig_date,
              'annotations':{'workers/message':'v5.8 guided AI menu (staging only)',
                             'workers/tag':'NGO_GRANTS_UI_V58_CANDIDATE'}}
    original=api('GET','/workers/scripts/'+SCRIPT+'/deployments')
    deployed=[]
    for dep in (original.get('result') or {}).get('deployments',[]):
        deployed.append({'id':dep.get('id'),'versions':dep.get('versions')})
    print('CURRENT_DEPLOYMENT_PRESENT',bool(deployed))
    print('PRE_UPLOAD_BINDINGS_OK',sorted(existing))
    payload,ct=multipart([
       ('metadata',None,'application/json',json.dumps(metadata,separators=(',',':'))),
       ('worker.mjs','worker.mjs','application/javascript+module',source),
    ])
    result=api('POST','/workers/scripts/'+SCRIPT+'/versions?bindings_inherit=strict',payload,ct)
    if result.get('success') is not True:
        raise RuntimeError('Version upload returned failure; no production deploy')
    info=result.get('result') or {}
    version=info.get('id') or info.get('version_id')
    if not version: raise RuntimeError('Uploaded but Cloudflare did not return version ID')
    print('DORMANT_VERSION_CREATED',version)
    print('PRODUCTION_DEPLOYMENT_UNCHANGED')
    verification=api('GET','/workers/scripts/'+SCRIPT+'/versions/'+version)
    v=verification.get('result') or {}
    if verification.get('success') is not True or v.get('id')!=version:
        raise RuntimeError('Cannot verify staged Worker version')
    # Save only public release IDs; do not upload code/credentials as artifacts.
    manifest={'script':SCRIPT,'version_id':version,'deployments_before':deployed,
              'compatible_date':orig_date,'staged_only':True}
    out=Path(os.getenv('RUNNER_TEMP','/tmp'))/'ngo-worker-v58-stage.json'
    out.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    print('STAGED_MANIFEST_CREATED',out.name)


if __name__=='__main__':
    main()