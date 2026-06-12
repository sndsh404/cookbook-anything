// book_swarm.ts - acquisition and verification swarms over the span store.
//
// Acquisition: a librarian coordinator partitions a multi-chapter book's
// page spans among reader workers (adjacent assignments overlap by one
// chapter so independent agreement is possible), fans out in parallel, then
// hands off to an archivist that writes the findings file. Workers only
// READ; nothing they produce enters model.json except through `ca admit`,
// which re-checks every span reference and drops unsourced assertions.
//
// Verification: workers fan out over the rest of the span store and report
// span-backed support for an existing claim; silence is recorded as
// silence, never as a verdict.
//
//   node --experimental-strip-types book_swarm.ts acquire <cookbook> [--workers N]
//   node --experimental-strip-types book_swarm.ts verify <cookbook> <claim_id> [--workers N]

import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { runSwarm, type Agent, type Result, type Task } from "./swarm.ts";

interface Span {
  id: string;
  locator: string;
  text: string;
}

function loadSpans(cookbook: string): Span[] {
  return readFileSync(join(cookbook, "spans.jsonl"), "utf-8")
    .split(/\r?\n/)
    .filter(Boolean)
    .map((l) => JSON.parse(l));
}

function arg(name: string, def: string): string {
  const i = process.argv.indexOf(`--${name}`);
  return i >= 0 ? process.argv[i + 1] : def;
}

// the same sentence filter the markdown extractor uses; candidates only,
// since ca admit re-verifies every one against its span
function claimWorthy(s: string): boolean {
  const t = s.trim();
  return (
    t.length >= 30 &&
    t.length <= 300 &&
    t[0] === t[0].toUpperCase() &&
    /[A-Z]/.test(t[0]) &&
    t.endsWith(".") &&
    !t.startsWith("TODO") &&
    !t.startsWith("http") &&
    !t.includes("|") &&
    !t.includes("```") &&
    !t.includes("?") &&
    !t.includes("[REDACTED")
  );
}

function sentences(text: string): string[] {
  return text.split(/(?<=[.!?])\s+/).map((s) => s.trim()).filter(Boolean);
}

function reader(id: number): Agent {
  return {
    name: `reader-${id}`,
    instructions:
      "Read the chapter spans assigned to you. Return every claim-worthy " +
      "sentence with the span it came from. Never assert anything you " +
      "cannot point at.",
    fn: (task: Task): Result => {
      const spans = task.spans as Span[];
      const findings = [];
      const covered = [];
      for (const s of spans) {
        covered.push({ worker: `reader-${id}`, locator: s.locator });
        for (const sent of sentences(s.text)) {
          if (claimWorthy(sent)) {
            findings.push({
              kind: "claim",
              text: sent,
              span_id: s.id,
              worker: `reader-${id}`,
              locator: s.locator,
            });
          }
        }
      }
      return { contextUpdates: { findings, covered } };
    },
  };
}

function archivist(cookbook: string): Agent {
  return {
    name: "archivist",
    instructions:
      "Write the collected findings to disk for `ca admit`. You do not " +
      "judge them; the gate does.",
    fn: (_task: Task, ctx): Result => {
      const out = join(cookbook, "swarm_findings.json");
      writeFileSync(
        out,
        JSON.stringify({ findings: ctx.findings ?? [], covered: ctx.covered ?? [] }, null, 1),
      );
      return { value: out };
    },
  };
}

function librarian(cookbook: string, nWorkers: number): Agent {
  return {
    name: "librarian",
    instructions:
      "Partition the book's chapters among readers, overlapping adjacent " +
      "assignments by one chapter so agreement between independent readers " +
      "is possible. Fan out, then hand the results to the archivist.",
    fn: (_task: Task): Result => {
      const chapters = loadSpans(cookbook).filter((s) => /#p\d+$/.test(s.locator));
      if (chapters.length === 0) {
        throw new Error("no multi-chapter pdf spans found in the span store");
      }
      const per = Math.ceil(chapters.length / nWorkers);
      const handoffs = [];
      for (let w = 0; w < nWorkers; w++) {
        const slice = chapters.slice(w * per, (w + 1) * per + 1); // +1 = overlap
        if (slice.length === 0) continue;
        handoffs.push({
          agent: reader(w + 1),
          task: {
            description: `read ${slice.length} chapters (${slice[0].locator}..)`,
            spans: slice,
          },
        });
      }
      return {
        handoffs,
        handoff: {
          agent: archivist(cookbook),
          task: { description: "archive findings for ca admit" },
        },
      };
    },
  };
}

function verifier(id: number, claimId: string, claimText: string): Agent {
  return {
    name: `verifier-${id}`,
    instructions:
      "Check whether your assigned spans independently contain the claim. " +
      "Report span-backed support or stay silent; silence is a finding too.",
    fn: (task: Task): Result => {
      const spans = task.spans as Span[];
      const findings = [];
      const silent = [];
      for (const s of spans) {
        if (s.text.includes(claimText)) {
          findings.push({
            kind: "support",
            claim_id: claimId,
            span_id: s.id,
            worker: `verifier-${id}`,
          });
        } else {
          silent.push({ worker: `verifier-${id}`, span_id: s.id });
        }
      }
      return { contextUpdates: { findings, silent } };
    },
  };
}

async function cmdAcquire(cookbook: string, nWorkers: number): Promise<void> {
  const report = await runSwarm(librarian(cookbook, nWorkers), {
    description: "acquire a multi-chapter book in parallel",
  });
  const covered = new Set(
    ((report.context.covered as Array<{ locator: string }>) ?? []).map((c) => c.locator),
  );
  console.log(
    JSON.stringify({
      agents: report.steps.map((s) => s.agent),
      chapters_covered: covered.size,
      findings: ((report.context.findings as unknown[]) ?? []).length,
    }),
  );
}

async function cmdVerify(cookbook: string, claimId: string, nWorkers: number): Promise<void> {
  const model = JSON.parse(readFileSync(join(cookbook, "model.json"), "utf-8"));
  const claim = model.claims.find((c: { id: string }) => c.id === claimId);
  if (!claim) throw new Error(`claim ${claimId} not in model`);
  const cited = new Set(claim.spans as string[]);
  const spans = loadSpans(cookbook).filter((s) => !cited.has(s.id));
  const per = Math.ceil(spans.length / nWorkers);

  const coordinator: Agent = {
    name: "verify-coordinator",
    instructions: "Fan claim verification out to independent verifiers.",
    fn: (): Result => ({
      handoffs: Array.from({ length: nWorkers }, (_v, w) => ({
        agent: verifier(w + 1, claimId, claim.text),
        task: {
          description: `verify ${claimId} against ${per} spans`,
          spans: spans.slice(w * per, (w + 1) * per),
        },
      })),
      handoff: {
        agent: archivist(cookbook),
        task: { description: "archive verification verdicts" },
      },
    }),
  };

  const report = await runSwarm(coordinator, { description: `verify ${claimId}` });
  console.log(
    JSON.stringify({
      agents: report.steps.map((s) => s.agent),
      supports: ((report.context.findings as unknown[]) ?? []).length,
      silent: ((report.context.silent as unknown[]) ?? []).length,
    }),
  );
}

const [cmd, cookbook, ...rest] = process.argv.slice(2);
const workers = Number(arg("workers", "3"));
if (cmd === "acquire" && cookbook) {
  await cmdAcquire(cookbook, workers);
} else if (cmd === "verify" && cookbook && rest[0]) {
  await cmdVerify(cookbook, rest[0], workers);
} else {
  console.error("usage: book_swarm.ts <acquire|verify> <cookbook> [claim_id] [--workers N]");
  process.exit(2);
}
