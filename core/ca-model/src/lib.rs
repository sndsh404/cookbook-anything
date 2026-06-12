//! ca-model: the knowledge model (DESIGN 4), with the invariants encoded in
//! the type system so they cannot be violated at compile time:
//!
//!   - an `Edge` cannot be constructed without an `ExtractorId`
//!   - a `Claim` cannot exist without at least one span (`SpanRefs` is non-empty)
//!   - an `Asset` cannot exist without a `License`
//!   - an agent-proposed edge cannot reach confidence 1.0
//!
//! Deserialization goes through raw mirror structs with `TryFrom`, so a
//! hand-tampered model.json that violates an invariant is rejected at load.

use serde::{Deserialize, Serialize};
use std::collections::HashSet;
use std::path::Path;

pub const AGENT_CONFIDENCE_CAP: f64 = 0.75;

// ---------------------------------------------------------------- ids

macro_rules! id_type {
    ($name:ident) => {
        #[derive(Debug, Clone, PartialEq, Eq, Hash, PartialOrd, Ord, Serialize, Deserialize)]
        #[serde(transparent)]
        pub struct $name(pub String);
        impl $name {
            pub fn as_str(&self) -> &str {
                &self.0
            }
        }
        impl std::fmt::Display for $name {
            fn fmt(&self, f: &mut std::fmt::Formatter) -> std::fmt::Result {
                write!(f, "{}", self.0)
            }
        }
    };
}
id_type!(SourceId);
id_type!(SpanId);
id_type!(NodeId);
id_type!(ClaimId);
id_type!(AssetId);

/// Which deterministic extractor produced a fact. Cannot be empty.
#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
#[serde(transparent)]
pub struct ExtractorId(String);

impl ExtractorId {
    pub fn new(s: impl Into<String>) -> Result<Self, ModelError> {
        let s = s.into();
        if s.trim().is_empty() {
            return Err(ModelError::EmptyExtractor);
        }
        Ok(ExtractorId(s))
    }
    pub fn is_agent(&self) -> bool {
        self.0.starts_with("agent")
    }
    pub fn as_str(&self) -> &str {
        &self.0
    }
}

impl<'de> Deserialize<'de> for ExtractorId {
    fn deserialize<D: serde::Deserializer<'de>>(d: D) -> Result<Self, D::Error> {
        let s = String::deserialize(d)?;
        ExtractorId::new(s).map_err(serde::de::Error::custom)
    }
}

/// Confidence in [0, 1]. 1.0 = mechanically extracted.
#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
#[serde(transparent)]
pub struct Confidence(f64);

impl Confidence {
    pub fn new(v: f64) -> Self {
        Confidence(v.clamp(0.0, 1.0))
    }
    pub const FULL: Confidence = Confidence(1.0);
    pub fn get(&self) -> f64 {
        self.0
    }
    pub fn is_full(&self) -> bool {
        self.0 >= 1.0
    }
}

/// A non-empty list of span references. A claim without a span cannot exist.
#[derive(Debug, Clone, Serialize)]
#[serde(transparent)]
pub struct SpanRefs(Vec<SpanId>);

impl SpanRefs {
    pub fn new(first: SpanId, rest: Vec<SpanId>) -> Self {
        let mut v = vec![first];
        v.extend(rest);
        SpanRefs(v)
    }
    pub fn try_from_vec(v: Vec<SpanId>) -> Result<Self, ModelError> {
        if v.is_empty() {
            return Err(ModelError::ClaimWithoutSpan);
        }
        Ok(SpanRefs(v))
    }
    pub fn iter(&self) -> impl Iterator<Item = &SpanId> {
        self.0.iter()
    }
    pub fn as_slice(&self) -> &[SpanId] {
        &self.0
    }
    pub fn retain(&mut self, f: impl FnMut(&SpanId) -> bool) -> Result<(), ModelError> {
        self.0.retain(f);
        if self.0.is_empty() {
            return Err(ModelError::ClaimWithoutSpan);
        }
        Ok(())
    }
}

impl<'de> Deserialize<'de> for SpanRefs {
    fn deserialize<D: serde::Deserializer<'de>>(d: D) -> Result<Self, D::Error> {
        let v = Vec::<SpanId>::deserialize(d)?;
        SpanRefs::try_from_vec(v).map_err(serde::de::Error::custom)
    }
}

// ---------------------------------------------------------------- errors

#[derive(Debug, PartialEq)]
pub enum ModelError {
    EmptyExtractor,
    ClaimWithoutSpan,
    AssetWithoutVerifiedLicense,
    Invalid(String),
}

impl std::fmt::Display for ModelError {
    fn fmt(&self, f: &mut std::fmt::Formatter) -> std::fmt::Result {
        match self {
            ModelError::EmptyExtractor => write!(f, "edge without an extractor (hard rule 1)"),
            ModelError::ClaimWithoutSpan => write!(f, "claim without a span (hard rule 2)"),
            ModelError::AssetWithoutVerifiedLicense => {
                write!(f, "asset without a verified license record (F-13)")
            }
            ModelError::Invalid(s) => write!(f, "invalid model: {s}"),
        }
    }
}
impl std::error::Error for ModelError {}

// ---------------------------------------------------------------- records

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SourceRec {
    pub id: SourceId,
    #[serde(rename = "type")]
    pub kind: String,
    pub path: String,
    pub parser: String,
    pub sha256: String,
    #[serde(default)]
    pub ingested_at: String,
    /// per-file content hashes for folder sources; what makes a one-file
    /// change re-parse one file instead of the whole tree (M5)
    #[serde(default)]
    pub files: std::collections::BTreeMap<String, String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Span {
    pub id: SpanId,
    pub source: SourceId,
    pub locator: String,
    pub text_sha: String,
    /// Redacted text. The secret filter ran before this was written.
    #[serde(default)]
    pub text: String,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum NodeKind {
    File,
    Function,
    Class,
    Module,
    Concept,
    Table,
    Column,
    Section,
    Person,
    Decision,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Node {
    pub id: NodeId,
    #[serde(rename = "type")]
    pub kind: NodeKind,
    pub name: String,
    #[serde(default)]
    pub summary: String,
    #[serde(default)]
    pub attrs: serde_json::Map<String, serde_json::Value>,
    #[serde(default)]
    pub spans: Vec<SpanId>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum EdgeKind {
    Imports,
    Calls,
    Defines,
    Contains,
    Documents,
    DependsOn,
    ForeignKey,
    Supersedes,
    Contradicts,
}

/// An edge in the structure graph. Private fields: the only ways to make one
/// are `Edge::extracted` (confidence 1.0, real extractor) and
/// `Edge::proposed_by_agent` (confidence capped below 1.0). No extractor, no
/// edge - by construction.
#[derive(Debug, Clone, Serialize)]
#[serde(into = "RawEdge")]
pub struct Edge {
    source: NodeId,
    target: NodeId,
    kind: EdgeKind,
    extractor: ExtractorId,
    spans: Vec<SpanId>,
    confidence: Confidence,
}

#[derive(Serialize, Deserialize, Clone)]
struct RawEdge {
    source: NodeId,
    target: NodeId,
    #[serde(rename = "type")]
    kind: EdgeKind,
    extractor: ExtractorId,
    #[serde(default)]
    spans: Vec<SpanId>,
    confidence: Confidence,
}

impl From<Edge> for RawEdge {
    fn from(e: Edge) -> Self {
        RawEdge {
            source: e.source,
            target: e.target,
            kind: e.kind,
            extractor: e.extractor,
            spans: e.spans,
            confidence: e.confidence,
        }
    }
}

impl TryFrom<RawEdge> for Edge {
    type Error = ModelError;
    fn try_from(r: RawEdge) -> Result<Self, ModelError> {
        if r.extractor.is_agent() && r.confidence.is_full() {
            return Err(ModelError::Invalid(format!(
                "agent-proposed edge at confidence 1.0: {} -> {}",
                r.source, r.target
            )));
        }
        Ok(Edge {
            source: r.source,
            target: r.target,
            kind: r.kind,
            extractor: r.extractor,
            spans: r.spans,
            confidence: r.confidence,
        })
    }
}

impl<'de> Deserialize<'de> for Edge {
    fn deserialize<D: serde::Deserializer<'de>>(d: D) -> Result<Self, D::Error> {
        let raw = RawEdge::deserialize(d)?;
        Edge::try_from(raw).map_err(serde::de::Error::custom)
    }
}

impl Edge {
    /// A mechanically extracted edge: confidence 1.0, always.
    pub fn extracted(
        source: NodeId,
        target: NodeId,
        kind: EdgeKind,
        extractor: ExtractorId,
        spans: Vec<SpanId>,
    ) -> Edge {
        Edge { source, target, kind, extractor, spans, confidence: Confidence::FULL }
    }

    /// An agent-proposed edge: confidence capped below 1.0, renders dashed,
    /// lands in the unverified appendix. The cap is not negotiable.
    pub fn proposed_by_agent(
        agent_name: &str,
        source: NodeId,
        target: NodeId,
        kind: EdgeKind,
        spans: Vec<SpanId>,
        confidence: f64,
    ) -> Edge {
        let ex = ExtractorId(format!("agent:{agent_name}"));
        Edge {
            source,
            target,
            kind,
            extractor: ex,
            spans,
            confidence: Confidence::new(confidence.min(AGENT_CONFIDENCE_CAP)),
        }
    }

    pub fn source(&self) -> &NodeId {
        &self.source
    }
    pub fn target(&self) -> &NodeId {
        &self.target
    }
    pub fn kind(&self) -> EdgeKind {
        self.kind
    }
    pub fn extractor(&self) -> &ExtractorId {
        &self.extractor
    }
    pub fn spans(&self) -> &[SpanId] {
        &self.spans
    }
    pub fn confidence(&self) -> Confidence {
        self.confidence
    }
    pub fn is_unverified(&self) -> bool {
        !self.confidence.is_full()
    }
    pub fn retarget(&mut self, target: NodeId) {
        self.target = target;
    }
    pub fn prune_spans(&mut self, keep: &HashSet<SpanId>) -> bool {
        let before = self.spans.len();
        self.spans.retain(|s| keep.contains(s));
        self.spans.len() != before
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ClaimStatus {
    Active,
    Superseded,
}

/// A claim cannot exist without at least one span: `SpanRefs` is non-empty
/// by construction and by deserialization.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Claim {
    pub id: ClaimId,
    pub text: String,
    pub spans: SpanRefs,
    pub confidence: Confidence,
    pub status: ClaimStatus,
    #[serde(default)]
    pub supersedes: Option<ClaimId>,
}

impl Claim {
    pub fn new(id: ClaimId, text: String, spans: SpanRefs, confidence: f64) -> Claim {
        Claim {
            id,
            text,
            spans,
            confidence: Confidence::new(confidence),
            status: ClaimStatus::Active,
            supersedes: None,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TourStep {
    pub node: NodeId,
    pub why: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Tour {
    pub id: String,
    pub steps: Vec<TourStep>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GlossaryEntry {
    pub term: String,
    pub definition: String,
    pub first_span: SpanId,
}

/// A verified license record. `name` and `verified_by` cannot be empty.
#[derive(Debug, Clone, Serialize)]
pub struct License {
    name: String,
    #[serde(default)]
    pub author: String,
    #[serde(default)]
    pub evidence_url: String,
    verified_by: String,
}

#[derive(Deserialize)]
struct RawLicense {
    name: String,
    #[serde(default)]
    author: String,
    #[serde(default)]
    evidence_url: String,
    verified_by: String,
}

impl License {
    pub fn verified(
        name: impl Into<String>,
        author: impl Into<String>,
        evidence_url: impl Into<String>,
        verified_by: impl Into<String>,
    ) -> Result<License, ModelError> {
        let (name, verified_by) = (name.into(), verified_by.into());
        if name.trim().is_empty() || verified_by.trim().is_empty() {
            return Err(ModelError::AssetWithoutVerifiedLicense);
        }
        Ok(License { name, author: author.into(), evidence_url: evidence_url.into(), verified_by })
    }
    pub fn name(&self) -> &str {
        &self.name
    }
    pub fn verified_by(&self) -> &str {
        &self.verified_by
    }
}

impl<'de> Deserialize<'de> for License {
    fn deserialize<D: serde::Deserializer<'de>>(d: D) -> Result<Self, D::Error> {
        let r = RawLicense::deserialize(d)?;
        License::verified(r.name, r.author, r.evidence_url, r.verified_by)
            .map_err(serde::de::Error::custom)
    }
}

/// An external asset cannot exist without a `License` - it is a required,
/// non-optional field, so "embed first, license later" does not compile.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Asset {
    pub id: AssetId,
    pub kind: String,
    pub origin_url: String,
    pub archive_path: String,
    #[serde(default)]
    pub fetched_at: String,
    #[serde(default)]
    pub sha256: String,
    pub license: License,
    pub attribution: String,
}

// ---------------------------------------------------------------- model

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct Model {
    #[serde(default)]
    pub sources: Vec<SourceRec>,
    #[serde(default)]
    pub spans: Vec<Span>,
    #[serde(default)]
    pub nodes: Vec<Node>,
    #[serde(default)]
    pub edges: Vec<Edge>,
    #[serde(default)]
    pub claims: Vec<Claim>,
    #[serde(default)]
    pub tours: Vec<Tour>,
    #[serde(default)]
    pub glossary: Vec<GlossaryEntry>,
    #[serde(default)]
    pub assets: Vec<Asset>,
}

impl Model {
    pub fn load(path: &Path) -> Result<Model, ModelError> {
        let text = std::fs::read_to_string(path)
            .map_err(|e| ModelError::Invalid(format!("read {}: {e}", path.display())))?;
        serde_json::from_str(&text).map_err(|e| ModelError::Invalid(e.to_string()))
    }

    pub fn save(&self, path: &Path) -> Result<(), ModelError> {
        let text =
            serde_json::to_string_pretty(self).map_err(|e| ModelError::Invalid(e.to_string()))?;
        std::fs::write(path, text)
            .map_err(|e| ModelError::Invalid(format!("write {}: {e}", path.display())))
    }

    /// Referential checks the type system cannot enforce (cross-record).
    pub fn validate(&self) -> Vec<String> {
        let mut errors = Vec::new();
        let span_ids: HashSet<_> = self.spans.iter().map(|s| &s.id).collect();
        let node_ids: HashSet<_> = self.nodes.iter().map(|n| &n.id).collect();
        let src_ids: HashSet<_> = self.sources.iter().map(|s| &s.id).collect();

        for s in &self.spans {
            if !src_ids.contains(&s.source) {
                errors.push(format!("span {} references missing source {}", s.id, s.source));
            }
        }
        for n in &self.nodes {
            for sp in &n.spans {
                if !span_ids.contains(sp) {
                    errors.push(format!("node {} references missing span {sp}", n.id));
                }
            }
        }
        for e in &self.edges {
            if !node_ids.contains(e.source()) || !node_ids.contains(e.target()) {
                errors.push(format!("dangling edge {} -> {}", e.source(), e.target()));
            }
        }
        for c in &self.claims {
            for sp in c.spans.iter() {
                if !span_ids.contains(sp) {
                    errors.push(format!("claim {} references missing span {sp}", c.id));
                }
            }
        }
        for g in &self.glossary {
            if !span_ids.contains(&g.first_span) {
                errors.push(format!("glossary term {} references missing span", g.term));
            }
        }
        errors
    }
}

// ---------------------------------------------------------------- tests

#[cfg(test)]
mod tests {
    use super::*;

    fn nid(s: &str) -> NodeId {
        NodeId(s.into())
    }

    #[test]
    fn edge_requires_extractor_at_deserialize() {
        let bad = r#"{"source":"a","target":"b","type":"imports","extractor":"","confidence":1.0}"#;
        assert!(serde_json::from_str::<Edge>(bad).is_err());
        let missing =
            r#"{"source":"a","target":"b","type":"imports","confidence":1.0}"#;
        assert!(serde_json::from_str::<Edge>(missing).is_err());
    }

    #[test]
    fn agent_edge_cannot_reach_full_confidence() {
        let e = Edge::proposed_by_agent("planner", nid("a"), nid("b"), EdgeKind::DependsOn, vec![], 1.0);
        assert!(e.confidence().get() <= AGENT_CONFIDENCE_CAP);
        assert!(e.is_unverified());
        // and a tampered file is rejected at load
        let bad = r#"{"source":"a","target":"b","type":"depends_on","extractor":"agent:planner","confidence":1.0}"#;
        assert!(serde_json::from_str::<Edge>(bad).is_err());
    }

    #[test]
    fn claim_requires_span() {
        assert!(SpanRefs::try_from_vec(vec![]).is_err());
        let bad = r#"{"id":"c:1","text":"x.","spans":[],"confidence":0.8,"status":"active"}"#;
        assert!(serde_json::from_str::<Claim>(bad).is_err());
        let ok = r#"{"id":"c:1","text":"x.","spans":["span:1"],"confidence":0.8,"status":"active"}"#;
        assert!(serde_json::from_str::<Claim>(ok).is_ok());
    }

    #[test]
    fn asset_requires_license() {
        let bad = r#"{"id":"asset:1","kind":"image","origin_url":"u","archive_path":"p","attribution":"a"}"#;
        assert!(serde_json::from_str::<Asset>(bad).is_err());
        let unverified = r#"{"id":"asset:1","kind":"image","origin_url":"u","archive_path":"p",
            "license":{"name":"CC BY-SA 4.0","verified_by":""},"attribution":"a"}"#;
        assert!(serde_json::from_str::<Asset>(unverified).is_err());
        let ok = r#"{"id":"asset:1","kind":"image","origin_url":"u","archive_path":"p",
            "license":{"name":"CC BY-SA 4.0","author":"x","verified_by":"commons_api"},"attribution":"a"}"#;
        assert!(serde_json::from_str::<Asset>(ok).is_ok());
    }

    #[test]
    fn model_roundtrip_and_validate() {
        let mut m = Model::default();
        m.sources.push(SourceRec {
            id: SourceId("src:0001".into()),
            kind: "folder".into(),
            path: "x".into(),
            parser: "p".into(),
            sha256: "h".into(),
            ingested_at: String::new(),
        });
        m.spans.push(Span {
            id: SpanId("span:1".into()),
            source: SourceId("src:0001".into()),
            locator: "f#L1".into(),
            text_sha: "t".into(),
            text: "hello".into(),
        });
        m.nodes.push(Node {
            id: nid("node:a"),
            kind: NodeKind::File,
            name: "a".into(),
            summary: String::new(),
            attrs: Default::default(),
            spans: vec![SpanId("span:1".into())],
        });
        m.nodes.push(Node {
            id: nid("node:b"),
            kind: NodeKind::File,
            name: "b".into(),
            summary: String::new(),
            attrs: Default::default(),
            spans: vec![],
        });
        m.edges.push(Edge::extracted(
            nid("node:a"),
            nid("node:b"),
            EdgeKind::Imports,
            ExtractorId::new("ca-extract@python").unwrap(),
            vec![SpanId("span:1".into())],
        ));
        assert!(m.validate().is_empty());
        let json = serde_json::to_string(&m).unwrap();
        let back: Model = serde_json::from_str(&json).unwrap();
        assert_eq!(back.edges.len(), 1);
        assert_eq!(back.edges[0].extractor().as_str(), "ca-extract@python");

        // a dangling edge is caught by validate
        m.edges.push(Edge::extracted(
            nid("node:a"),
            nid("node:GONE"),
            EdgeKind::Calls,
            ExtractorId::new("x").unwrap(),
            vec![],
        ));
        assert_eq!(m.validate().len(), 1);
    }
}
