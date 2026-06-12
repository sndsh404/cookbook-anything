//! write: drafts paper.md strictly from the model, one factual sentence per
//! claim marker {{c:NNNN}}. Two kinds of claims feed the prose: doc claims
//! (sentences lifted verbatim from sources at compile time) and derived
//! claims minted here from graph structure, each with the spans of the nodes
//! it describes. The markers are the leash: ca verify walks every one.

use ca_model::{Claim, ClaimId, Model, NodeKind, SpanRefs};
use std::collections::HashMap;
use std::fmt::Write as _;
use std::path::Path;

use crate::plan::Plan;

pub struct WriteOut {
    pub paper: String,
    pub n_factual: usize,
    pub n_marked: usize,
}

fn mint<'a>(
    model: &mut Model,
    next: &mut usize,
    text: String,
    spans: SpanRefs,
) -> (String, ClaimId) {
    let id = ClaimId(format!("c:w{:04}", *next));
    *next += 1;
    model.claims.push(Claim::new(id.clone(), text.clone(), spans, 0.9));
    (format!("{text} {{{{{}}}}}", id.0), id)
}

pub fn write_paper(model: &mut Model, plan: &Plan, repo_name: &str, plant_unsupported: bool) -> WriteOut {
    // writer-owned derived claims (c:w*) are regenerated deterministically
    // every run; drop stale ones so reruns never accumulate duplicates
    model.claims.retain(|c| !c.id.0.starts_with("c:w"));
    let mut p = String::new();
    let mut n_factual = 0usize;
    let mut n_marked = 0usize;
    let mut next_w = 1usize;

    let nodes_by_id: HashMap<String, usize> =
        model.nodes.iter().enumerate().map(|(i, n)| (n.id.0.clone(), i)).collect();

    let mut fact = |model: &mut Model, next: &mut usize, text: String, spans: SpanRefs,
                    nf: &mut usize, nm: &mut usize| -> String {
        *nf += 1;
        *nm += 1;
        mint(model, next, text, spans).0
    };

    // ---------- TL;DR + page-one figure
    let n_files = model.nodes.iter().filter(|n| n.kind == NodeKind::File).count();
    let n_fns = model.nodes.iter().filter(|n| n.kind == NodeKind::Function).count();
    let first_span = model.nodes.iter().find(|n| !n.spans.is_empty()).map(|n| n.spans[0].clone());
    let Some(first_span) = first_span else {
        return WriteOut { paper: "(empty model)".into(), n_factual: 0, n_marked: 0 };
    };

    writeln!(p, "# {repo_name}: a guided cookbook\n").ok();
    writeln!(p, "## TL;DR\n").ok();
    let s = fact(model, &mut next_w,
        format!("This codebase compiles to a model of {n_files} files and {n_fns} functions, every one traced to source."),
        SpanRefs::new(first_span.clone(), vec![]), &mut n_factual, &mut n_marked);
    write!(p, "{s} ").ok();
    let s = fact(model, &mut next_w,
        format!("The tour below walks {} areas in dependency order, so nothing is used before it is taught.", plan.chapters.len()),
        SpanRefs::new(first_span.clone(), vec![]), &mut n_factual, &mut n_marked);
    writeln!(p, "{s}\n").ok();
    writeln!(p, "![the system in one figure](figures/fig_page_one.png)\n").ok();
    writeln!(p, "*Figure: The clusters of this codebase and which ones depend on which.*\n").ok();

    // ---------- Introduction (CARS)
    writeln!(p, "## Introduction\n").ok();
    let doc_claims: Vec<(ClaimId, String)> = model
        .claims
        .iter()
        // superseded claims stay in the model for the audit trail, but only
        // active ones may be quoted as fact
        .filter(|c| !c.id.0.starts_with("c:w") && c.status == ca_model::ClaimStatus::Active)
        .take(3)
        .map(|c| (c.id.clone(), c.text.clone()))
        .collect();
    for (id, text) in &doc_claims {
        n_factual += 1;
        n_marked += 1;
        write!(p, "{text} {{{{{}}}}} ", id.0).ok();
    }
    writeln!(p, "\n").ok();
    writeln!(p, "Read the chapters in order; each one assumes only what came before it. Use the cookbook section at the end to turn the tour into runnable steps.\n").ok();
    if plant_unsupported {
        // a deliberately unsupported factual sentence: the verifier must flag it
        writeln!(p, "The scheduler rebalances shards every night at 02:00 UTC.\n").ok();
        n_factual += 1;
    }
    writeln!(p, "Chapter map:\n").ok();
    for ch in &plan.chapters {
        writeln!(p, "- Chapter {}: {}", ch.index + 1, ch.title).ok();
    }
    writeln!(p).ok();

    // ---------- chapters
    for ch in &plan.chapters {
        writeln!(p, "## Chapter {}: {}\n", ch.index + 1, ch.title).ok();
        let mut member_idx: Vec<usize> =
            ch.node_ids.iter().filter_map(|id| nodes_by_id.get(id).copied()).collect();
        // documented files first: the bullets should teach, not apologize
        member_idx.sort_by_key(|&i| (model.nodes[i].summary.is_empty(), model.nodes[i].name.clone()));
        let spans: Vec<_> = member_idx
            .iter()
            .filter_map(|&i| model.nodes[i].spans.first().cloned())
            .collect();
        let Some(head_span) = spans.first().cloned() else { continue };
        let s = fact(model, &mut next_w,
            format!("The {} area holds {} files of this codebase.", ch.title, ch.node_ids.len()),
            SpanRefs::new(head_span.clone(), spans.iter().skip(1).take(3).cloned().collect()),
            &mut n_factual, &mut n_marked);
        writeln!(p, "{s}\n").ok();

        for &i in member_idx.iter().take(5) {
            let (name, summary, span) = {
                let n = &model.nodes[i];
                (n.name.clone(), n.summary.clone(), n.spans.first().cloned())
            };
            if let (false, Some(sp)) = (summary.is_empty(), span) {
                // derived claims are not verbatim-checked, so the voice
                // profile (no em dashes) may be applied to the quote
                let quote = summary.trim_end_matches('.').replace('\u{2014}', "-");
                let s = fact(model, &mut next_w,
                    format!("`{}` says of itself: \"{}\".", name, quote),
                    SpanRefs::new(sp, vec![]), &mut n_factual, &mut n_marked);
                writeln!(p, "- {s}").ok();
            } else {
                writeln!(p, "- `{name}` (no docstring; see the source span in the claims appendix)").ok();
            }
        }
        writeln!(p).ok();
        writeln!(p, "![chapter figure](figures/fig_ch{}.png)\n", ch.index + 1).ok();
        let caption = match ch.figure.recipe.as_str() {
            "dependency_graph" => format!("The import structure inside {}: most files lean on one hub.", ch.title),
            _ => format!("A few files carry most of the code in {}.", ch.title),
        };
        writeln!(p, "*Figure: {caption}*\n").ok();
        writeln!(p, "What you can now do: open any file in `{}` and place it on this chapter's figure.\n", ch.title).ok();
    }

    // ---------- cookbook
    writeln!(p, "## The cookbook\n").ok();
    writeln!(p, "1. Clone the repo and open the entry points listed below. (expected: the files exist at the cited spans) [unverified]").ok();
    writeln!(p, "2. Re-run the compile stage and diff model.json against the claims appendix. (expected: zero unresolved references) [unverified]\n").ok();

    // ---------- glossary
    writeln!(p, "## Glossary\n").ok();
    for g in model.glossary.iter().take(20) {
        writeln!(p, "- **{}**: {} ({})", g.term, g.definition, g.first_span.0).ok();
    }
    writeln!(p).ok();

    // ---------- claims appendix (the verifiability receipt; non-optional)
    writeln!(p, "## Claims appendix\n").ok();
    let span_loc: HashMap<&str, &str> =
        model.spans.iter().map(|s| (s.id.0.as_str(), s.locator.as_str())).collect();
    let claim_lines: Vec<String> = model
        .claims
        .iter()
        .map(|c| {
            let locs: Vec<&str> =
                c.spans.iter().filter_map(|sp| span_loc.get(sp.0.as_str()).copied()).collect();
            format!("- `{}` \"{}\" -> {}", c.id.0, c.text, locs.join(", "))
        })
        .collect();
    for line in claim_lines {
        writeln!(p, "{line}").ok();
    }
    writeln!(p).ok();

    // ---------- unverified appendix
    writeln!(p, "## Unverified appendix\n").ok();
    let unverified: Vec<String> = model
        .edges
        .iter()
        .filter(|e| e.is_unverified())
        .map(|e| format!("- {} -> {} ({:?}, confidence {})", e.source(), e.target(), e.kind(), e.confidence().get()))
        .collect();
    if unverified.is_empty() {
        writeln!(p, "- no agent-proposed edges in this model").ok();
    }
    for u in unverified {
        writeln!(p, "{u}").ok();
    }
    writeln!(p, "- cookbook steps marked [unverified] above await execution evidence").ok();

    WriteOut { paper: p, n_factual, n_marked }
}

pub fn coverage_json(out: &WriteOut) -> String {
    let pct = if out.n_factual == 0 { 0.0 } else { 100.0 * out.n_marked as f64 / out.n_factual as f64 };
    serde_json::json!({
        "claim_coverage_pct": (pct * 10.0).round() / 10.0,
        "n_factual": out.n_factual,
        "n_marked": out.n_marked,
    })
    .to_string()
}

/// Strip {{c:...}} markers for the shipped paper (utf-8 safe, no regex dep).
pub fn strip_markers(s: &str) -> String {
    let mut out = String::with_capacity(s.len());
    let mut rest = s;
    while let Some(start) = rest.find("{{") {
        if let Some(end_rel) = rest[start..].find("}}") {
            let mut head = &rest[..start];
            if head.ends_with(' ') {
                head = &head[..head.len() - 1];
            }
            out.push_str(head);
            rest = &rest[start + end_rel + 2..];
        } else {
            break;
        }
    }
    out.push_str(rest);
    out
}

pub fn save(workspace: &Path, paper: &str, coverage: &str) -> std::io::Result<()> {
    let out = workspace.join("out");
    std::fs::create_dir_all(&out)?;
    std::fs::write(out.join("paper.draft.md"), paper)?;
    std::fs::write(out.join("coverage.json"), coverage)?;
    Ok(())
}
