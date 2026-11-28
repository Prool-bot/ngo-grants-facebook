"""Move the existing opt-in support link to header position 1 only."""
from __future__ import annotations
import json
import os
import re
import sys
from pathlib import Path
from patch_quiet_support import BLOCK, SCRIPT, DIRECT, NATIVE, MARKER, URL, LABEL, native_public_html

HEADER_LINK = (
    '<a id="ngoQuietSupportLink" href="' + URL + '" target="_blank" rel="noopener noreferrer"'
    ' style="display:inline-flex;align-items:center;justify-content:center;box-sizing:border-box;'
    'max-width:100%;white-space:nowrap;color:#245b9c;background:#f3f8ff;'
    'font-size:12px;font-weight:600;text-decoration:none;line-height:1.3;'
    'padding:7px 10px;border:1px solid #d5e4f7;border-radius:20px">'
    + LABEL + '</a>'
)
MODE = r'(<span\b[^>]*\bid="mode"[^>]*)(>[^<]*</span>)'

def move_link(html: str) -> str:
    if html.count(BLOCK)!=1 or html.count(SCRIPT)!=1 or html.count(URL)!=1 or html.count('</header>')!=1:
        raise RuntimeError("Unexpected active support HTML")
    start=html.index('<header class="header">')
    end=html.index('</header>',start)
    head=html[start:end]
    if len(re.findall(MODE,head))!=1 or 'style=' in re.search(MODE,head).group(1):
        raise RuntimeError("Mode badge fingerprint changed")
    new_head=re.sub(MODE,lambda m:m.group(1)+' style="display:none"'+m.group(2),head,count=1)
    new_head+=HEADER_LINK+'\n'
    updated=html[:start]+new_head+html[end:]
    updated=updated.replace(BLOCK+'\n','',1) if BLOCK+'\n' in updated else updated.replace(BLOCK,'',1)
    if updated.count('id="ngoQuietSupportLink"')!=1 or updated.count(URL)!=1:
        raise RuntimeError("Support link not unique")
    return updated

def splice(source: str,prefix: str,live: str) -> str:
    if source.count(prefix)!=1:
        raise RuntimeError("Embedded HTML literal not unique")
    at=source.index(prefix)+len(prefix)
    old,used=json.JSONDecoder().raw_decode(source[at:])
    if old!=live or source[at+used:at+used+1]!=';':
        raise RuntimeError("Active source differs from served HTML")
    return source[:at]+json.dumps(move_link(old),ensure_ascii=True)+source[at+used:]

def patch(source: str,direct: str,native: str) -> str:
    if source.count(MARKER)!=1 or len(source)>8_000_000:
        raise RuntimeError("Active v0.5.7 Worker fingerprint changed")
    return splice(splice(source,DIRECT,direct),NATIVE,native)

def check_header(html: str):
    head=html.split('<header class="header">',1)[1].split('</header>',1)[0]
    if (HEADER_LINK not in head or 'id="mode" style="display:none"' not in head
        or html.count('id="ngoQuietSupportLink"')!=1 or BLOCK in html
        or 'id="progressFill"' not in html or html.count(SCRIPT)!=1):
        raise RuntimeError("Top support link or unchanged progress bar not verified")

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
    print("SUPPORT_HEADER_ONLY_PATCH_VERIFIED=True")

if __name__=="__main__":
    try:main()
    except RuntimeError as e:raise SystemExit(str(e)) from None
