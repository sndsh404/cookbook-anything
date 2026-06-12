//! Schema-first extractor for tabular/SQL sources (DESIGN 4): tables,
//! columns, types, foreign keys, row counts. Row values never enter here.

use crate::ExtractOut;
use ca_model::{Edge, EdgeKind, ExtractorId, Node, NodeId, NodeKind, Span};
use regex::Regex;
use std::sync::OnceLock;

pub const EXTRACTOR: &str = "ca-extract@schema";

struct Res {
    create_table: Regex,
    foreign_key: Regex,
    inline_ref: Regex,
    column: Regex,
}

fn res() -> &'static Res {
    static R: OnceLock<Res> = OnceLock::new();
    R.get_or_init(|| Res {
        create_table: Regex::new(
            r#"(?is)CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?["`]?(?:\w+\.)?(\w+)["`]?\s*\((.*?)\)\s*;"#,
        )
        .unwrap(),
        foreign_key: Regex::new(
            r#"(?i)FOREIGN\s+KEY\s*\(\s*["`]?(\w+)["`]?\s*\)\s*REFERENCES\s+["`]?(?:\w+\.)?(\w+)["`]?"#,
        )
        .unwrap(),
        inline_ref: Regex::new(r#"(?i)^["`]?(\w+)["`]?\s+\w+.*?REFERENCES\s+["`]?(?:\w+\.)?(\w+)["`]?"#)
            .unwrap(),
        column: Regex::new(r#"^["`]?(\w+)["`]?\s+([A-Za-z]\w*(?:\(\d+(?:,\s*\d+)?\))?)"#).unwrap(),
    })
}

fn table_id(src_root: &str, name: &str) -> NodeId {
    NodeId(format!("node:table/{src_root}/{name}"))
}

pub fn extract_csv(file_span: &Span, src_root: &str, out: &mut ExtractOut) {
    let rel = file_span.locator.replace('\\', "/");
    let Some(header_line) = file_span.text.lines().next() else { return };
    let header: Vec<String> = header_line
        .split(',')
        .map(|h| h.trim().trim_matches('"').to_string())
        .filter(|h| !h.is_empty())
        .collect();
    if header.is_empty() {
        return;
    }
    let n_rows = file_span.text.lines().count().saturating_sub(1);
    let sid = out.add_span('t', file_span.source.clone(), format!("{rel}#L1"), header_line);
    let name = rel.rsplit('/').next().unwrap_or(&rel).trim_end_matches(".csv").to_string();
    let tid = table_id(src_root, &name);
    let ex = ExtractorId::new(EXTRACTOR).unwrap();
    out.nodes.push(Node {
        id: tid.clone(),
        kind: NodeKind::Table,
        name,
        summary: format!("{} columns, {} rows", header.len(), n_rows),
        attrs: serde_json::Map::from_iter([("rows".into(), serde_json::Value::from(n_rows))]),
        spans: vec![sid.clone()],
    });
    for col in header {
        let cid = NodeId(format!("{}.{col}", tid.0));
        out.nodes.push(Node {
            id: cid.clone(),
            kind: NodeKind::Column,
            name: col,
            summary: String::new(),
            attrs: Default::default(),
            spans: vec![sid.clone()],
        });
        out.edges.push(Edge::extracted(tid.clone(), cid, EdgeKind::Contains, ex.clone(), vec![sid.clone()]));
    }
}

pub fn extract_sql(file_span: &Span, src_root: &str, out: &mut ExtractOut) {
    let r = res();
    let rel = file_span.locator.replace('\\', "/");
    let text = file_span.text.clone();
    let ex = ExtractorId::new(EXTRACTOR).unwrap();

    for m in r.create_table.captures_iter(&text) {
        let tname = &m[1];
        let body = &m[2];
        let line_no = text[..m.get(0).unwrap().start()].matches('\n').count() + 1;
        let sid = out.add_span('t', file_span.source.clone(), format!("{rel}#L{line_no}"), &m[0]);
        let tid = table_id(src_root, tname);
        if !out.nodes.iter().any(|n| n.id == tid) {
            out.nodes.push(Node {
                id: tid.clone(),
                kind: NodeKind::Table,
                name: tname.to_string(),
                summary: String::new(),
                attrs: Default::default(),
                spans: vec![sid.clone()],
            });
        }
        let mut fks: Vec<(String, String)> = Vec::new();
        for part in body.split(',') {
            let part = part.trim();
            if part.is_empty() {
                continue;
            }
            let upper = part.to_uppercase();
            if upper.starts_with("PRIMARY")
                || upper.starts_with("UNIQUE")
                || upper.starts_with("CONSTRAINT")
                || upper.starts_with("CHECK")
                || upper.starts_with("INDEX")
                || upper.starts_with("KEY")
                || upper.starts_with("FOREIGN")
            {
                for fk in r.foreign_key.captures_iter(part) {
                    fks.push((fk[1].to_string(), fk[2].to_string()));
                }
                continue;
            }
            if let Some(fk) = r.inline_ref.captures(part) {
                fks.push((fk[1].to_string(), fk[2].to_string()));
            }
            if let Some(cm) = r.column.captures(part) {
                let (col, ctype) = (&cm[1], &cm[2]);
                let cid = NodeId(format!("{}.{col}", tid.0));
                if !out.nodes.iter().any(|n| n.id == cid) {
                    out.nodes.push(Node {
                        id: cid.clone(),
                        kind: NodeKind::Column,
                        name: col.to_string(),
                        summary: ctype.to_string(),
                        attrs: serde_json::Map::from_iter([(
                            "sqltype".into(),
                            serde_json::Value::from(ctype),
                        )]),
                        spans: vec![sid.clone()],
                    });
                    out.edges.push(Edge::extracted(
                        tid.clone(),
                        cid,
                        EdgeKind::Contains,
                        ex.clone(),
                        vec![sid.clone()],
                    ));
                }
            }
        }
        for (_, ref_table) in fks {
            let rid = table_id(src_root, &ref_table);
            if !out.nodes.iter().any(|n| n.id == rid) {
                out.nodes.push(Node {
                    id: rid.clone(),
                    kind: NodeKind::Table,
                    name: ref_table,
                    summary: "(referenced)".into(),
                    attrs: Default::default(),
                    spans: vec![sid.clone()],
                });
            }
            out.edges.push(Edge::extracted(
                tid.clone(),
                rid,
                EdgeKind::ForeignKey,
                ex.clone(),
                vec![sid.clone()],
            ));
        }
    }
}
