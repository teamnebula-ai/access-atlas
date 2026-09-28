---
name: report
description: "Render the Access Atlas scorecard report from a run: grade and score, the standard it was graded against and which law requires it, annotated screenshots, findings with legal mapping, coverage, audit trail, comparison with the last run, and a copy-ready fix prompt; then publish it and hand back a summary. Use when someone says \"make the report\", \"render the scorecard\", \"publish the audit\", \"what did the audit find\", \"compare with last time\", or as step 5 of an audit."
argument-hint: "<run folder>"
---

# Report — the scorecard, and the hand-back

`E=${CLAUDE_PLUGIN_ROOT}/engine`.

```bash
python3 $E/render.py --run $RUN
```

It reads the run's decisions (owner, type, place, population, standards, scope), the scans and
`manual.json` in the folder, and writes into the run:

| File | For |
|---|---|
| `<site>.html` | the report, self-contained: emailed, printed, opened offline |
| `<site>.artifact.html` | the same page for a hosted artifact (no document wrapper) |
| `<site>.fix-prompt.md` | the fix prompt, for the site's code repository |
| `<site>.findings.json` | score, grade, per-page scores, coverage, findings, for trackers and comparisons |
| `compare.json` | fixed / new / still failing versus the last finished run, if there is one |

It attaches all of them to the run with their hashes and closes the `render` step.

## What the scorecard says

- The grade (A–F), the score (mean page score; each page loses 15/8/3/1 per critical/serious/
  moderate/minor issue type), and **how many WCAG criteria were actually tested**. The score only
  measures what a scanner sees; the report says so.
- **Graded against**: the WCAG version and level, the organization, and the laws that bind it.
  Laws that were reviewed but don't bind this kind of organization are named with the reason.
- The next deadline for this organization (population-aware for US local governments).
- **Since the last audit**: fixed / new / still failing, with a warning when the scopes differ.

## Publish

Hosted artifacts available (e.g. Claude's Artifact tool)? Publish `<site>.artifact.html` and open
it. Otherwise the `.html` file is the deliverable. Either way:

```bash
python3 $E/ledger.py step $RUN publish done --note "<link or 'file only'>"
```

Never hand-edit a rendered report. Change the run's decisions or inputs and render again.

## Hand back

Answer first, in one line: grade, score, legal failures, the standard, the next deadline.
("B (86/100): 5 issues break ADA Title II (WCAG 2.1 AA), 1 critical. Travis County's deadline is
April 26, 2027.") Then:

1. The top fixes (from "What to fix first").
2. What was not tested, and why the scan stopped (pages left unscanned, if any).
3. The comparison with the last audit, if there was one.
4. The report link or path, and the fix prompt path. Offer the **fix** skill.

`python3 $E/ledger.py step $RUN handback done`. Never say "compliant". Don't blur legal failures
with best-practice gaps in the summary.
