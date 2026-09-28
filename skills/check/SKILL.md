---
name: check
description: "Walk the manual accessibility checks a scanner can't do (keyboard-only, screen reader, zoom and text spacing, colour, captions, forms and time-outs, documents), or audit a native iOS/Android app, and record the results so the report shows them honestly. Use when someone says \"do the manual checks\", \"test it with a keyboard\", \"screen reader test\", \"check the mobile app\", \"audit our iPhone app\", or as step 4 of an audit."
argument-hint: "<run folder>"
---

# Check — the two thirds a scanner can't see

> **Clarify first.** Ask which key tasks matter if the run doesn't already record `key_tasks`.
> The checks walk real tasks, not random pages.

`E=${CLAUDE_PLUGIN_ROOT}/engine`, guides at `${CLAUDE_PLUGIN_ROOT}/guides`.

- **Websites:** follow `guides/manual-checks.md` against each key task.
- **Native apps:** follow `guides/mobile.md`. There is nothing to scan; this skill *is* the audit.

## Who does what

| Check | With browser tools (Playwright, Chrome, computer use) | Without them |
|---|---|---|
| Keyboard only, focus order, traps | do it yourself: Tab, Shift+Tab, Enter, Esc through each task | a person does it |
| Zoom 200% / 400%, text spacing | do it yourself | a person does it |
| Screen reader | a person does it | a person does it |
| Captions, documents, forms and time-outs | do what you can see; a person confirms | a person does it |

Anything nobody checked stays **not tested**. Never record `pass` for a check that wasn't done.

## Record results

Write `$RUN/manual.json` in the format at the bottom of `manual-checks.md`: `results` per WCAG
criterion (`pass | fail | na | notrun`, with a note) and `findings` for each failure (criterion,
severity, what, where, fix). Name the tester and the assistive technology used. No member of the
public's personal data in notes.

```bash
python3 $E/ledger.py attach $RUN manual $RUN/manual.json
python3 $E/ledger.py step $RUN manual done --note "<n> criteria checked by <who>, AT: <tools>"
```

Skipping manual checks (the user only wants the automated pass)? Record it, so the report doesn't
read as more than it is:

```bash
python3 $E/ledger.py step $RUN manual skipped --note "automated pass only, at the user's request"
```
