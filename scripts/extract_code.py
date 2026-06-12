"""extract_code.py - structure graph for code sources (M1: python via ast).

Works over REDACTED span text from intake, never raw sources, so secret
hygiene survives compilation. Every edge born here carries confidence 1.0
and this extractor's name. Imports/defines/contains always; calls only
same-file (narrow-and-true over broad-and-flaky, DESIGN honest seam 2).
"""
from __future__ import annotations

import ast

EXTRACTOR = "extract_code.py@python"
MAX_SPAN_TEXT = 1500


def _sub_span(spans_out: list[dict], counter: list[int], src: str, locator: str,
              text: str) -> str:
    import hashlib
    sid = f"span:c{counter[0]:05d}"
    counter[0] += 1
    clipped = text[:MAX_SPAN_TEXT]
    spans_out.append({"id": sid, "source": src, "locator": locator,
                      "text_sha": hashlib.sha256(clipped.encode()).hexdigest(),
                      "text": clipped})
    return sid


def extract_python(file_span: dict, src_root_name: str, spans_out: list[dict],
                   nodes_out: list[dict], edges_out: list[dict],
                   counter: list[int]) -> dict[str, str]:
    """Returns {module_dotted_path: file_node_id} for cross-file import linking."""
    rel = file_span["locator"]
    text = file_span["text"]
    src = file_span["source"]
    file_id = f"node:file/{src_root_name}/{rel}".replace("\\", "/")
    lines = text.splitlines()

    try:
        tree = ast.parse(text)
    except SyntaxError:
        nodes_out.append({"id": file_id, "type": "file", "name": rel,
                          "summary": "unparseable python (syntax error); structure not extracted",
                          "attrs": {"language": "python", "loc": len(lines)},
                          "spans": [file_span["id"]]})
        return {}

    doc = ast.get_docstring(tree) or ""
    nodes_out.append({"id": file_id, "type": "file", "name": rel,
                      "summary": doc.strip().splitlines()[0] if doc.strip() else "",
                      "attrs": {"language": "python", "loc": len(lines)},
                      "spans": [file_span["id"]]})

    local_funcs: dict[str, str] = {}

    def add_def(node: ast.AST, qual: str, parent_id: str, edge_type: str) -> str:
        kind = "class" if isinstance(node, ast.ClassDef) else "function"
        a, b = node.lineno, getattr(node, "end_lineno", node.lineno)
        sid = _sub_span(spans_out, counter, src, f"{rel}#L{a}-L{b}",
                        "\n".join(lines[a - 1:b]))
        nid = f"node:py/{src_root_name}/{rel}#{qual}".replace("\\", "/")
        d = ast.get_docstring(node) or ""
        nodes_out.append({"id": nid, "type": kind, "name": qual,
                          "summary": d.strip().splitlines()[0] if d.strip() else "",
                          "attrs": {"language": "python", "loc": b - a + 1},
                          "spans": [sid]})
        edges_out.append({"source": parent_id, "target": nid, "type": edge_type,
                          "extractor": EXTRACTOR, "spans": [sid], "confidence": 1.0})
        return nid

    for top in tree.body:
        if isinstance(top, (ast.FunctionDef, ast.AsyncFunctionDef)):
            fid = add_def(top, top.name, file_id, "defines")
            local_funcs[top.name] = fid
        elif isinstance(top, ast.ClassDef):
            cid = add_def(top, top.name, file_id, "defines")
            for item in top.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    add_def(item, f"{top.name}.{item.name}", cid, "contains")

    # same-file calls between top-level functions
    for top in tree.body:
        if not isinstance(top, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        caller = local_funcs.get(top.name)
        if not caller:
            continue
        seen: set[str] = set()
        for call in ast.walk(top):
            if isinstance(call, ast.Call) and isinstance(call.func, ast.Name):
                callee = local_funcs.get(call.func.id)
                if callee and callee != caller and callee not in seen:
                    seen.add(callee)
                    edges_out.append({"source": caller, "target": callee,
                                      "type": "calls", "extractor": EXTRACTOR,
                                      "spans": [file_span["id"]], "confidence": 1.0})

    # imports: record dotted module names; compile.py links them to files
    imports: list[str] = []
    for top in ast.walk(tree):
        if isinstance(top, ast.Import):
            imports += [a.name for a in top.names]
        elif isinstance(top, ast.ImportFrom) and top.module:
            imports.append(top.module)
    for mod in sorted(set(imports)):
        mid = f"node:mod/{mod}"
        if not any(n["id"] == mid for n in nodes_out):
            nodes_out.append({"id": mid, "type": "module", "name": mod,
                              "summary": "", "attrs": {}, "spans": [file_span["id"]]})
        edges_out.append({"source": file_id, "target": mid, "type": "imports",
                          "extractor": EXTRACTOR, "spans": [file_span["id"]],
                          "confidence": 1.0})

    dotted = rel.replace("\\", "/").removesuffix(".py").replace("/", ".")
    return {dotted: file_id, dotted.removesuffix(".__init__"): file_id}
