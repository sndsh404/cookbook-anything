//! ca: the core CLI the runner invokes. Subcommands map to stages.
//!
//!   ca intake <sources_dir> <cookbook_dir>
//!   ca compile <cookbook_dir>
//!   ca topology <cookbook_dir>
//!   ca validate <model.json>
//!   ca grade <workspace_dir>

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
        Some("grade") if args.len() == 2 => cmd_grade(&args[1]),
        _ => {
            eprintln!("{usage}");
            ExitCode::from(2)
        }
    }
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
                       "n_spans": stats.n_spans})
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
            } else if loc.ends_with(".csv") {
                ca_extract::data::extract_csv(fs, root, &mut out);
            } else if loc.ends_with(".sql") {
                ca_extract::data::extract_sql(fs, root, &mut out);
            }
        }
        import_maps.insert(root.clone(), imap);
    }

    // relink import edges to in-repo files where the dotted path resolves
    let mut relinked = 0usize;
    for src in &sources {
        if let Some(imap) = import_maps.get(&src.path) {
            for e in out.edges.iter_mut() {
                if e.kind() == ca_model::EdgeKind::Imports {
                    if let Some(dotted) = e.target().0.strip_prefix("node:mod/") {
                        let hit = imap
                            .get(dotted)
                            .or_else(|| imap.get(&format!("{dotted}.__init__")))
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
        let _ = writeln!(
            runs,
            "{}",
            serde_json::json!({"at": ca_extract::intake::now_iso(), "stage": "compile",
                   "nodes": model.nodes.len(), "edges": model.edges.len(),
                   "claims": model.claims.len(), "could_not_fix": report.could_not_fix.len()})
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
