"""Read the currently deployed Cloudflare Worker safely as a JS *module*.

Cloudflare /workers/scripts response may be multipart/form-data containing
worker.mjs and metadata; passing raw multipart to Node is unsafe and fails.
Only the patched module is saved in runner temp (0600). Neither deployed source
nor secrets are printed or committed.
"""
from __future__ import annotations
from email.parser import BytesParser
from email import policy
import os
from pathlib import Path
import sys
import urllib.request
import urllib.error

from patch_live_worker_mini_app import patch_worker

MAX_BYTES=8_000_000
SCRIPT="ngo-grants-instant-bot"

def extract_js(content_type: str, body: bytes) -> str:
    if not body or len(body)>MAX_BYTES:raise RuntimeError("Worker source invalid size")
    if "multipart/" not in content_type.lower():
        return body.decode("utf-8","strict")
    msg=BytesParser(policy=policy.default).parsebytes(
        b"MIME-Version: 1.0\r\nContent-Type: "+content_type.encode("ascii")+
        b"\r\n\r\n"+body
    )
    parts=[]
    for item in msg.walk():
        filename=(item.get_filename() or
                  item.get_param("name",header="content-disposition") or "")
        if filename.endswith((".js",".mjs")):
            raw=item.get_payload(decode=True)
            if raw:parts.append(raw.decode("utf-8","strict"))
    if len(parts)!=1:
        raise RuntimeError("Exactly one JS Worker module required; refusing source")
    return parts[0]

def main() -> int:
    if len(sys.argv)!=2:raise RuntimeError("Expected runner-temp output path")
    account=(os.getenv("CF_WORKER_ACCOUNT_ID") or os.getenv("CF_ACCOUNT_ID") or "").strip()
    token=(os.getenv("CF_WORKER_API_TOKEN") or "").strip()
    if not account or not token:
        raise RuntimeError("Scoped Cloudflare read token missing")
    url=(f"https://api.cloudflare.com/client/v4/accounts/{account}"
         f"/workers/scripts/{SCRIPT}")
    req=urllib.request.Request(url,method="GET",headers={
        "Authorization":"Bearer "+token,
        "Accept":"application/javascript,multipart/form-data"
    })
    try:
        with urllib.request.urlopen(req,timeout=35) as response:
            ct=response.headers.get("Content-Type","")
            content=response.read(MAX_BYTES+1)
    except urllib.error.HTTPError as error:
        raise RuntimeError(f"Worker source GET HTTP {error.code}") from None
    except (urllib.error.URLError,TimeoutError,OSError) as error:
        raise RuntimeError(f"Worker source GET failed: {type(error).__name__}") from None
    source=extract_js(ct,content)
    preview=Path("mini-app/preview.html").read_text("utf-8")
    bridge=Path("worker/mini_app_keyboard_bridge.mjs").read_text("utf-8")
    result=patch_worker(source,preview,bridge)
    target=Path(sys.argv[1]).resolve()
    if not str(target).startswith(str(Path(os.getenv("RUNNER_TEMP","/tmp")).resolve())+"/"):
        raise RuntimeError("Refuse to write Worker candidate outside runner temp")
    fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,"w",encoding="utf-8") as out:out.write(result)
    print("PATCHED_SINGLE_MODULE_READY; no Worker code or secrets printed")
    return 0

if __name__=="__main__":
    try:raise SystemExit(main())
    except RuntimeError as e:raise SystemExit(str(e)) from None
