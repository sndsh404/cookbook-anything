"""model_schema.py - the contract every stage reads and writes (DESIGN 4).

validate(model) returns a list of error strings; empty list = valid.
Stdlib only; this is deliberately a hand-rolled checker, not jsonschema.
"""
from __future__ import annotations

NODE_TYPES = {"file", "function", "class", "module", "concept", "table",
              "column", "section", "person", "decision"}
EDGE_TYPES = {"imports", "calls", "defines", "contains", "documents",
              "depends_on", "foreign_key", "supersedes", "contradicts"}
SOURCE_TYPES = {"git_repo", "pdf", "markdown", "csv", "sql_dump", "folder", "file"}

REQUIRED = {
    "sources": ["id", "type", "path", "parser", "sha256"],
    "spans": ["id", "source", "locator", "text_sha"],
    "nodes": ["id", "type", "name", "spans"],
    "edges": ["source", "target", "type", "extractor", "confidence"],
    "claims": ["id", "text", "spans", "confidence", "status"],
    "glossary": ["term", "definition", "first_span"],
    "assets": ["id", "kind", "origin_url", "archive_path", "license", "attribution"],
}


def validate(model: dict) -> list[str]:
    errors: list[str] = []
    for kind in ("sources", "spans", "nodes", "edges", "claims", "tours", "glossary", "assets"):
        if kind not in model:
            errors.append(f"missing top-level key: {kind}")
    if errors:
        return errors

    for kind, fields in REQUIRED.items():
        for rec in model.get(kind, []):
            for f in fields:
                if f not in rec or rec[f] in (None, ""):
                    errors.append(f"{kind} record missing {f}: {str(rec)[:80]}")

    span_ids = {s["id"] for s in model["spans"]}
    node_ids = {n["id"] for n in model["nodes"]}
    src_ids = {s["id"] for s in model["sources"]}

    for s in model["spans"]:
        if s["source"] not in src_ids:
            errors.append(f"span {s['id']} references missing source {s['source']}")
    for n in model["nodes"]:
        if n["type"] not in NODE_TYPES:
            errors.append(f"node {n['id']} has unknown type {n['type']}")
        for sp in n.get("spans", []):
            if sp not in span_ids:
                errors.append(f"node {n['id']} references missing span {sp}")
    for e in model["edges"]:
        if e["type"] not in EDGE_TYPES:
            errors.append(f"edge has unknown type {e['type']}")
        if not e.get("extractor"):
            errors.append(f"edge {e['source']}->{e['target']} has no extractor (hard rule 1)")
        if e["source"] not in node_ids or e["target"] not in node_ids:
            errors.append(f"dangling edge {e['source']}->{e['target']}")
        if str(e["extractor"]).startswith("agent") and e.get("confidence", 1.0) >= 1.0:
            errors.append(f"agent-proposed edge at confidence 1.0: {e['source']}->{e['target']}")
    for c in model["claims"]:
        if not c.get("spans"):
            errors.append(f"claim {c['id']} has no spans (hard rule 2)")
        for sp in c.get("spans", []):
            if sp not in span_ids:
                errors.append(f"claim {c['id']} references missing span {sp}")
        if c.get("status") not in ("active", "superseded"):
            errors.append(f"claim {c['id']} has bad status {c.get('status')}")
    for g in model["glossary"]:
        if g.get("first_span") and g["first_span"] not in span_ids:
            errors.append(f"glossary term {g['term']} references missing span")
    return errors


def empty_model() -> dict:
    return {"sources": [], "spans": [], "nodes": [], "edges": [], "claims": [],
            "tours": [], "glossary": [], "assets": []}
