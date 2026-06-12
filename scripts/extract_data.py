"""extract_data.py - schema graph for tabular/SQL sources.

Schema-first by policy (DESIGN 4): tables, columns, types, foreign keys, row
counts. Row values do not enter the model here at all.
"""
from __future__ import annotations

import hashlib
import re

EXTRACTOR = "extract_data.py@schema"
CREATE_TABLE = re.compile(
    r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[\"`]?(?:\w+\.)?(\w+)[\"`]?\s*\((.*?)\)\s*;",
    re.I | re.S)
FOREIGN_KEY = re.compile(
    r"FOREIGN\s+KEY\s*\(\s*[\"`]?(\w+)[\"`]?\s*\)\s*REFERENCES\s+[\"`]?(?:\w+\.)?(\w+)[\"`]?",
    re.I)
INLINE_REF = re.compile(r"^[\"`]?(\w+)[\"`]?\s+\w+.*?REFERENCES\s+[\"`]?(?:\w+\.)?(\w+)[\"`]?", re.I)
COLUMN = re.compile(r"^[\"`]?(\w+)[\"`]?\s+([A-Za-z]\w*(?:\(\d+(?:,\s*\d+)?\))?)")


def _span(spans_out, counter, src, locator, text) -> str:
    sid = f"span:t{counter[0]:05d}"
    counter[0] += 1
    spans_out.append({"id": sid, "source": src, "locator": locator,
                      "text_sha": hashlib.sha256(text.encode()).hexdigest(),
                      "text": text[:2000]})
    return sid


def _table_id(src_root: str, name: str) -> str:
    return f"node:table/{src_root}/{name}"


def extract_csv(file_span: dict, src_root: str, spans_out, nodes_out, edges_out,
                counter: list[int]) -> None:
    text, src, rel = file_span["text"], file_span["source"], file_span["locator"]
    lines = text.splitlines()
    if not lines:
        return
    header = [h.strip().strip('"') for h in lines[0].split(",") if h.strip()]
    if not header:
        return
    sid = _span(spans_out, counter, src, f"{rel}#L1", lines[0])
    name = rel.replace("\\", "/").split("/")[-1].removesuffix(".csv")
    tid = _table_id(src_root, name)
    nodes_out.append({"id": tid, "type": "table", "name": name,
                      "summary": f"{len(header)} columns, {max(0, len(lines) - 1)} rows",
                      "attrs": {"rows": max(0, len(lines) - 1)}, "spans": [sid]})
    for col in header:
        cid = f"{tid}.{col}"
        nodes_out.append({"id": cid, "type": "column", "name": col,
                          "summary": "", "attrs": {}, "spans": [sid]})
        edges_out.append({"source": tid, "target": cid, "type": "contains",
                          "extractor": EXTRACTOR, "spans": [sid], "confidence": 1.0})


def extract_sql(file_span: dict, src_root: str, spans_out, nodes_out, edges_out,
                counter: list[int]) -> None:
    text, src, rel = file_span["text"], file_span["source"], file_span["locator"]
    for m in CREATE_TABLE.finditer(text):
        tname, body = m.group(1), m.group(2)
        line_no = text[:m.start()].count("\n") + 1
        sid = _span(spans_out, counter, src, f"{rel}#L{line_no}", m.group(0))
        tid = _table_id(src_root, tname)
        if not any(n["id"] == tid for n in nodes_out):
            nodes_out.append({"id": tid, "type": "table", "name": tname,
                              "summary": "", "attrs": {}, "spans": [sid]})
        fks: list[tuple[str, str]] = []
        for part in re.split(r",\s*\n|,(?=\s*[\"`]?\w+[\"`]?\s+\w)", body):
            part = part.strip()
            if not part or part.upper().startswith(("PRIMARY", "UNIQUE", "CONSTRAINT", "CHECK", "INDEX", "KEY")):
                for fk in FOREIGN_KEY.finditer(part):
                    fks.append((fk.group(1), fk.group(2)))
                continue
            if fk := INLINE_REF.match(part):
                fks.append((fk.group(1), fk.group(2)))
            if cm := COLUMN.match(part):
                col, ctype = cm.group(1), cm.group(2)
                cid = f"{tid}.{col}"
                if not any(n["id"] == cid for n in nodes_out):
                    nodes_out.append({"id": cid, "type": "column", "name": col,
                                      "summary": ctype, "attrs": {"sqltype": ctype},
                                      "spans": [sid]})
                    edges_out.append({"source": tid, "target": cid, "type": "contains",
                                      "extractor": EXTRACTOR, "spans": [sid],
                                      "confidence": 1.0})
        for col, ref in fks:
            rid = _table_id(src_root, ref)
            if not any(n["id"] == rid for n in nodes_out):
                nodes_out.append({"id": rid, "type": "table", "name": ref,
                                  "summary": "(referenced)", "attrs": {}, "spans": [sid]})
            edges_out.append({"source": tid, "target": rid, "type": "foreign_key",
                              "extractor": EXTRACTOR, "spans": [sid], "confidence": 1.0})
