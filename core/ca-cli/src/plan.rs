//! plan: topology becomes pedagogy. Chapters are file clusters ordered by
//! dependency (concepts before the things that use them); prerequisites may
//! only point backwards, so the chapter graph is acyclic BY CONSTRUCTION.
//!
//! Beyond ordering, plan now computes the TEACHING structure each chapter
//! needs (the Grokking template, see MEMORY.md): a worked-example path of
//! real call/import edges to follow, and the handful of key files to
//! explain. write narrates these; figures renders the path as a dataflow.

use ca_model::{EdgeKind, Model, NodeKind};
use serde::Serialize;
use std::collections::{BTreeMap, HashMap, HashSet};

#[derive(Serialize)]
pub struct FigurePlan {
    pub recipe: String,
    pub why: String,
}

#[derive(Serialize)]
pub struct Chapter {
    pub index: usize,
    pub title: String,
    pub cluster: String,
    pub node_ids: Vec<String>,
    pub figure: FigurePlan,
    pub prereqs: Vec<usize>,
    /// a real call/import path through this chapter's files, the worked
    /// example the chapter follows (node ids, in flow order)
    pub worked_path: Vec<String>,
    /// the few most-connected files, the ones the chapter explains in prose
    pub key_files: Vec<String>,
}

#[derive(Serialize)]
pub struct Plan {
    pub page_one: FigurePlan,
    pub chapters: Vec<Chapter>,
    pub forward_deps_dropped: usize,
}

/// Longest simple path (capped depth) over intra-chapter interaction edges,
/// calls preferred over imports. This is the worked example the chapter
/// follows: "A calls into B, which calls into C".
fn worked_path(files: &HashSet<&str>, adj: &HashMap<&str, Vec<&str>>) -> Vec<String> {
    const MAX_DEPTH: usize = 5;
    let mut best: Vec<&str> = Vec::new();
    // deterministic: sorted starts and sorted neighbors, longest path wins,
    // ties broken by node id so reruns produce the same worked example
    let mut starts: Vec<&str> = files.iter().copied().collect();
    starts.sort_unstable();
    for &start in &starts {
        let mut stack: Vec<Vec<&str>> = vec![vec![start]];
        while let Some(path) = stack.pop() {
            if path.len() > best.len() || (path.len() == best.len() && path < best) {
                best = path.clone();
            }
            if path.len() >= MAX_DEPTH {
                continue;
            }
            let last = *path.last().unwrap();
            let mut nbrs: Vec<&str> =
                adj.get(last).into_iter().flatten().copied().filter(|n| !path.contains(n)).collect();
            nbrs.sort_unstable();
            nbrs.dedup();
            // push in reverse so the smallest is explored first (stable order)
            for next in nbrs.into_iter().rev() {
                let mut np = path.clone();
                np.push(next);
                stack.push(np);
            }
        }
    }
    if best.len() < 2 {
        return Vec::new();
    }
    best.into_iter().map(String::from).collect()
}

pub fn build_plan(model: &Model, topo: &ca_topology::Topology) -> Plan {
    let pos: HashMap<&str, usize> = topo
        .dependency_order
        .iter()
        .enumerate()
        .map(|(i, n)| (n.0.as_str(), i))
        .collect();
    // a teaching chapter needs code to walk through. Pure-doc clusters (the
    // design docs, the checkpoints) are the rationale, not a chapter; their
    // claims feed the introduction and the chapter openings instead.
    let code_langs = ["python", "rust", "typescript"];
    let is_code_file: HashSet<&str> = model
        .nodes
        .iter()
        .filter(|n| {
            n.kind == NodeKind::File
                && n.attrs.get("language").and_then(|v| v.as_str()).is_some_and(|l| code_langs.contains(&l))
        })
        .map(|n| n.id.0.as_str())
        .collect();

    let mut ranked: Vec<(String, Vec<String>, f64)> = topo
        .clusters
        .iter()
        .filter(|(_, files)| files.len() >= 2)
        .filter(|(_, files)| files.iter().any(|f| is_code_file.contains(f.0.as_str())))
        .map(|(name, files)| {
            let avg = files
                .iter()
                .filter_map(|f| pos.get(f.0.as_str()))
                .map(|&i| i as f64)
                .sum::<f64>()
                / files.len().max(1) as f64;
            (name.clone(), files.iter().map(|f| f.0.clone()).collect(), avg)
        })
        .collect();
    ranked.sort_by(|a, b| a.2.partial_cmp(&b.2).unwrap_or(std::cmp::Ordering::Equal));
    let cluster_index: HashMap<&str, usize> =
        ranked.iter().enumerate().map(|(i, (n, _, _))| (n.as_str(), i)).collect();

    let file_cluster: HashMap<&str, &str> = topo
        .clusters
        .iter()
        .flat_map(|(c, files)| files.iter().map(move |f| (f.0.as_str(), c.as_str())))
        .collect();
    let file_ids: HashSet<&str> =
        model.nodes.iter().filter(|n| n.kind == NodeKind::File).map(|n| n.id.0.as_str()).collect();

    // cross-cluster import counts (for prereq ordering)
    let mut cross: BTreeMap<(usize, usize), usize> = BTreeMap::new();
    for e in &model.edges {
        if e.kind() != EdgeKind::Imports {
            continue;
        }
        if let (Some(&ca), Some(&cb)) = (
            file_cluster.get(e.source().0.as_str()).and_then(|c| cluster_index.get(c)),
            file_cluster.get(e.target().0.as_str()).and_then(|c| cluster_index.get(c)),
        ) {
            if ca != cb {
                *cross.entry((ca, cb)).or_default() += 1;
            }
        }
    }

    let mut forward_dropped = 0usize;
    let chapters: Vec<Chapter> = ranked
        .iter()
        .enumerate()
        .map(|(i, (name, files, _))| {
            let mut prereqs: Vec<usize> = cross
                .iter()
                .filter(|((a, b), n)| *a == i && b < a && **n > 0)
                .map(|((_, b), _)| *b)
                .collect();
            forward_dropped += cross.iter().filter(|((a, b), _)| *a == i && b > a).count();
            prereqs.dedup();

            let chapter_files: HashSet<&str> = files.iter().map(|s| s.as_str()).collect();

            // intra-chapter interaction edges: calls preferred, imports as
            // fallback. degree counts feed key-file selection; adjacency
            // feeds the worked path.
            let mut degree: HashMap<&str, usize> = HashMap::new();
            let mut call_adj: HashMap<&str, Vec<&str>> = HashMap::new();
            let mut imp_adj: HashMap<&str, Vec<&str>> = HashMap::new();
            for e in &model.edges {
                let (s, t) = (e.source().0.as_str(), e.target().0.as_str());
                if !chapter_files.contains(s) || !chapter_files.contains(t) || s == t {
                    continue;
                }
                if !file_ids.contains(s) || !file_ids.contains(t) {
                    continue;
                }
                match e.kind() {
                    EdgeKind::Calls => {
                        call_adj.entry(s).or_default().push(t);
                        *degree.entry(s).or_default() += 1;
                        *degree.entry(t).or_default() += 1;
                    }
                    EdgeKind::Imports => {
                        imp_adj.entry(s).or_default().push(t);
                        *degree.entry(s).or_default() += 1;
                        *degree.entry(t).or_default() += 1;
                    }
                    _ => {}
                }
            }

            let mut path = worked_path(&chapter_files, &call_adj);
            let from_calls = !path.is_empty();
            if path.is_empty() {
                path = worked_path(&chapter_files, &imp_adj);
            }

            // key files: most-connected first, fall back to declaration order
            let mut key: Vec<&str> = chapter_files.iter().copied().collect();
            key.sort_by_key(|f| (std::cmp::Reverse(degree.get(f).copied().unwrap_or(0)), *f));
            let key_files: Vec<String> = key.into_iter().take(5).map(String::from).collect();

            let figure = if path.len() >= 2 {
                FigurePlan {
                    recipe: "dataflow".into(),
                    why: if from_calls {
                        "follow one real call path through this area".into()
                    } else {
                        "follow one real import path through this area".into()
                    },
                }
            } else if degree.values().any(|&d| d >= 2) {
                FigurePlan {
                    recipe: "dependency_graph".into(),
                    why: "the internal dependency structure is the thing to see".into(),
                }
            } else {
                FigurePlan {
                    recipe: "quantity".into(),
                    why: "no internal call or import structure; sizes orient the reader".into(),
                }
            };

            Chapter {
                index: i,
                title: name.clone(),
                cluster: name.clone(),
                node_ids: files.clone(),
                figure,
                prereqs,
                worked_path: path,
                key_files,
            }
        })
        .collect();

    Plan {
        page_one: FigurePlan {
            recipe: "architecture_box".into(),
            why: "one diagram that carries the whole system before any prose".into(),
        },
        chapters,
        forward_deps_dropped: forward_dropped,
    }
}
