// robots.ts - robots.txt respected unconditionally (the scrapy floor).
// Simple prefix matcher: User-agent groups, Disallow/Allow, longest match wins.

export interface RobotsRules {
  fetched: boolean;
  groups: Map<string, { allow: string[]; disallow: string[] }>;
}

export function parseRobots(text: string): RobotsRules {
  const groups = new Map<string, { allow: string[]; disallow: string[] }>();
  let current: string[] = [];
  for (const raw of text.split(/\r?\n/)) {
    const line = raw.replace(/#.*$/, "").trim();
    if (!line) continue;
    const m = line.match(/^([A-Za-z-]+)\s*:\s*(.*)$/);
    if (!m) continue;
    const key = m[1].toLowerCase();
    const value = m[2].trim();
    if (key === "user-agent") {
      const ua = value.toLowerCase();
      if (!groups.has(ua)) groups.set(ua, { allow: [], disallow: [] });
      current = [ua];
    } else if (key === "disallow" || key === "allow") {
      for (const ua of current) {
        const g = groups.get(ua)!;
        if (value) (key === "allow" ? g.allow : g.disallow).push(value);
      }
    }
  }
  return { fetched: true, groups };
}

export function isAllowed(rules: RobotsRules, userAgent: string, path: string): boolean {
  if (!rules.fetched) return true; // no robots.txt = allowed by convention
  const g = rules.groups.get(userAgent.toLowerCase()) ?? rules.groups.get("*");
  if (!g) return true;
  let best: { rule: string; allow: boolean } | null = null;
  for (const rule of g.disallow) {
    if (path.startsWith(rule) && (!best || rule.length > best.rule.length)) {
      best = { rule, allow: false };
    }
  }
  for (const rule of g.allow) {
    if (path.startsWith(rule) && (!best || rule.length >= best.rule.length)) {
      best = { rule, allow: true };
    }
  }
  return best ? best.allow : true;
}
