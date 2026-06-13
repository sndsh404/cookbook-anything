//! ca: the core CLI the runner invokes. Subcommands map to stages.
//!
//!   ca intake <sources_dir> <cookbook_dir>
//!   ca compile <cookbook_dir>
//!   ca topology <cookbook_dir>
//!   ca validate <model.json>
//!   ca grade <workspace_dir>

mod admit;
mod plan;
mod verify;
mod write;

use ca_extract::{intake::intake, ExtractOut};
use ca_model::{GlossaryEntry, Model, NodeKind};
use std::collections::BTreeMap;
use std::io::Write;
use std::path::{Path, PathBuf};
use std::process::ExitCode;

fn main() -> ExitCode {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let usage = "usage: ca <intake|compile|topology|plan|write|verify|validate|grade> <paths...>";
    match args.first().map(String::as_str) {
        Some("intake") if args.len() == 3 => cmd_intake(&args[1], &args[2]),
        Some("compile") if args.len() == 2 => cmd_compile(&args[1]),
        Some("topology") if args.len() == 2 => cmd_topology(&args[1]),
        Some("plan") if args.len() == 2 => cmd_plan(&args[1]),
        Some("write") if args.len() >= 4 => cmd_write(&args[1], &args[2], &args[3], &args[4..]),
        Some("verify") if args.len() == 3 => cmd_verify(&args[1], &args[2]),
        Some("validate") if args.len() == 2 => cmd_validate(&args[1]),
        Some("admit") if args.len() == 3 => cmd_admit(&args[1], &args[2]),
        Some("grade") if args.len() == 2 => cmd_grade(&args[1]),
        _ => {
            eprintln!("{usage}");
            ExitCode::from(2)
        }
    }
}

fn cmd_admit(cookbook: &str, findings_path: &str) -> ExitCode {
    let cb = PathBuf::from(cookbook);
    let mut model = match Model::load(&cb.join("model.json")) {
        Ok(m) => m,
        Err(e) => {
            eprintln!("admit: {e}");
            return ExitCode::FAILURE;
        }
    };
    let file: admit::FindingsFile = match std::fs::read_to_string(findings_path)
        .map_err(|e| e.to_string())
        .and_then(|t| serde_json::from_str(&t).map_err(|e| e.to_string()))
    {
        Ok(f) => f,
        Err(e) => {
            eprintln!("admit: cannot read findings: {e}");
            return ExitCode::FAILURE;
        }
    };
    let rep = admit::admit(&mut model, file);
    let errors = model.validate();
    if !errors.is_empty() {
        eprintln!("admit: model invalid after admission, refusing to save: {errors:?}");
        return ExitCode::FAILURE;
    }
    if let Err(e) = model.save(&cb.join("model.json")) {
        eprintln!("admit: save failed: {e}");
        return ExitCode::FAILURE;
    }
    if let Ok(mut runs) =
        std::fs::OpenOptions::new().create(true).append(true).open(cb.join("runs.jsonl"))
    {
        let _ = writeln!(
            runs,
            "{}",
            serde_json::json!({"at": ca_extract::intake::now_iso(), "stage": "admit",
                "admitted": rep.admitted, "supported": rep.supported,
                "contradictions": rep.contradictions, "rejected": rep.rejected.len(),
                "events": rep.events})
        );
    }
    for r in &rep.rejected {
        println!("  REJECTED {r}");
    }
    println!(
        "{}",
        serde_json::json!({"admitted": rep.admitted, "supported": rep.supported,
            "contradictions": rep.contradictions, "rejected": rep.rejected.len()})
    );
    ExitCode::SUCCESS
}

fn cmd_plan(cookbook: &str) -> ExitCode {
    let cb = PathBuf::from(cookbook);
    match Model::load(&cb.join("model.json")) {
        Ok(model) => {
            let topo = ca_topology::analyze(&model);
            let p = plan::build_plan(&model, &topo);
            std::fs::write(cb.join("plan.json"), serde_json::to_string_pretty(&p).unwrap()).ok();
            println!(
                "[Stage 3/7] plan: {} chapters, {} forward deps dropped (graph acyclic by construction)",
                p.chapters.len(),
                p.forward_deps_dropped
            );
            ExitCode::SUCCESS
        }
        Err(e) => {
            eprintln!("plan: {e}");
            ExitCode::FAILURE
        }
    }
}

fn cmd_write(cookbook: &str, workspace: &str, repo_name: &str, flags: &[String]) -> ExitCode {
    let cb = PathBuf::from(cookbook);
    let ws = PathBuf::from(workspace);
    let plant = flags.iter().any(|f| f == "--plant-unsupported");
    let ship = flags.iter().any(|f| f == "--ship");
    let mut model = match Model::load(&cb.join("model.json")) {
        Ok(m) => m,
        Err(e) => {
            eprintln!("write: {e}");
            return ExitCode::FAILURE;
        }
    };
    let plan_json = std::fs::read_to_string(cb.join("plan.json")).unwrap_or_default();
    let p: serde_json::Value = serde_json::from_str(&plan_json).unwrap_or_default();
    // rebuild the Plan from json (only the fields the writer needs)
    let chapters = p["chapters"]
        .as_array()
        .map(|a| {
            a.iter()
                .map(|c| plan::Chapter {
                    index: c["index"].as_u64().unwrap_or(0) as usize,
                    title: c["title"].as_str().unwrap_or("").to_string(),
                    cluster: c["cluster"].as_str().unwrap_or("").to_string(),
                    node_ids: c["node_ids"]
                        .as_array()
                        .map(|v| v.iter().filter_map(|x| x.as_str().map(String::from)).collect())
                        .unwrap_or_default(),
                    figure: plan::FigurePlan {
                        recipe: c["figure"]["recipe"].as_str().unwrap_or("").to_string(),
                        why: c["figure"]["why"].as_str().unwrap_or("").to_string(),
                    },
                    prereqs: vec![],
                })
                .collect::<Vec<_>>()
        })
        .unwrap_or_default();
    let plan = plan::Plan {
        page_one: plan::FigurePlan { recipe: "architecture_box".into(), why: String::new() },
        chapters,
        forward_deps_dropped: 0,
    };

    let out = write::write_paper(&mut model, &plan, repo_name, plant);
    let cov = write::coverage_json(&out);
    if let Err(e) = write::save(&ws, &out.paper, &cov) {
        eprintln!("write: {e}");
        return ExitCode::FAILURE;
    }
    // derived claims were minted into the model; persist them (audit trail)
    model.save(&cb.join("model.json")).ok();
    if let Ok(mut runs) = std::fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open(cb.join("runs.jsonl"))
    {
        let _ = writeln!(
            runs,
            "{}",
            serde_json::json!({"at": ca_extract::intake::now_iso(), "stage": "write",
                   "factual": out.n_factual, "marked": out.n_marked, "planted": plant})
        );
    }
    if ship {
        let shipped = write::strip_markers(&out.paper);
        std::fs::write(ws.join("out").join("paper.md"), shipped).ok();
    }
    println!(
        "[Stage 4/7] write: {} factual sentences, {} marked ({})",
        out.n_factual,
        out.n_marked,
        cov
    );
    ExitCode::SUCCESS
}

fn cmd_verify(cookbook: &str, workspace: &str) -> ExitCode {
    let cb = PathBuf::from(cookbook);
    let ws = PathBuf::from(workspace);
    let model = match Model::load(&cb.join("model.json")) {
        Ok(m) => m,
        Err(e) => {
            eprintln!("verify: {e}");
            return ExitCode::FAILURE;
        }
    };
    let draft = match std::fs::read_to_string(ws.join("out").join("paper.draft.md")) {
        Ok(d) => d,
        Err(e) => {
            eprintln!("verify: no draft: {e}");
            return ExitCode::FAILURE;
        }
    };
    let report = verify::verify(&model, &draft);
    std::fs::create_dir_all(ws.join("out")).ok();
    std::fs::write(
        ws.join("out").join("verify_report.json"),
        serde_json::to_string_pretty(&report).unwrap(),
    )
    .ok();
    println!(
        "[Stage 4/7] verify: coverage {}% ({} marked, {} unsupported, {} broken markers)",
        report.coverage_pct, report.n_marked, report.n_unsupported,
        report.broken_markers.len()
    );
    for b in &report.broken_markers {
        println!("  BROKEN {b}");
    }
    for u in report.unsupported_sentences.iter().take(5) {
        println!("  UNSUPPORTED {u}");
    }
    if report.coverage_pct < 95.0 || !report.broken_markers.is_empty() {
        ExitCode::FAILURE
    } else {
        ExitCode::SUCCESS
    }
}

fn cmd_intake(sources: &str, cookbook: &str) -> ExitCode {
    match intake(Path::new(sources), Path::new(cookbook)) {
        Ok(stats) => {
            println!(
                "{}",
                serde_json::json!({"parsed": stats.parsed, "skipped": stats.skipped,
                       "redactions": stats.redactions, "n_sources": stats.n_sources,
                       "n_spans": stats.n_spans, "files_reparsed": stats.files_reparsed})
            );
            ExitCode::SUCCESS
        }
        Err(e) => {
            eprintln!("intake failed: {e}");
            ExitCode::FAILURE
        }
    }
}

fn cmd_compile(cookbook: &str) -> ExitCode {
    let cb = PathBuf::from(cookbook);
    let manifest: serde_json::Value = match std::fs::read_to_string(cb.join("manifest.json"))
        .map_err(|e| e.to_string())
        .and_then(|t| serde_json::from_str(&t).map_err(|e| e.to_string()))
    {
        Ok(v) => v,
        Err(e) => {
            eprintln!("compile: cannot read manifest: {e}");
            return ExitCode::FAILURE;
        }
    };
    let sources: Vec<ca_model::SourceRec> =
        serde_json::from_value(manifest["sources"].clone()).unwrap_or_default();
    let spans_text = std::fs::read_to_string(cb.join("spans.jsonl")).unwrap_or_default();
    let file_spans: Vec<ca_model::Span> =
        spans_text.lines().filter_map(|l| serde_json::from_str(l).ok()).collect();

    println!("[Stage 2/7] compile: {} sources, {} file spans", sources.len(), file_spans.len());

    let mut out = ExtractOut::new();
    let mut import_maps: BTreeMap<String, BTreeMap<String, ca_model::NodeId>> = BTreeMap::new();

    for src in &sources {
        let root = &src.path;
        let mut imap = BTreeMap::new();
        for fs in file_spans.iter().filter(|s| s.source == src.id) {
            let loc = fs.locator.replace('\\', "/").to_lowercase();
            if loc.ends_with(".py") {
                imap.extend(ca_extract::python::extract(fs, root, &mut out));
            } else if loc.ends_with(".md") || loc.ends_with(".rst") || loc.ends_with(".txt") || src.kind == "pdf" {
                ca_extract::markdown::extract(fs, root, &mut out);
            } else if loc.ends_with(".rs") {
                ca_extract::nativecode::extract_rust(fs, root, &mut out);
            } else if loc.ends_with(".ts") || loc.ends_with(".tsx") || loc.ends_with(".mjs") {
                ca_extract::nativecode::extract_ts(fs, root, &mut out);
            } else if loc.ends_with(".csv") {
                ca_extract::data::extract_csv(fs, root, &mut out);
            } else if loc.ends_with(".sql") {
                ca_extract::data::extract_sql(fs, root, &mut out);
            }
        }
        import_maps.insert(root.clone(), imap);
    }

    // relink import edges to in-repo files where the dotted path resolves.
    // bare-module imports (e.g. `from render import x` when render.py is on
    // sys.path) only relink when the basename is UNAMBIGUOUS across the repo;
    // an ambiguous basename is left as an external module node rather than
    // risk a false file->file arrow (the firewall prefers a missing edge to
    // a wrong one).
    let mut relinked = 0usize;
    for src in &sources {
        if let Some(imap) = import_maps.get(&src.path) {
            let mut basename: BTreeMap<&str, Option<&ca_model::NodeId>> = BTreeMap::new();
            for (dotted, fid) in imap {
                let base = dotted.rsplit('.').next().unwrap_or(dotted);
                basename
                    .entry(base)
                    .and_modify(|v| *v = None) // collision: poison it
                    .or_insert(Some(fid));
            }
            for e in out.edges.iter_mut() {
                // both imports (A depends on B) and calls (A invokes into B)
                // relink module targets to in-repo files
                if e.kind() == ca_model::EdgeKind::Imports || e.kind() == ca_model::EdgeKind::Calls {
                    if let Some(dotted) = e.target().0.strip_prefix("node:mod/") {
                        let hit = imap
                            .get(dotted)
                            .or_else(|| imap.get(&format!("{dotted}.__init__")))
                            .or_else(|| basename.get(dotted).copied().flatten())
                            .cloned();
                        if let Some(t) = hit {
                            if &t != e.source() {
                                e.retarget(t);
                                relinked += 1;
                            }
                        }
                    }
                }
            }
        }
    }

    // deterministic glossary from class docstrings
    let mut seen: std::collections::HashSet<String> =
        out.glossary.iter().map(|g| g.term.to_lowercase()).collect();
    let class_entries: Vec<GlossaryEntry> = out
        .nodes
        .iter()
        .filter(|n| n.kind == NodeKind::Class && !n.summary.is_empty() && !n.name.contains('.'))
        .filter(|n| seen.insert(n.name.to_lowercase()))
        .filter_map(|n| {
            n.spans.first().map(|sp| GlossaryEntry {
                term: n.name.clone(),
                definition: n.summary.chars().take(300).collect(),
                first_span: sp.clone(),
            })
        })
        .collect();
    out.glossary.extend(class_entries);

    let mut model = Model {
        sources,
        spans: {
            let mut all = file_spans.clone();
            all.extend(out.spans);
            all
        },
        nodes: out.nodes,
        edges: out.edges,
        claims: out.claims,
        tours: vec![],
        glossary: out.glossary,
        assets: vec![],
    };

    let report = ca_merge::merge(&mut model);

    // ---- supersession (hard rule 3): a re-run that contradicts an existing
    // claim marks the old one superseded and links the new one to it; old
    // claims are carried forward, never deleted. Matched by span locator.
    let prev_model = Model::load(&cb.join("model.json")).ok();
    let mut claim_events: Vec<serde_json::Value> = Vec::new();
    if let Some(prev) = prev_model {
        let new_loc: std::collections::HashMap<String, String> =
            model.spans.iter().map(|s| (s.id.0.clone(), s.locator.clone())).collect();
        let prev_loc: std::collections::HashMap<String, String> =
            prev.spans.iter().map(|s| (s.id.0.clone(), s.locator.clone())).collect();
        let prev_max: usize = prev
            .claims
            .iter()
            .filter_map(|c| c.id.0.strip_prefix("c:").and_then(|n| n.parse().ok()))
            .max()
            .unwrap_or(0);
        // active prev doc-claims by locator of their first span
        let mut prev_by_locator: std::collections::HashMap<String, ca_model::Claim> =
            std::collections::HashMap::new();
        for c in prev.claims.iter().filter(|c| {
            c.status == ca_model::ClaimStatus::Active && !c.id.0.starts_with("c:w")
        }) {
            if let Some(loc) = c.spans.iter().next().and_then(|sp| prev_loc.get(sp.0.as_str())) {
                prev_by_locator.insert(loc.clone(), c.clone());
            }
        }
        let mut carried: Vec<ca_model::Claim> =
            prev.claims.iter().filter(|c| !c.id.0.starts_with("c:w")).cloned().collect();
        let carried_ids: std::collections::HashSet<String> =
            carried.iter().map(|c| c.id.0.clone()).collect();
        let mut next_id = prev_max + 1;
        let mut final_claims: Vec<ca_model::Claim> = Vec::new();
        for mut c in std::mem::take(&mut model.claims) {
            let loc = c.spans.iter().next().and_then(|sp| new_loc.get(sp.0.as_str())).cloned();
            match loc.and_then(|l| prev_by_locator.get(&l).cloned()) {
                Some(old) if old.text == c.text => {
                    // unchanged claim: keep the old identity
                    carried.retain(|x| x.id != old.id);
                    let mut kept = old.clone();
                    kept.spans = c.spans.clone();
                    final_claims.push(kept);
                }
                Some(old) => {
                    // contradiction: supersede, link, keep the old one
                    c.id = ca_model::ClaimId(format!("c:{:04}", next_id));
                    next_id += 1;
                    c.supersedes = Some(old.id.clone());
                    claim_events.push(serde_json::json!({
                        "event": "superseded", "new": c.id.0, "old": old.id.0,
                        "new_text": c.text.chars().take(80).collect::<String>()}));
                    carried.retain(|x| x.id != old.id);
                    let mut dead = old.clone();
                    dead.status = ca_model::ClaimStatus::Superseded;
                    final_claims.push(dead);
                    final_claims.push(c);
                }
                None => {
                    if carried_ids.contains(&c.id.0) {
                        // id collision with a carried claim: renumber
                        c.id = ca_model::ClaimId(format!("c:{:04}", next_id));
                        next_id += 1;
                    }
                    claim_events.push(serde_json::json!({"event": "new", "id": c.id.0}));
                    final_claims.push(c);
                }
            }
        }
        // prev claims whose locators vanished from this run: keep superseded
        // ones for the audit trail; drop actives whose spans no longer exist
        let new_span_ids: std::collections::HashSet<&str> =
            model.spans.iter().map(|s| s.id.0.as_str()).collect();
        for old in carried {
            if old.status == ca_model::ClaimStatus::Superseded
                && old.spans.iter().all(|sp| new_span_ids.contains(sp.0.as_str()))
            {
                final_claims.push(old);
            }
        }
        model.claims = final_claims;
    } else {
        for c in &model.claims {
            claim_events.push(serde_json::json!({"event": "new", "id": c.id.0}));
        }
    }

    println!(
        "  extracted: {} nodes, {} edges, {} claims, {} glossary terms ({relinked} imports relinked)",
        model.nodes.len(),
        model.edges.len(),
        model.claims.len(),
        model.glossary.len()
    );
    println!(
        "  Fixed: {}",
        if report.fixed.is_empty() { "nothing to fix".into() } else { report.fixed.join("; ") }
    );
    if !report.could_not_fix.is_empty() {
        println!("  Could not fix:");
        for x in &report.could_not_fix {
            println!("   - {x}");
        }
    }

    if let Err(e) = model.save(&cb.join("model.json")) {
        eprintln!("compile: save failed: {e}");
        return ExitCode::FAILURE;
    }
    if let Ok(mut runs) =
        std::fs::OpenOptions::new().create(true).append(true).open(cb.join("runs.jsonl"))
    {
        let n_superseded = claim_events.iter().filter(|e| e["event"] == "superseded").count();
        let _ = writeln!(
            runs,
            "{}",
            serde_json::json!({"at": ca_extract::intake::now_iso(), "stage": "compile",
                   "nodes": model.nodes.len(), "edges": model.edges.len(),
                   "claims": model.claims.len(), "could_not_fix": report.could_not_fix.len(),
                   "claims_superseded": n_superseded,
                   "claim_events": claim_events.into_iter().take(60).collect::<Vec<_>>()})
        );
    }
    println!(
        "[Stage 2/7] done: model.json written ({} residue items)",
        report.could_not_fix.len()
    );
    if report.could_not_fix.is_empty() { ExitCode::SUCCESS } else { ExitCode::FAILURE }
}

fn cmd_topology(cookbook: &str) -> ExitCode {
    let cb = PathBuf::from(cookbook);
    match Model::load(&cb.join("model.json")) {
        Ok(model) => {
            let topo = ca_topology::analyze(&model);
            let json = serde_json::to_string_pretty(&topo).unwrap();
            std::fs::write(cb.join("topology.json"), &json).ok();
            println!(
                "[Stage 3/7] topology: {} entry points, {} files ordered, {} cycles broken",
                topo.entry_points.len(),
                topo.dependency_order.len(),
                topo.cycles_broken
            );
            ExitCode::SUCCESS
        }
        Err(e) => {
            eprintln!("topology: {e}");
            ExitCode::FAILURE
        }
    }
}

fn cmd_validate(model_path: &str) -> ExitCode {
    match Model::load(Path::new(model_path)) {
        Ok(m) => {
            let errors = m.validate();
            if errors.is_empty() {
                println!("valid: {} nodes, {} edges, {} claims", m.nodes.len(), m.edges.len(), m.claims.len());
                ExitCode::SUCCESS
            } else {
                for e in &errors {
                    eprintln!("invalid: {e}");
                }
                ExitCode::FAILURE
            }
        }
        Err(e) => {
            // type invariants rejected the file at load: that is the firewall working
            eprintln!("rejected: {e}");
            ExitCode::FAILURE
        }
    }
}

fn cmd_grade(workspace: &str) -> ExitCode {
    let g = ca_grade::grade(Path::new(workspace));
    println!("GRADE {}/100 {}", g.score, if g.red { "(RED - does not ship)" } else { "(green)" });
    for f in &g.findings {
        println!("  {:?} [{}] (-{}) {}", f.severity, f.rule, f.deduction, f.text);
    }
    let out_dir = Path::new(workspace).join("out");
    std::fs::create_dir_all(&out_dir).ok();
    std::fs::write(out_dir.join("grade.json"), serde_json::to_string_pretty(&g).unwrap()).ok();
    if g.red { ExitCode::FAILURE } else { ExitCode::SUCCESS }
}
