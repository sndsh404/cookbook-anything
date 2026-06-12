"""extract_doc.py - section graph + claims for markdown/PDF-text sources.

Sections come from headings; claims are sentences lifted verbatim from
paragraphs (the claim text IS span text, which is what makes it a claim and
not an opinion). Glossary entries come from bold-term definition lines.
"""
from __future__ import annotations

import hashlib
import re

EXTRACTOR = "extract_doc.py@markdown"
HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
BOLD_DEF = re.compile(r"^\*\*([^*]{2,40})\*\*\s*[:—-]\s*(.+)$")
SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:60]


def _span(spans_out, counter, src, locator, text) -> str:
    sid = f"span:d{counter[0]:05d}"
    counter[0] += 1
    spans_out.append({"id": sid, "source": src, "locator": locator,
                      "text_sha": hashlib.sha256(text.encode()).hexdigest(),
                      "text": text[:2000]})
    return sid


def claim_worthy(sentence: str) -> bool:
    s = sentence.strip()
    return (30 <= len(s) <= 300 and s[0].isupper() and s.endswith(".")
            and not s.startswith(("TODO", "Note:", "http"))
            and "|" not in s and "```" not in s and "?" not in s)


def extract_markdown(file_span: dict, src_root_name: str, spans_out: list[dict],
                     nodes_out: list[dict], edges_out: list[dict],
                     claims_out: list[dict], glossary_out: list[dict],
                     counter: list[int], claim_counter: list[int]) -> None:
    rel = file_span["locator"]
    text = file_span["text"]
    src = file_span["source"]
    file_id = f"node:file/{src_root_name}/{rel}".replace("\\", "/")
    nodes_out.append({"id": file_id, "type": "file", "name": rel,
                      "summary": "", "attrs": {"language": "markdown"},
                      "spans": [file_span["id"]]})

    lines = text.splitlines()
    # section boundaries
    heads = [(i, len(m.group(1)), m.group(2)) for i, line in enumerate(lines)
             if (m := HEADING.match(line)) and not line.startswith("    ")]
    stack: list[tuple[int, str]] = []  # (level, node_id)
    for idx, (line_no, level, title) in enumerate(heads):
        end = heads[idx + 1][0] - 1 if idx + 1 < len(heads) else len(lines) - 1
        body = "\n".join(lines[line_no:end + 1])
        sid = _span(spans_out, counter, src, f"{rel}#L{line_no + 1}-L{end + 1}", body)
        nid = f"node:sec/{src_root_name}/{rel}#{_slug(title)}".replace("\\", "/")
        if any(n["id"] == nid for n in nodes_out):
            nid = f"{nid}-{line_no}"
        # summary: first non-heading, non-blank paragraph line
        first_para = next((ln.strip() for ln in lines[line_no + 1:end + 1]
                           if ln.strip() and not HEADING.match(ln)), "")
        nodes_out.append({"id": nid, "type": "section", "name": title,
                          "summary": SENTENCE_END.split(first_para)[0][:200] if first_para else "",
                          "attrs": {}, "spans": [sid]})
        while stack and stack[-1][0] >= level:
            stack.pop()
        parent = stack[-1][1] if stack else file_id
        edges_out.append({"source": parent, "target": nid, "type": "contains",
                          "extractor": EXTRACTOR, "spans": [sid], "confidence": 1.0})
        stack.append((level, nid))

        # claims + glossary from this section's paragraphs
        para: list[str] = []
        def flush(end_line: int) -> None:
            if not para:
                return
            ptext = " ".join(para)
            if ptext.startswith(("```", "|", ">", "-", "*", "1.")):
                para.clear()
                return
            psid = _span(spans_out, counter, src,
                         f"{rel}#L{end_line - len(para) + 1}-L{end_line}", ptext)
            for sent in SENTENCE_END.split(ptext)[:2]:
                if claim_worthy(sent):
                    claims_out.append({"id": f"c:{claim_counter[0]:04d}",
                                       "text": sent.strip(), "spans": [psid],
                                       "confidence": 0.8, "status": "active",
                                       "supersedes": None})
                    claim_counter[0] += 1
                    break
            para.clear()

        in_code = False
        for j in range(line_no + 1, end + 1):
            ln = lines[j]
            if ln.strip().startswith("```"):
                in_code = not in_code
                para.clear()
                continue
            if in_code:
                continue
            if m := BOLD_DEF.match(ln.strip()):
                gsid = _span(spans_out, counter, src, f"{rel}#L{j + 1}", ln.strip())
                glossary_out.append({"term": m.group(1).strip(),
                                     "definition": m.group(2).strip()[:300],
                                     "first_span": gsid})
                continue
            if ln.strip():
                para.append(ln.strip())
            else:
                flush(j)
        flush(end + 1)
