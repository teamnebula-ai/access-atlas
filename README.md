# Access Atlas

**Accessibility audits mapped to the law.** Point it at a public-sector website. It tells you
what fails, **which law requires the fix**, what to fix first, what was never tested, and hands
you a prompt that gets an AI coding agent to fix it all.

Government sites have to meet accessibility standards: ADA Title II and Section 508 in the US,
a state law or policy in most states, the Web Accessibility Directive in the EU, and similar
rules elsewhere. The standards are public. What's hard is knowing which version applies to
*you*, by when, and which of your failures actually break it. Access Atlas keeps a researched,
sourced registry of those rules, and every finding in its report points back to them.

## What you get

A self-contained report (one HTML file, also shareable as a Claude Artifact):

- **Scorecard**: a grade and score, legal failures, critical issues, pages affected, how many
  WCAG criteria were actually tested, and days to the next deadline.
- **What we saw**: screenshots with every failing element outlined and numbered.
- **Findings**: each one mapped to its WCAG success criterion, explained in plain language, with
  a close-up of the element and the laws that require it. Failures no selected law requires
  are marked best practice, not a legal gap.
- **What the law requires**: statutes, deadlines, exceptions, procurement duties and sources
  for each jurisdiction.
- **Coverage**: every WCAG A/AA criterion as fails, needs review, passes or **not tested**. It
  never reports "compliant".
- **Fix prompt**: copy it into Claude Code, Cursor or Copilot in the site's repo.

## The registry

90 jurisdictions and counting, one JSON file each under
[`skills/access-atlas/registry/`](skills/access-atlas/registry):

| Where | Coverage |
|---|---|
| United States | ADA Title II (with the April 2026 deadline extension), Section 508, ADA Title III, public higher ed, **all 50 states, DC and 5 territories**, 8 major cities |
| Europe | EU Web Accessibility Directive, European Accessibility Act, EN 301 549, Germany, France, Netherlands, Ireland, Spain, Italy, Sweden, Denmark, UK |
| Elsewhere | Canada (federal, Ontario, Québec), Australia, New Zealand, Japan, Israel, India, Brazil, South Korea |

Every entry records the sources actually read, the research date, and a confidence level. Low
confidence means "verify before quoting", and the report shows that label.
**Your country or city missing? [Add it](CONTRIBUTING.md#add-a-jurisdiction). It's one file.**

## Install

It's an [Agent Skill](https://docs.claude.com/en/docs/claude-code/skills): a folder of
instructions and scripts that Claude Code (and other skill-aware agents) load on demand.

```bash
git clone https://github.com/iankiku/access-atlas && cd access-atlas
./install.sh                     # symlinks the skill into ~/.claude/skills (or $CLAUDE_CONFIG_DIR/skills)
skills/access-atlas/scripts/ensure-deps.sh   # Playwright + axe-core into ~/.cache/access-atlas
```

Then ask: *"Run an accessibility audit on example.gov for a county in Colorado."*

Scripts run without an agent too (Node 18+, Python 3.9+):

```bash
cd skills/access-atlas/scripts
node scan.mjs https://example.gov --plan                       # size the site first
node scan.mjs https://example.gov --max-pages 50 --out scan.json
python3 render.py --jurisdictions us-co --scan scan.json --org "City of Example" --product example.gov --out report.html
```

## Large sites

It sizes the site before it scans (`--plan`), and the agent asks you how deep to go: quick,
standard, full, or specific sections. Every scan stops at the first limit it hits: page cap,
link depth, pages per folder, time budget, **saturation** (20 pages in a row with nothing new),
or signs of being blocked. The report says which one stopped it. It honours robots.txt and
paces its requests.

## Limits

- Automated testing finds roughly a third of accessibility barriers. The rest need a person:
  the skill includes the manual checklist ([`manual-checks.md`](skills/access-atlas/references/manual-checks.md))
  and a mobile-app guide ([`mobile.md`](skills/access-atlas/references/mobile.md)).
- **Not legal advice and not a conformance statement.** Confirm interpretation with counsel or
  the jurisdiction's accessibility office.
- PDFs and Office documents are listed, not scanned.

## Contributing

Law changes, new jurisdictions, fixes to the scanner or report: see [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE). Started by Ian Kiku at Team Nebula.
