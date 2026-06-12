// Seeded crawl target for the M2.5 gate: 50 public pages, a /private/ tree
// that robots.txt forbids, and offsite links that the allowlist must scope
// out. Counts every hit so the test can prove politeness from the server's
// side of the wire.
import { createServer } from "node:http";

const PORT = Number(process.argv[2] ?? 8931);
const N_PAGES = 49; // + index = 50 public pages

let hits = 0;
let privateHits = 0;

const server = createServer((req, res) => {
  const url = new URL(req.url, `http://127.0.0.1:${PORT}`);
  if (url.pathname === "/__stats") {
    res.writeHead(200, { "content-type": "application/json" });
    res.end(JSON.stringify({ hits, privateHits }));
    return;
  }
  hits++;
  if (url.pathname === "/robots.txt") {
    res.writeHead(200, { "content-type": "text/plain" });
    res.end("User-agent: *\nDisallow: /private/\n");
    return;
  }
  if (url.pathname.startsWith("/private/")) {
    privateHits++;
    res.writeHead(200, { "content-type": "text/html" });
    res.end("<html><title>secret</title><body>you should not be here</body></html>");
    return;
  }
  if (url.pathname === "/") {
    const links = Array.from({ length: 5 }, (_, i) => `<a href="/page/${i + 1}">p${i + 1}</a>`).join(" ");
    res.writeHead(200, { "content-type": "text/html" });
    res.end(`<html><title>seed</title><body><h1>Seeded site</h1>${links}
      <a href="/private/vault">vault</a>
      <a href="http://offsite.invalid/page">offsite</a></body></html>`);
    return;
  }
  const m = url.pathname.match(/^\/page\/(\d+)$/);
  if (m) {
    const k = Number(m[1]);
    if (k <= N_PAGES) {
      const next = k < N_PAGES ? `<a href="/page/${k + 1}">next</a>` : "";
      const more = k + 5 <= N_PAGES ? `<a href="/page/${k + 5}">skip</a>` : "";
      res.writeHead(200, { "content-type": "text/html" });
      res.end(`<html><title>page ${k}</title><body><h2>Page ${k}</h2>
        <p>This is seeded page number ${k} with some prose.</p>
        ${next} ${more} <a href="/private/page-${k}">private</a></body></html>`);
      return;
    }
  }
  res.writeHead(404, { "content-type": "text/plain" });
  res.end("not found");
});

server.listen(PORT, "127.0.0.1", () => console.log(`testserver ready on ${PORT}`));
