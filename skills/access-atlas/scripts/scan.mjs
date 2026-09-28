#!/usr/bin/env node
// access-atlas scanner. Two modes:
//
//   --plan   Size the site before scanning: reads robots.txt and the sitemap (or a quick
//            link crawl with plain HTTP), then prints page counts by section and page type
//            and time estimates per scope. No browser, no axe. Use it to ask the user
//            how deep to go.
//   default  Crawl same-origin pages in a real browser, run axe-core against WCAG A/AA,
//            add a 320px reflow check (1.4.10) and a keyboard sample (2.4.1 / 2.4.7),
//            and take screenshots with the failing elements outlined.
//
// Scope and stop rules (every run records which one stopped it):
//   --max-pages N        hard page cap (default 25)
//   --max-depth N        link depth from the start page (default 3)
//   --per-section N      pages per parent folder, so 900 news articles cost N, not 900 (default 5; 0 = no cap)
//   --time-budget M      minutes (default 15)
//   --quiet-stop N       stop after N pages in a row that show no new issue type or page type (default 20; 0 = off)
//   --delay MS           pause between pages (default 750) — this is someone's production site
//   --include-path P     stay under a path prefix; repeatable via comma
//   --urls a,b,c         scan exactly these URLs (task pages) and nothing else
//   --sitemap            seed the queue from the sitemap as well as links
// Also: --out scan.json --shots DIR --no-shots --mobile --auth-state state.json --wait MS
//
// It honours robots.txt Disallow for all agents, stops on repeated 403/429, and never
// submits forms. Dependencies live in ~/.cache/access-atlas (scripts/ensure-deps.sh).

import { createRequire } from 'node:module';
import { writeFileSync, readFileSync, existsSync, mkdirSync } from 'node:fs';
import { homedir } from 'node:os';
import { join, resolve } from 'node:path';
import { isBlocked } from './robots.mjs';

const args = process.argv.slice(2);
const opt = (n, d) => { const i = args.indexOf(`--${n}`); return i >= 0 ? args[i + 1] : d; };
const flag = (n) => args.includes(`--${n}`);
const start = args.find((a) => /^https?:\/\//.test(a));
if (!start) {
  console.error('Usage: node scan.mjs <url> [--plan] [--max-pages N] [--max-depth N] [--per-section N] [--time-budget MIN] [--out file]');
  process.exit(1);
}
const origin = new URL(start).origin;
const UA = 'access-atlas accessibility audit (+https://www.w3.org/WAI/)';
const SKIP_EXT = /\.(pdf|docx?|xlsx?|pptx?|zip|jpe?g|png|gif|svg|webp|mp4|mp3|ics|csv|xml|json|rss)(\?|$)/i;
const DOC_EXT = /\.(pdf|docx?|xlsx?|pptx?)(\?|$)/i;
const includes = (opt('include-path', '') || '').split(',').filter(Boolean);

// ---------- shared helpers
function normalise(href, base = start) {
  try {
    const u = new URL(href, base);
    u.hash = '';
    if (u.origin !== origin || SKIP_EXT.test(u.pathname)) return null;
    if (includes.length && !includes.some((p) => u.pathname.startsWith(p))) return null;
    for (const k of [...u.searchParams.keys()]) if (/^(utm_|fbclid|gclid|sort|page|print)/i.test(k)) u.searchParams.delete(k);
    return u.toString();
  } catch { return null; }
}
// Page type: digits, ids and dates collapse, so /news/2026/09/foo and /news/2025/01/bar share one.
const pageType = (url) => new URL(url).pathname.split('/').filter(Boolean)
  .map((s) => (/\d/.test(s) || s.length > 40 ? ':id' : s)).slice(0, 4).join('/') || '/';
const section = (url) => { const p = new URL(url).pathname.split('/').filter(Boolean); return '/' + p.slice(0, Math.max(1, p.length - 1)).join('/'); };

async function getText(url) {
  try {
    const r = await fetch(url, { headers: { 'user-agent': UA }, redirect: 'follow', signal: AbortSignal.timeout(15000) });
    return r.ok ? await r.text() : '';
  } catch { return ''; }
}
async function robots() {
  const txt = await getText(`${origin}/robots.txt`);
  const dis = [], maps = [];
  let applies = false;
  for (const raw of txt.split('\n')) {
    const line = raw.split('#')[0].trim();
    const [k, ...rest] = line.split(':');
    const v = rest.join(':').trim();
    if (/^user-agent$/i.test(k)) applies = v === '*';
    else if (/^disallow$/i.test(k) && applies && v) dis.push(v);
    else if (/^sitemap$/i.test(k)) maps.push(v);
  }
  return { disallow: dis, sitemaps: maps };
}
const blocked = isBlocked;
async function sitemapUrls(seeds, limit = 5000) {
  const out = new Set(), queue = [...(seeds.length ? seeds : [`${origin}/sitemap.xml`])], seen = new Set();
  while (queue.length && out.size < limit && seen.size < 50) {
    const sm = queue.shift();
    if (seen.has(sm)) continue;
    seen.add(sm);
    const xml = await getText(sm);
    for (const m of xml.matchAll(/<loc>\s*([^<\s]+)\s*<\/loc>/gi)) {
      const loc = m[1].replace(/&amp;/g, '&');
      if (/sitemap[^/]*\.xml/i.test(loc)) queue.push(loc);
      else { const n = normalise(loc); if (n) out.add(n); }
    }
  }
  return [...out].slice(0, limit);
}

// ---------- plan mode: size the site, no browser
if (flag('plan')) {
  const r = await robots();
  let urls = await sitemapUrls(r.sitemaps);
  let source = urls.length ? 'sitemap' : 'link crawl';
  if (!urls.length) {
    const seen = new Set([normalise(start)]), q = [normalise(start)];
    while (q.length && seen.size < 600) {
      const u = q.shift();
      const html = await getText(u);
      for (const m of html.matchAll(/href\s*=\s*["']([^"'#]+)["']/gi)) {
        const n = normalise(m[1], u);
        if (n && !seen.has(n) && !blocked(n, r.disallow)) { seen.add(n); q.push(n); }
      }
    }
    urls = [...seen];
    if (seen.size >= 600) source += ' (stopped at 600 — the site is larger)';
  }
  const bySection = {}, types = new Set();
  for (const u of urls) { const s = '/' + (new URL(u).pathname.split('/').filter(Boolean)[0] || ''); bySection[s] = (bySection[s] || 0) + 1; types.add(section(u)); }
  const secPerPage = 6;
  const est = (n) => `${Math.max(1, Math.round((n * secPerPage) / 60))} min`;
  const sections = Object.entries(bySection).sort((a, b) => b[1] - a[1]);
  const perSectionPages = Object.keys(bySection).length * 5;
  const plan = {
    target: start, source, urlsFound: urls.length, truncated: source.includes('stopped'), folders: types.size, robotsDisallow: r.disallow,
    topSections: sections.slice(0, 15).map(([s, n]) => ({ section: s, pages: n })),
    options: {
      quick: { pages: 25, estimate: est(25), flags: '--max-pages 25 --max-depth 2 --per-section 3' },
      standard: { pages: Math.min(150, perSectionPages), estimate: est(Math.min(150, perSectionPages)), flags: '--max-pages 150 --max-depth 4 --per-section 5 --sitemap' },
      full: { pages: urls.length, estimate: est(urls.length), flags: `--max-pages ${urls.length} --max-depth 99 --per-section 0 --sitemap --time-budget ${Math.max(30, Math.round((urls.length * secPerPage) / 60) + 10)}` },
    },
  };
  const out = opt('out', 'plan.json');
  writeFileSync(out, JSON.stringify(plan, null, 2));
  const truncated = source.includes('stopped');
  console.log(`${start}: ${urls.length}${truncated ? '+' : ''} pages found via ${source}, in ${types.size} folders.`);
  if (truncated) console.log('  The full count is unknown; a full scan needs a time budget, and --sitemap if the site has one.');
  console.log(`Largest sections: ${sections.slice(0, 6).map(([s, n]) => `${s} ${n}`).join(', ')}`);
  for (const [k, v] of Object.entries(plan.options)) console.log(`  ${k.padEnd(9)} ~${v.pages} pages, ~${v.estimate}   ${v.flags}`);
  console.log(`wrote ${out}`);
  process.exit(0);
}

// ---------- scan mode
const CACHE = process.env.ACCESS_ATLAS_CACHE || join(homedir(), '.cache', 'access-atlas');
const req = createRequire(join(CACHE, 'package.json'));
let chromium, devices, axeSource;
try {
  ({ chromium, devices } = req('playwright'));
  axeSource = readFileSync(req.resolve('axe-core/axe.min.js'), 'utf8');
} catch (e) {
  console.error(`Missing dependencies in ${CACHE}. Run scripts/ensure-deps.sh first.\n${e.message}`);
  process.exit(2);
}

const L = {
  maxPages: +opt('max-pages', 25), maxDepth: +opt('max-depth', 3), perSection: +opt('per-section', 5),
  timeBudgetMin: +opt('time-budget', 15), quietStop: +opt('quiet-stop', 20), delay: +opt('delay', 750), wait: +opt('wait', 1500),
};
const out = opt('out', 'scan.json');
const shotsDir = flag('no-shots') ? null : resolve(opt('shots', out.replace(/\.json$/, '') + '-shots'));
if (shotsDir) mkdirSync(shotsDir, { recursive: true });
const MAX_PAGE_SHOTS = 10, MAX_CROPS = 20;
const TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];
const mobile = flag('mobile');
const authState = opt('auth-state', '');

const r = await robots();
const fixed = (opt('urls', '') || '').split(',').filter(Boolean).map((u) => normalise(u)).filter(Boolean);
const queue = (fixed.length ? fixed : [normalise(start) || start]).map((u) => ({ url: u, depth: 0 }));
if (!fixed.length && flag('sitemap')) for (const u of await sitemapUrls(r.sitemaps, 3000)) queue.push({ url: u, depth: 1 });
const seen = new Set(queue.map((q) => q.url));
const skipped = { robots: 0, perSection: 0, depth: 0 };
const perSectionCount = {};
const pages = [], documents = new Set(), rulesSeen = new Set(), typesSeen = new Set();
let quiet = 0, fails = 0, crops = 0, pageShots = 0, stopReason = 'ran out of pages to scan';
const t0 = Date.now();

const browser = await chromium.launch();
const ctxOpts = mobile ? { ...devices['iPhone 13'] } : { viewport: { width: 1280, height: 900 } };
ctxOpts.userAgent = (mobile ? devices['iPhone 13'].userAgent : undefined) || undefined;
if (authState && existsSync(authState)) ctxOpts.storageState = authState;
const context = await browser.newContext(ctxOpts);
const shotName = (url, suffix) => new URL(url).pathname.replace(/[^a-z0-9]+/gi, '-').replace(/^-|-$/g, '').slice(0, 60) + (suffix ? `-${suffix}` : '') || 'home';

while (queue.length) {
  if (pages.length >= L.maxPages) { stopReason = `reached the page cap (${L.maxPages})`; break; }
  if ((Date.now() - t0) / 60000 > L.timeBudgetMin) { stopReason = `reached the time budget (${L.timeBudgetMin} min)`; break; }
  if (L.quietStop && quiet >= L.quietStop) { stopReason = `${L.quietStop} pages in a row found no new issue type or page type`; break; }
  if (pages.length >= 6 && fails / pages.length > 0.3) { stopReason = 'more than 30% of pages failed to load (blocked or rate-limited)'; break; }

  const { url, depth } = queue.shift();
  if (blocked(url, r.disallow)) { skipped.robots++; continue; }
  const sec = section(url);
  if (!fixed.length && L.perSection && (perSectionCount[sec] || 0) >= L.perSection) { skipped.perSection++; continue; }
  perSectionCount[sec] = (perSectionCount[sec] || 0) + 1;

  const page = await context.newPage();
  const rec = { url, depth, title: '', status: null, error: null, violations: [], incomplete: [], passes: 0, checks: {}, shot: null };
  try {
    const resp = await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 45000 });
    rec.status = resp ? resp.status() : null;
    if (rec.status === 429 || rec.status === 403) throw new Error(`HTTP ${rec.status}`);
    await page.waitForTimeout(L.wait);
    rec.title = await page.title();

    if (!fixed.length) {
      const hrefs = await page.$$eval('a[href]', (as) => as.map((a) => a.href));
      for (const h of hrefs) {
        if (DOC_EXT.test(h)) documents.add(h);
        const n = normalise(h);
        if (!n || seen.has(n)) continue;
        seen.add(n);
        if (depth + 1 > L.maxDepth) { skipped.depth++; continue; }
        queue.push({ url: n, depth: depth + 1 });
      }
    }

    await page.addScriptTag({ content: axeSource });
    Object.assign(rec, await page.evaluate(async (tags) => {
      // eslint-disable-next-line no-undef
      const res = await axe.run(document, { runOnly: { type: 'tag', values: tags }, resultTypes: ['violations', 'incomplete'] });
      const slim = (v) => ({
        id: v.id, impact: v.impact, help: v.help, description: v.description, helpUrl: v.helpUrl, tags: v.tags, count: v.nodes.length,
        nodes: v.nodes.slice(0, 8).map((n) => ({ target: n.target.map(String).join(' '), html: n.html.slice(0, 300), summary: (n.failureSummary || '').slice(0, 400) })),
      });
      return { violations: res.violations.map(slim), incomplete: res.incomplete.map(slim), passes: res.passes.length };
    }, TAGS));

    // Screenshots: outline failing elements with numbered tags, one frame per page (capped),
    // plus a close-up of the first failing element for each rule (capped).
    if (shotsDir && rec.violations.length && pageShots < MAX_PAGE_SHOTS) {
      const legend = rec.violations.map((v, i) => ({ n: i + 1, rule: v.id }));
      await page.evaluate((vs) => {
        const st = document.createElement('style');
        st.id = '__a11y_st';
        st.textContent = '.__a11y_hit{outline:4px solid #d0021b!important;outline-offset:2px!important}.__a11y_tag{position:absolute;z-index:2147483647;background:#d0021b;color:#fff;font:700 14px/1 system-ui;padding:3px 6px;border-radius:3px;pointer-events:none}';
        document.head.appendChild(st);
        vs.forEach((v, i) => v.nodes.slice(0, 3).forEach((n) => {
          let el; try { el = document.querySelector(n.target); } catch { return; }
          if (!el) return;
          el.classList.add('__a11y_hit');
          const b = el.getBoundingClientRect(), t = document.createElement('span');
          t.className = '__a11y_tag'; t.textContent = String(i + 1);
          t.style.left = `${Math.max(0, b.left + scrollX)}px`; t.style.top = `${Math.max(0, b.top + scrollY - 20)}px`;
          document.body.appendChild(t);
        }));
      }, rec.violations);
      const h = await page.evaluate(() => document.documentElement.scrollHeight);
      const file = join(shotsDir, `${shotName(url)}.jpg`);
      await page.screenshot({ path: file, type: 'jpeg', quality: 55, fullPage: true, clip: { x: 0, y: 0, width: page.viewportSize().width, height: Math.min(h, 2200) } });
      rec.shot = { file, legend };
      pageShots++;
      for (const v of rec.violations) {
        if (crops >= MAX_CROPS || v.cropped) continue;
        const target = v.nodes[0] && v.nodes[0].target;
        if (!target) continue;
        try {
          const loc = page.locator(target).first();
          const box = await loc.boundingBox({ timeout: 1500 });
          if (!box || box.width < 4 || box.height < 4) continue;
          const pad = 24, vw = page.viewportSize().width;
          const clip = { x: Math.max(0, box.x - pad), y: Math.max(0, box.y - pad), width: Math.min(vw, box.width + pad * 2), height: Math.min(500, box.height + pad * 2) };
          const cf = join(shotsDir, `${shotName(url, v.id)}.jpg`);
          await page.screenshot({ path: cf, type: 'jpeg', quality: 70, fullPage: true, clip });
          v.crop = cf; crops++;
        } catch { /* element not screenshot-able (hidden, in iframe) — the report still has its HTML */ }
      }
      await page.evaluate(() => { document.getElementById('__a11y_st')?.remove(); document.querySelectorAll('.__a11y_tag').forEach((t) => t.remove()); document.querySelectorAll('.__a11y_hit').forEach((e) => e.classList.remove('__a11y_hit')); });
    }
    if (shotsDir && pages.length === 0 && !rec.shot) {
      const file = join(shotsDir, 'start.jpg');
      await page.screenshot({ path: file, type: 'jpeg', quality: 55 });
      rec.shot = { file, legend: [] };
    }

    if (!mobile) {
      await page.setViewportSize({ width: 320, height: 800 });
      await page.waitForTimeout(400);
      rec.checks.reflow = await page.evaluate(() => { const sw = document.documentElement.scrollWidth; return { scrollWidth: sw, viewport: 320, pass: sw <= 322 }; });
      await page.setViewportSize({ width: 1280, height: 900 });
    }

    await page.evaluate(() => document.activeElement && document.activeElement.blur && document.activeElement.blur());
    const stops = [];
    for (let i = 0; i < 12; i++) {
      await page.keyboard.press('Tab');
      const s = await page.evaluate(() => {
        const el = document.activeElement;
        if (!el || el === document.body) return null;
        const cs = getComputedStyle(el);
        const outline = cs.outlineStyle !== 'none' && parseFloat(cs.outlineWidth) > 0;
        const ring = cs.boxShadow && cs.boxShadow !== 'none';
        return { tag: el.tagName.toLowerCase(), text: (el.innerText || el.getAttribute('aria-label') || el.getAttribute('title') || '').trim().slice(0, 60), href: el.getAttribute('href') || '', visibleFocus: !!(outline || ring) };
      });
      if (s) stops.push(s);
    }
    const first = stops[0];
    rec.checks.keyboard = {
      stops: stops.length,
      skipLink: !!(first && /^#/.test(first.href) && /skip|main|content/i.test(first.text + first.href)),
      noVisibleFocus: stops.filter((s) => !s.visibleFocus).map((s) => `${s.tag} "${s.text}"`).slice(0, 6),
      firstStop: first ? `${first.tag} "${first.text}"` : null,
    };
  } catch (e) {
    rec.error = String(e.message || e).slice(0, 300);
    fails++;
  }
  pages.push(rec);
  await page.close();

  const newRules = rec.violations.map((v) => v.id).filter((id) => !rulesSeen.has(id));
  const t = pageType(url), newType = !typesSeen.has(t);
  newRules.forEach((id) => rulesSeen.add(id));
  typesSeen.add(t);
  quiet = newRules.length || newType ? 0 : quiet + 1;
  process.stderr.write(`[${pages.length}] ${url} — ${rec.error ? 'ERROR ' + rec.error.slice(0, 60) : rec.violations.length + ' rule failures'}${newRules.length ? ` (+${newRules.length} new)` : ''}\n`);
  if (queue.length) await new Promise((res) => setTimeout(res, L.delay));
}
await browser.close();

const result = {
  tool: { name: 'access-atlas/scan.mjs', engine: 'axe-core', tags: TAGS, mobileEmulation: mobile },
  target: start, scannedAt: new Date().toISOString(), minutes: +((Date.now() - t0) / 60000).toFixed(1),
  scope: { mode: fixed.length ? 'listed URLs' : 'crawl', limits: L, includePaths: includes, stopReason, skipped, notYetScanned: queue.length, pageTypesSeen: typesSeen.size },
  pagesScanned: pages.length, pagesDiscovered: seen.size, documentsFound: [...documents].slice(0, 200), pages,
};
writeFileSync(out, JSON.stringify(result, null, 2));
console.log(`wrote ${out}: ${pages.length} pages, ${pages.reduce((a, p) => a + p.violations.length, 0)} rule failures, ${documents.size} documents. Stopped: ${stopReason}. ${queue.length} discovered pages not scanned.`);
