//! verify: the adversarial pass. Walks every {{c:NNNN}} marker in the draft,
//! opens the claim and its spans, and confirms support: doc claims must
//! appear verbatim in their span text; derived claims must resolve to live
//! spans. Then it hunts the other direction: factual-looking sentences with
//! NO marker are flagged, not silently fixed.

use ca_model::Model;
use serde::Serialize;
use std::collections::{HashMap, HashSet};

#[derive(Serialize)]
pub struct VerifyReport {
    pub coverage_pct: f64,
    pub n_marked: usize,
    pub n_unsupported: usize,
    pub broken_markers: Vec<String>,
    pub unsupported_sentences: Vec<String>,
}

const IMPERATIVE_OPENERS: &[&str] =
    &["Read", "Use", "Open", "Clone", "Run", "See", "Note", "Start"];

fn extract_markers(text: &str) -> Vec<(String, String)> {
    // (claim_id, sentence_before_marker)
    let mut out = Vec::new();
    let mut rest = text;
    let mut consumed = String::new();
    while let Some(start) = rest.find("{{") {
        if let Some(end_rel) = rest[start..].find("}}") {
            let id = rest[start + 2..start + end_rel].to_string();
            consumed.push_str(&rest[..start]);
            let sentence = consumed
                .rsplit(|c| c == '!' || c == '?')
                .next()
                .unwrap_or("")
                .rsplit(". ")
                .next()
                .unwrap_or("")
                .trim()
                .to_string();
            out.push((id, sentence));
            consumed.clear();
            rest = &rest[start + end_rel + 2..];
        } else {
            break;
        }
    }
    out
}

fn body_sections(paper: &str) -> String {
    // everything before the cookbook/glossary/appendix tail
    match paper.find("## The cookbook") {
        Some(i) => paper[..i].to_string(),
        None => paper.to_string(),
    }
}

pub fn verify(model: &Model, draft: &str) -> VerifyReport {
    let claims: HashMap<&str, &ca_model::Claim> =
        model.claims.iter().map(|c| (c.id.0.as_str(), c)).collect();
    let span_text: HashMap<&str, &str> =
        model.spans.iter().map(|s| (s.id.0.as_str(), s.text.as_str())).collect();
    let span_ids: HashSet<&str> = span_text.keys().copied().collect();

    let mut broken: Vec<String> = Vec::new();
    let markers = extract_markers(draft);
    for (id, _sentence) in &markers {
        match claims.get(id.as_str()) {
            None => broken.push(format!("marker {{{{{id}}}}} resolves to no claim")),
            Some(c) => {
                let missing: Vec<&str> = c
                    .spans
                    .iter()
                    .filter(|sp| !span_ids.contains(sp.0.as_str()))
                    .map(|sp| sp.0.as_str())
                    .collect();
                if !missing.is_empty() {
                    broken.push(format!("claim {id} cites missing spans {missing:?}"));
                    continue;
                }
                if !id.starts_with("c:w") {
                    // doc claim: text must appear in its span text, verbatim
                    let supported = c.spans.iter().any(|sp| {
                        span_text.get(sp.0.as_str()).is_some_and(|t| t.contains(c.text.as_str()))
                    });
                    if !supported {
                        broken.push(format!(
                            "claim {id} text does not appear in its cited spans: \"{}\"",
                            &c.text.chars().take(60).collect::<String>()
                        ));
                    }
                }
            }
        }
    }

    // the other direction: factual-looking sentences with no marker.
    // A marker covers exactly the sentence it follows: split each line on
    // markers; within each pre-marker segment only the LAST sentence is the
    // marked one, everything else is a candidate.
    let body = body_sections(draft);
    let mut unsupported: Vec<String> = Vec::new();
    let mut candidate = |s: &str, unsupported: &mut Vec<String>| {
        let s = s.trim().trim_end_matches('.').trim();
        if s.is_empty() {
            return;
        }
        let words: Vec<&str> = s.split_whitespace().collect();
        let first = words.first().copied().unwrap_or("");
        if words.len() >= 8
            && first.chars().next().is_some_and(|c| c.is_uppercase())
            && !IMPERATIVE_OPENERS.contains(&first)
        {
            unsupported.push(format!("{s}."));
        }
    };
    for line in body.lines() {
        let t = line.trim();
        if t.is_empty()
            || t.starts_with('#')
            || t.starts_with('!')
            || t.starts_with('*')
            || t.starts_with('-')
            || t.starts_with("Chapter map")
            || t.starts_with("What you can now do")
            || t.chars().next().is_some_and(|c| c.is_ascii_digit())
        {
            continue;
        }
        let mut rest = t;
        loop {
            match rest.find("{{") {
                Some(start) => {
                    let segment = rest[..start].trim_end();
                    let sentences: Vec<&str> = segment.split(". ").collect();
                    // all but the last sentence in this segment are unmarked
                    for s in &sentences[..sentences.len().saturating_sub(1)] {
                        candidate(s, &mut unsupported);
                    }
                    match rest[start..].find("}}") {
                        Some(end_rel) => rest = &rest[start + end_rel + 2..],
                        None => break,
                    }
                }
                None => {
                    for s in rest.split(". ") {
                        candidate(s, &mut unsupported);
                    }
                    break;
                }
            }
        }
    }

    let n_marked = markers.len();
    let denom = n_marked + unsupported.len();
    let coverage = if denom == 0 { 100.0 } else { 100.0 * n_marked as f64 / denom as f64 };
    VerifyReport {
        coverage_pct: (coverage * 10.0).round() / 10.0,
        n_marked,
        n_unsupported: unsupported.len(),
        broken_markers: broken,
        unsupported_sentences: unsupported,
    }
}
