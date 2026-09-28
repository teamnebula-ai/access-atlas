# Access Atlas

**Accessibility audits graded against the law that actually applies.** Give it a public-sector
website. It works out who owns it (a county, a city, a state agency, a university), which
accessibility law binds that owner, and grades the site against that standard. Then it tells you
what fails, what to fix first, what was never tested, and hands you a prompt that gets an AI
coding agent to fix it all.

Government sites have to meet accessibility standards: ADA Title II and Section 508 in the US,
a state law or policy in most states, the Web Accessibility Directive in the EU, and similar
rules elsewhere. The standards are public. What's hard is knowing which one applies to *you*.
A Texas county is bound by ADA Title II, not the Texas rule for state agencies. Then you need
the version, the deadline, and which of your failures actually break it. Access Atlas keeps a
researched, sourced registry of those rules, and every finding points back to them.

## Example: a county website

```text
/access-atlas:audit https://www.traviscountytx.gov
```

1. **Owner:** Travis County, a county in Texas (from the domain and the page title). The agent
   confirms it with you and asks whether the county serves 50,000+ people.
2. **Standards:** ADA Title II binds counties, so it grades against **WCAG 2.1 AA**, deadline
   April 26, 2027. The Texas state rule is listed as *reviewed, not binding* because it covers
   state agencies and public universities.
3. **Scope:** it sizes the site, then asks how deep to go: quick, standard, full or named sections.
4. **Report:** the scorecard says *"Graded against WCAG 2.1 Level AA, the standard required of Travis County
   (county, TX, US) by: ADA Title II…"*, with the grade, screenshots, findings and a fix prompt.
5. **Next time:** a repeat audit shows what was fixed, what's new and what's still failing.

## The skills

Installed as a Claude Code plugin, each is a command. Any agent can follow them as files.

| Skill | Use it to |
|---|---|
| `/access-atlas:audit` | run the whole audit, start to finish |
| `/access-atlas:scope` | find out who owns a site, which laws bind them, how big the site is |
| `/access-atlas:scan` | run the automated scan with screenshots and stop rules |
| `/access-atlas:check` | walk the manual checks (keyboard, screen reader, zoom), or audit a mobile app |
| `/access-atlas:report` | render and publish the scorecard, compare with the last run |
| `/access-atlas:fix` | fix the findings in the site's code, then re-audit to prove it |
| `/access-atlas:laws` | ask what a state or country requires, or add a missing one |

You don't need to type them: ask for "an accessibility audit of our county site" and the right
skill picks it up.

## What you get

A self-contained report (one HTML file, also publishable as a shareable page):

- **Scorecard**: grade and score, the standard it was graded against and the law that requires
  it, legal failures, critical issues, pages affected, how many WCAG criteria were actually
  tested, and days to the owner's next deadline.
- **Since the last audit**: fixed, new and still failing, with a warning when the scope changed.
- **What we saw**: screenshots with every failing element outlined and numbered.
- **Findings**: each mapped to its WCAG success criterion, explained in plain language, with a
  close-up and the laws that require it. Failures no binding law requires are marked best practice.
- **What the law requires**: each law marked *Binding*, *May apply* or *Reference only*, with
  deadlines, exceptions, duties and sources.
- **Coverage**: every WCAG A/AA criterion as fails, needs review, passes or **not tested**. It
  never reports "compliant".
- **Audit trail**: every decision (owner, standards, scope) with who made it and why, and the run log.
- **Fix prompt**: copy it into Claude Code, Cursor or Copilot in the site's repository.

## Every run is recorded

Each audit gets a run folder, `a11y-audits/<site>/<date_time>/` (or `$ACCESS_ATLAS_HOME`):

| File | What's in it |
|---|---|
| `run.json` | decisions (value, why, by user or agent, when), step status, outputs with checksums |
| `log.jsonl` | append-only log of every step and every page scanned |
| `plan.json`, `scan.json`, `tasks.json`, `manual.json` | the inputs to the report |
| `<site>.html`, `.fix-prompt.md`, `.findings.json` | the outputs |
| `compare.json` | the difference from the previous run |

`engine/ledger.py history a11y-audits/<site>` lists past runs; `ledger.py open <url> --carry`
starts a new one with the same owner and standards.

## The registry

90 jurisdictions and counting, one JSON file each under [`data/registry/`](data/registry):

| Where | Coverage |
|---|---|
| United States | ADA Title II (with the April 2026 deadline extension), Section 508, ADA Title III, public higher ed, **all 50 states, DC and 5 territories**, 8 major cities |
| Europe | EU Web Accessibility Directive, European Accessibility Act, EN 301 549, Germany, France, Netherlands, Ireland, Spain, Italy, Sweden, Denmark, UK |
| Elsewhere | Canada (federal, Ontario, Québec), Australia, New Zealand, Japan, Israel, India, Brazil, South Korea |

Every entry records **who it covers**, the sources actually read, the research date, and a
confidence level. Low confidence means "verify before quoting", and the report shows it.
**Your country or city missing? [Add it](CONTRIBUTING.md#add-a-jurisdiction). It's one file.**

## Install

**Claude Code (plugin):**

```text
/plugin marketplace add <owner>/access-atlas
/plugin install access-atlas@access-atlas
```

**Any other agent** (Codex, Cursor, Copilot, Gemini CLI, Aider, Windsurf, Cline, an Agent SDK
app): clone the repository. [`AGENTS.md`](AGENTS.md) tells any agent how to use it, and tools
that read `AGENTS.md`, `CLAUDE.md` or `GEMINI.md` pick it up when you work in the repo. To use
the skills from anywhere, `./install.sh [skills-dir]` links them into your agent's skills folder.

**No agent at all** (Node 18+, Python 3.9+):

```bash
engine/ensure-deps.sh                       # once: Playwright + axe-core into ~/.cache/access-atlas
engine/audit.sh https://example.gov --scope quick
```

`audit.sh` detects the owner (override with `--org`, `--entity`, `--country`, `--region`),
sizes the site, and on anything over 40 pages without `--scope` it prints the options and stops,
so you choose. Add `--urls` for key task pages (pay a bill, apply for a permit), which are always
scanned.

## Large sites

It sizes the site before scanning, and you choose how deep to go. Every scan stops at the first
limit it hits: page cap, link depth, pages per folder, time budget, **saturation** (20 pages in a
row with nothing new), or signs of being blocked. The report says which one stopped it and how
many pages were left. It honours robots.txt and paces its requests.

## Limits

- Automated testing finds roughly a third of accessibility barriers. The rest need a person:
  see [`guides/manual-checks.md`](guides/manual-checks.md) and, for native apps,
  [`guides/mobile.md`](guides/mobile.md).
- Owner detection is a guess from public signals. It's recorded as unconfirmed until a person confirms it.
- **Not legal advice and not a conformance statement.** Confirm interpretation with counsel or
  the jurisdiction's accessibility office.
- PDFs and Office documents are listed, not scanned.

## Contributing

Law changes, new jurisdictions, fixes to the scanner or report: see [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE).
