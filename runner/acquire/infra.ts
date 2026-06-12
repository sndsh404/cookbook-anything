// infra.ts - the politeness middleware floor: HTTP cache (nothing fetched
// twice), per-domain rate limiting, append-only audit trail, budgets.

import { createHash } from "node:crypto";
import { mkdirSync, readFileSync, writeFileSync, appendFileSync, existsSync } from "node:fs";
import { join } from "node:path";

export const USER_AGENT =
  "cookbook-anything/0.1 (+https://github.com/sndsh404/cookbook-anything; research tool; contact: hiiamsandeshbhandari@gmail.com)";

export function sha256(data: string | Buffer): string {
  return createHash("sha256").update(data).digest("hex");
}

export interface Budget {
  maxPages: number;
  maxBytes: number;
  pagesUsed: number;
  bytesUsed: number;
}

export function newBudget(maxPages = 100, maxMB = 50): Budget {
  return { maxPages, maxBytes: maxMB * 1024 * 1024, pagesUsed: 0, bytesUsed: 0 };
}

export function budgetAllows(b: Budget, bytes = 0): boolean {
  return b.pagesUsed < b.maxPages && b.bytesUsed + bytes <= b.maxBytes;
}

export class Audit {
  private path: string;
  constructor(workspace: string) {
    const dir = join(workspace, ".cookbook");
    mkdirSync(dir, { recursive: true });
    this.path = join(dir, "acquire_audit.jsonl");
  }
  log(event: Record<string, unknown>): void {
    appendFileSync(this.path, JSON.stringify({ at: new Date().toISOString(), ...event }) + "\n");
  }
  file(): string {
    return this.path;
  }
}

export class HttpCache {
  private dir: string;
  constructor(workspace: string) {
    this.dir = join(workspace, ".cookbook", "http_cache");
    mkdirSync(this.dir, { recursive: true });
  }
  get(url: string): { body: Buffer; contentType: string } | null {
    const key = sha256(url);
    const meta = join(this.dir, key + ".json");
    if (!existsSync(meta)) return null;
    const m = JSON.parse(readFileSync(meta, "utf-8"));
    return { body: readFileSync(join(this.dir, key + ".bin")), contentType: m.contentType };
  }
  put(url: string, body: Buffer, contentType: string): void {
    const key = sha256(url);
    writeFileSync(join(this.dir, key + ".bin"), body);
    writeFileSync(
      join(this.dir, key + ".json"),
      JSON.stringify({ url, contentType, cachedAt: new Date().toISOString(), bytes: body.length }),
    );
  }
}

const lastHit = new Map<string, number>();

export async function rateLimit(host: string, minIntervalMs = 500): Promise<void> {
  const now = Date.now();
  const prev = lastHit.get(host) ?? 0;
  const wait = prev + minIntervalMs - now;
  if (wait > 0) await new Promise((r) => setTimeout(r, wait));
  lastHit.set(host, Date.now());
}
