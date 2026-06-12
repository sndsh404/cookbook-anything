"""compile_model.py - Stage 2 orchestrator: extract -> annotate -> merge.

Reads the intake span store (redacted text), dispatches per-file extractors,
links cross-file imports, derives a deterministic glossary from class
docstrings, merges, validates, writes model.json.

Usage: python scripts/compile_model.py <cookbook_dir>
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import extract_code
import extract_data
import extract_doc
import merge as merge_mod
import model_schema


def compile_model(cookbook_dir: Path) -> dict:
    manifest = json.loads((cookbook_dir / "manifest.json").read_text(encoding="utf-8"))
    spans_in = [json.loads(line) for line in
                (cookbook_dir / "spans.jsonl").read_text(encoding="utf-8").splitlines() if line]
    by_source: dict[str, list[dict]] = {}
    for s in spans_in:
        by_source.setdefault(s["source"], []).append(s)

    model = model_schema.empty_model()
    model["sources"] = manifest["sources"]
    model["spans"] = list(spans_in)
    counter, claim_counter = [1], [1]
    import_maps: dict[str, dict[str, str]] = {}  # src_root -> dotted -> file node id

    n_files = sum(len(v) for v in by_source.values())
    print(f"[Stage 2/7] compile: {len(manifest['sources'])} sources, {n_files} file spans")

    for src in manifest["sources"]:
        root = src["path"]
        imap: dict[str, str] = {}
        for fs in by_source.get(src["id"], []):
            loc = fs["locator"].replace("\\", "/").lower()
            if loc.endswith(".py"):
                imap.update(extract_code.extract_python(
                    fs, root, model["spans"], model["nodes"], model["edges"], counter))
            elif loc.endswith((".md", ".rst", ".txt")) or src["type"] == "pdf":
                extract_doc.extract_markdown(
                    fs, root, model["spans"], model["nodes"], model["edges"],
                    model["claims"], model["glossary"], counter, claim_counter)
            elif loc.endswith(".csv"):
                extract_data.extract_csv(fs, root, model["spans"], model["nodes"],
                                         model["edges"], counter)
            elif loc.endswith(".sql"):
                extract_data.extract_sql(fs, root, model["spans"], model["nodes"],
                                         model["edges"], counter)
        import_maps[root] = imap

    # link imports to in-repo files where the dotted path resolves
    relinked = 0
    for src in manifest["sources"]:
        imap = import_maps.get(src["path"], {})
        if not imap:
            continue
        for e in model["edges"]:
            if e["type"] == "imports" and e["target"].startswith("node:mod/"):
                dotted = e["target"].removeprefix("node:mod/")
                target = imap.get(dotted) or imap.get(dotted + ".__init__")
                if target and target != e["source"]:
                    e["target"] = target
                    relinked += 1

    # deterministic glossary from class docstrings (term = class name)
    seen_terms = {g["term"].lower() for g in model["glossary"]}
    for n in model["nodes"]:
        if n["type"] == "class" and n.get("summary") and "." not in n["name"]:
            if n["name"].lower() not in seen_terms:
                seen_terms.add(n["name"].lower())
                model["glossary"].append({"term": n["name"],
                                          "definition": n["summary"][:300],
                                          "first_span": n["spans"][0]})

    model, fixed, could_not_fix = merge_mod.merge(model)
    print(f"  extracted: {len(model['nodes'])} nodes, {len(model['edges'])} edges, "
          f"{len(model['claims'])} claims, {len(model['glossary'])} glossary terms "
          f"({relinked} imports relinked to files)")
    print("  Fixed: " + ("; ".join(fixed) if fixed else "nothing to fix"))
    if could_not_fix:
        print("  Could not fix:")
        for x in could_not_fix:
            print("   -", x)

    (cookbook_dir / "model.json").write_text(json.dumps(model, indent=1), encoding="utf-8")
    with (cookbook_dir / "runs.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"at": datetime.now(timezone.utc).isoformat(),
                             "stage": "compile", "nodes": len(model["nodes"]),
                             "edges": len(model["edges"]), "claims": len(model["claims"]),
                             "could_not_fix": len(could_not_fix)}) + "\n")
    print(f"[Stage 2/7] done: model.json written ({len(could_not_fix)} residue items)")
    return model


if __name__ == "__main__":
    compile_model(Path(sys.argv[1]))
