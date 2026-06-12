// acquire.ts - Stage 0 CLI. No agent fetches directly; every request goes
// through here. robots.txt unconditionally, allowlist scoping, rate limits,
// HTTP cache, archive-on-fetch, budgets, audit trail, license gate.
//
//   node --experimental-strip-types acquire.ts crawl <seed> --workspace <ws> --allow <host[,host]> [--max-pages N]
//   node --experimental-strip-types acquire.ts asset <File:Title> --workspace <ws> [--claim <license>] [--fixture <json>]

import { mkdirSync, writeFileSync, appendFileSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { parseRobots, isAllowed, type RobotsRules } from "./robots.ts";
import { Audit, HttpCache, USER_AGENT, budgetAllows, newBudget, rateLimit, sha256 } from "./infra.ts";
import { htmlToMarkdown } from "./html2md.ts";
import { commonsApiUrl, gate, parseCommonsResponse } from "./license.ts";

function arg(name: string, def = ""): string {
  const i = process.argv.indexOf(`--${name}`);
  return i >= 0 ? process.argv[i + 1] : def;
}

interface Ctx {
  workspace: string;
  allow: Set<string>;
  audit: Audit;
  cache: HttpCache;
  budget: ReturnType<typeof newBudget>;
  robots: Map<string, RobotsRules>;
  stats: { fetched: number; cacheHits: number; deniedRobots: number; deniedAllowlist: number };
}

async function getRobots(ctx: Ctx, origin: string): Promise<RobotsRules> {
  let r = ctx.robots.get(origin);
  if (r) return r;
  const url = origin + "/robots.txt";
  const cached = ctx.cache.get(url);
  if (cached) {
    r = parseRobots(cached.body.toString("utf-8"));
  } else {
    try {
      const res = await fetch(url, { headers: { "User-Agent": USER_AGENT } });
      if (res.ok) {
        const text = await res.text();
        ctx.cache.put(url, Buffer.from(text), "text/plain");
        r = parseRobots(text);
      } else {
        r = { fetched: false, groups: new Map() };
      }
    } catch {
      r = { fetched: false, groups: new Map() };
    }
  }
  ctx.robots.set(origin, r);
  ctx.audit.log({ event: "robots", origin, fetched: r.fetched });
  return r;
}

async function politeFetch(ctx: Ctx, url: string, purpose: string):
  Promise<{ body: Buffer; contentType: string; fromCache: boolean } | null> {
  const u = new URL(url);
  if (!ctx.allow.has(u.hostname)) {
    ctx.stats.deniedAllowlist++;
    ctx.audit.log({ event: "denied", reason: "off-allowlist", url, purpose });
    return null;
  }
  const robots = await getRobots(ctx, u.origin);
  if (!isAllowed(robots, "cookbook-anything", u.pathname)) {
    ctx.stats.deniedRobots++;
    ctx.audit.log({ event: "denied", reason: "robots.txt", url, purpose });
    return null;
  }
  const cached = ctx.cache.get(url);
  if (cached) {
    ctx.stats.cacheHits++;
    ctx.audit.log({ event: "cache_hit", url, purpose });
    return { ...cached, fromCache: true };
  }
  if (!budgetAllows(ctx.budget)) {
    ctx.audit.log({ event: "denied", reason: "budget", url, purpose });
    return null;
  }
  await rateLimit(u.hostname);
  try {
    const res = await fetch(url, { headers: { "User-Agent": USER_AGENT } });
    const body = Buffer.from(await res.arrayBuffer());
    const contentType = res.headers.get("content-type") ?? "";
    ctx.budget.pagesUsed++;
    ctx.budget.bytesUsed += body.length;
    ctx.stats.fetched++;
    ctx.audit.log({ event: "fetch", url, purpose, status: res.status, bytes: body.length });
    if (res.ok) ctx.cache.put(url, body, contentType);
    return res.ok ? { body, contentType, fromCache: false } : null;
  } catch (e) {
    ctx.audit.log({ event: "fetch_error", url, purpose, error: String(e) });
    return null;
  }
}

function archivePage(ctx: Ctx, url: string, html: string): string {
  // archive-on-fetch: spans point at the archived copy, never the live URL alone
  const dir = join(ctx.workspace, "sources", "web");
  mkdirSync(dir, { recursive: true });
  const key = sha256(url).slice(0, 16);
  const { markdown, title } = htmlToMarkdown(html);
  const md = `---\norigin_url: ${url}\nfetched_at: ${new Date().toISOString()}\ntitle: "${title}"\n---\n\n${markdown}\n`;
  writeFileSync(join(dir, `${key}.md`), md);
  writeFileSync(join(dir, `${key}.html`), html);
  return key;
}

async function cmdCrawl(): Promise<number> {
  const seed = process.argv[3];
  const ws = arg("workspace");
  const maxPages = Number(arg("max-pages", "100"));
  const allow = new Set(arg("allow", new URL(seed).hostname).split(","));
  const ctx: Ctx = {
    workspace: ws, allow, audit: new Audit(ws), cache: new HttpCache(ws),
    budget: newBudget(maxPages), robots: new Map(),
    stats: { fetched: 0, cacheHits: 0, deniedRobots: 0, deniedAllowlist: 0 },
  };
  const queue = [seed];
  const seen = new Set<string>(queue);
  let archived = 0;
  while (queue.length > 0) {
    const url = queue.shift()!;
    const got = await politeFetch(ctx, url, "crawl");
    if (!got) continue;
    const html = got.body.toString("utf-8");
    if (!got.fromCache) {
      archivePage(ctx, url, html);
      archived++;
    }
    const { links } = htmlToMarkdown(html);
    for (const link of links) {
      try {
        const abs = new URL(link, url).toString().split("#")[0];
        if (!seen.has(abs) && (abs.startsWith("http://") || abs.startsWith("https://"))) {
          seen.add(abs);
          queue.push(abs);
        }
      } catch { /* bad href, skip */ }
    }
  }
  console.log(JSON.stringify({ ...ctx.stats, archived }));
  return 0;
}

async function cmdAsset(): Promise<number> {
  const title = process.argv[3];
  const ws = arg("workspace");
  const claim = arg("claim") || null;
  const fixture = arg("fixture");
  const audit = new Audit(ws);

  let apiJson: any = null;
  let verifiedBy = "commons_api";
  const apiUrl = commonsApiUrl(title);
  if (fixture) {
    apiJson = JSON.parse(readFileSync(fixture, "utf-8"));
    verifiedBy = "commons_api(fixture)";
    audit.log({ event: "license_check", title, source: "fixture" });
  } else {
    try {
      const res = await fetch(apiUrl, { headers: { "User-Agent": USER_AGENT } });
      apiJson = await res.json();
      audit.log({ event: "license_check", title, source: "live", url: apiUrl });
    } catch (e) {
      audit.log({ event: "license_check_failed", title, error: String(e) });
    }
  }

  const meta = apiJson ? parseCommonsResponse(apiJson) : null;
  const verdict = gate(claim, meta, verifiedBy);
  audit.log({ event: "license_verdict", title, decision: verdict.decision, reason: verdict.reason });
  const cbDir = join(ws, ".cookbook");
  mkdirSync(cbDir, { recursive: true });

  if (verdict.decision === "embed") {
    const id = `asset:${sha256(title).slice(0, 8)}`;
    const rec = {
      id, kind: "image", origin_url: meta!.descriptionUrl || apiUrl,
      archive_path: `sources/web/${id}.img`, fetched_at: new Date().toISOString(),
      sha256: "", license: verdict.license, attribution: verdict.attribution,
    };
    appendFileSync(join(cbDir, "assets.jsonl"), JSON.stringify(rec) + "\n");
    console.log(JSON.stringify({ decision: "embed", asset: rec }));
    return 0;
  }
  if (verdict.decision === "flag_user") {
    console.log(JSON.stringify({ decision: "flag_user", reason: verdict.reason }));
    return 2;
  }
  // reject_redraw: convert into a figure request, the superior outcome anyway
  const req = { requested_at: new Date().toISOString(), instead_of: title, reason: verdict.reason,
                want: "an original diagram drawn from the model via the recipe library" };
  appendFileSync(join(cbDir, "figure_requests.jsonl"), JSON.stringify(req) + "\n");
  console.log(JSON.stringify({ decision: "reject_redraw", reason: verdict.reason }));
  return 3;
}

const cmd = process.argv[2];
const rc = cmd === "crawl" ? await cmdCrawl() : cmd === "asset" ? await cmdAsset() : (console.error("usage: acquire.ts <crawl|asset> ..."), 2);
process.exit(rc as number);
