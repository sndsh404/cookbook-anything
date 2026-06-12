//! ca-merge: normalize, dedupe, drop dangling refs. Reports Fixed (pattern
//! counts) vs Could-not-fix (judgment residue). Note the agent-confidence
//! clamp from the Python prototype is gone: ca-model makes an agent edge at
//! confidence 1.0 unrepresentable, so there is nothing left to clamp.

use ca_model::{Model, NodeId, SpanId};
use std::collections::{BTreeMap, HashSet};

pub struct MergeReport {
    pub fixed: Vec<String>,
    pub could_not_fix: Vec<String>,
}

pub fn merge(model: &mut Model) -> MergeReport {
    let mut fixed: BTreeMap<&'static str, usize> = BTreeMap::new();
    let mut could_not_fix: Vec<String> = Vec::new();
    fn bump(k: &'static str, m: &mut BTreeMap<&'static str, usize>) {
        *m.entry(k).or_default() += 1;
    }

    // dedupe nodes by id, merging span lists and preferring non-empty summaries
    let mut by_id: BTreeMap<NodeId, ca_model::Node> = BTreeMap::new();
    for n in std::mem::take(&mut model.nodes) {
        match by_id.get_mut(&n.id) {
            Some(prev) => {
                for sp in n.spans {
                    if !prev.spans.contains(&sp) {
                        prev.spans.push(sp);
                    }
                }
                if prev.summary.is_empty() && !n.summary.is_empty() {
                    prev.summary = n.summary;
                }
                bump("deduped node", &mut fixed);
            }
            None => {
                by_id.insert(n.id.clone(), n);
            }
        }
    }
    model.nodes = by_id.into_values().collect();
    let node_ids: HashSet<NodeId> = model.nodes.iter().map(|n| n.id.clone()).collect();

    // dedupe spans by id
    let mut seen_spans: HashSet<SpanId> = HashSet::new();
    let before = model.spans.len();
    model.spans.retain(|s| seen_spans.insert(s.id.clone()));
    for _ in 0..(before - model.spans.len()) {
        bump("deduped span", &mut fixed);
    }
    let span_ids: HashSet<SpanId> = seen_spans;

    // dedupe edges, drop danglers, prune bad span refs
    let mut seen_edges: HashSet<(NodeId, NodeId, String)> = HashSet::new();
    let mut kept = Vec::new();
    for mut e in std::mem::take(&mut model.edges) {
        let key = (e.source().clone(), e.target().clone(), format!("{:?}", e.kind()));
        if !seen_edges.insert(key) {
            bump("deduped edge", &mut fixed);
            continue;
        }
        if !node_ids.contains(e.source()) || !node_ids.contains(e.target()) {
            bump("dropped dangling edge", &mut fixed);
            continue;
        }
        if e.prune_spans(&span_ids) {
            bump("pruned edge span refs", &mut fixed);
        }
        kept.push(e);
    }
    model.edges = kept;

    // node span refs
    for n in &mut model.nodes {
        let before = n.spans.len();
        n.spans.retain(|sp| span_ids.contains(sp));
        if n.spans.len() != before {
            bump("pruned node span refs", &mut fixed);
            if n.spans.is_empty() {
                could_not_fix.push(format!("node {} lost all spans", n.id));
            }
        }
    }

    // claims: SpanRefs::retain errors when a claim would lose all spans
    // (hard rule 2); such claims are dropped and reported, never kept bare
    let mut ok_claims = Vec::new();
    for mut c in std::mem::take(&mut model.claims) {
        match c.spans.retain(|sp| span_ids.contains(sp)) {
            Ok(()) => ok_claims.push(c),
            Err(_) => {
                could_not_fix.push(format!("claim {} has no resolvable spans; dropped", c.id));
                bump("dropped spanless claim", &mut fixed);
            }
        }
    }
    model.claims = ok_claims;

    // glossary: dedupe terms, drop bad span refs
    let mut seen_terms: HashSet<String> = HashSet::new();
    let mut ok_gloss = Vec::new();
    for g in std::mem::take(&mut model.glossary) {
        if !seen_terms.insert(g.term.to_lowercase()) {
            bump("deduped glossary term", &mut fixed);
            continue;
        }
        if !span_ids.contains(&g.first_span) {
            bump("dropped glossary term with bad span", &mut fixed);
            continue;
        }
        ok_gloss.push(g);
    }
    model.glossary = ok_gloss;

    for err in model.validate() {
        could_not_fix.push(format!("schema: {err}"));
    }

    MergeReport {
        fixed: fixed.into_iter().map(|(k, v)| format!("{k} x{v}")).collect(),
        could_not_fix,
    }
}
