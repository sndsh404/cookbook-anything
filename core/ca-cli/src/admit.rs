//! admit: the one door through which swarm findings enter the model.
//!
//! Workers (TypeScript, parallel, untrusted) produce findings; this gate
//! applies the same rules as everything else: a claim finding is admitted
//! only if its span exists AND the claim text appears verbatim in that
//! span's redacted text. Multiple workers agreeing raises confidence; a
//! contradiction mints a second span-backed claim and records the
//! disagreement (never a silent overwrite, never a vote). Anything
//! unsourced is rejected and listed, period.

use ca_model::{Claim, ClaimId, ClaimStatus, Model, SpanRefs};
use serde::Deserialize;
use std::collections::{BTreeMap, HashMap};

#[derive(Deserialize)]
pub struct FindingsFile {
    pub findings: Vec<Finding>,
}

#[derive(Deserialize, Clone)]
pub struct Finding {
    #[serde(default = "default_kind")]
    pub kind: String, // "claim" | "support" | "contradict"
    #[serde(default)]
    pub text: String,
    #[serde(default)]
    pub span_id: String,
    #[serde(default)]
    pub claim_id: String,
    #[serde(default)]
    pub worker: String,
}

fn default_kind() -> String {
    "claim".into()
}

pub struct AdmitReport {
    pub admitted: usize,
    pub supported: usize,
    pub contradictions: usize,
    pub rejected: Vec<String>,
    pub events: Vec<serde_json::Value>,
}

const BASE_CONFIDENCE: f64 = 0.6;
const AGREEMENT_STEP: f64 = 0.15;
const SUPPORT_STEP: f64 = 0.1;
const CONFIDENCE_CAP: f64 = 0.95;

pub fn admit(model: &mut Model, file: FindingsFile) -> AdmitReport {
    let span_text: HashMap<String, String> =
        model.spans.iter().map(|s| (s.id.0.clone(), s.text.clone())).collect();
    let mut next_id = model
        .claims
        .iter()
        .filter_map(|c| c.id.0.strip_prefix("c:").and_then(|n| n.parse::<usize>().ok()))
        .max()
        .unwrap_or(0)
        + 1;

    let mut rep = AdmitReport {
        admitted: 0,
        supported: 0,
        contradictions: 0,
        rejected: Vec::new(),
        events: Vec::new(),
    };

    // ---- claim findings: group identical texts so agreement is visible
    let mut groups: BTreeMap<String, (Vec<String>, Vec<String>)> = BTreeMap::new(); // text -> (span_ids, workers)
    for f in file.findings.iter().filter(|f| f.kind == "claim") {
        let Some(stext) = span_text.get(&f.span_id) else {
            rep.rejected.push(format!(
                "worker {}: span {} does not exist (unsourced assertion dropped)",
                f.worker, f.span_id
            ));
            continue;
        };
        if f.text.trim().is_empty() || !stext.contains(f.text.trim()) {
            rep.rejected.push(format!(
                "worker {}: text not found verbatim in span {}: \"{}\"",
                f.worker,
                f.span_id,
                f.text.chars().take(60).collect::<String>()
            ));
            continue;
        }
        let e = groups.entry(f.text.trim().to_string()).or_default();
        if !e.0.contains(&f.span_id) {
            e.0.push(f.span_id.clone());
        }
        if !e.1.contains(&f.worker) {
            e.1.push(f.worker.clone());
        }
    }

    for (text, (span_ids, workers)) in groups {
        // idempotent: an existing active claim with the same text gains the
        // new spans as agreement instead of being duplicated
        if let Some(existing) = model
            .claims
            .iter_mut()
            .find(|c| c.status == ClaimStatus::Active && c.text == text)
        {
            let mut added = 0usize;
            for sid in &span_ids {
                if !existing.spans.iter().any(|sp| &sp.0 == sid) {
                    let mut v: Vec<_> = existing.spans.iter().cloned().collect();
                    v.push(ca_model::SpanId(sid.clone()));
                    if let Ok(sr) = SpanRefs::try_from_vec(v) {
                        existing.spans = sr;
                        added += 1;
                    }
                }
            }
            if added > 0 {
                let c = (existing.confidence.get() + SUPPORT_STEP * added as f64)
                    .min(CONFIDENCE_CAP);
                existing.confidence = ca_model::Confidence::new(c);
                rep.supported += added;
                rep.events.push(serde_json::json!({"event": "agreement",
                    "claim": existing.id.0, "new_spans": added,
                    "confidence": existing.confidence.get()}));
            }
            continue;
        }
        let conf = (BASE_CONFIDENCE + AGREEMENT_STEP * (workers.len() as f64 - 1.0))
            .min(CONFIDENCE_CAP);
        let id = ClaimId(format!("c:{next_id:04}"));
        next_id += 1;
        let spans = SpanRefs::try_from_vec(
            span_ids.iter().map(|s| ca_model::SpanId(s.clone())).collect(),
        )
        .expect("group always has at least one span");
        model.claims.push(Claim::new(id.clone(), text.clone(), spans, conf));
        rep.admitted += 1;
        rep.events.push(serde_json::json!({"event": "admitted", "claim": id.0,
            "workers": workers, "confidence": conf}));
    }

    // ---- verification verdicts
    for f in file.findings.iter().filter(|f| f.kind == "support" || f.kind == "contradict") {
        let Some(stext) = span_text.get(&f.span_id) else {
            rep.rejected.push(format!(
                "worker {}: verdict cites missing span {}",
                f.worker, f.span_id
            ));
            continue;
        };
        let Some(pos) = model.claims.iter().position(|c| c.id.0 == f.claim_id) else {
            rep.rejected.push(format!(
                "worker {}: verdict on unknown claim {}",
                f.worker, f.claim_id
            ));
            continue;
        };
        if f.kind == "support" {
            // a supporting span must actually contain the claim text
            let claim_text = model.claims[pos].text.clone();
            if !stext.contains(claim_text.as_str()) {
                rep.rejected.push(format!(
                    "worker {}: support span {} does not contain claim {} text",
                    f.worker, f.span_id, f.claim_id
                ));
                continue;
            }
            let c = &mut model.claims[pos];
            if !c.spans.iter().any(|sp| sp.0 == f.span_id) {
                let mut v: Vec<_> = c.spans.iter().cloned().collect();
                v.push(ca_model::SpanId(f.span_id.clone()));
                if let Ok(sr) = SpanRefs::try_from_vec(v) {
                    c.spans = sr;
                    let nc = (c.confidence.get() + SUPPORT_STEP).min(CONFIDENCE_CAP);
                    c.confidence = ca_model::Confidence::new(nc);
                    rep.supported += 1;
                    rep.events.push(serde_json::json!({"event": "supported",
                        "claim": c.id.0, "span": f.span_id, "confidence": nc}));
                }
            }
        } else {
            // contradiction: the counter-statement must itself be span-backed;
            // it becomes a second claim and the disagreement is recorded,
            // never resolved by vote
            if f.text.trim().is_empty() || !stext.contains(f.text.trim()) {
                rep.rejected.push(format!(
                    "worker {}: contradiction text not found verbatim in span {}",
                    f.worker, f.span_id
                ));
                continue;
            }
            let id = ClaimId(format!("c:{next_id:04}"));
            next_id += 1;
            let spans = SpanRefs::new(ca_model::SpanId(f.span_id.clone()), vec![]);
            model.claims.push(Claim::new(id.clone(), f.text.trim().to_string(), spans, BASE_CONFIDENCE));
            rep.contradictions += 1;
            rep.events.push(serde_json::json!({"event": "contradicted",
                "claim": f.claim_id, "by": id.0, "span": f.span_id}));
        }
    }

    rep
}
