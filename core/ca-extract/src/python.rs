//! Line-based Python structure extractor: defines/contains/imports always,
//! same-file calls between top-level functions only. Narrow-and-true over
//! broad-and-flaky (DESIGN honest seam 2): no cross-file call resolution.

use crate::ExtractOut;
use ca_model::{Edge, EdgeKind, ExtractorId, Node, NodeId, NodeKind, Span};
use regex::Regex;
use std::collections::BTreeMap;
use std::sync::OnceLock;

pub const EXTRACTOR: &str = "ca-extract@python";

struct Res {
    def: Regex,
    import_plain: Regex,
    import_from: Regex,
    from_names: Regex,
}

fn res() -> &'static Res {
    static R: OnceLock<Res> = OnceLock::new();
    R.get_or_init(|| Res {
        def: Regex::new(r"^(\s*)(?:async\s+)?(def|class)\s+(\w+)").unwrap(),
        import_plain: Regex::new(r"^\s*import\s+([\w.]+(?:\s*,\s*[\w.]+)*)").unwrap(),
        import_from: Regex::new(r"^\s*from\s+([\w.]+)\s+import\s").unwrap(),
        // `from MODULE import a, b as c, d` -> module + the imported names
        from_names: Regex::new(r"^\s*from\s+([\w.]+)\s+import\s+(.+)").unwrap(),
    })
}

#[derive(Clone)]
struct Def {
    line: usize, // 0-based
    indent: usize,
    kind: &'static str,
    name: String,
    end: usize,
}

fn find_defs(lines: &[&str]) -> Vec<Def> {
    let re = &res().def;
    let mut defs: Vec<Def> = Vec::new();
    for (i, line) in lines.iter().enumerate() {
        if let Some(c) = re.captures(line) {
            defs.push(Def {
                line: i,
                indent: c[1].len(),
                kind: if &c[2] == "class" { "class" } else { "def" },
                name: c[3].to_string(),
                end: lines.len() - 1,
            });
        }
    }
    // end line: next non-blank, non-comment line at indent <= def indent
    for k in 0..defs.len() {
        for (j, line) in lines.iter().enumerate().skip(defs[k].line + 1) {
            let t = line.trim_start();
            if t.is_empty() || t.starts_with('#') {
                continue;
            }
            let ind = line.len() - t.len();
            if ind <= defs[k].indent {
                defs[k].end = j - 1;
                break;
            }
        }
    }
    defs
}

fn docstring(lines: &[&str], def_line: usize, def_end: usize) -> String {
    // find the header's closing ':' within a few lines, then look for a
    // triple-quoted string right after
    let mut body_start = None;
    for j in def_line..(def_line + 10).min(def_end + 1) {
        if lines[j].trim_end().ends_with(':') {
            body_start = Some(j + 1);
            break;
        }
    }
    let Some(start) = body_start else { return String::new() };
    for j in start..(start + 3).min(def_end + 1) {
        let t = lines[j].trim();
        if t.is_empty() {
            continue;
        }
        for q in ["\"\"\"", "'''"] {
            if let Some(rest) = t.strip_prefix(q).or_else(|| {
                t.strip_prefix('r').and_then(|r| r.strip_prefix(q))
            }) {
                if let Some(one_line) = rest.strip_suffix(q) {
                    return one_line.trim().to_string();
                }
                if !rest.trim().is_empty() {
                    return rest.trim().to_string();
                }
                // content starts on the next line
                for l in lines.iter().take(def_end + 1).skip(j + 1) {
                    let lt = l.trim();
                    if lt.starts_with(q) {
                        return String::new();
                    }
                    if !lt.is_empty() {
                        return lt.trim_end_matches(q).trim().to_string();
                    }
                }
            }
        }
        return String::new(); // first statement is not a docstring
    }
    String::new()
}

/// Returns dotted-module-path -> file node id, for cross-file import linking.
pub fn extract(file_span: &Span, src_root: &str, out: &mut ExtractOut) -> BTreeMap<String, NodeId> {
    let rel = file_span.locator.replace('\\', "/");
    let text = file_span.text.clone();
    let lines: Vec<&str> = text.lines().collect();
    let file_id = NodeId(format!("node:file/{src_root}/{rel}"));
    let ex = ExtractorId::new(EXTRACTOR).unwrap();

    let defs = find_defs(&lines);
    let module_doc = lines
        .first()
        .filter(|l| l.trim_start().starts_with("\"\"\"") || l.trim_start().starts_with("'''"))
        .map(|l| l.trim().trim_matches(|c| c == '"' || c == '\'').trim().to_string())
        .unwrap_or_default();

    out.nodes.push(Node {
        id: file_id.clone(),
        kind: NodeKind::File,
        name: rel.clone(),
        summary: module_doc,
        attrs: serde_json::Map::from_iter([
            ("language".into(), "python".into()),
            ("loc".into(), serde_json::Value::from(lines.len())),
        ]),
        spans: vec![file_span.id.clone()],
    });

    let mut local_funcs: BTreeMap<String, NodeId> = BTreeMap::new();
    let mut top_ranges: Vec<(String, usize, usize)> = Vec::new();

    let mut add_def = |d: &Def, qual: &str, parent: &NodeId, etype: EdgeKind, out: &mut ExtractOut| -> NodeId {
        let body = lines[d.line..=d.end].join("\n");
        let sid = out.add_span(
            'c',
            file_span.source.clone(),
            format!("{rel}#L{}-L{}", d.line + 1, d.end + 1),
            &body,
        );
        let nid = NodeId(format!("node:py/{src_root}/{rel}#{qual}"));
        out.nodes.push(Node {
            id: nid.clone(),
            kind: if d.kind == "class" { NodeKind::Class } else { NodeKind::Function },
            name: qual.to_string(),
            summary: docstring(&lines, d.line, d.end),
            attrs: serde_json::Map::from_iter([
                ("language".into(), "python".into()),
                ("loc".into(), serde_json::Value::from(d.end - d.line + 1)),
            ]),
            spans: vec![sid.clone()],
        });
        out.edges.push(Edge::extracted(parent.clone(), nid.clone(), etype, ex.clone(), vec![sid]));
        nid
    };

    let top: Vec<Def> = defs.iter().filter(|d| d.indent == 0).cloned().collect();
    for d in &top {
        if d.kind == "def" {
            let nid = add_def(d, &d.name, &file_id, EdgeKind::Defines, out);
            local_funcs.insert(d.name.clone(), nid);
            top_ranges.push((d.name.clone(), d.line, d.end));
        } else {
            let cid = add_def(d, &d.name, &file_id, EdgeKind::Defines, out);
            // methods: defs inside the class range at the first deeper indent seen
            let inner: Vec<&Def> = defs
                .iter()
                .filter(|m| m.line > d.line && m.end <= d.end && m.indent > 0)
                .collect();
            if let Some(method_indent) = inner.iter().map(|m| m.indent).min() {
                for m in inner.into_iter().filter(|m| m.indent == method_indent) {
                    add_def(m, &format!("{}.{}", d.name, m.name), &cid, EdgeKind::Contains, out);
                }
            }
        }
    }

    // same-file calls between top-level functions: ONE alternation regex per
    // file, each body scanned once (the per-pair version was the compile
    // stage's hot spot)
    if local_funcs.len() >= 2 {
        let alternation: Vec<String> =
            local_funcs.keys().map(|n| regex::escape(n)).collect();
        let call_re = Regex::new(&format!(r"\b({})\s*\(", alternation.join("|"))).unwrap();
        for (caller_name, a, b) in &top_ranges {
            let caller = local_funcs[caller_name].clone();
            let body = lines[*a..=(*b).min(lines.len() - 1)].join("\n");
            let mut seen: std::collections::BTreeSet<&str> = std::collections::BTreeSet::new();
            for m in call_re.captures_iter(&body) {
                let callee_name = m.get(1).unwrap().as_str();
                if callee_name == caller_name
                    || body[..m.get(0).unwrap().start()].ends_with("def ")
                    || !seen.insert(callee_name)
                {
                    continue;
                }
                out.edges.push(Edge::extracted(
                    caller.clone(),
                    local_funcs[callee_name].clone(),
                    EdgeKind::Calls,
                    ex.clone(),
                    vec![file_span.id.clone()],
                ));
            }
        }
    }

    // imports
    let mut mods: Vec<String> = Vec::new();
    for line in &lines {
        if let Some(c) = res().import_from.captures(line) {
            mods.push(c[1].to_string());
        } else if let Some(c) = res().import_plain.captures(line) {
            mods.extend(c[1].split(',').map(|m| m.trim().to_string()));
        }
    }
    mods.sort();
    mods.dedup();
    for m in mods {
        let mid = NodeId(format!("node:mod/{m}"));
        if !out.nodes.iter().any(|n| n.id == mid) {
            out.nodes.push(Node {
                id: mid.clone(),
                kind: NodeKind::Module,
                name: m.clone(),
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

    // cross-module calls: `from M import name` binds name->M; if name(...) is
    // actually invoked in this file, that is a real call INTO module M, a
    // richer interaction than the bare import (an import may be unused). The
    // edge targets the module node and is relinked to the file in main.rs,
    // giving file->file `calls` edges the teaching figures can follow.
    let mut binding: BTreeMap<String, String> = BTreeMap::new(); // name -> module
    for line in &lines {
        if let Some(c) = res().from_names.captures(line) {
            let module = c[1].to_string();
            for part in c[2].split(',') {
                let name = part.trim().trim_start_matches('(').split_whitespace().next().unwrap_or("");
                let bound = part.split(" as ").last().unwrap_or(name).trim().trim_end_matches(')');
                if !name.is_empty() && name != "*" {
                    binding.insert(bound.to_string(), module.clone());
                }
            }
        }
    }
    if !binding.is_empty() {
        let body = lines.join("\n");
        let mut called_mods: std::collections::BTreeSet<String> = std::collections::BTreeSet::new();
        for (name, module) in &binding {
            let pat = Regex::new(&format!(r"\b{}\s*\(", regex::escape(name))).unwrap();
            // skip the import line itself; require an actual call site
            if pat.is_match(&body) {
                called_mods.insert(module.clone());
            }
        }
        for module in called_mods {
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
                EdgeKind::Calls,
                ex.clone(),
                vec![file_span.id.clone()],
            ));
        }
    }

    let dotted = rel.trim_end_matches(".py").replace('/', ".");
    let mut map = BTreeMap::new();
    map.insert(dotted.clone(), file_id.clone());
    if let Some(pkg) = dotted.strip_suffix(".__init__") {
        map.insert(pkg.to_string(), file_id);
    }
    map
}
