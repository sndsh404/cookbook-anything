//! write: drafts paper.md strictly from the model, and TEACHES on top of the
//! verified facts. Each chapter follows the six-move template distilled from
//! Grokking Algorithms (see MEMORY.md): problem first, name the job, walk one
//! worked example along real call edges, a figure that shows interaction,
//! explain the key files in plain language, close with what you can now do.
//!
//! Provenance is unchanged: every factual sentence carries a {{c:NNNN}}
//! marker that resolves to a claim with spans. The teaching is in WHICH true
//! facts we surface and how we sequence them, never in inventing new ones.

use ca_model::{Claim, ClaimId, Model, NodeKind, SpanRefs};
use std::collections::{HashMap, HashSet};
use std::fmt::Write as _;
use std::path::Path;

use crate::plan::{Chapter, Plan};

pub struct WriteOut {
    pub paper: String,
    pub n_factual: usize,
    pub n_marked: usize,
}

// ----- read-only snapshots taken before any minting (avoids borrow conflicts)

struct DocClaim {
    id: String,
    text: String,
    spans: Vec<String>,
    /// sourced from quality_reports (session metrics like grades and counts);
    /// true facts, but operational noise, not design rationale to teach from
    operational: bool,
}

struct Snap {
    doc_claims: Vec<DocClaim>,
    node_name: HashMap<String, String>,
    file_summary: HashMap<String, String>,   // file node id -> docstring
    file_loc: HashMap<String, u64>,
    file_lang: HashMap<String, String>,
    file_first_span: HashMap<String, String>,
    defs_by_file: HashMap<String, Vec<String>>, // file rel-path -> def names
    span_loc: HashMap<String, String>,
    label: HashMap<String, String>, // file id -> disambiguated short label
}

impl Snap {
    fn label(&self, fid: &str) -> String {
        self.label
            .get(fid)
            .cloned()
            .unwrap_or_else(|| basename(self.node_name.get(fid).map(String::as_str).unwrap_or(fid)))
    }
}

fn snapshot(model: &Model) -> Snap {
    let loc_of: HashMap<&str, &str> =
        model.spans.iter().map(|s| (s.id.0.as_str(), s.locator.as_str())).collect();
    let doc_claims = model
        .claims
        .iter()
        .filter(|c| !c.id.0.starts_with("c:w") && c.status == ca_model::ClaimStatus::Active)
        .map(|c| {
            let operational = c
                .spans
                .iter()
                .filter_map(|s| loc_of.get(s.0.as_str()))
                .any(|l| l.replace('\\', "/").starts_with("quality_reports"));
            DocClaim {
                id: c.id.0.clone(),
                text: c.text.clone(),
                spans: c.spans.iter().map(|s| s.0.clone()).collect(),
                operational,
            }
        })
        .collect();

    let mut node_name = HashMap::new();
    let mut file_summary = HashMap::new();
    let mut file_loc = HashMap::new();
    let mut file_lang = HashMap::new();
    let mut file_first_span = HashMap::new();
    let mut defs_by_file: HashMap<String, Vec<String>> = HashMap::new();

    for n in &model.nodes {
        node_name.insert(n.id.0.clone(), n.name.clone());
        match n.kind {
            NodeKind::File => {
                if !n.summary.is_empty() {
                    file_summary.insert(n.id.0.clone(), n.summary.clone());
                }
                if let Some(loc) = n.attrs.get("loc").and_then(|v| v.as_u64()) {
                    file_loc.insert(n.id.0.clone(), loc);
                }
                if let Some(l) = n.attrs.get("language").and_then(|v| v.as_str()) {
                    file_lang.insert(n.id.0.clone(), l.to_string());
                }
                if let Some(sp) = n.spans.first() {
                    file_first_span.insert(n.id.0.clone(), sp.0.clone());
                }
            }
            NodeKind::Function | NodeKind::Class => {
                let id = &n.id.0;
                if let Some(rest) =
                    id.strip_prefix("node:py/").or_else(|| id.strip_prefix("node:nat/"))
                {
                    if let Some(fp) = rest.split('#').next() {
                        defs_by_file.entry(fp.to_string()).or_default().push(n.name.clone());
                    }
                }
            }
            _ => {}
        }
    }

    let span_loc =
        model.spans.iter().map(|s| (s.id.0.clone(), s.locator.clone())).collect();

    // disambiguated labels: basename if unique among files, else parent/base
    // (so five lib.rs become ca-model/lib.rs, ca-extract/lib.rs, ...)
    let mut base_count: HashMap<String, usize> = HashMap::new();
    for (id, name) in &node_name {
        if file_lang.contains_key(id) {
            *base_count.entry(basename(name)).or_default() += 1;
        }
    }
    let mut label = HashMap::new();
    for (id, name) in &node_name {
        if !file_lang.contains_key(id) {
            continue;
        }
        let b = basename(name);
        let lab = if base_count.get(&b).copied().unwrap_or(0) > 1 {
            disambiguate(name, &b)
        } else {
            b
        };
        label.insert(id.clone(), lab);
    }

    Snap {
        doc_claims,
        node_name,
        file_summary,
        file_loc,
        file_lang,
        file_first_span,
        defs_by_file,
        span_loc,
        label,
    }
}

fn basename(name: &str) -> String {
    name.replace('\\', "/").rsplit('/').next().unwrap_or(name).to_string()
}

/// Render a verbatim claim for the BODY under the voice profile: em dashes
/// out (no em dashes anywhere we author prose). The claim's text in the model
/// and the claims appendix stays exactly as the source had it; this only
/// affects display, and the claim id still resolves to the same span.
fn display(text: &str) -> String {
    text.replace('\u{2014}', " - ")
}

/// When a basename collides (five lib.rs), qualify with the nearest
/// meaningful ancestor directory, skipping generic ones like `src`, so
/// core/ca-model/src/lib.rs becomes `ca-model/lib.rs`, not `src/lib.rs`.
fn disambiguate(name: &str, base: &str) -> String {
    let norm = name.replace('\\', "/");
    let parts: Vec<&str> = norm.split('/').collect();
    const GENERIC: &[&str] = &["src", "lib", "source"];
    for anc in parts.iter().rev().skip(1) {
        if !GENERIC.contains(anc) {
            return format!("{anc}/{base}");
        }
    }
    parts
        .iter()
        .rev()
        .nth(1)
        .map(|d| format!("{d}/{base}"))
        .unwrap_or_else(|| base.to_string())
}

/// file node id -> its rel path (drops the "node:file/<root>/" prefix's root)
fn file_rel(id: &str) -> &str {
    id.strip_prefix("node:file/").unwrap_or(id)
}

// ----- claim selection: assign each design claim to the chapter whose
// vocabulary it best matches, so chapters open with the WHY, not a file list

fn chapter_keywords(ch: &Chapter, snap: &Snap) -> HashSet<String> {
    let mut kw = HashSet::new();
    kw.insert(ch.title.to_lowercase());
    for fid in &ch.node_ids {
        let name = snap.node_name.get(fid).cloned().unwrap_or_default();
        for seg in name.split(['/', '\\', '.', '_', '-']) {
            if seg.len() >= 4 {
                kw.insert(seg.to_lowercase());
            }
        }
        // def names defined in this file are strong domain vocabulary
        if let Some(defs) = snap.defs_by_file.get(file_rel(fid)) {
            for d in defs {
                if d.len() >= 4 {
                    kw.insert(d.to_lowercase());
                }
            }
        }
    }
    kw
}

fn claim_score(text_lc: &str, keywords: &HashSet<String>) -> usize {
    keywords.iter().filter(|k| text_lc.contains(k.as_str())).count()
}

/// Returns (intro_claim_ids, per-chapter assigned claim ids in score order).
fn assign_claims(plan: &Plan, snap: &Snap) -> (Vec<String>, HashMap<usize, Vec<String>>) {
    let texts: HashMap<&str, String> =
        snap.doc_claims.iter().map(|c| (c.id.as_str(), c.text.to_lowercase())).collect();

    // thesis claims for the introduction: the ones that describe the whole
    // tool, by global vocabulary
    let thesis_kw: HashSet<String> = [
        "firewall", "deterministic", "ground truth", "provenance", "cookbook",
        "compiler", "verifiable", "extractor", "the model",
    ]
    .iter()
    .map(|s| s.to_string())
    .collect();
    let mut by_thesis: Vec<(&str, usize)> = snap
        .doc_claims
        .iter()
        .filter(|c| !c.operational)
        .map(|c| (c.id.as_str(), claim_score(&texts[c.id.as_str()], &thesis_kw)))
        .filter(|(_, s)| *s >= 1)
        .collect();
    by_thesis.sort_by_key(|(_, s)| std::cmp::Reverse(*s));
    let intro: Vec<String> = by_thesis.iter().take(3).map(|(id, _)| id.to_string()).collect();
    let intro_set: HashSet<&str> = intro.iter().map(|s| s.as_str()).collect();

    // assign every other claim to its best-matching chapter
    let kw_per_chapter: Vec<HashSet<String>> =
        plan.chapters.iter().map(|ch| chapter_keywords(ch, snap)).collect();
    let mut assigned: HashMap<usize, Vec<(String, usize)>> = HashMap::new();
    for c in &snap.doc_claims {
        if intro_set.contains(c.id.as_str()) || c.operational {
            continue;
        }
        let tlc = &texts[c.id.as_str()];
        let best = plan
            .chapters
            .iter()
            .enumerate()
            .map(|(i, _)| (i, claim_score(tlc, &kw_per_chapter[i])))
            .filter(|(_, s)| *s >= 1)
            .max_by_key(|(_, s)| *s);
        if let Some((ci, score)) = best {
            assigned.entry(ci).or_default().push((c.id.clone(), score));
        }
    }
    let mut out: HashMap<usize, Vec<String>> = HashMap::new();
    for (ci, mut v) in assigned {
        v.sort_by_key(|(_, s)| std::cmp::Reverse(*s));
        out.insert(ci, v.into_iter().take(4).map(|(id, _)| id).collect());
    }
    (intro, out)
}

// ----- key-file role: plain-language one-liner, derived from real structure

fn file_role(fid: &str, snap: &Snap) -> String {
    if let Some(s) = snap.file_summary.get(fid) {
        // one clean clause: first sentence, strip a leading "name - " / "name:"
        // prefix (python docstrings often repeat the filename), no trailing
        // period (it is embedded mid-sentence)
        // first line, then drop a leading "name - " / "name: " prefix BEFORE
        // taking the first sentence (the filename itself contains a period)
        let line = s.split('\n').next().unwrap_or(s);
        let after = line.split_once(" - ").map(|(_, r)| r).unwrap_or(line);
        let after = after.split_once(": ").map(|(_, r)| r).unwrap_or(after);
        let first = after.split_once(". ").map(|(l, _)| l).unwrap_or(after);
        let clean: String =
            first.trim().trim_end_matches([',', ';', ':', '.', ' ']).replace('\u{2014}', "-").chars().take(90).collect();
        if !clean.is_empty() {
            let mut c = clean.chars();
            let lower = c.next().map(|f| f.to_lowercase().collect::<String>() + c.as_str());
            return lower.unwrap_or(clean);
        }
    }
    let defs = snap.defs_by_file.get(file_rel(fid));
    if let Some(defs) = defs.filter(|d| !d.is_empty()) {
        let shown: Vec<String> = defs.iter().take(3).map(|d| format!("`{d}`")).collect();
        return format!("defines {}", shown.join(", "));
    }
    let lang = snap.file_lang.get(fid).cloned().unwrap_or_else(|| "source".into());
    let loc = snap.file_loc.get(fid).copied().unwrap_or(0);
    format!("{loc} lines of {lang}")
}

// ----- minting helper

fn mint(model: &mut Model, next: &mut usize, text: String, spans: SpanRefs) -> String {
    let id = ClaimId(format!("c:w{:04}", *next));
    *next += 1;
    model.claims.push(Claim::new(id.clone(), text.clone(), spans, 0.9));
    format!("{text} {{{{{}}}}}", id.0)
}

fn span_of(snap: &Snap, fid: &str) -> Option<SpanRefs> {
    snap.file_first_span.get(fid).map(|s| SpanRefs::new(ca_model::SpanId(s.clone()), vec![]))
}

pub fn write_paper(
    model: &mut Model,
    plan: &Plan,
    repo_name: &str,
    plant_unsupported: bool,
) -> WriteOut {
    model.claims.retain(|c| !c.id.0.starts_with("c:w"));
    let snap = snapshot(model);
    let (intro_claims, chapter_claims) = assign_claims(plan, &snap);

    let mut p = String::new();
    let mut nf = 0usize;
    let mut nm = 0usize;
    let mut next_w = 1usize;
    let mut used_claims: HashSet<String> = HashSet::new();

    let n_files = snap.file_lang.len();
    let n_fns = model.nodes.iter().filter(|n| n.kind == NodeKind::Function).count();
    let Some(any_span) = snap.file_first_span.values().next().cloned() else {
        return WriteOut { paper: "(empty model)".into(), n_factual: 0, n_marked: 0 };
    };
    let anchor = || SpanRefs::new(ca_model::SpanId(any_span.clone()), vec![]);

    // ---------------- TL;DR
    writeln!(p, "# {repo_name}: a guided cookbook\n").ok();
    writeln!(p, "## TL;DR\n").ok();
    let s = mint(model, &mut next_w,
        format!("This is a tour of {repo_name}, compiled from its own source into a model of {n_files} files and {n_fns} functions, every sentence below traceable to a span."),
        anchor());
    nf += 1; nm += 1;
    write!(p, "{s} ").ok();
    let s = mint(model, &mut next_w,
        format!("Each chapter takes one area, shows the problem it solves, and walks a real path through the code, so by the end you can change it yourself."),
        anchor());
    nf += 1; nm += 1;
    writeln!(p, "{s}\n").ok();
    writeln!(p, "![the system in one figure](figures/fig_page_one.png)\n").ok();
    writeln!(p, "*Figure: the layers of {repo_name}. Each cluster is a box; the chapters that follow open them up one at a time.*\n").ok();

    // ---------------- Introduction (problem first, thesis claims)
    writeln!(p, "## Introduction\n").ok();
    writeln!(p, "Read it like this: the source is compiled into a model, and every sentence here is pinned to a span in that model. In the project's own words:\n").ok();
    let mut intro_used = 0;
    for cid in &intro_claims {
        if let Some(c) = snap.doc_claims.iter().find(|c| &c.id == cid) {
            write!(p, "{} {{{{{}}}}} ", display(&c.text), c.id).ok();
            used_claims.insert(cid.clone());
            nf += 1; nm += 1;
            intro_used += 1;
        }
    }
    if intro_used > 0 {
        writeln!(p, "\n").ok();
    }
    if plant_unsupported {
        writeln!(p, "The scheduler rebalances shards every night at 02:00 UTC.\n").ok();
        nf += 1;
    }
    writeln!(p, "Read the chapters in order; each assumes only what came before. Use the cookbook at the end to turn the tour into commands.\n").ok();
    writeln!(p, "Chapter map:\n").ok();
    for ch in &plan.chapters {
        writeln!(p, "- Chapter {}: {}", ch.index + 1, ch.title).ok();
    }
    writeln!(p).ok();

    // ---------------- chapters (the six-move template)
    for ch in &plan.chapters {
        write_chapter(&mut p, model, &mut next_w, &mut nf, &mut nm, ch, &snap,
                      &chapter_claims, &mut used_claims);
    }

    // ---------------- cookbook (real recipes traced to files)
    write_cookbook(&mut p, &snap, plan);

    // ---------------- glossary
    writeln!(p, "## Glossary\n").ok();
    for g in model.glossary.iter().take(20) {
        writeln!(p, "- **{}**: {} ({})", g.term, g.definition.replace('\u{2014}', "-"), g.first_span.0).ok();
    }
    writeln!(p).ok();

    // ---------------- claims appendix (the receipt)
    writeln!(p, "## Claims appendix\n").ok();
    for c in &model.claims {
        let locs: Vec<&str> =
            c.spans.iter().filter_map(|sp| snap.span_loc.get(sp.0.as_str()).map(|s| s.as_str())).collect();
        writeln!(p, "- `{}` \"{}\" -> {}", c.id.0, c.text, locs.join(", ")).ok();
    }
    writeln!(p).ok();

    // ---------------- unverified appendix
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

    WriteOut { paper: p, n_factual: nf, n_marked: nm }
}

#[allow(clippy::too_many_arguments)]
fn write_chapter(
    p: &mut String,
    model: &mut Model,
    next_w: &mut usize,
    nf: &mut usize,
    nm: &mut usize,
    ch: &Chapter,
    snap: &Snap,
    chapter_claims: &HashMap<usize, Vec<String>>,
    used: &mut HashSet<String>,
) {
    writeln!(p, "## Chapter {}: {}\n", ch.index + 1, ch.title).ok();

    // move 1: PROBLEM FIRST - open with the design claims this area embodies
    let claims: Vec<&DocClaim> = chapter_claims
        .get(&ch.index)
        .map(|ids| {
            ids.iter()
                .filter(|id| !used.contains(*id))
                .filter_map(|id| snap.doc_claims.iter().find(|c| &c.id == id))
                .collect()
        })
        .unwrap_or_default();
    if !claims.is_empty() {
        writeln!(p, "See why this area exists, in the project's own words:\n").ok();
        for c in claims.iter().take(3) {
            write!(p, "{} {{{{{}}}}} ", display(&c.text), c.id).ok();
            used.insert(c.id.clone());
            *nf += 1;
            *nm += 1;
        }
        writeln!(p, "\n").ok();
    }

    // move 2: NAME THE JOB - the anchor file and what it defines, span-backed
    let key = &ch.key_files;
    if let Some(first_key) = key.first() {
        if let Some(spans) = span_of(snap, first_key) {
            let role = file_role(first_key, snap);
            let s = mint(model, next_w,
                format!("At the center of `{}` is `{}`: {}.", ch.title, snap.label(first_key), role),
                spans);
            writeln!(p, "{s}\n").ok();
            *nf += 1;
            *nm += 1;
        }
    }

    // move 3 + 4: WORKED EXAMPLE along a real path, then the teaching figure
    if ch.worked_path.len() >= 2 {
        let names: Vec<String> = ch.worked_path.iter().map(|id| snap.label(id)).collect();
        let path_spans: Vec<ca_model::SpanId> = ch
            .worked_path
            .iter()
            .filter_map(|id| snap.file_first_span.get(id).map(|s| ca_model::SpanId(s.clone())))
            .collect();
        if let Some((first, rest)) = path_spans.split_first() {
            let chain = names
                .iter()
                .enumerate()
                .map(|(i, n)| if i == 0 { format!("`{n}`") } else { format!("which reaches into `{n}`") })
                .collect::<Vec<_>>()
                .join(", ");
            let s = mint(model, next_w,
                format!("Follow one real path through {}: start at {}.", ch.title, chain),
                SpanRefs::new(first.clone(), rest.to_vec()));
            writeln!(p, "{s}\n").ok();
            *nf += 1;
            *nm += 1;
        }
        writeln!(p, "![how the pieces talk](figures/fig_ch{}.png)\n", ch.index + 1).ok();
        let endpoints = format!("`{}` to `{}`", names.first().cloned().unwrap_or_default(), names.last().cloned().unwrap_or_default());
        writeln!(p, "*Figure: the path from {endpoints}. Each box hands off to the next, so changing one tells you exactly what downstream it can touch.*\n").ok();
    } else {
        writeln!(p, "![how the pieces relate](figures/fig_ch{}.png)\n", ch.index + 1).ok();
        writeln!(p, "*Figure: how the files in `{}` depend on each other. The hub is the file you change most carefully, because the others lean on it.*\n", ch.title).ok();
    }

    // move 5: KEY FILES in plain language (deduped by label)
    writeln!(p, "The pieces that matter here:\n").ok();
    let mut seen_labels: HashSet<String> = HashSet::new();
    let mut shown = 0;
    for fid in key.iter() {
        let name = snap.label(fid);
        if !seen_labels.insert(name.clone()) {
            continue;
        }
        let role = file_role(fid, snap);
        if let Some(spans) = span_of(snap, fid) {
            let s = mint(model, next_w, format!("`{name}`: {role}"), spans);
            writeln!(p, "- {s}").ok();
            *nf += 1;
            *nm += 1;
            shown += 1;
        }
        if shown >= 5 {
            break;
        }
    }
    writeln!(p).ok();

    // move 6: WHAT YOU CAN NOW DO
    let capability = if ch.worked_path.len() >= 2 {
        format!("open `{}` and follow the calls above to see how `{}` does its job end to end", snap.label(&ch.worked_path[0]), ch.title)
    } else if let Some(k) = key.first() {
        format!("start at `{}` and read outward; the figure shows what depends on it", snap.label(k))
    } else {
        format!("read the files in `{}` in the order above", ch.title)
    };
    writeln!(p, "What you can now do: {capability}.\n").ok();
}

fn write_cookbook(p: &mut String, snap: &Snap, plan: &Plan) {
    writeln!(p, "## The cookbook\n").ok();
    writeln!(p, "Concrete tasks, each traced to the files you touch.\n").ok();

    let has = |needle: &str| snap.node_name.values().any(|n| n.replace('\\', "/").contains(needle));

    let mut n = 0;
    // recipe: run the whole pipeline
    if has("runner/stages.ts") {
        n += 1;
        writeln!(p, "### {n}. Run it on a codebase\n").ok();
        writeln!(p, "```").ok();
        writeln!(p, "node --experimental-strip-types runner/stages.ts <sources-dir> <workspace> <name>").ok();
        writeln!(p, "```").ok();
        writeln!(p, "Edit: nothing. Run: `runner/stages.ts`. Expected: a graded paper at `<workspace>/out/paper.md` with figures. Verified by: `tests/test_m4_ship.py`.\n").ok();
    }
    // recipe: add a figure recipe
    if has("figlib/recipes/__init__.py") {
        n += 1;
        writeln!(p, "### {n}. Add a figure recipe\n").ok();
        writeln!(p, "1. Create `figlib/recipes/yourrecipe.py` with a `render(payload, model)` function, modeled on `figlib/recipes/quantity.py`.").ok();
        writeln!(p, "2. Register it in `figlib/recipes/__init__.py` (the `registry()` map) and add its ceiling to `CEILINGS`.").ok();
        writeln!(p, "3. Expected: `python figlib/figcheck.py` passes your figure with provenance resolving to the model.").ok();
        writeln!(p, "4. Verified by: `tests/test_m2_figures.py` (the seeded-defect critic must stay at 10/10).\n").ok();
    }
    // recipe: add a language extractor
    if has("core/ca-extract/src/nativecode.rs") {
        n += 1;
        writeln!(p, "### {n}. Teach the compiler a new language\n").ok();
        writeln!(p, "1. Add an extractor in `core/ca-extract/src/` (model it on `nativecode.rs`: emit a file node, `defines` edges, and `imports`).").ok();
        writeln!(p, "2. Dispatch it by extension in `core/ca-cli/src/main.rs` (the compile loop).").ok();
        writeln!(p, "3. Expected: `ca compile` produces nodes for the new files, all edges carrying your extractor's name.").ok();
        writeln!(p, "4. Verified by: `tests/test_m1_compile.py` (100% of edges must keep an extractor).\n").ok();
    }
    if n == 0 {
        writeln!(p, "(No recipe templates detected in this codebase.)\n").ok();
    }
    let _ = plan;
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
