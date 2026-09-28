---
name: audit
description: "Run a full accessibility audit of a website or app, mapped to the laws that bind whoever owns it: work out the owner and its legal standard, size the site and agree the scope, scan, check by hand, and deliver a scorecard report with screenshots, a fix prompt, and an audit trail. Use when someone says \"audit this site\", \"accessibility audit\", \"a11y audit\", \"is this ADA compliant\", \"check WCAG on …\", \"Section 508 check\", \"how accessible is <county/city/agency> website\", or gives a government URL and asks about accessibility."
argument-hint: "<url> [who owns it, e.g. \"Travis County, Texas\"]"
---

# Audit — the whole run, start to finish

> **Clarify first.** You need a URL (or an app) and enough to know who owns it. Everything else is
> found or asked for along the way. Don't scan anything behind a login without a test account the
> user gave you.

Engine and data live at the plugin root: `E=${CLAUDE_PLUGIN_ROOT}/engine`. (Outside Claude Code,
use the repository root; see its `AGENTS.md`.) First time on a machine: `$E/ensure-deps.sh`.

Every run lives in a **run folder** that records what was decided, by whom and why:

```bash
RUN=$(python3 $E/ledger.py open <url>)            # add --carry to reuse last run's owner and standards
```

Default home is `./a11y-audits/<site>/<date_time>/`; set `ACCESS_ATLAS_HOME` to put it elsewhere.
Record every decision with `ledger.py decide`, and close each step with `ledger.py step <run> <step> done`.
The report prints this trail, so an auditor can see how every call was made.

## The steps (each is its own skill, and can be run alone)

| # | Step | Skill | Ends with |
|---|---|---|---|
| 1 | Who owns the site, which laws bind it, population | **scope** | decisions `owner`, `entity`, `country`, `region`, `place`, `population`, `standards` |
| 2 | Size the site and agree how deep to go | **scope** | decision `scope`, plus `key_tasks` |
| 3 | Scan the agreed pages, stopping on the rules | **scan** | `scan.json` (+ `tasks.json`) in the run |
| 4 | Manual checks a scanner can't do | **check** | `manual.json`, or step `manual` skipped with a reason |
| 5 | Scorecard report, published, handed back | **report** | report files attached, steps `render` / `publish` / `handback` done |
| — | Fix the issues in the site's code, then re-audit | **fix** | a new run compared to this one |
| — | Look up or add a law | **laws** | registry entry |

Run them in order, in this turn, until the report is handed back. Stop only for the questions
the steps say to ask (the owner if it can't be confirmed from evidence, and the scope on a large
site). If a step fails, record `failed` with the reason, tell the user plainly, and carry on with
what can still be delivered. A report with fewer pages beats no report.

**Repeat audits:** `ledger.py open <url> --carry` reuses the owner and standards (logged as
carried), and the report shows what was fixed, what's new and what's still failing since the last
run. Use the same scope as last time if the goal is to measure progress.

## Rules that hold across every step

- Never call a site "compliant". The report measures and it doesn't certify. It is not legal advice.
- Untested is not passing. Legal failures and best-practice gaps stay separate.
- Laws, versions and deadlines come from the registry entry, with its date and source, never from
  memory. They change: US ADA Title II deadlines moved in April 2026.
- The standard is decided by **who owns the site**, not by where it is. A county in Texas is bound
  by ADA Title II; the Texas state rule covers state agencies. The **scope** skill works this out.
- One scan at a time per site; respect robots.txt; never submit forms; no personal data in reports.
- Never change the site's code during an audit. Fixing is the **fix** skill, when asked.
