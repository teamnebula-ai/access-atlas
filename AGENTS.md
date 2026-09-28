# AGENTS.md

Access Atlas runs accessibility audits of websites and apps, **graded against the law that binds
whoever owns them**, and hands back a scorecard report and a prompt that fixes what it found.

This file is for any AI agent: Claude Code, Codex, Cursor, GitHub Copilot, Gemini CLI, Aider,
Windsurf, Cline, an Agent SDK app, or anything else that can run shell commands and read files.
`CLAUDE.md` and `GEMINI.md` import it.

## Using it: running an audit

The procedures are skills in `skills/<name>/SKILL.md`. Read the one that matches the request and
follow it. Start with **audit** for a full run; it calls the others in order.

| Skill | What it does |
|---|---|
| [`audit`](skills/audit/SKILL.md) | The whole run: owner → standards → scope → scan → checks → report |
| [`scope`](skills/scope/SKILL.md) | Who owns the site, which laws bind them, how big it is, how deep to go |
| [`scan`](skills/scan/SKILL.md) | Automated WCAG scan with screenshots and stop rules |
| [`check`](skills/check/SKILL.md) | Manual checks (keyboard, screen reader, zoom); native mobile apps |
| [`report`](skills/report/SKILL.md) | Scorecard report, publish, hand back |
| [`fix`](skills/fix/SKILL.md) | Fix the findings in the site's code, then re-audit and compare |
| [`laws`](skills/laws/SKILL.md) | Look up, add or update a jurisdiction in the registry |

**Paths.** Skills write `${CLAUDE_PLUGIN_ROOT}/engine/...`. Claude Code fills that in when the
repo is installed as a plugin. Anywhere else, it means **the root of this repository**:
substitute the path, or `export CLAUDE_PLUGIN_ROOT=<repo root>` once in your shell.

**Needs:** a shell, Node 18+, Python 3.9+. No API keys or accounts. Once per machine:
`engine/ensure-deps.sh` (installs Playwright and axe-core into `~/.cache/access-atlas`, never
into anyone's project). On Windows without bash: in `~/.cache/access-atlas` run `npm init -y`,
`npm i playwright axe-core`, `npx playwright install chromium`.

**Every run is recorded.** `engine/ledger.py` keeps a run folder per audit
(`./a11y-audits/<site>/<date_time>/`, or `$ACCESS_ATLAS_HOME`) with the decisions made and why
(`run.json`), an append-only log (`log.jsonl`), and the outputs with their hashes. The report
prints this as its audit trail and compares against the previous run.

### Adapting to your harness

| A skill mentions | If you have it | If you don't |
|---|---|---|
| A multiple-choice question (AskUserQuestion) | use it for the scope question | ask in chat as a short numbered list and wait. **Never pick a scope for a site over ~40 pages without asking** |
| Publishing an artifact (a hosted page) | publish `<site>.artifact.html` | the `<site>.html` file is the deliverable; give its path |
| Browser tools (Playwright MCP, Chrome, computer use) | do the keyboard and zoom checks yourself | leave them "not tested" and list them for a person |
| Background tasks | run long scans in the background | run in the foreground; `--time-budget` bounds it |

A harness with a command timeout should pass `--time-budget` below it (8 minutes under a
10-minute limit). No agent at all? `engine/audit.sh <url> --scope quick` runs the whole
automated pass in one command.

### Rules, whatever the harness

- Never call a site "compliant". Never mark a criterion passing when nobody checked it.
- Grade against the laws that bind the **owner** (a county, a state agency, a university), as
  the `scope` skill works out. Quote laws and deadlines from the registry, never from memory.
- Keep legal failures and best-practice gaps separate.
- No scanning behind a login without a test account the user provided. No form submissions.
  One scan at a time per site. No personal data in reports or notes.
- Never change a site's code during an audit. That's the `fix` skill, when asked.

## Changing it: working on this repository

```
.claude-plugin/     plugin.json + marketplace.json (Claude Code plugin)
skills/<name>/      SKILL.md per skill (audit, scope, scan, check, report, fix, laws)
engine/             scan.mjs + robots.mjs (Node, Playwright + axe-core)
                    render.py, jurisdictions.py, identify.py, ledger.py (Python stdlib only)
                    audit.sh (no-agent runner), ensure-deps.sh, tests/
data/registry/<cc>/…/<id>.json   one jurisdiction per file;  data/wcag.json   criteria catalog
guides/             manual-checks.md, mobile.md
evals/              plugin evals: claude plugin eval . --allow-tools Bash [--tag offline]
```

Before every commit, all of these must pass:

```bash
python3 engine/jurisdictions.py check
python3 -m unittest discover -s engine/tests -p "test_*.py"
node --check engine/scan.mjs && node engine/tests/robots.test.mjs
bash -n install.sh engine/audit.sh engine/ensure-deps.sh
```

- **Registry changes need a source someone can open.** See [CONTRIBUTING.md](CONTRIBUTING.md).
  Never raise `confidence` above what a primary source supports; never invent a citation.
- **Python stays standard library only.** The scanner's only dependencies are Playwright and axe-core.
- **Behaviour change → a test that fails without it.** The report must pass its own scan with
  0 violations after any template change.
- **Skills stay harness-neutral.** Anything specific to one tool says what to do without it.
- **No names, emails or machine paths** of any contributor in code, fixtures or sample output.
  Use `${CLAUDE_PLUGIN_ROOT}`, relative paths and environment variables.
- **Release:** bump the version in `.claude-plugin/plugin.json` and `marketplace.json`.
