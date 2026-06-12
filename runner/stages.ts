// stages.ts - the stage runner: invokes the Rust core (ca) and the Python
// renderer (figlib) in pipeline order, stops on the first red stage, and
// finishes with the scored gate. Each layer talks only through model.json
// and typed payloads on disk.
//
//   node --experimental-strip-types stages.ts <sources_dir> <workspace_dir> <repo_name>

import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, "..");
const CA = join(root, "core", "target", "release", process.platform === "win32" ? "ca.exe" : "ca");
const PY = process.env.CA_PYTHON ?? "python";

function run(name: string, cmd: string, args: string[]): boolean {
  const r = spawnSync(cmd, args, { stdio: "inherit" });
  if (r.status !== 0) {
    console.error(`[stages] ${name} FAILED (exit ${r.status})`);
    return false;
  }
  return true;
}

const [sources, workspace, repoName] = process.argv.slice(2);
if (!sources || !workspace || !repoName) {
  console.error("usage: stages.ts <sources_dir> <workspace_dir> <repo_name>");
  process.exit(2);
}
if (!existsSync(CA)) {
  console.error(`[stages] core binary missing at ${CA}; run cargo build --release`);
  process.exit(1);
}
const cookbook = join(workspace, ".cookbook");

const pipeline: Array<[string, string, string[]]> = [
  ["intake", CA, ["intake", sources, cookbook]],
  ["compile", CA, ["compile", cookbook]],
  ["topology", CA, ["topology", cookbook]],
  ["plan", CA, ["plan", cookbook]],
  ["write", CA, ["write", cookbook, workspace, repoName, "--ship"]],
  ["verify", CA, ["verify", cookbook, workspace]],
  ["figures", PY, [join(root, "figlib", "figures_from_plan.py"), cookbook, workspace]],
  ["lint", PY, [join(root, "figlib", "lint_prose.py"),
                join(workspace, "out", "paper.md"),
                join(workspace, "out", "lint_report.json")]],
];

for (const [name, cmd, args] of pipeline) {
  if (!run(name, cmd, args)) process.exit(1);
}

// the scored gate decides; stages.ts only relays its verdict
const ok = run("grade", CA, ["grade", workspace]);
process.exit(ok ? 0 : 1);
