//! Stage 1 INTAKE: walk sources, route to parsers, secret-filter, write
//! manifest + redacted span store + per-source trace timelines + runs.jsonl.
//! Incremental: unchanged sha256 => skipped, spans carried over, zero re-parse.

use crate::{pdf, secrets};
use ca_model::{SourceId, SourceRec, Span, SpanId};
use serde_json::json;
use sha2::{Digest, Sha256};
use std::collections::BTreeMap;
use std::fs;
use std::io::Write;
use std::path::{Path, PathBuf};

pub const SKIP_DIRS: &[&str] = &[".git", "__pycache__", "node_modules", ".venv", "venv", ".cookbook"];
const MAX_FILE_BYTES: u64 = 2_000_000;
const TEXT_EXT: &[&str] = &[
    "py", "md", "txt", "rst", "json", "yaml", "yml", "toml", "cfg", "ini", "csv", "sql", "js",
    "ts", "tsx", "html", "css", "sh", "ps1", "go", "rs", "java", "c", "cpp", "h", "hpp",
];

pub fn now_iso() -> String {
    let secs = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0);
    let days = secs / 86400;
    let (h, m, s) = ((secs % 86400) / 3600, (secs % 3600) / 60, secs % 60);
    // civil-from-days (Howard Hinnant's algorithm)
    let z = days as i64 + 719_468;
    let era = z.div_euclid(146_097);
    let doe = z.rem_euclid(146_097);
    let yoe = (doe - doe / 1460 + doe / 36524 - doe / 146_096) / 365;
    let y = yoe + era * 400;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let d = doy - (153 * mp + 2) / 5 + 1;
    let mo = if mp < 10 { mp + 3 } else { mp - 9 };
    let y = if mo <= 2 { y + 1 } else { y };
    format!("{y:04}-{mo:02}-{d:02}T{h:02}:{m:02}:{s:02}Z")
}

pub struct Trace {
    path: PathBuf,
}

impl Trace {
    pub fn new(path: PathBuf) -> Trace {
        if let Some(p) = path.parent() {
            let _ = fs::create_dir_all(p);
        }
        Trace { path }
    }
    pub fn event(&self, kind: &str, fields: serde_json::Value) {
        let mut rec = json!({"at": now_iso(), "event": kind});
        if let (Some(obj), Some(extra)) = (rec.as_object_mut(), fields.as_object()) {
            for (k, v) in extra {
                obj.insert(k.clone(), v.clone());
            }
        }
        if let Ok(mut fh) = fs::OpenOptions::new().create(true).append(true).open(&self.path) {
            let _ = writeln!(fh, "{rec}");
        }
    }
}

fn sha_hex(data: &[u8]) -> String {
    let mut h = Sha256::new();
    h.update(data);
    format!("{:x}", h.finalize())
}

fn skip_path(p: &Path) -> bool {
    p.components().any(|c| SKIP_DIRS.contains(&c.as_os_str().to_string_lossy().as_ref()))
}

fn walk_files(root: &Path) -> Vec<PathBuf> {
    let mut out = Vec::new();
    let mut stack = vec![root.to_path_buf()];
    while let Some(dir) = stack.pop() {
        let Ok(rd) = fs::read_dir(&dir) else { continue };
        for entry in rd.flatten() {
            let p = entry.path();
            if skip_path(&p) {
                continue;
            }
            if p.is_dir() {
                stack.push(p);
            } else {
                out.push(p);
            }
        }
    }
    out.sort();
    out
}

fn stat_string(f: &Path) -> String {
    f.metadata()
        .map(|m| {
            let mtime = m
                .modified()
                .ok()
                .and_then(|t| t.duration_since(std::time::UNIX_EPOCH).ok())
                .map(|d| d.as_secs())
                .unwrap_or(0);
            format!("{}:{}", m.len(), mtime)
        })
        .unwrap_or_default()
}

/// (combined digest, rel -> sha, rel -> "size:mtime"). A file whose stat
/// matches the previous run reuses the stored sha without being read.
pub fn hash_source(
    path: &Path,
    prev: Option<(&BTreeMap<String, String>, &BTreeMap<String, String>)>,
) -> (String, BTreeMap<String, String>, BTreeMap<String, String>) {
    if path.is_file() {
        return (sha_hex(&fs::read(path).unwrap_or_default()), BTreeMap::new(), BTreeMap::new());
    }
    let mut h = Sha256::new();
    let mut files = BTreeMap::new();
    let mut stats = BTreeMap::new();
    for f in walk_files(path) {
        let rel = f.strip_prefix(path).unwrap_or(&f).to_string_lossy().replace('\\', "/");
        let st = stat_string(&f);
        let fh = match prev {
            Some((pf, ps)) if ps.get(&rel) == Some(&st) && pf.contains_key(&rel) => {
                pf[&rel].clone()
            }
            _ => sha_hex(&fs::read(&f).unwrap_or_default()),
        };
        h.update(rel.as_bytes());
        h.update(fh.as_bytes());
        files.insert(rel.clone(), fh);
        stats.insert(rel, st);
    }
    (format!("{:x}", h.finalize()), files, stats)
}

pub fn classify(path: &Path) -> &'static str {
    if path.is_dir() {
        return if path.join(".git").exists() { "git_repo" } else { "folder" };
    }
    match path.extension().and_then(|e| e.to_str()).unwrap_or("").to_lowercase().as_str() {
        "pdf" => "pdf",
        "md" => "markdown",
        "csv" => "csv",
        "sql" => "sql_dump",
        _ => "file",
    }
}

#[derive(Debug, Default)]
pub struct IntakeStats {
    pub parsed: usize,
    pub skipped: usize,
    pub redactions: usize,
    pub n_sources: usize,
    pub n_spans: usize,
    /// files actually re-read this run (the M5 incremental number)
    pub files_reparsed: usize,
}

struct SpanSink<'a> {
    spans: &'a mut Vec<Span>,
    next: usize,
    redactions: BTreeMap<String, usize>,
}

impl SpanSink<'_> {
    fn add(&mut self, src: &SourceId, locator: String, raw_text: &str) {
        let (clean, counts) = secrets::redact(raw_text);
        for (k, v) in counts {
            *self.redactions.entry(k).or_default() += v;
        }
        self.spans.push(Span {
            id: SpanId(format!("span:{:05}", self.next)),
            source: src.clone(),
            locator,
            text_sha: sha_hex(clean.as_bytes()),
            text: clean,
        });
        self.next += 1;
    }
}

/// Ingest one file from a folder source. Returns true if a span was added.
fn ingest_file(f: &Path, rel: &str, src_id: &SourceId, trace: &Trace, sink: &mut SpanSink) -> bool {
    let ext = f.extension().and_then(|e| e.to_str()).unwrap_or("").to_lowercase();
    if ext == "pdf" {
        let pt = pdf::extract_text(&fs::read(f).unwrap_or_default());
        for fb in &pt.fallbacks {
            trace.event("fallback", json!({"file": rel, "note": fb}));
        }
        sink.add(src_id, rel.to_string(), &pt.text);
        return true;
    }
    if !TEXT_EXT.contains(&ext.as_str())
        || f.metadata().map(|m| m.len()).unwrap_or(0) > MAX_FILE_BYTES
    {
        return false;
    }
    match fs::read(f) {
        Ok(bytes) => {
            sink.add(src_id, rel.to_string(), &String::from_utf8_lossy(&bytes));
            true
        }
        Err(e) => {
            trace.event("fallback", json!({"file": rel, "note": e.to_string()}));
            false
        }
    }
}

fn parse_source(
    item: &Path,
    src_id: &SourceId,
    src_type: &str,
    trace: &Trace,
    sink: &mut SpanSink,
) {
    match src_type {
        "git_repo" | "folder" => {
            let mut n = 0usize;
            for f in walk_files(item) {
                let rel = f
                    .strip_prefix(item)
                    .unwrap_or(&f)
                    .to_string_lossy()
                    .replace('\\', "/");
                if ingest_file(&f, &rel, src_id, trace, sink) {
                    n += 1;
                }
            }
            trace.event("parsed", json!({"files": n}));
        }
        "pdf" => {
            let pt = pdf::extract_text(&fs::read(item).unwrap_or_default());
            for fb in &pt.fallbacks {
                trace.event("fallback", json!({"note": fb}));
            }
            sink.add(src_id, item.file_name().unwrap_or_default().to_string_lossy().into(), &pt.text);
            trace.event("parsed", json!({"files": 1}));
        }
        _ => {
            let bytes = fs::read(item).unwrap_or_default();
            sink.add(
                src_id,
                item.file_name().unwrap_or_default().to_string_lossy().into(),
                &String::from_utf8_lossy(&bytes),
            );
            trace.event("parsed", json!({"files": 1}));
        }
    }
}

pub fn intake(sources_dir: &Path, cookbook_dir: &Path) -> std::io::Result<IntakeStats> {
    fs::create_dir_all(cookbook_dir)?;
    let manifest_path = cookbook_dir.join("manifest.json");
    let spans_path = cookbook_dir.join("spans.jsonl");

    let old_sources: Vec<SourceRec> = manifest_path
        .exists()
        .then(|| fs::read_to_string(&manifest_path).ok())
        .flatten()
        .and_then(|t| serde_json::from_str::<serde_json::Value>(&t).ok())
        .and_then(|v| serde_json::from_value(v["sources"].clone()).ok())
        .unwrap_or_default();
    let old_by_path: BTreeMap<String, SourceRec> =
        old_sources.into_iter().map(|s| (s.path.clone(), s)).collect();

    let old_spans: Vec<Span> = spans_path
        .exists()
        .then(|| fs::read_to_string(&spans_path).ok())
        .flatten()
        .map(|t| t.lines().filter_map(|l| serde_json::from_str(l).ok()).collect())
        .unwrap_or_default();

    let mut items: Vec<PathBuf> = fs::read_dir(sources_dir)?
        .flatten()
        .map(|e| e.path())
        .filter(|p| !skip_path(p))
        .collect();
    items.sort();
    println!("[Stage 1/7] intake: {} sources in {}", items.len(), sources_dir.display());

    let mut sources: Vec<SourceRec> = Vec::new();
    let mut spans: Vec<Span> = Vec::new();
    let next_span = old_spans
        .iter()
        .filter_map(|s| s.id.0.strip_prefix("span:").and_then(|n| n.parse::<usize>().ok()))
        .max()
        .unwrap_or(0)
        + 1;
    let mut stats = IntakeStats::default();
    let mut sink_next = next_span;

    for (i, item) in items.iter().enumerate() {
        let rel = item.file_name().unwrap_or_default().to_string_lossy().to_string();
        let src_type = classify(item);
        let prev = old_by_path.get(&rel);
        let (digest, file_hashes, file_stats) =
            hash_source(item, prev.map(|p| (&p.files, &p.stats)));
        let src_id = prev
            .map(|p| p.id.clone())
            .unwrap_or_else(|| SourceId(format!("src:{:04}", old_by_path.len() + stats.parsed + 1)));
        let trace = Trace::new(
            cookbook_dir.join("trace").join(format!("{}.jsonl", src_id.0.replace(':', "-"))),
        );
        let parser = format!("ca-extract@{src_type}");

        if let Some(p) = prev {
            if p.sha256 == digest {
                trace.event("skipped", json!({"reason": "unchanged (sha256 match)"}));
                sources.push(p.clone());
                spans.extend(old_spans.iter().filter(|s| s.source == src_id).cloned());
                stats.skipped += 1;
                println!("  [{}/{}] {rel}: unchanged, skipped", i + 1, items.len());
                continue;
            }
        }

        trace.event("detected", json!({"type": src_type, "parser": parser}));
        let mut sink = SpanSink { spans: &mut spans, next: sink_next, redactions: BTreeMap::new() };

        // per-file incremental: a changed folder source re-reads only the
        // files whose hashes moved; everything else carries its spans over
        let incremental = prev
            .filter(|p| !p.files.is_empty() && matches!(src_type, "git_repo" | "folder"))
            .cloned();
        if let Some(p) = incremental {
            let (mut changed, mut carried, mut removed) = (0usize, 0usize, 0usize);
            for f in walk_files(item) {
                let frel =
                    f.strip_prefix(item).unwrap_or(&f).to_string_lossy().replace('\\', "/");
                match (p.files.get(&frel), file_hashes.get(&frel)) {
                    (Some(old), Some(new)) if old == new => {
                        let n_before = sink.spans.len();
                        sink.spans.extend(
                            old_spans
                                .iter()
                                .filter(|s| s.source == src_id && s.locator == frel)
                                .cloned(),
                        );
                        if sink.spans.len() > n_before {
                            carried += 1;
                        }
                    }
                    _ => {
                        if ingest_file(&f, &frel, &src_id, &trace, &mut sink) {
                            changed += 1;
                        }
                    }
                }
            }
            removed += p.files.keys().filter(|k| !file_hashes.contains_key(*k)).count();
            stats.files_reparsed += changed;
            trace.event(
                "incremental",
                json!({"reparsed": changed, "carried": carried, "removed": removed}),
            );
            println!(
                "  [{}/{}] {rel}: incremental, {changed} files reparsed, {carried} carried",
                i + 1,
                items.len()
            );
        } else {
            let before = sink.spans.len();
            parse_source(item, &src_id, src_type, &trace, &mut sink);
            stats.files_reparsed += sink.spans.len() - before;
            println!("  [{}/{}] {rel}: {src_type} parsed", i + 1, items.len());
        }

        sink_next = sink.next;
        let n_red: usize = sink.redactions.values().sum();
        if n_red > 0 {
            // counts and kinds only, never values
            trace.event("redacted", json!({"counts": sink.redactions}));
        }
        stats.parsed += 1;
        stats.redactions += n_red;
        sources.push(SourceRec {
            id: src_id,
            kind: src_type.to_string(),
            path: rel.clone(),
            parser,
            sha256: digest,
            ingested_at: now_iso(),
            files: file_hashes,
            stats: file_stats,
        });
    }

    fs::write(
        &manifest_path,
        serde_json::to_string_pretty(&json!({"sources": sources}))?,
    )?;
    let mut out = String::new();
    for s in &spans {
        out.push_str(&serde_json::to_string(s)?);
        out.push('\n');
    }
    fs::write(&spans_path, out)?;
    let mut runs = fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open(cookbook_dir.join("runs.jsonl"))?;
    writeln!(
        runs,
        "{}",
        json!({"at": now_iso(), "stage": "intake", "parsed": stats.parsed,
               "skipped": stats.skipped, "redactions": stats.redactions,
               "n_sources": sources.len(), "n_spans": spans.len()})
    )?;
    stats.n_sources = sources.len();
    stats.n_spans = spans.len();
    println!(
        "[Stage 1/7] done: {} parsed ({} files reread), {} skipped, {} secrets redacted, {} spans",
        stats.parsed, stats.files_reparsed, stats.skipped, stats.redactions, stats.n_spans
    );
    Ok(stats)
}
