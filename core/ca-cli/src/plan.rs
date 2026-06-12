//! plan: topology becomes pedagogy. Chapters are file clusters ordered by
//! dependency (concepts before the things that use them); prerequisites may
//! only point backwards, so the chapter graph is acyclic BY CONSTRUCTION,
//! and any forward dependency is recorded honestly instead of hidden.

use ca_model::{EdgeKind, Model, NodeKind};
use serde::Serialize;
use std::collections::{BTreeMap, HashMap};

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
}

#[derive(Serialize)]
pub struct Plan {
    pub page_one: FigurePlan,
    pub chapters: Vec<Chapter>,
    pub forward_deps_dropped: usize,
}

pub fn build_plan(model: &Model, topo: &ca_topology::Topology) -> Plan {
    // order clusters by the average dependency-order position of their files
    let pos: HashMap<&str, usize> = topo
        .dependency_order
        .iter()
        .enumerate()
        .map(|(i, n)| (n.0.as_str(), i))
        .collect();
    let mut ranked: Vec<(String, Vec<String>, f64)> = topo
        .clusters
        .iter()
        .filter(|(_, files)| files.len() >= 2)
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

    // cross-cluster import counts
    let file_cluster: HashMap<&str, &str> = topo
        .clusters
        .iter()
        .flat_map(|(c, files)| files.iter().map(move |f| (f.0.as_str(), c.as_str())))
        .collect();
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
                *cross.entry((ca, cb)).or_default() += 1; // chapter ca depends on cb
            }
        }
    }

    let mut forward_dropped = 0usize;
    let intra: HashMap<usize, usize> = {
        let mut m = HashMap::new();
        for e in &model.edges {
            if e.kind() != EdgeKind::Imports {
                continue;
            }
            if let (Some(&ca), Some(&cb)) = (
                file_cluster.get(e.source().0.as_str()).and_then(|c| cluster_index.get(c)),
                file_cluster.get(e.target().0.as_str()).and_then(|c| cluster_index.get(c)),
            ) {
                if ca == cb {
                    *m.entry(ca).or_default() += 1;
                }
            }
        }
        m
    };

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
            let n_intra = intra.get(&i).copied().unwrap_or(0);
            let figure = if n_intra >= 2 {
                FigurePlan {
                    recipe: "dependency_graph".into(),
                    why: format!("{n_intra} import edges inside this cluster are the structure to teach"),
                }
            } else {
                FigurePlan {
                    recipe: "quantity".into(),
                    why: "few internal edges; sizes orient the reader faster here".into(),
                }
            };
            Chapter {
                index: i,
                title: name.clone(),
                cluster: name.clone(),
                node_ids: files.clone(),
                figure,
                prereqs,
            }
        })
        .collect();

    // concept nodes: section/glossary backed files could extend chapters later
    let _ = model.nodes.iter().filter(|n| n.kind == NodeKind::Concept).count();

    Plan {
        page_one: FigurePlan {
            recipe: "architecture_box".into(),
            why: "one diagram that carries the whole system before any prose".into(),
        },
        chapters,
        forward_deps_dropped: forward_dropped,
    }
}
