//! Line-based extractors for Rust and TypeScript: a file node plus top-level
//! definitions (defines) plus imports (to module nodes). Narrow-and-true
//! (DESIGN honest seam 2): no cross-file resolution, no call graph, no
//! generics awareness. Enough to place the Rust core and the TS runner on
//! the architecture map honestly instead of omitting them.

use crate::ExtractOut;
use ca_model::{Edge, EdgeKind, ExtractorId, Node, NodeId, NodeKind, Span};
use regex::Regex;
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
fn extract_lang(
    file_span: &Span,
    src_root: &str,
    out: &mut ExtractOut,
    lang: &str,
    extractor: &str,
    def_re: &Regex,
    import_re: &Regex,
    doc_prefix: &str,
) {
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

    // imports become module nodes (external-ish; no cross-file relink, the
    // honest narrow scope). First path segment is the module identity.
    imports.sort();
    imports.dedup();
    for imp in imports {
        let module = imp.split(|c| c == '/' || c == ':').next().unwrap_or(&imp);
        let module = module.trim_start_matches("./").trim_start_matches("../");
        if module.is_empty() {
            continue;
        }
        let mid = NodeId(format!("node:mod/{module}"));
        if !out.nodes.iter().any(|n| n.id == mid) {
            out.nodes.push(Node {
                id: mid.clone(),
                kind: NodeKind::Module,
                name: module.to_string(),
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
}

pub fn extract_rust(file_span: &Span, src_root: &str, out: &mut ExtractOut) {
    let p = pats();
    extract_lang(file_span, src_root, out, "rust", RUST, &p.rust_def, &p.rust_use, "///");
}

pub fn extract_ts(file_span: &Span, src_root: &str, out: &mut ExtractOut) {
    let p = pats();
    extract_lang(file_span, src_root, out, "typescript", TS, &p.ts_def, &p.ts_import, "//");
}
