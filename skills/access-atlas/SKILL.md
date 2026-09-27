---
name: access-atlas
description: "Audit a public-sector website or mobile app for digital accessibility against the laws that actually bind it (ADA Title II, Section 508, every US state plus DC and territories, major cities, the EU Web Accessibility Directive and EN 301 549, the UK, Canada, Australia and more) and produce a scorecard report with annotated screenshots, what fails, which law requires it, what to fix first, what was never tested, and a ready-to-paste prompt for an AI coding agent to fix it all. Sizes large sites first and asks how deep to go. Use when someone says \"/access-atlas\", \"accessibility audit\", \"a11y audit\", \"is this site ADA compliant\", \"check WCAG\", \"Section 508 check\", \"Title II deadline\", \"audit this city/county/state site\", \"VPAT prep\", \"what accessibility law applies to us\", or wants a remediation list for a government site or app."
---

# Access Atlas — accessibility audits mapped to the law

> **Clarify first.** Two things decide everything else; ask for whichever is missing, in one
> question: **what** to audit (a URL, or a mobile app and its platforms) and **whose rules**
> apply (the organization and where it sits — "a county in Colorado", "a federal agency", "an
> Irish council"). If the user gives only a URL, infer the jurisdiction from the domain and the
> site's footer or about page, say what you inferred, and continue. Never scan behind a login
> without a test account, and never with a real person's credentials.

Public bodies know WCAG exists; they rarely know which version, which law, which deadline, or
which of their failures actually matter legally. Access Atlas answers all four in a report a
non-engineer can act on, and hands engineers a prompt that fixes it.

## What you produce

| File | For |
|---|---|
| `<name>.html` | the full report: scorecard, annotated screenshots, findings, law, coverage, fix prompt. Self-contained; emailed, printed, opened offline |
| `<name>.artifact.html` | the same page for the Artifact tool (it adds its own skeleton), the shareable link |
| `<name>.fix-prompt.md` | the fix prompt on its own: paste into Claude Code, Cursor or Copilot in the site's repo |
| `<name>.findings.json` | score, per-page scores, coverage, one row per finding: feed a tracker |

Report order: **scorecard** (grade and score, legal failures, critical count, pages affected,
criteria tested, days to deadline, home-page screenshot) → short answer → what to fix first →
**what we saw** (screenshots with failing elements outlined and numbered) → every finding with
its WCAG criterion, a plain-language meaning, a close-up of the element, and which law requires
it → page scores → what each law requires → coverage of every A/AA criterion → linked documents
→ method, including why the scan stopped → **fix prompt** with a copy button.

Put output in the user's working docs folder (e.g. `docs/a11y/<site>/<YYYY-MM-DD>/`), never
inside the repo being audited unless they ask.

## The run

Scripts sit beside this file in `scripts/`. Dependencies install into `~/.cache/access-atlas`,
never into the user's project: run `scripts/ensure-deps.sh` once per machine.

### 1. Resolve the jurisdictions

```bash
python3 scripts/jurisdictions.py list colorado          # find ids
python3 scripts/jurisdictions.py resolve us-co           # → us-co,us-ada-title-ii (parents come along)
python3 scripts/jurisdictions.py show us-ada-title-ii    # read it before you quote it
```

Pick by **who owns the site**, not who visits it:
- US state or local government, public university, special district → the state entry (+ city
  entry if there is one). ADA Title II comes along automatically.
- US federal agency, or a contractor building for one → `us-federal-508`.
- EU public body → the country entry (pulls in `eu-wad`). A private company selling into the
  EU → `eu-eaa`.
- Unsure → include both; the report shows each law separately.

No entry for the jurisdiction? Don't invent one. Run with the nearest parent, say so in the
scope note, and suggest the user add it (see CONTRIBUTING.md; it is one JSON file). Check each
entry's `confidence` and `as_of`: confirm a **low** entry against its source before quoting it.

### 2. Size the site, then ask how deep to go

Never start a big crawl blind. First, size it (plain HTTP, no browser, about a minute):

```bash
node scripts/scan.mjs https://example.gov --plan --out plan.json
```

It reads robots.txt and the sitemap (or does a quick link crawl), then prints the page count,
the largest sections, and three ready-made scopes with time estimates. **Then ask the user**
(AskUserQuestion when available; otherwise a short numbered question), showing the real
numbers from the plan:

- **Quick**: ~25 pages, 2 levels deep, 3 per folder. A first look in a few minutes.
- **Standard** (recommended for most sites): up to 150 pages, 5 per folder, sitemap included.
  Covers every kind of page without scanning 900 near-identical news posts.
- **Full**: every discovered deep link, with a time budget. For a formal audit or a small site.
- **Specific sections or task pages**: `--include-path /services,/permits`, or `--urls`
  with the pages the public actually uses (pay a bill, apply, register, find a meeting).

Always also ask which **key tasks** matter most; those pages get scanned by URL, whatever the
crawl scope. Small site (under ~40 pages)? Skip the question and scan it all; say so.

### 3. Scan: it knows when to stop

```bash
node scripts/scan.mjs https://example.gov --max-pages 150 --max-depth 4 --per-section 5 --sitemap --out scan.json
node scripts/scan.mjs https://example.gov --urls https://example.gov/pay,https://example.gov/permits/apply --out tasks.json
```

Every run stops at the **first** of these, and records which one in the report:

| Stop rule | Flag (default) | Why |
|---|---|---|
| Page cap | `--max-pages` (25) | the scope the user chose |
| Link depth | `--max-depth` (3) | deep archives rarely add new templates |
| Per folder | `--per-section` (5) | 900 articles in `/news/` share one template; 5 find its bugs |
| Time budget | `--time-budget` minutes (15) | a scan the user is waiting on must end |
| Saturation | `--quiet-stop` (20) | 20 pages in a row with no new issue type and no new kind of page: more pages won't change the report |
| Being blocked | automatic | more than 30% of pages failing to load, or a 403/429, means stop, not retry |

It also honours robots.txt, waits `--delay` ms between pages (750), never submits forms, and
takes screenshots (up to 10 annotated pages and 20 close-ups; `--no-shots` to skip). Run one
scan at a time against a site: this is someone's production service.

If the scan stopped on the page cap or time budget with many pages left, say so plainly in the
hand-back and offer a deeper run. Don't silently extend it.

### 4. Manual checks: what makes it an audit

A scanner catches about a third of failures. Walk `references/manual-checks.md` against the key
tasks and record results in `manual.json` (format in that file). With browser tools available,
do the keyboard and zoom checks yourself; the screen-reader pass needs a person, or it stays
"not tested". **Never mark a criterion `pass` that nobody checked.**

A native app can't be scanned: use `references/mobile.md`, and everything goes in `manual.json`.

### 5. Render, publish, look

```bash
python3 scripts/render.py --jurisdictions us-co --scan scan.json,tasks.json --manual manual.json \
  --org "City of Example" --product "example.gov" --kind website \
  --scope "Standard scan: 150 pages, 5 per folder, plus pay-a-bill and permit flows; PDFs not scanned" \
  --out docs/a11y/example-gov/2026-09-27/example-gov.html
```

Publish `<name>.artifact.html` with the Artifact tool when it's available (icon `checklist`),
then open it and look. The disk copy is the record, and the link is for sharing. Never
hand-edit a rendered report: change the inputs and render again.

### 6. Hand it back

Answer first, in one line: grade, legal failures, next deadline ("C (72/100): 9 issues break
ADA Title II, 3 of them critical; deadline April 26, 2027"). Then the top fixes, what was not
tested, why the scan stopped, the link and the file paths. Offer the fix prompt for their
repo. If asked to file tickets: one per finding from `findings.json`, only into a tracker the
user named.

## Rules that keep it honest

- **Not a conformance statement, not legal advice.** The report says so on its face. Never tell
  anyone they are "compliant"; say what was tested and what failed.
- **The score measures only what a scanner sees.** Always show it next to "criteria tested".
  A 95 with 13/50 tested is not a clean bill of health.
- **Untested is not passing.** "No failures found (automated)" only for criteria a scanner fully
  decides.
- **Legal vs best practice stays separate.** A WCAG 2.2 failure is not a legal gap for a body
  bound to 2.1.
- **Cite the source, date the claim.** Deadlines move: DOJ pushed ADA Title II back a year in
  April 2026. Quote the registry entry and its source, not memory.
- **No personal data in reports.** Describe the page and the element, never a member of the
  public's name, case or account. Screenshots of logged-in pages need the user's OK.
- **Documents count.** PDFs and Office files fall under the same rules; the report lists them and
  says they were not scanned.

## The registry

`registry/<country>/[...]/<id>.json`: one jurisdiction per file, with the standard, statutes and
policy URLs, deadlines, exceptions, other duties (accessibility statement, coordinator,
procurement ACR/VPAT), mobile coverage, sources, research date and confidence.

```bash
python3 scripts/jurisdictions.py check    # schema, >1 year stale, low confidence, unmapped standards
```

When a law changes: edit the file, set `as_of` to today, add the source you actually opened to
`sources`, and never raise `confidence` above what a primary source supports. To add a
jurisdiction: copy a sibling file, set `parent` to the law it inherits (a US state →
`us-federal`, an EU country → `eu-wad`), and run `check`.
