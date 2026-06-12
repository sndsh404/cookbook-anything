//! Secret filter: runs BEFORE any text reaches the span store.
//! Logs counts and kinds, never values.

use regex::Regex;
use std::collections::BTreeMap;
use std::sync::OnceLock;

pub type RedactionCounts = BTreeMap<String, usize>;

struct Patterns {
    blocks: Vec<(&'static str, Regex)>,
    assignment: Regex,
    entropy_token: Regex,
}

fn patterns() -> &'static Patterns {
    static P: OnceLock<Patterns> = OnceLock::new();
    P.get_or_init(|| Patterns {
        blocks: vec![
            (
                "private_key",
                Regex::new(r"(?s)-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----").unwrap(),
            ),
            ("aws_key", Regex::new(r"\bAKIA[0-9A-Z]{16}\b").unwrap()),
            ("github_token", Regex::new(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b").unwrap()),
            ("slack_token", Regex::new(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b").unwrap()),
            (
                "jwt",
                Regex::new(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{4,}\b").unwrap(),
            ),
        ],
        assignment: Regex::new(
            r#"(?i)\b(api[_-]?key|secret[_-]?key|secret|token|passwd|password)\b(\s*[:=]\s*["']?)([^\s"',;]{8,})"#,
        )
        .unwrap(),
        entropy_token: Regex::new(r"[A-Za-z0-9+/_=-]{28,}").unwrap(),
    })
}

fn shannon(s: &str) -> f64 {
    let mut freq = [0usize; 256];
    for b in s.bytes() {
        freq[b as usize] += 1;
    }
    let n = s.len() as f64;
    freq.iter()
        .filter(|&&c| c > 0)
        .map(|&c| {
            let p = c as f64 / n;
            -p * p.log2()
        })
        .sum()
}

/// Strip secrets; return (clean_text, counts_by_kind).
pub fn redact(text: &str) -> (String, RedactionCounts) {
    let p = patterns();
    let mut counts = RedactionCounts::new();
    let mut out = text.to_string();

    for (kind, re) in &p.blocks {
        let n = re.find_iter(&out).count();
        if n > 0 {
            out = re.replace_all(&out, format!("[REDACTED:{kind}]")).into_owned();
            *counts.entry(kind.to_string()).or_default() += n;
        }
    }

    let mut n_assign = 0usize;
    out = p
        .assignment
        .replace_all(&out, |c: &regex::Captures| {
            if c[3].contains("REDACTED") {
                return c[0].to_string();
            }
            n_assign += 1;
            format!("{}{}[REDACTED:credential_assignment]", &c[1], &c[2])
        })
        .into_owned();
    if n_assign > 0 {
        *counts.entry("credential_assignment".into()).or_default() += n_assign;
    }

    let mut n_entropy = 0usize;
    out = p
        .entropy_token
        .replace_all(&out, |c: &regex::Captures| {
            let tok = &c[0];
            if tok.contains("REDACTED") || shannon(tok) <= 4.2 {
                tok.to_string()
            } else {
                n_entropy += 1;
                "[REDACTED:high_entropy]".to_string()
            }
        })
        .into_owned();
    if n_entropy > 0 {
        *counts.entry("high_entropy".into()).or_default() += n_entropy;
    }
    (out, counts)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn redacts_each_kind() {
        let key = ["AKIA", "IOSFODNN7", "EXAMPLE"].join("");
        let text = format!(
            "a = 1\nkey = \"{key}\"\npassword = \"hunter2secretpw\"\nplain = \"hello world\"\n"
        );
        let (clean, counts) = redact(&text);
        assert!(!clean.contains(&key));
        assert!(!clean.contains("hunter2secretpw"));
        assert!(clean.contains("plain = \"hello world\""));
        assert!(counts.values().sum::<usize>() >= 2);
    }

    #[test]
    fn entropy_catches_random_blobs_not_prose() {
        let blob = "Zx9kQ2mP7vL4nR8tW3yB6cF1dH5jS0aG9eK2uX7o";
        let (clean, _) = redact(&format!("x {blob} y"));
        assert!(!clean.contains(blob));
        let (clean2, c2) = redact("the quick brown fox jumps over the lazy dog repeatedly");
        assert!(clean2.contains("quick brown fox"));
        assert!(c2.is_empty());
    }
}
