//! ca-extract: the deterministic floors of INTAKE and COMPILE-extract.
//! Every edge born here is `Edge::extracted` (confidence 1.0, named
//! extractor). Agents never get write access to this crate's outputs.

pub mod data;
pub mod intake;
pub mod markdown;
pub mod nativecode;
pub mod pdf;
pub mod python;
pub mod secrets;

use ca_model::{Claim, Edge, GlossaryEntry, Node, SourceId, Span, SpanId};
use sha2::{Digest, Sha256};

/// Accumulator passed through extractors.
pub struct ExtractOut {
    pub spans: Vec<Span>,
    pub nodes: Vec<Node>,
    pub edges: Vec<Edge>,
    pub claims: Vec<Claim>,
    pub glossary: Vec<GlossaryEntry>,
    pub span_counter: usize,
    pub claim_counter: usize,
}

pub const MAX_SPAN_TEXT: usize = 1500;

impl ExtractOut {
    pub fn new() -> Self {
        ExtractOut {
            spans: Vec::new(),
            nodes: Vec::new(),
            edges: Vec::new(),
            claims: Vec::new(),
            glossary: Vec::new(),
            span_counter: 1,
            claim_counter: 1,
        }
    }

    /// Sub-spans derive from already-redacted intake text, so secret hygiene
    /// survives compilation by construction.
    pub fn add_span(&mut self, prefix: char, source: SourceId, locator: String, text: &str) -> SpanId {
        let clipped: String = text.chars().take(MAX_SPAN_TEXT).collect();
        let sid = SpanId(format!("span:{prefix}{:05}", self.span_counter));
        self.span_counter += 1;
        let mut h = Sha256::new();
        h.update(clipped.as_bytes());
        self.spans.push(Span {
            id: sid.clone(),
            source,
            locator,
            text_sha: format!("{:x}", h.finalize()),
            text: clipped,
        });
        sid
    }
}

impl Default for ExtractOut {
    fn default() -> Self {
        Self::new()
    }
}
