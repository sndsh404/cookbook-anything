//! Line-based extractors for Rust and TypeScript: a file node plus top-level
//! definitions (defines) plus imports (to module nodes). Narrow-and-true
//! (DESIGN honest seam 2): no cross-file resolution, no call graph, no
//! generics awareness. Enough to place the Rust core and the TS runner on
//! the architecture map honestly instead of omitting them.

use crate::ExtractOut;
use ca_model::{Edge, EdgeKind, ExtractorId, Node, NodeId, NodeKind, Span};
use regex::Regex;
use std::collections::BTreeMap;
use std::sync::OnceLock;

pub const RUST: &str = "ca-extract@rust";
pub const TS: &str = "ca-extract@typescript";

struct Pats {
    rust_def: Regex,
    rust_use: Regex,
    ts_def: Regex,
    ts_import: Regex,
}

fn pats() -> &'static Pats {
    static P: OnceLock<Pats> = OnceLock::new();
    P.get_or_init(|| Pats {
        rust_def: Regex::new(
            r"^\s*(?:pub(?:\([^)]*\))?\s+)?(?:async\s+)?(fn|struct|enum|trait|mod)\s+([A-Za-z_]\w*)",
        )
        .unwrap(),
        rust_use: Regex::new(r"^\s*(?:pub\s+)?use\s+([A-Za-z_][\w:]*)").unwrap(),
        ts_def: Regex::new(
            r"^\s*(?:export\s+)?(?:default\s+)?(?:abstract\s+)?(?:async\s+)?(function|class|interface)\s+([A-Za-z_]\w*)",
        )
        .unwrap(),
        ts_import: Regex::new(r#"^\s*import\b[^;]*?\bfrom\s+["']([^"']+)["']"#).unwrap(),
    })
}

fn kind_for(keyword: &str) -> NodeKind {
    match keyword {
        "fn" | "function" => NodeKind::Function,
        "mod" => NodeKind::Module,
        _ => NodeKind::Class, // struct/enum/trait/class/interface
    }
}

/// Shared body: `def_re` captures (keyword, name); `import_re` captures the
/// imported module path in group 1.
#[allow(clippy::too_many_arguments)]
fn extract_lang(
    file_span: &Span,
    src_root: &str,
    out: &mut ExtractOut,
    lang: &str,
    extractor: &str,
    def_re: &Regex,
    import_re: &Regex,
    doc_prefix: &str,
    module_of: &dyn Fn(&str) -> Option<String>,
) -> BTreeMap<String, NodeId> {
    let rel = file_span.locator.replace('\\', "/");
    let lines: Vec<&str> = file_span.text.lines().collect();
    let ex = ExtractorId::new(extractor).unwrap();
    let file_id = NodeId(format!("node:file/{src_root}/{rel}"));
    out.nodes.push(Node {
        id: file_id.clone(),
        kind: NodeKind::File,
        name: rel.clone(),
        summary: String::new(),
        attrs: serde_json::Map::from_iter([
            ("language".into(), lang.into()),
            ("loc".into(), serde_json::Value::from(lines.len())),
        ]),
        spans: vec![file_span.id.clone()],
    });

    let mut pending_doc = String::new();
    let mut imports: Vec<String> = Vec::new();

    for (i, raw) in lines.iter().enumerate() {
        let line = *raw;
        // doc comments riding just above a definition become its summary
        let trimmed = line.trim_start();
        if trimmed.starts_with(doc_prefix) {
            let d = trimmed.trim_start_matches(doc_prefix).trim();
            if !d.is_empty() {
                pending_doc = d.to_string();
            }
            continue;
        }

        if let Some(c) = import_re.captures(line) {
            imports.push(c[1].to_string());
            pending_doc.clear();
            continue;
        }

        if let Some(c) = def_re.captures(line) {
            let keyword = &c[1];
            let name = &c[2];
            let prefix = lang.chars().next().unwrap_or('n'); // 'r' rust, 't' ts
            let sid = out.add_span(prefix, file_span.source.clone(),
                                   format!("{rel}#L{}", i + 1), line.trim());
            let nid = NodeId(format!("node:nat/{src_root}/{rel}#{name}"));
            out.nodes.push(Node {
                id: nid.clone(),
                kind: kind_for(keyword),
                name: name.to_string(),
                summary: std::mem::take(&mut pending_doc),
                attrs: serde_json::Map::from_iter([("language".into(), lang.into())]),
                spans: vec![sid.clone()],
            });
            out.edges.push(Edge::extracted(
                file_id.clone(),
                nid,
                EdgeKind::Defines,
                ex.clone(),
                vec![sid],
            ));
            continue;
        }
        pending_doc.clear();
    }

    // imports become module nodes; `module_of` reduces a raw import to the
    // identifier that the relink step (main.rs) matches against in-repo
    // files, so cross-file edges resolve instead of dangling as externals.
    imports.sort();
    imports.dedup();
    for imp in imports {
        let Some(module) = module_of(&imp) else { continue };
        let mid = NodeId(format!("node:mod/{module}"));
        if !out.nodes.iter().any(|n| n.id == mid) {
            out.nodes.push(Node {
                id: mid.clone(),
                kind: NodeKind::Module,
                name: module.clone(),
                summary: String::new(),
                attrs: Default::default(),
                spans: vec![file_span.id.clone()],
            });
        }
        out.edges.push(Edge::extracted(
            file_id.clone(),
            mid,
            EdgeKind::Imports,
            ex.clone(),
            vec![file_span.id.clone()],
        ));
    }

    // this file's identity for relinking: its basename (stem), plus, for a
    // crate root (.../src/lib.rs or main.rs), the crate name with dashes
    // turned to underscores, so `use ca_model::...` resolves to its lib.rs.
    let mut map = BTreeMap::new();
    let parts: Vec<&str> = rel.split('/').collect();
    if let Some(stem) = parts.last().and_then(|f| f.rsplit('.').nth(1)) {
        map.insert(stem.to_string(), file_id.clone());
    }
    if rel.ends_with("/src/lib.rs") || rel.ends_with("/src/main.rs") {
        if let Some(crate_dir) = parts.iter().rev().nth(2) {
            map.insert(crate_dir.replace('-', "_"), file_id.clone());
        }
    }
    map
}

/// Rust: `use crate::plan::X` -> plan; `use ca_model::Model` -> ca_model;
/// `use super::plan` -> plan. Returns the module identifier to match files.
fn rust_module_of(imp: &str) -> Option<String> {
    let segs: Vec<&str> = imp.split("::").collect();
    let first = *segs.first()?;
    let m = if matches!(first, "crate" | "super" | "self") {
        *segs.get(1)?
    } else {
        first
    };
    (!m.is_empty()).then(|| m.to_string())
}

/// TS: `./robots.ts` -> robots; `./swarm/swarm.ts` -> swarm; bare/node
/// specifiers (`node:fs`, `playwright`) reduce to their own stem and simply
/// will not match any in-repo file, staying external.
fn ts_module_of(imp: &str) -> Option<String> {
    let path = imp.trim_start_matches("./").trim_start_matches("../");
    let last = path.rsplit('/').next().unwrap_or(path);
    let stem = last.split('.').next().unwrap_or(last); // strip .ts/.tsx/.mjs
    (!stem.is_empty()).then(|| stem.to_string())
}

pub fn extract_rust(file_span: &Span, src_root: &str, out: &mut ExtractOut) -> BTreeMap<String, NodeId> {
    let p = pats();
    extract_lang(file_span, src_root, out, "rust", RUST, &p.rust_def, &p.rust_use, "///", &rust_module_of)
}

pub fn extract_ts(file_span: &Span, src_root: &str, out: &mut ExtractOut) -> BTreeMap<String, NodeId> {
    let p = pats();
    extract_lang(file_span, src_root, out, "typescript", TS, &p.ts_def, &p.ts_import, "//", &ts_module_of)
}
