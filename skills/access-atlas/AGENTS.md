# Access Atlas: instructions for any AI agent

You are an AI agent (Claude Code, Codex, Cursor, Copilot, Gemini CLI, Aider, Windsurf, Cline,
an Agent SDK app, or anything else that can run shell commands and read files). This folder
lets you run an **accessibility audit of a website or app, mapped to the laws that require
it**, and hand back a scorecard report plus a prompt that fixes the issues.

The full procedure is in [`SKILL.md`](SKILL.md) in this folder. **Read it and follow it.**
This file tells you how to do that in whatever harness you are running in.

## When to use it

Someone asks for an accessibility audit, an "a11y audit", ADA / Section 508 / WCAG compliance,
a Title II deadline, what accessibility law applies to their organization, or a remediation
list for a government (or any public-facing) website or mobile app.

## What you need

- A shell, **Node 18+** and **Python 3.9+**. No API keys, no accounts, no network services
  besides the site being audited.
- One-time setup: `scripts/ensure-deps.sh` (installs Playwright + axe-core into
  `~/.cache/access-atlas`, never into the user's project). On Windows without bash, run the
  same steps by hand: in a folder `~/.cache/access-atlas`, run `npm init -y`,
  `npm i playwright axe-core`, then `npx playwright install chromium`.

All paths below are relative to this folder.

## The procedure, in one screen

1. **Clarify** what to audit (URL or app) and who owns it (which country, state or city).
2. **Pick jurisdictions:** `python3 scripts/jurisdictions.py list <text>` then `resolve <ids>`.
3. **Size the site:** `node scripts/scan.mjs <url> --plan --out plan.json`.
4. **Ask the user how deep to go** (quick / standard / full / specific sections), plus which key
   tasks matter. Show the page counts and time estimates from the plan.
5. **Scan** with the chosen flags (printed by `--plan`), plus `--urls` for the key task pages.
6. **Manual checks** from `references/manual-checks.md` (or `references/mobile.md` for native
   apps), recorded in `manual.json`. Anything nobody checked stays "not tested".
7. **Render:** `python3 scripts/render.py --jurisdictions <ids> --scan scan.json[,tasks.json] [--manual manual.json] --org "<org>" --product "<site>" --out <dir>/<name>.html`.
8. **Hand back:** grade and score, legal failures, next deadline, top fixes, what wasn't tested,
   why the scan stopped, and the file paths. Offer `<name>.fix-prompt.md` for the site's repo.

No agent at all? `scripts/audit.sh` runs steps 3, 5 and 7 in one command (see its header).

## Harness differences: how to adapt

| SKILL.md mentions | If your harness has it | If it doesn't |
|---|---|---|
| AskUserQuestion (multiple-choice prompt) | use it for the scope question | ask in chat as a short numbered list and wait for the answer. **Don't pick a scope for a site over ~40 pages without asking** |
| Artifact tool (hosted shareable page) | publish `<name>.artifact.html` | skip it. The `<name>.html` file is the deliverable: give its path, and the user can open it in any browser |
| Browser tools (Playwright MCP, Chrome, computer use) | do the keyboard and zoom manual checks yourself | leave those criteria "not tested" and list them for a person |
| Background tasks | run long scans in the background | run in the foreground; `--time-budget` keeps it bounded |
| Sub-agents | not needed | not needed |

Long scans: `--time-budget` (minutes) always bounds a run, so a harness with a command timeout
should pass a budget below that timeout (e.g. 8 minutes under a 10-minute limit).

## Rules you must keep, whatever the harness

- Never call a site "compliant". Report what was tested and what failed. The report says it is
  not a conformance statement or legal advice; don't contradict it.
- Never mark a WCAG criterion as passing when nobody checked it.
- Keep legal failures and best-practice gaps separate. The report does this; don't merge them
  in your summary.
- Quote deadlines and laws from the registry entry (with its date and source), not from memory.
  They change. The US ADA Title II dates moved in April 2026.
- Don't scan behind a login without a test account the user gave you. Don't submit forms. Run
  one scan at a time against a site.
- Don't put personal data (names, case numbers, account details) in reports or notes.
- Never modify the site's code during an audit. Fixing is a separate step, using the fix
  prompt, and only when the user asks.
