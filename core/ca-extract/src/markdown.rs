//! Markdown extractor: section graph from headings; claims are sentences
//! lifted VERBATIM from paragraphs (the claim text IS span text); glossary
//! entries from bold-term definition lines.

use crate::ExtractOut;
use ca_model::{Claim, ClaimId, Edge, EdgeKind, ExtractorId, GlossaryEntry, Node, NodeId, NodeKind, Span, SpanRefs};
use regex::Regex;
use std::sync::OnceLock;

pub const EXTRACTOR: &str = "ca-extract@markdown";

struct Res {
    heading: Regex,
    bold_def: Regex,
    sentence_end: Regex,
}

fn res() -> &'static Res {
    static R: OnceLock<Res> = OnceLock::new();
    R.get_or_init(|| Res {
        heading: Regex::new(r"^(#{1,6})\s+(.+?)\s*#*\s*$").unwrap(),
        bold_def: Regex::new(r"^\*\*([^*]{2,40})\*\*\s*[:-]\s*(.+)$").unwrap(),
        sentence_end: Regex::new(r"[.!?]\s+").unwrap(),
    })
}

fn slug(s: &str) -> String {
    let mut out = String::new();
    for ch in s.to_lowercase().chars() {
        if ch.is_ascii_alphanumeric() {
            out.push(ch);
        } else if !out.ends_with('-') {
            out.push('-');
        }
    }
    out.trim_matches('-').chars().take(60).collect()
}

fn split_sentences<'a>(re: &Regex, text: &'a str) -> Vec<&'a str> {
    let mut out = Vec::new();
    let mut start = 0usize;
    for m in re.find_iter(text) {
        out.push(text[start..m.start() + 1].trim());
        start = m.end();
    }
    if start < text.len() {
        out.push(text[start..].trim());
    }
    out
}

fn claim_worthy(s: &str) -> bool {
    let s = s.trim();
    s.len() >= 30
        && s.len() <= 300
        && s.chars().next().is_some_and(|c| c.is_uppercase())
        && s.ends_with('.')
        && !s.starts_with("TODO")
        && !s.starts_with("http")
        && !s.contains('|')
        && !s.contains("```")
        && !s.contains('?')
        // a sentence mutilated by the secret filter is evidence, not prose
        && !s.contains("[REDACTED")
        // a sentence containing our own claim-marker delimiters (e.g. docs
        // describing the {{c:NNNN}} syntax) would inject a fake marker if
        // quoted; it is meta-prose about the tool, not a clean claim
        && !s.contains("{{")
        && !s.contains("}}")
}

pub fn extract(file_span: &Span, src_root: &str, out: &mut ExtractOut) {
    let r = res();
    let rel = file_span.locator.replace('\\', "/");
    let text = file_span.text.clone();
    let src = file_span.source.clone();
    let lines: Vec<&str> = text.lines().collect();
    let ex = ExtractorId::new(EXTRACTOR).unwrap();
    let file_id = NodeId(format!("node:file/{src_root}/{rel}"));
    out.nodes.push(Node {
        id: file_id.clone(),
        kind: NodeKind::File,
        name: rel.clone(),
        summary: String::new(),
        // loc lets doc chapters render a quantity figure like code chapters,
        // instead of referencing a figure the figure stage never produced
        attrs: serde_json::Map::from_iter([
            ("language".into(), "markdown".into()),
            ("loc".into(), serde_json::Value::from(lines.len())),
        ]),
        spans: vec![file_span.id.clone()],
    });

    let heads: Vec<(usize, usize, String)> = lines
        .iter()
        .enumerate()
        .filter(|(_, l)| !l.starts_with("    "))
        .filter_map(|(i, l)| r.heading.captures(l).map(|c| (i, c[1].len(), c[2].to_string())))
        .collect();

    let mut stack: Vec<(usize, NodeId)> = Vec::new();
    for (idx, (line_no, level, title)) in heads.iter().enumerate() {
        let end = if idx + 1 < heads.len() { heads[idx + 1].0 - 1 } else { lines.len() - 1 };
        let body = lines[*line_no..=end].join("\n");
        let sid = out.add_span('d', src.clone(), format!("{rel}#L{}-L{}", line_no + 1, end + 1), &body);
        let mut nid = NodeId(format!("node:sec/{src_root}/{rel}#{}", slug(title)));
        if out.nodes.iter().any(|n| n.id == nid) {
            nid = NodeId(format!("{}-{}", nid.0, line_no));
        }
        let first_para = lines[line_no + 1..=end]
            .iter()
            .map(|l| l.trim())
            .find(|l| !l.is_empty() && !r.heading.is_match(l))
            .unwrap_or("");
        let summary = split_sentences(&r.sentence_end, first_para)
            .first()
            .map(|s| s.chars().take(200).collect())
            .unwrap_or_default();
        out.nodes.push(Node {
            id: nid.clone(),
            kind: NodeKind::Section,
            name: title.clone(),
            summary,
            attrs: Default::default(),
            spans: vec![sid.clone()],
        });
        while stack.last().is_some_and(|(lv, _)| *lv >= *level) {
            stack.pop();
        }
        let parent = stack.last().map(|(_, id)| id.clone()).unwrap_or_else(|| file_id.clone());
        out.edges.push(Edge::extracted(parent, nid.clone(), EdgeKind::Contains, ex.clone(), vec![sid]));
        stack.push((*level, nid));

        // paragraphs: claims + glossary
        let mut para: Vec<String> = Vec::new();
        let mut in_code = false;
        let mut flush = |para: &mut Vec<String>, end_line: usize, out: &mut ExtractOut| {
            if para.is_empty() {
                return;
            }
            let ptext = para.join(" ");
            let plen = para.len();
            para.clear();
            if ptext.starts_with("```")
                || ptext.starts_with('|')
                || ptext.starts_with('>')
                || ptext.starts_with('-')
                || ptext.starts_with('*')
                || ptext.starts_with("1.")
            {
                return;
            }
            let psid = out.add_span(
                'd',
                src.clone(),
                format!("{rel}#L{}-L{}", end_line + 1 - plen, end_line),
                &ptext,
            );
            for sent in split_sentences(&res().sentence_end, &ptext).into_iter().take(2) {
                if claim_worthy(sent) {
                    let id = ClaimId(format!("c:{:04}", out.claim_counter));
                    out.claim_counter += 1;
                    out.claims.push(Claim::new(
                        id,
                        sent.trim().to_string(),
                        SpanRefs::new(psid.clone(), vec![]),
                        0.8,
                    ));
                    break;
                }
            }
        };

        for j in (*line_no + 1)..=end {
            let ln = lines[j].trim();
            if ln.starts_with("```") {
                in_code = !in_code;
                para.clear();
                continue;
            }
            if in_code {
                continue;
            }
            if let Some(c) = r.bold_def.captures(ln) {
                let gsid = out.add_span('d', src.clone(), format!("{rel}#L{}", j + 1), ln);
                out.glossary.push(GlossaryEntry {
                    term: c[1].trim().to_string(),
                    definition: c[2].trim().chars().take(300).collect(),
                    first_span: gsid,
                });
                continue;
            }
            if !ln.is_empty() {
                para.push(ln.to_string());
            } else {
                flush(&mut para, j, out);
            }
        }
        flush(&mut para, end + 1, out);
    }
}
