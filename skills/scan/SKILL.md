---
name: scan
description: "Scan a website's pages for WCAG failures with axe-core in a real browser, plus 400%-zoom reflow and a keyboard sample, taking annotated screenshots and stopping on page, depth, per-folder, time, saturation or blocking limits. Use when someone says \"scan this site\", \"run the accessibility scan\", \"check these pages\", \"rescan after the fix\", or as step 3 of an audit."
argument-hint: "<run folder or url> [scope flags]"
---

# Scan — the automated pass, with brakes

> **Clarify first.** A scope must be agreed before a crawl of anything over ~40 pages (see the
> **scope** skill). A handful of named URLs needs no question.

`E=${CLAUDE_PLUGIN_ROOT}/engine`. First time on a machine: `$E/ensure-deps.sh` (installs Playwright
and axe-core into `~/.cache/access-atlas`, never into anyone's project).

```bash
node $E/scan.mjs <url> --run $RUN <flags from the agreed scope>
node $E/scan.mjs <url> --run $RUN --urls <key task urls, comma-separated>     # always, if any were named
```

With `--run`, output lands in the run folder (`scan.json`, `tasks.json`, `*-shots/`) and every page
is logged to its `log.jsonl`.

## What it checks

axe-core against WCAG 2.0, 2.1 and 2.2 A/AA; a 320px reflow check (WCAG 1.4.10); and a keyboard
sample (skip link, visible focus). Pages with failures get a screenshot with the failing elements
outlined and numbered (up to 10 pages), plus a close-up of the first failing element of each rule
(up to 20). `--no-shots` skips them; get the user's OK before screenshotting logged-in pages.

## When it stops

At the first of these, and it records which one in the report:

| Rule | Flag (default) |
|---|---|
| Page cap | `--max-pages` (25) |
| Link depth | `--max-depth` (3) |
| Pages per folder | `--per-section` (5; 0 = no cap) |
| Time budget | `--time-budget` minutes (15) |
| Saturation: nothing new for N pages in a row | `--quiet-stop` (20; 0 = off) |
| Being blocked: >30% of pages fail, or HTTP 403/429 | automatic |

It honours robots.txt, waits `--delay` ms between pages (750), and never submits forms. In a
harness with a command timeout, set `--time-budget` below it.

## After the scan

Read the last line: pages scanned, rule failures, why it stopped, and how many discovered pages
were **not** scanned. Log it and close the step:

```bash
python3 $E/ledger.py step $RUN scan done --note "<pages> pages; stopped: <reason>; <n> not scanned"
```

Stopped on the page cap or time budget with many pages left? Tell the user plainly and offer a
deeper run. Never extend a scan silently. Blocked? Record `failed` with the reason and continue
to the report with what was scanned.

**Rescan after a fix** (see **fix**): open a new run with `--carry` and scan the *same* scope and
key tasks, so the comparison is like for like.
