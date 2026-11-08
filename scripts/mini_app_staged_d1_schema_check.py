"""Query a DORMANT Worker version to read only authorized D1 table metadata.

No D1 rows, no public deployment, no user data. The same version-override
header already used by the verified v0.4 release process is reused.
"""
from __future__ import annotations
import json,os,re,urllib.request,urllib.error
from pathlib import Path

SCRIPT="ngo-grants-instant-bot"
TABLES=("requests","legacy_limits","settings","catalogs")

def safe_schema(info):
    if not isinstance(info,dict) or info.get("ok") is not True:
        raise RuntimeError("Staged schema audit response malformed")
    schema=info.get("schema")
    if not isinstance(schema,dict) or sorted(schema)!=sorted(TABLES):
        raise RuntimeError("Staged D1 tables differ from expected")
    safe={}
    for table in TABLES:
        item=schema[table]
        columns=item.get("columns")
        if not isinstance(columns,list) or not columns or len(columns)>50:
            raise RuntimeError("Missing D1 table columns")
        names=[]
        for row in columns:
            name=row.get("name")
            if (not isinstance(name,str) or
                re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]{0,63}",name) is None):
                raise RuntimeError("Unexpected D1 column name")
            names.append({
               "name":name,
               "type":str(row.get("type",""))[:25],
               "primary_key":int(row.get("pk") or 0),
               "not_null":bool(row.get("notnull"))
            })
        safe[table]={
          "columns":names,
          "unique_indexes":int(item.get("unique_indexes") or 0),
          "index_count":int(item.get("index_count") or 0)
        }
    return safe

def main():
    receipt=Path(os.getenv("RUNNER_TEMP","/tmp"))/"ngo-worker-miniapp-stage.json"
    version=json.loads(receipt.read_text("utf-8"))
    identifier=version.get("version_id")
    if (version.get("staged_only") is not True or version.get("script")!=SCRIPT or
        not isinstance(identifier,str) or
        re.fullmatch(r"[0-9a-f-]{36}",identifier) is None):
        raise RuntimeError("Unknown dormant Worker version receipt")
    gateway=os.getenv("NGO_BOT_GATEWAY_URL","").rstrip("/")
    key=os.getenv("NGO_BOT_SYNC_SECRET","")
    if not (gateway.startswith("https://") and ".workers.dev" in gateway and key):
        raise RuntimeError("Missing existing Worker gateway credentials")
    req=urllib.request.Request(gateway+"/_internal/miniapp/d1-schema-audit",method="GET",
      headers={
        "Authorization":"Bearer "+key,
        "Cloudflare-Workers-Version-Overrides":f'{SCRIPT}="{identifier}"',
        "Cache-Control":"no-store",
        "Accept":"application/json",
        "User-Agent":"NGOGrantsMiniAppStageSchema/1.0"
      })
    try:
        with urllib.request.urlopen(req,timeout=35) as resp:
            status=resp.status
            header=resp.headers.get("X-Miniapp-Schema-Stage")
            raw=resp.read(70000)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Staged read-only schema audit HTTP {exc.code}") from None
    except (OSError,urllib.error.URLError,TimeoutError) as exc:
        raise RuntimeError(f"Staged read-only schema network {type(exc).__name__}") from None
    if status!=200 or header!="1":
        raise RuntimeError("Version override not applied to staged-only schema Worker")
    safe=safe_schema(json.loads(raw))
    print("STAGED_ONLY_D1_SCHEMA_METADATA_VERIFIED")
    for name,data in safe.items():
        print("D1_"+name.upper()+"_COLUMNS="+json.dumps(data["columns"]))
        print("D1_"+name.upper()+"_UNIQUE_INDEX_COUNT="+str(data["unique_indexes"]))
        print("D1_"+name.upper()+"_INDEX_COUNT="+str(data["index_count"]))
    print("NO_D1_ROWS_READ_OR_CHANGED")
    print("ACTIVE_WORKER_UNCHANGED")
    return 0

if __name__=="__main__":
    try:raise SystemExit(main())
    except RuntimeError as exc:raise SystemExit(str(exc)) from None
