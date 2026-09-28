---
name: fix
description: "Fix the accessibility issues an Access Atlas audit found, working in the website's own code repository from the run's fix prompt, then prove it by re-auditing the same scope and comparing runs (fixed / new / still failing). Use when someone says \"fix the accessibility issues\", \"apply the fix prompt\", \"remediate these findings\", \"did our fixes work\", \"re-audit after the fixes\", or hands over a fix-prompt.md."
argument-hint: "<run folder or fix-prompt.md> [path to the site's code]"
---

# Fix — change the code, then prove it

> **Clarify first.** You need the site's **source code** (a repository or folder the user owns and
> asks you to change) and the run the fixes come from. Never edit a live site, a CMS, or code you
> weren't pointed at. For a CMS site with no code, hand the fix prompt to whoever edits the templates.

`E=${CLAUDE_PLUGIN_ROOT}/engine`.

## 1. Work from the fix prompt

Read `<run>/<site>.fix-prompt.md`. It lists every issue with the failing elements, the legal
target, and how to verify. Follow its rules:

- Fix the **source** (the template, component or stylesheet), not the page. One component fix
  usually clears every page listed.
- Most severe first. Native HTML before ARIA. Keep the design; adjust colour tokens for contrast.
- **No accessibility overlays or widgets.** They don't make a site conform.
- After each fix, run axe-core on the listed pages and add a regression test (jest-axe,
  `@axe-core/playwright`, or whatever the project already uses).
- Third-party content you can't change: say so, don't hide it.

Work the way the project works: its branch rules, its test command, its review process. End with
a list of issue IDs and what changed where.

## 2. Prove it: re-audit the same scope

Once the fixes are deployed where they can be scanned (staging is fine; say which):

```bash
NEW=$(python3 $E/ledger.py open <url> --carry)          # reuses owner + standards, logged as carried
python3 $E/ledger.py decide $NEW scope '<same scope as before>' --why "re-audit after fixes" --by agent
node $E/scan.mjs <url> --run $NEW <same flags>           # plus the same --urls key tasks
python3 $E/render.py --run $NEW                          # the scorecard shows fixed / new / still failing
```

`python3 $E/ledger.py compare <old-run> <new-run>` prints the same comparison on its own.

Report the result honestly. "Fixed" means the automated check no longer finds it on the scanned
pages. Manual criteria stay as they were until someone re-checks them (**check** skill).
