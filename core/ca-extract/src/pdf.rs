//! Minimal PDF text-layer extraction: stream objects, optional FlateDecode,
//! Tj/TJ operators. Honest fallback (a trace note) when there is no text
//! layer; v0 does not OCR (DESIGN honest seam 4).

use flate2::read::ZlibDecoder;
use regex::bytes::Regex as BytesRegex;
use regex::Regex;
use std::io::Read;
use std::sync::OnceLock;

pub struct PdfText {
    pub text: String,
    pub fallbacks: Vec<String>,
}

/// Per-page text, one entry per content stream that yielded text. Chapter
/// workers in the acquisition swarm each take a page range, so pages need
/// their own spans (locator "book.pdf#p3").
pub struct PdfPages {
    pub pages: Vec<String>,
    pub fallbacks: Vec<String>,
}

pub fn extract_text(data: &[u8]) -> PdfText {
    let p = extract_pages(data);
    PdfText { text: p.pages.join(" "), fallbacks: p.fallbacks }
}

pub fn extract_pages(data: &[u8]) -> PdfPages {
    static STREAM: OnceLock<BytesRegex> = OnceLock::new();
    static TEXT_OP: OnceLock<Regex> = OnceLock::new();
    static LITERAL: OnceLock<Regex> = OnceLock::new();
    let stream_re = STREAM.get_or_init(|| {
        // (?-u): compressed stream bytes are not valid UTF-8, and unicode
        // mode would refuse to let `.` cross them
        BytesRegex::new(r"(?s-u)<<(.*?)>>\s*stream\r?\n(.*?)\r?\nendstream").unwrap()
    });
    let text_op = TEXT_OP.get_or_init(|| {
        Regex::new(r"\((?:[^()\\]|\\.)*\)\s*Tj|\[(?:[^\[\]\\]|\\.)*\]\s*TJ").unwrap()
    });
    let literal = LITERAL.get_or_init(|| Regex::new(r"\(((?:[^()\\]|\\.)*)\)").unwrap());

    let mut pages: Vec<String> = Vec::new();
    let mut fallbacks = Vec::new();

    for cap in stream_re.captures_iter(data) {
        let head = &cap[1];
        let mut body: Vec<u8> = cap[2].to_vec();
        if head.windows(12).any(|w| w == b"/FlateDecode") {
            let mut decoded = Vec::new();
            let mut z = ZlibDecoder::new(&body[..]);
            match z.read_to_end(&mut decoded) {
                Ok(_) => body = decoded,
                Err(_) => {
                    fallbacks.push("FlateDecode stream failed to inflate; skipped".into());
                    continue;
                }
            }
        }
        if head.windows(6).any(|w| w == b"/Image") {
            continue;
        }
        let s: String = body.iter().map(|&b| b as char).collect(); // latin-1
        let mut chunks: Vec<String> = Vec::new();
        for m in text_op.find_iter(&s) {
            for lit in literal.captures_iter(m.as_str()) {
                chunks.push(lit[1].replace(r"\(", "(").replace(r"\)", ")").replace(r"\\", "\\"));
            }
        }
        if !chunks.is_empty() {
            pages.push(chunks.join(" ").trim().to_string());
        }
    }
    if pages.is_empty() {
        fallbacks.push("no extractable text layer (would need OCR); skipping with trace note".into());
    }
    PdfPages { pages, fallbacks }
}
