//! ca-grade: the scored gate (DESIGN 8.1). Start at 100, deduct by severity.
//! The skill may not override this; a red grade cannot ship.
//!
//! Model/claim/provenance checks live here in Rust. Image-level checks come
//! from figcheck.py, which writes figcheck_report.json; prose lints come from
//! lint_prose.py (lint_report.json). ca-grade ingests both reports and folds
//! them into the one score.

use ca_model::Model;
use regex::Regex;
use serde::{Deserialize, Serialize};
use std::path::Path;

pub const BANNED_WORDS: &[&str] = &[
    "leverage", "robust", "seamless", "delve", "utilize", "streamline",
    "crucial", "comprehensive", "holistic", "in today's fast-paced world",
    "it's important to note", "dive deep",
];

#[derive(Debug, Clone, Serialize, PartialEq, Eq)]
pub enum Severity {
    P0,
    P1,
    P2,
}

#[derive(Debug, Clone, Serialize)]
pub struct Finding {
    pub severity: Severity,
    pub rule: String,
    pub text: String,
    pub deduction: i64,
}

#[derive(Serialize)]
pub struct Grade {
    pub score: i64,
    pub red: bool,
    pub findings: Vec<Finding>,
}

#[derive(Deserialize)]
struct ExternalReport {
    #[serde(default)]
    findings: Vec<ExternalFinding>,
}

#[derive(Deserialize)]
struct ExternalFinding {
    severity: String,
    rule: String,
    text: String,
}

fn push(findings: &mut Vec<Finding>, sev: Severity, rule: &str, text: String, deduction: i64) {
    findings.push(Finding { severity: sev, rule: rule.into(), text, deduction });
}

/// Grade a workspace: model checks + shipped-prose scans + ingested reports.
pub fn grade(workspace: &Path) -> Grade {
    let mut findings: Vec<Finding> = Vec::new();
    let model_path = workspace.join(".cookbook").join("model.json");

    // model load: deserialization itself enforces the type invariants, so a
    // failure here is a P0 provenance break, not a parse nit
    let model = match Model::load(&model_path) {
        Ok(m) => Some(m),
        Err(e) => {
            if model_path.exists() {
                push(&mut findings, Severity::P0, "F-01",
                     format!("model.json violates an invariant or is corrupt: {e}"), 100);
            }
            None
        }
    };

    if let Some(m) = &model {
        for err in m.validate() {
            push(&mut findings, Severity::P0, "F-01", err, 100);
        }
        // assets: License type guarantees name+verified_by; check attribution matches
        for a in &m.assets {
            if a.attribution.trim().is_empty() {
                push(&mut findings, Severity::P0, "F-13",
                     format!("asset {} has empty attribution", a.id), 100);
            }
        }
    }

    // shipped prose scans
    let paper = workspace.join("out").join("paper.md");
    if paper.exists() {
        let text = std::fs::read_to_string(&paper).unwrap_or_default();
        let code_re = Regex::new(r"(?s)```.*?```").unwrap();
        // prose rules apply to the authored body; glossary and appendices
        // quote source material verbatim as evidence (same scope as lint_prose)
        let authored = text.split("## Glossary").next().unwrap_or(&text).to_string();
        let prose = code_re.replace_all(&authored, "");
        for w in BANNED_WORDS {
            let re = Regex::new(&format!(r"(?i)\b{}\b", regex::escape(w))).unwrap();
            let n = re.find_iter(&prose).count() as i64;
            if n > 0 {
                push(&mut findings, Severity::P1, "prose",
                     format!("banned vocabulary in shipped prose: '{w}' x{n}"), 3 * n);
            }
        }
        let em = prose.matches('\u{2014}').count() as i64;
        if em > 0 {
            push(&mut findings, Severity::P1, "prose",
                 format!("em dashes in shipped prose: {em}"), 3 * em);
        }
        // page-one figure: an image reference within the first 60 lines
        let head: String = text.lines().take(60).collect::<Vec<_>>().join("\n");
        if !head.contains("![") {
            push(&mut findings, Severity::P0, "page-one-figure",
                 "page-one figure missing from the paper head".into(), 20);
        }
        // claim coverage comes from `ca verify`, which recomputes it over the
        // FINISHED prose (backed factual sentences / all factual sentences).
        // The writer cannot report its own coverage; if verify did not run, or
        // a marker broke, this gate fires.
        let cov_path = workspace.join("out").join("verify_report.json");
        match std::fs::read_to_string(&cov_path) {
            Ok(t) => {
                let v: serde_json::Value = serde_json::from_str(&t).unwrap_or_default();
                let cov = v["coverage_pct"].as_f64().unwrap_or(0.0);
                let broken = v["broken_markers"].as_array().map(|a| a.len()).unwrap_or(0);
                if cov < 95.0 {
                    push(&mut findings, Severity::P0, "claim-coverage",
                         format!("claim coverage {cov:.1}% < 95% (independently measured by ca verify)"), 40);
                }
                if broken > 0 {
                    push(&mut findings, Severity::P0, "claim-coverage",
                         format!("{broken} factual sentence(s) cite a claim that no longer resolves to a span"), 40);
                }
            }
            Err(_) => {
                if paper.exists() {
                    push(&mut findings, Severity::P0, "claim-coverage",
                         "no verify_report.json: coverage was never independently checked".into(), 40);
                }
            }
        }
    }

    // ingest external reports (figcheck.py, lint_prose.py, acquire audit)
    for (name, p0_ded, p1_ded) in [
        ("figcheck_report.json", 100, 10),
        ("lint_report.json", 40, 10),
        ("acquire_audit_violations.json", 100, 10),
        ("teaching_report.json", 100, 10),
    ] {
        let p = workspace.join("out").join(name);
        if let Ok(t) = std::fs::read_to_string(&p) {
            if let Ok(rep) = serde_json::from_str::<ExternalReport>(&t) {
                for f in rep.findings {
                    let (sev, ded) = match f.severity.as_str() {
                        "P0" => (Severity::P0, p0_ded),
                        "P1" => (Severity::P1, p1_ded),
                        _ => (Severity::P2, 1),
                    };
                    push(&mut findings, sev, &f.rule, f.text, ded);
                }
            }
        }
    }

    let score = (100 - findings.iter().map(|f| f.deduction).sum::<i64>()).max(0);
    let red = score < 80 || findings.iter().any(|f| f.severity == Severity::P0);
    Grade { score, red, findings }
}
