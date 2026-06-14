//! brief + assemble: the writer is split in two so the model can write and
//! the checks can run AFTER, never the writer grading itself.
//!
//!   ca brief    -> emits brief.json: per chapter, a menu of VERIFIED facts
//!                  (each {id, text, span}). Every fact is span-backed; the
//!                  author may only reword and sequence these, never invent.
//!   (author)    -> brief.json into authored.json (prose + per-sentence
//!                  citations). A Claude subagent today, runner/write/author.ts
//!                  against the API later. Same files either way.
//!   ca assemble -> stitches authored.json + the deterministic appendices into
//!                  paper.draft.md (markers) and paper.md (stripped).
//!   ca verify   -> independently scores coverage over the FINISHED prose.
//!
//! Provenance is unchanged: the appendices and the claim/span system are the
//! same. What changed is that the writer no longer fills a fixed template, and
//! no longer certifies its own coverage.

use ca_model::{Claim, ClaimId, Model, NodeKind, SpanRefs};
use serde::{Deserialize, Serialize};
use std::collections::{HashMap, HashSet};
use std::fmt::Write as _;

use crate::plan::{Chapter, Plan};

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

// ===================================================================
// brief: a per-chapter menu of verified facts the author may reword
// ===================================================================

#[derive(Serialize, Deserialize, Clone)]
pub struct Fact {
    pub id: String,
    pub text: String,
    pub locator: String,
}

#[derive(Serialize, Deserialize)]
pub struct ChapterBrief {
    pub index: usize,
    pub title: String,
    pub figure: String,
    pub figure_recipe: String,
    pub path_labels: Vec<String>,
    pub why: Vec<Fact>,
    pub path: Vec<Fact>,
    pub files: Vec<Fact>,
}

#[derive(Serialize, Deserialize)]
pub struct Brief {
    pub repo: String,
    pub n_files: usize,
    pub n_functions: usize,
    pub tldr: Vec<Fact>,
    pub intro: Vec<Fact>,
    pub chapters: Vec<ChapterBrief>,
    pub cookbook_md: String,
    pub glossary_md: String,
    pub claims_appendix_md: String,
    pub unverified_appendix_md: String,
}

/// Mint a derived fact as a real span-backed claim and return it. Same
/// mechanism the old writer used; here the text is a neutral statement the
/// author rewords, and the id is what the author cites.
fn mint_fact(model: &mut Model, next: &mut usize, text: String, span_id: String, locator: String) -> Fact {
    let id = ClaimId(format!("c:w{:04}", *next));
    *next += 1;
    model.claims.push(Claim::new(
        id.clone(),
        text.clone(),
        SpanRefs::new(ca_model::SpanId(span_id), vec![]),
        0.9,
    ));
    Fact { id: id.0, text, locator }
}

fn loc_for_span(snap: &Snap, span_id: &str) -> String {
    snap.span_loc.get(span_id).cloned().unwrap_or_default()
}

pub fn build_brief(model: &mut Model, plan: &Plan, repo: &str) -> Brief {
    // derived facts are regenerated every run; drop stale ones first
    model.claims.retain(|c| !c.id.0.starts_with("c:w"));
    let snap = snapshot(model);
    let (intro_ids, chapter_claim_ids) = assign_claims(plan, &snap);
    let mut next_w = 1usize;

    let doc_fact = |id: &str| -> Option<Fact> {
        snap.doc_claims.iter().find(|c| c.id == id).map(|c| Fact {
            id: c.id.clone(),
            text: c.text.clone(),
            locator: c.spans.first().map(|s| loc_for_span(&snap, s)).unwrap_or_default(),
        })
    };

    let n_files = snap.file_lang.len();
    let n_functions = model.nodes.iter().filter(|n| n.kind == NodeKind::Function).count();

    // tldr facts (minted, anchored to any real span)
    let mut tldr = Vec::new();
    if let Some(any) = snap.file_first_span.values().next().cloned() {
        let loc = loc_for_span(&snap, &any);
        tldr.push(mint_fact(
            model,
            &mut next_w,
            format!("{repo} compiles to a model of {n_files} files and {n_functions} functions, and every fact in this tour resolves to a source span"),
            any,
            loc,
        ));
    }

    let intro: Vec<Fact> = intro_ids.iter().filter_map(|id| doc_fact(id)).collect();

    let mut chapters = Vec::new();
    for ch in &plan.chapters {
        let why: Vec<Fact> = chapter_claim_ids
            .get(&ch.index)
            .map(|ids| ids.iter().filter_map(|id| doc_fact(id)).collect())
            .unwrap_or_default();

        let path_labels: Vec<String> = ch.worked_path.iter().map(|id| snap.label(id)).collect();
        let mut path = Vec::new();
        for w in ch.worked_path.windows(2) {
            let (a, b) = (&w[0], &w[1]);
            if let Some(sp) = snap.file_first_span.get(a).cloned() {
                let loc = loc_for_span(&snap, &sp);
                let (la, lb) = (snap.label(a), snap.label(b));
                path.push(mint_fact(model, &mut next_w, format!("`{la}` calls into `{lb}`"), sp, loc));
            }
        }

        let mut files = Vec::new();
        let mut seen = HashSet::new();
        for fid in &ch.key_files {
            let label = snap.label(fid);
            if !seen.insert(label.clone()) {
                continue;
            }
            if let Some(sp) = snap.file_first_span.get(fid).cloned() {
                let loc = loc_for_span(&snap, &sp);
                let role = file_role(fid, &snap);
                files.push(mint_fact(model, &mut next_w, format!("`{label}`: {role}"), sp, loc));
            }
            if files.len() >= 5 {
                break;
            }
        }

        chapters.push(ChapterBrief {
            index: ch.index,
            title: ch.title.clone(),
            figure: format!("fig_ch{}.png", ch.index + 1),
            figure_recipe: ch.figure.recipe.clone(),
            path_labels,
            why,
            path,
            files,
        });
    }

    let cookbook_md = cookbook_md(&snap, plan);
    let glossary_md = glossary_md(model);
    let claims_appendix_md = claims_appendix_md(model, &snap);
    let unverified_appendix_md = unverified_appendix_md(model);

    Brief {
        repo: repo.to_string(),
        n_files,
        n_functions,
        tldr,
        intro,
        chapters,
        cookbook_md,
        glossary_md,
        claims_appendix_md,
        unverified_appendix_md,
    }
}

// ----- the deterministic tail (appendices, glossary, cookbook) -----

fn cookbook_md(snap: &Snap, _plan: &Plan) -> String {
    let mut p = String::new();
    writeln!(p, "## The cookbook\n").ok();
    writeln!(p, "Concrete tasks, each traced to the files you touch.\n").ok();
    let has = |needle: &str| snap.node_name.values().any(|n| n.replace('\\', "/").contains(needle));
    let mut n = 0;
    if has("runner/stages.ts") {
        n += 1;
        writeln!(p, "### {n}. Run it on a codebase\n").ok();
        writeln!(p, "```").ok();
        writeln!(p, "node --experimental-strip-types runner/stages.ts <sources-dir> <workspace> <name>").ok();
        writeln!(p, "```").ok();
        writeln!(p, "Edit: nothing. Run: `runner/stages.ts`. Expected: a graded paper at `<workspace>/out/paper.md` with figures. Verified by: `tests/test_m4_ship.py`.\n").ok();
    }
    if has("figlib/recipes/__init__.py") {
        n += 1;
        writeln!(p, "### {n}. Add a figure recipe\n").ok();
        writeln!(p, "1. Create `figlib/recipes/yourrecipe.py` with a `render(payload, model)` function, modeled on `figlib/recipes/quantity.py`.").ok();
        writeln!(p, "2. Register it in `figlib/recipes/__init__.py` (the `registry()` map) and add its ceiling to `CEILINGS`.").ok();
        writeln!(p, "3. Expected: `python figlib/figcheck.py` passes your figure with provenance resolving to the model.").ok();
        writeln!(p, "4. Verified by: `tests/test_m2_figures.py` (the seeded-defect critic must stay at 10/10).\n").ok();
    }
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
    p
}

fn glossary_md(model: &Model) -> String {
    let mut p = String::new();
    writeln!(p, "## Glossary\n").ok();
    for g in model.glossary.iter().take(20) {
        writeln!(p, "- **{}**: {} ({})", g.term, g.definition.replace('\u{2014}', "-"), g.first_span.0).ok();
    }
    writeln!(p).ok();
    p
}

fn claims_appendix_md(model: &Model, snap: &Snap) -> String {
    let mut p = String::new();
    writeln!(p, "## Claims appendix\n").ok();
    for c in &model.claims {
        let locs: Vec<&str> = c
            .spans
            .iter()
            .filter_map(|sp| snap.span_loc.get(sp.0.as_str()).map(|s| s.as_str()))
            .collect();
        writeln!(p, "- `{}` \"{}\" -> {}", c.id.0, c.text, locs.join(", ")).ok();
    }
    writeln!(p).ok();
    p
}

fn unverified_appendix_md(model: &Model) -> String {
    let mut p = String::new();
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
    writeln!(p).ok();
    p
}

// ===================================================================
// assemble: stitch authored prose + the deterministic tail into a paper
// ===================================================================

#[derive(Deserialize)]
pub struct AuthoredChapter {
    pub index: usize,
    pub markdown: String,
}

#[derive(Deserialize)]
pub struct Authored {
    pub tldr: String,
    pub page_one_caption: String,
    pub intro: String,
    pub chapters: Vec<AuthoredChapter>,
}

pub fn assemble(brief: &Brief, authored: &Authored) -> String {
    let repo = &brief.repo;
    let mut p = String::new();
    writeln!(p, "# {repo}: a guided cookbook\n").ok();
    writeln!(p, "## TL;DR\n").ok();
    writeln!(p, "{}\n", authored.tldr.trim()).ok();
    writeln!(p, "![the system in one figure](figures/fig_page_one.png)\n").ok();
    writeln!(p, "*Figure: {}*\n", authored.page_one_caption.trim()).ok();

    writeln!(p, "## Introduction\n").ok();
    writeln!(p, "{}\n", authored.intro.trim()).ok();
    writeln!(p, "Chapter map:\n").ok();
    for ch in &brief.chapters {
        writeln!(p, "- Chapter {}: {}", ch.index + 1, ch.title).ok();
    }
    writeln!(p).ok();

    for ch in &brief.chapters {
        writeln!(p, "## Chapter {}: {}\n", ch.index + 1, ch.title).ok();
        if let Some(a) = authored.chapters.iter().find(|c| c.index == ch.index) {
            writeln!(p, "{}\n", a.markdown.trim()).ok();
        } else {
            writeln!(p, "(chapter not authored)\n").ok();
        }
    }

    p.push_str(&brief.cookbook_md);
    p.push_str(&brief.glossary_md);
    p.push_str(&brief.claims_appendix_md);
    p.push_str(&brief.unverified_appendix_md);
    p
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
