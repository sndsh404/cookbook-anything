// html2md.ts - rung 1 of the fetch ladder: static HTML to clean markdown
// (the firecrawl-style canonical text format). Deliberately simple: block
// tags, headings, links, lists, code; scripts/styles stripped.

function decodeEntities(s: string): string {
  return s
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&nbsp;/g, " ")
    .replace(/&amp;/g, "&");
}

export function htmlToMarkdown(html: string): { markdown: string; title: string; links: string[] } {
  const title = decodeEntities((html.match(/<title[^>]*>([\s\S]*?)<\/title>/i)?.[1] ?? "").trim());
  const links: string[] = [];
  for (const m of html.matchAll(/<a\s[^>]*href\s*=\s*["']([^"'#]+)["']/gi)) {
    links.push(m[1]);
  }

  let s = html
    .replace(/<script[\s\S]*?<\/script>/gi, "")
    .replace(/<style[\s\S]*?<\/style>/gi, "")
    .replace(/<!--[\s\S]*?-->/g, "");

  s = s.replace(/<h([1-6])[^>]*>([\s\S]*?)<\/h\1>/gi, (_m, lv, body) =>
    `\n${"#".repeat(Number(lv))} ${body.replace(/<[^>]+>/g, "").trim()}\n`);
  s = s.replace(/<pre[^>]*>([\s\S]*?)<\/pre>/gi, (_m, body) =>
    `\n\`\`\`\n${body.replace(/<[^>]+>/g, "")}\n\`\`\`\n`);
  s = s.replace(/<li[^>]*>([\s\S]*?)<\/li>/gi, (_m, body) =>
    `\n- ${body.replace(/<[^>]+>/g, "").trim()}`);
  s = s.replace(/<a\s[^>]*href\s*=\s*["']([^"']+)["'][^>]*>([\s\S]*?)<\/a>/gi, (_m, href, body) =>
    `[${body.replace(/<[^>]+>/g, "").trim()}](${href})`);
  s = s.replace(/<(p|div|section|article|br|tr)[^>]*>/gi, "\n");
  s = s.replace(/<[^>]+>/g, "");
  s = decodeEntities(s);
  s = s.replace(/[ \t]+\n/g, "\n").replace(/\n{3,}/g, "\n\n").trim();
  return { markdown: s, title, links };
}
