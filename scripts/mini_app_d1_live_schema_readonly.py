"""Strict read-only D1 schema introspection through official Cloudflare API.

The Cloudflare D1 Query endpoint is POST, but every SQL string is hard-coded
PRAGMA table_info/index_list: no writes, no rows and no user records. Never
print account/database IDs, binding metadata values, secrets or SQL bodies.
"""
from __future__ import annotations
import json
import os
import re
import urllib.error
import urllib.request

TABLES=("requests","legacy_limits","settings","catalogs")
SCRIPT="ngo-grants-instant-bot"


def cloudflare(method,path,token,account,payload=None):
    if method not in ("GET","POST"):raise ValueError("Unsupported API method")
    if method=="POST":
        if not isinstance(payload,dict) or not re.fullmatch(
            r"PRAGMA (?:table_info|index_list)\('(requests|legacy_limits|settings|catalogs)'\)",
            payload.get("sql","")
        ):
            raise ValueError("Only hard-coded read-only schema introspection allowed")
        if set(payload)!={"sql"}:raise ValueError("No query parameters allowed")
    url="https://api.cloudflare.com/client/v4/accounts/"+account+path
    req=urllib.request.Request(url,method=method,headers={
        "Authorization":"Bearer "+token,"Accept":"application/json",
        "Content-Type":"application/json",
        "User-Agent":"NGOGrantsMiniAppSchemaReadOnly/1.0"
    },data=json.dumps(payload).encode() if payload else None)
    try:
        with urllib.request.urlopen(req,timeout=30) as resp:
            raw=resp.read(150000)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Cloudflare D1 schema HTTP {exc.code}") from None
    except (urllib.error.URLError,OSError,TimeoutError) as exc:
        raise RuntimeError(f"Cloudflare D1 schema network {type(exc).__name__}") from None
    result=json.loads(raw)
    if result.get("success") is not True:
        raise RuntimeError("Cloudflare D1 schema query refused")
    return result.get("result")


def validated_db_id(settings)->str|None:
    binds=(settings or {}).get("bindings") or []
    found=[x for x in binds if x.get("name")=="DB" and x.get("type")=="d1"]
    if len(found)!=1:
        raise RuntimeError("Expected exactly one existing D1 binding")
    binding=found[0]
    identity=binding.get("id") or binding.get("database_id")
    if not isinstance(identity,str) or not re.fullmatch(
        r"[0-9a-fA-F]{8}-(?:[0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}",identity
    ):
        print("D1_ID_FROM_WORKER_BINDING=UNAVAILABLE")
        print("D1_BINDING_KEY_NAMES="+",".join(sorted(binding.keys())))
        return None
    return identity


def result_rows(data):
    # Cloudflare API may wrap results as an array of single-query objects.
    if isinstance(data,list):
        if len(data)!=1:raise RuntimeError("Multiple unexpected D1 results")
        data=data[0]
    if not isinstance(data,dict) or data.get("success") is not True:
        raise RuntimeError("Invalid D1 schema query result")
    rows=data.get("results")
    if not isinstance(rows,list):raise RuntimeError("Missing D1 schema results")
    return rows


def inspect():
    account=(os.getenv("CF_WORKER_ACCOUNT_ID") or os.getenv("CF_ACCOUNT_ID") or "").strip()
    token=(os.getenv("CF_WORKER_API_TOKEN") or "").strip()
    if not account or not token:raise RuntimeError("Cloudflare metadata credentials missing")
    st=cloudflare("GET",f"/workers/scripts/{SCRIPT}/settings",token,account)
    dbid=validated_db_id(st)
    if dbid is None:return False
    for table in TABLES:
        info=result_rows(cloudflare("POST",
            f"/d1/database/{dbid}/query",token,account,
            {"sql":f"PRAGMA table_info('{table}')"}))
        indexes=result_rows(cloudflare("POST",
            f"/d1/database/{dbid}/query",token,account,
            {"sql":f"PRAGMA index_list('{table}')"}))
        names=[]
        for col in info:
            name=col.get("name")
            if not isinstance(name,str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,60}",name):
                raise RuntimeError("Unexpected D1 column identifier")
            names.append({"name":name,"type":str(col.get("type") or "").upper(),
                 "pk":int(col.get("pk") or 0),
                 "required":bool(col.get("notnull"))})
        print("D1_"+table.upper()+"_COLUMNS="+json.dumps(names,ensure_ascii=True))
        print("D1_"+table.upper()+"_INDEX_COUNT="+str(len(indexes)))
    print("D1_SCHEMA_READ_ONLY_SUCCESS")
    return True


if __name__=="__main__":
    try:inspect()
    except RuntimeError as exc:
        # Missing D1 Read permission is a documented integration blocker;
        # no speculative schema or database modification is attempted.
        print("D1_SCHEMA_READ_ONLY_UNAVAILABLE="+str(exc))
