// swarm.ts - the two primitives, taken from OpenAI's swarm and nothing else:
// an Agent (name + instructions + a function) and a handoff (a function
// returning another Agent, or Result.handoffs for a parallel fan-out), with
// one shared contextVariables object threaded through every step. Stateless
// between runs, tiny on purpose.
//
// One deliberate difference from the original: our agent functions are
// deterministic code, not chat completions. The judgment layer can be swapped
// in later behind the same two primitives; the firewall does not care who is
// running, because nothing an agent returns enters model.json except through
// `ca admit`.

export type ContextVariables = Record<string, unknown>;

export interface Task {
  description: string;
  [key: string]: unknown;
}

export interface Result {
  value?: unknown;
  /** sequential handoff: this agent takes over the task */
  handoff?: { agent: Agent; task: Task };
  /** parallel fan-out: each handoff runs concurrently, context updates merge */
  handoffs?: Array<{ agent: Agent; task: Task }>;
  /** merged into the shared context (arrays concatenate, like findings) */
  contextUpdates?: ContextVariables;
}

export interface Agent {
  name: string;
  instructions: string;
  fn: (task: Task, ctx: Readonly<ContextVariables>) => Promise<Result> | Result;
}

export interface RunReport {
  steps: Array<{ agent: string; task: string }>;
  context: ContextVariables;
}

function mergeContext(ctx: ContextVariables, updates?: ContextVariables): void {
  if (!updates) return;
  for (const [k, v] of Object.entries(updates)) {
    if (Array.isArray(v) && Array.isArray(ctx[k])) {
      (ctx[k] as unknown[]).push(...v);
    } else {
      ctx[k] = v;
    }
  }
}

const MAX_STEPS = 50;

export async function runSwarm(
  start: Agent,
  task: Task,
  contextVariables: ContextVariables = {},
): Promise<RunReport> {
  const ctx = contextVariables;
  const steps: RunReport["steps"] = [];
  let active: { agent: Agent; task: Task } | undefined = { agent: start, task };

  while (active && steps.length < MAX_STEPS) {
    const { agent, task: t } = active;
    steps.push({ agent: agent.name, task: t.description });
    const result = await agent.fn(t, ctx);
    mergeContext(ctx, result.contextUpdates);

    if (result.handoffs && result.handoffs.length > 0) {
      // parallel fan-out: workers run concurrently against the same shared
      // context; their updates merge in completion order
      const reports = await Promise.all(
        result.handoffs.map((h) => runSwarm(h.agent, h.task, {})),
      );
      for (const r of reports) {
        steps.push(...r.steps);
        mergeContext(ctx, r.context);
      }
      active = result.handoff;
    } else {
      active = result.handoff;
    }
  }
  return { steps, context: ctx };
}
