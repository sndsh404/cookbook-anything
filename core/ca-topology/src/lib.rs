//! ca-topology: computed structure signals BEFORE any pedagogy is designed
//! (the Understand-Anything move). Entry points, degree centrality,
//! dependency order over imports, clusters by directory.

use ca_model::{EdgeKind, Model, NodeId, NodeKind};
use serde::Serialize;
use std::collections::{BTreeMap, HashSet, VecDeque};

#[derive(Serialize)]
pub struct Topology {
    pub entry_points: Vec<NodeId>,
    pub dependency_order: Vec<NodeId>,
    pub centrality: BTreeMap<String, usize>,
    pub clusters: BTreeMap<String, Vec<NodeId>>,
    pub cycles_broken: usize,
}

pub fn analyze(model: &Model) -> Topology {
    let files: Vec<&NodeId> = model
        .nodes
        .iter()
        .filter(|n| n.kind == NodeKind::File)
        .map(|n| &n.id)
        .collect();
    let file_set: HashSet<&NodeId> = files.iter().copied().collect();

    // imports graph among file nodes only
    let mut deps: BTreeMap<&NodeId, Vec<&NodeId>> = BTreeMap::new(); // file -> files it imports
    let mut rdeps: BTreeMap<&NodeId, usize> = BTreeMap::new(); // how many import it
    for e in &model.edges {
        if e.kind() == EdgeKind::Imports
            && file_set.contains(e.source())
            && file_set.contains(e.target())
        {
            deps.entry(e.source()).or_default().push(e.target());
            *rdeps.entry(e.target()).or_default() += 1;
        }
    }

    // degree centrality over all edges (in+out)
    let mut centrality: BTreeMap<String, usize> = BTreeMap::new();
    for e in &model.edges {
        *centrality.entry(e.source().0.clone()).or_default() += 1;
        *centrality.entry(e.target().0.clone()).or_default() += 1;
    }

    // entry points: README-ish files first, then files nobody imports that
    // import others (mains), most-central first
    let mut entry_points: Vec<NodeId> = Vec::new();
    for f in &files {
        let name = f.0.to_lowercase();
        if name.contains("readme") {
            entry_points.push((*f).clone());
        }
    }
    let mut mains: Vec<&NodeId> = files
        .iter()
        .copied()
        .filter(|f| rdeps.get(*f).copied().unwrap_or(0) == 0 && deps.contains_key(*f))
        .collect();
    mains.sort_by_key(|f| std::cmp::Reverse(centrality.get(&f.0).copied().unwrap_or(0)));
    for m in mains.into_iter().take(5) {
        if !entry_points.contains(m) {
            entry_points.push(m.clone());
        }
    }

    // dependency order: Kahn over "A imports B => B before A"; cycles broken
    // by smallest in-degree, counted honestly
    let mut indeg: BTreeMap<&NodeId, usize> = files.iter().map(|f| (*f, 0usize)).collect();
    for tos in deps.values() {
        // edge B <- A counts on A (A depends on B): A's indegree = number of deps
    let _ = tos;
    }
    for (f, tos) in &deps {
        *indeg.get_mut(*f).unwrap() = tos.iter().filter(|t| file_set.contains(**t)).count();
    }
    let mut users: BTreeMap<&NodeId, Vec<&NodeId>> = BTreeMap::new(); // dep -> users
    for (f, tos) in &deps {
        for t in tos {
            users.entry(*t).or_default().push(*f);
        }
    }
    let mut q: VecDeque<&NodeId> = indeg.iter().filter(|(_, d)| **d == 0).map(|(f, _)| *f).collect();
    let mut order: Vec<NodeId> = Vec::new();
    let mut done: HashSet<&NodeId> = HashSet::new();
    let mut cycles_broken = 0usize;
    loop {
        while let Some(f) = q.pop_front() {
            if !done.insert(f) {
                continue;
            }
            order.push(f.clone());
            for u in users.get(f).into_iter().flatten() {
                if let Some(d) = indeg.get_mut(*u) {
                    *d = d.saturating_sub(1);
                    if *d == 0 && !done.contains(*u) {
                        q.push_back(*u);
                    }
                }
            }
        }
        // cycle: pick the remaining node with the smallest in-degree
        if let Some((f, _)) = indeg
            .iter()
            .filter(|(f, _)| !done.contains(**f))
            .min_by_key(|(_, d)| **d)
        {
            cycles_broken += 1;
            q.push_back(*f);
        } else {
            break;
        }
    }

    // clusters by top directory under the source root
    let mut clusters: BTreeMap<String, Vec<NodeId>> = BTreeMap::new();
    for f in &files {
        let path = f.0.trim_start_matches("node:file/");
        let parts: Vec<&str> = path.split('/').collect();
        let cluster = if parts.len() > 2 { parts[1].to_string() } else { "(root)".to_string() };
        clusters.entry(cluster).or_default().push((*f).clone());
    }

    Topology { entry_points, dependency_order: order, centrality, clusters, cycles_broken }
}
