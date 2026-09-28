# AGENTS.md

Instructions for AI agents working **in this repository**, whether you are using the tool or
changing it.

## Using the tool (running an accessibility audit)

Read [`skills/access-atlas/AGENTS.md`](skills/access-atlas/AGENTS.md). It explains how any
agent, in any harness, runs the audit, and it points to the full procedure in
[`skills/access-atlas/SKILL.md`](skills/access-atlas/SKILL.md).

## Changing the tool

Layout:

```
.claude-plugin/          Claude Code plugin + marketplace manifests
commands/audit.md        /access-atlas:audit slash command (plugin)
skills/access-atlas/     the skill: SKILL.md (procedure), AGENTS.md (any-harness guide)
  scripts/               scan.mjs (Node + Playwright), render.py + jurisdictions.py (Python stdlib), audit.sh, tests
  references/            wcag.json (criteria catalog), manual-checks.md, mobile.md
  registry/<cc>/…/<id>.json   one jurisdiction per file
```

Before every commit, run all three. Each must pass:

```bash
python3 skills/access-atlas/scripts/jurisdictions.py check
python3 -m unittest discover -s skills/access-atlas/scripts -p "test_*.py"
node --check skills/access-atlas/scripts/scan.mjs
```

Rules:
- **Registry changes need a source someone can open.** Follow [CONTRIBUTING.md](CONTRIBUTING.md).
  Never raise `confidence` above what a primary source supports, and never invent a citation.
- **`render.py` and `jurisdictions.py` stay Python standard library only.** `scan.mjs`'s only
  dependencies are Playwright and axe-core, installed to `~/.cache/access-atlas`.
- **Behaviour change → a test that fails without it.**
- **The report must pass its own scan** with 0 violations after any template change.
- **Keep the skill harness-neutral.** Anything specific to one tool (AskUserQuestion, the
  Artifact tool) must say what to do when it isn't there. The adaptation table lives in
  `skills/access-atlas/AGENTS.md`.
- **Bump the version** in both `.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json`
  when you release.
- No personal data, credentials, or real people's details in fixtures, examples or sample output.
