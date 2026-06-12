// license.ts - the license gate (DESIGN stage 0). An external image enters
// the model only with a VERIFIED license record. Verification means license
// metadata from a programmatic source (Wikimedia Commons API here), never a
// page's prose claim. Unknown/all-rights-reserved => deny-and-redraw: the
// gate emits a figure request instead of embedding.

export interface LicenseRecord {
  name: string;
  author: string;
  evidence_url: string;
  verified_by: string;
}

export interface GateVerdict {
  decision: "embed" | "flag_user" | "reject_redraw";
  license?: LicenseRecord;
  attribution?: string;
  reason: string;
}

const OK_FREE = /^(public domain|pd|cc0)/i;
const OK_ATTRIB = /^cc[ -]by(?![ -]nc|[ -]nd)([ -]sa)?/i;
const FLAG = /(nc|nd)/i;

export function judgeLicense(name: string, author: string, evidenceUrl: string,
                             verifiedBy: string): GateVerdict {
  const n = name.trim();
  if (!n || /all rights reserved|copyright/i.test(n)) {
    return {
      decision: "reject_redraw",
      reason: `license "${n || "unknown"}" cannot be verified as free; ` +
        "filing a figure request to re-draw the facts as an original diagram",
    };
  }
  const license: LicenseRecord = { name: n, author, evidence_url: evidenceUrl, verified_by: verifiedBy };
  if (OK_FREE.test(n)) {
    return { decision: "embed", license, attribution: `Image: ${author || "unknown"}, ${n}`, reason: "free license" };
  }
  if (OK_ATTRIB.test(n)) {
    const attribution = `Image: ${author || "unknown"}, ${n}, via Wikimedia Commons`;
    return { decision: "embed", license, attribution, reason: "attribution license; attribution line is non-removable" };
  }
  if (FLAG.test(n)) {
    return { decision: "flag_user", license, reason: `license ${n} has NC/ND terms; needs logged user approval (F-13)` };
  }
  return { decision: "reject_redraw", reason: `license "${n}" not in a recognized free tier; deny-and-redraw` };
}

interface CommonsMeta {
  licenseShortName: string;
  artist: string;
  descriptionUrl: string;
}

export function parseCommonsResponse(json: any): CommonsMeta | null {
  const pages = json?.query?.pages;
  if (!pages) return null;
  const page = Object.values(pages)[0] as any;
  const info = page?.imageinfo?.[0];
  const meta = info?.extmetadata;
  if (!meta) return null;
  const strip = (s: string) => (s ?? "").replace(/<[^>]+>/g, "").trim();
  return {
    licenseShortName: strip(meta.LicenseShortName?.value ?? ""),
    artist: strip(meta.Artist?.value ?? ""),
    descriptionUrl: info.descriptionurl ?? "",
  };
}

export function commonsApiUrl(fileTitle: string): string {
  const t = encodeURIComponent(fileTitle.startsWith("File:") ? fileTitle : `File:${fileTitle}`);
  return (
    "https://commons.wikimedia.org/w/api.php?action=query&format=json" +
    `&prop=imageinfo&iiprop=extmetadata|url&titles=${t}`
  );
}

/// The gate itself: pageClaim is what the embedding page SAYS the license
/// is; apiMeta is what the metadata API PROVES. Disagreement = rejection.
export function gate(pageClaim: string | null, apiMeta: CommonsMeta | null,
                     verifiedBy: string): GateVerdict {
  if (!apiMeta) {
    return { decision: "reject_redraw", reason: "no programmatic license metadata available; deny-and-redraw" };
  }
  const verdict = judgeLicense(apiMeta.licenseShortName, apiMeta.artist, apiMeta.descriptionUrl, verifiedBy);
  if (pageClaim && verdict.decision === "embed") {
    const claim = pageClaim.toLowerCase().replace(/[^a-z0-9]+/g, "");
    const proven = apiMeta.licenseShortName.toLowerCase().replace(/[^a-z0-9]+/g, "");
    if (!proven.includes(claim) && !claim.includes(proven)) {
      return {
        decision: "reject_redraw",
        reason: `page claims "${pageClaim}" but API metadata says "${apiMeta.licenseShortName}"; ` +
          "claim/evidence mismatch, rejected",
      };
    }
  }
  return verdict;
}
