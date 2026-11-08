"""Read-only sanitized D1 schema report from approved private live Worker JS.

No SQL literal, complete code, secrets or D1 data is logged.
"""
from __future__ import annotations
import re
import sys
from pathlib import Path

TABLES=("requests","legacy_limits","settings","catalogs")
def analyze(raw:str)->dict:
    if not raw or len(raw)>8_000_000:raise ValueError("Worker source size changed")
    out={}
    for table in TABLES:
        pattern=r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[`\"']?"+table+r"[`\"']?\s*\((.{0,2500}?)\)"
        m=re.search(pattern,raw,re.I|re.S)
        cols=[]
        if m:
            for entry in m.group(1).split(","):
                first=re.match(r"\s*[`\"']?([A-Za-z_][A-Za-z_0-9]*)",entry)
                if first and first.group(1).upper() not in ("PRIMARY","UNIQUE","FOREIGN","CONSTRAINT","CHECK"):
                    cols.append(first.group(1))
        inserts=len(re.findall(r"\bINSERT\s+(?:OR\s+\w+\s+)?INTO\s+"+table+r"\b",raw,re.I))
        out[table]={"schema_in_worker":bool(m),"column_names":cols[:22],"insert_statement_count":inserts}
    return out

if __name__=="__main__":
    text=Path(sys.argv[1]).read_text("utf-8")
    result=analyze(text)
    for table,v in result.items():
        print("D1_TABLE_"+table.upper()+"_SCHEMA_IN_WORKER="+str(v["schema_in_worker"]))
        print("D1_TABLE_"+table.upper()+"_COLUMNS="+",".join(v["column_names"]))
        print("D1_TABLE_"+table.upper()+"_INSERTS="+str(v["insert_statement_count"]))
    print("D1_READ_ONLY_SCHEMA_AUDIT_COMPLETE")
