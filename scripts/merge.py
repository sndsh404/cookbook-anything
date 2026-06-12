"""merge.py - normalize, dedupe, drop dangling refs; report Fixed vs Could not fix.

Also the enforcement point for hard rule 1's pressure valve: any edge whose
extractor starts with "agent" is clamped to confidence < 1.0, no matter what
the proposer wrote. Scripts are cheaper and more precise for mechanical
fixes; judgment is reserved for the could-not-fix list.
"""
from __future__ import annotations

from collections import Counter

import model_schema

AGENT_CONFIDENCE_CAP = 0.75


def merge(model: dict) -> tuple[dict, list[str], list[str]]:
    fixed: Counter = Counter()
    could_not_fix: list[str] = []

    # dedupe nodes by id, merging span lists
    by_id: dict[str, dict] = {}
    for n in model["nodes"]:
        if n["id"] in by_id:
            prev = by_id[n["id"]]
            prev["spans"] = sorted(set(prev["spans"]) | set(n.get("spans", [])))
            if not prev.get("summary") and n.get("summary"):
                prev["summary"] = n["summary"]
            fixed["deduped node"] += 1
        else:
            by_id[n["id"]] = n
    model["nodes"] = list(by_id.values())
    node_ids = set(by_id)

    # dedupe spans by id
    seen_spans: dict[str, dict] = {}
    for s in model["spans"]:
        if s["id"] in seen_spans:
            fixed["deduped span"] += 1
        else:
            seen_spans[s["id"]] = s
    model["spans"] = list(seen_spans.values())
    span_ids = set(seen_spans)

    # clamp agent-proposed edges (hard rule 1 pressure valve)
    for e in model["edges"]:
        if str(e.get("extractor", "")).startswith("agent") and e.get("confidence", 1.0) >= 1.0:
            e["confidence"] = AGENT_CONFIDENCE_CAP
            fixed["clamped agent edge to confidence<1.0"] += 1

    # dedupe edges, drop danglers
    kept, seen_edges = [], set()
    for e in model["edges"]:
        key = (e["source"], e["target"], e["type"])
        if key in seen_edges:
            fixed["deduped edge"] += 1
            continue
        if e["source"] not in node_ids or e["target"] not in node_ids:
            fixed["dropped dangling edge"] += 1
            continue
        bad_spans = [sp for sp in e.get("spans", []) if sp not in span_ids]
        if bad_spans:
            e["spans"] = [sp for sp in e["spans"] if sp in span_ids]
            fixed["pruned edge span refs"] += 1
        seen_edges.add(key)
        kept.append(e)
    model["edges"] = kept

    # node span refs
    for n in model["nodes"]:
        bad = [sp for sp in n.get("spans", []) if sp not in span_ids]
        if bad:
            n["spans"] = [sp for sp in n["spans"] if sp in span_ids]
            fixed["pruned node span refs"] += 1
            if not n["spans"]:
                could_not_fix.append(f"node {n['id']} lost all spans")

    # claims: a claim without resolvable spans cannot be auto-fixed (hard rule 2)
    ok_claims = []
    for c in model["claims"]:
        c["spans"] = [sp for sp in c.get("spans", []) if sp in span_ids]
        if c["spans"]:
            ok_claims.append(c)
        else:
            could_not_fix.append(f"claim {c['id']} has no resolvable spans; dropped from model")
            fixed["dropped spanless claim"] += 1
    model["claims"] = ok_claims

    # glossary: dedupe terms, prune bad span refs
    seen_terms: set[str] = set()
    ok_gloss = []
    for g in model["glossary"]:
        t = g["term"].lower()
        if t in seen_terms:
            fixed["deduped glossary term"] += 1
            continue
        if g.get("first_span") not in span_ids:
            fixed["dropped glossary term with bad span"] += 1
            continue
        seen_terms.add(t)
        ok_gloss.append(g)
    model["glossary"] = ok_gloss

    errors = model_schema.validate(model)
    for err in errors:
        could_not_fix.append(f"schema: {err}")

    fixed_report = [f"{k} x{v}" for k, v in sorted(fixed.items())]
    return model, fixed_report, could_not_fix
