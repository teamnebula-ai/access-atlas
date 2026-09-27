# Manual checks — the two-thirds a scanner can't see

A scan decides a handful of criteria outright (contrast, page language, titles, missing
labels). Everything else needs a person. Run these in order; each takes minutes, not
hours, on a typical public-facing site. Record results in `manual.json` (format at the
bottom) — the report turns every unrecorded criterion into "Not tested", never "Pass".

**Pick the pages by task, not by count.** Government audits fail on the transactions:
pay a bill, apply for a permit, report a problem, register to vote, find a meeting agenda.
Choose the 3–5 tasks the public actually comes for and walk each one end to end.

## 1. Keyboard only (10 min) — 2.1.1, 2.1.2, 2.4.3, 2.4.7, 2.4.11, 3.2.1

Put the mouse away. For each task:
- Tab from the address bar. Is the first stop a working "skip to content" link?
- Can you reach and operate every menu, accordion, date picker, map, modal, and payment field?
- Does focus stay visible the whole way (not hidden behind a sticky header or cookie banner)?
- Can you always leave a widget with Tab or Esc? (Embedded maps and chat widgets are the usual traps.)
- Does opening a modal move focus into it, and closing it return focus?

## 2. Screen reader (20 min) — 1.1.1, 1.3.1, 2.4.4, 2.4.6, 3.3.1, 4.1.2, 4.1.3

VoiceOver (macOS: Cmd+F5; iOS: Settings › Accessibility), NVDA (Windows, free), TalkBack (Android).
- Headings list (VO: rotor; NVDA: H / Insert+F7): does the outline describe the page?
- Links list: does each make sense alone? ("Click here" ×14 is a failure.)
- Images: meaningful ones described, decorative ones silent. Flyers-as-images = 1.4.5 fail.
- Forms: each field announces its label and required state; errors are announced when you submit.
- Custom controls announce role and state ("collapsed", "selected", "checked").
- Search results / "saved" messages announced without moving focus (4.1.3).

## 3. Zoom and reflow (5 min) — 1.4.4, 1.4.10, 1.4.12

- Browser zoom 200%: nothing cut off or overlapping.
- 1280px window at 400% zoom: no sideways scrolling for text (the scanner checks this; confirm on task pages).
- Text-spacing bookmarklet (line-height 1.5, paragraph 2×, letter 0.12em, word 0.16em): nothing clipped.

## 4. Colour and contrast by hand (5 min) — 1.4.1, 1.4.3, 1.4.11

- Text on images, gradients and hover states (the scanner can't read these reliably).
- Input borders, icon-only buttons, focus rings, chart segments: 3:1 against neighbours.
- Greyscale the screen: errors, required fields and links are still distinguishable.

## 5. Media (per video) — 1.2.1–1.2.5, 1.4.2, 2.2.2

- Recorded video: accurate captions (auto-captions uncorrected usually fail), transcript linked.
- Live-streamed meetings: real-time captions offered (council and board meetings are the common gap).
- Auto-playing audio/video/carousels: pause control present.

## 6. Forms and time limits — 1.3.5, 2.2.1, 3.3.2–3.3.4, 3.3.7, 3.3.8

- Visible labels, stated formats ("MM/DD/YYYY"), required fields marked in text.
- Submit with errors: each named in text, with a suggested fix.
- Payments/applications: review step before submit, or a way to correct.
- Session time-out warns and lets you extend.
- Login: paste and password managers work; CAPTCHA has a non-puzzle alternative.
- Multi-step forms don't ask for the same thing twice.

## 7. Consistency (5 min) — 2.4.5, 3.2.3, 3.2.4, 3.2.6

- Search or site map exists. Navigation and help links sit in the same place on every page.

## 8. Documents — WCAG applied to non-web documents

- Open the top 5 PDFs by traffic (agendas, forms, notices). Tagged? Reading order right?
  Form fields labelled? Scanned-image PDFs with no text layer fail outright.
- Note which are "archived" or pre-existing — ADA Title II and the EU directive have
  exceptions for these; check the jurisdiction entry's `exceptions` before counting them.

## Recording results — `manual.json`

```json
{
  "tester": "Name, role",
  "date": "2026-09-27",
  "assistive_tech": ["VoiceOver macOS 15 + Safari", "keyboard only, Chrome"],
  "results": {
    "2.1.1": {"result": "fail", "note": "Payment date picker unreachable by keyboard"},
    "2.4.7": {"result": "pass"},
    "1.2.4": {"result": "na", "note": "No live streams on site"}
  },
  "findings": [
    {"sc": "2.1.1", "severity": "critical", "what": "Can't pay a utility bill with a keyboard",
     "where": "/utilities/pay", "detail": "The date picker traps focus; Tab never reaches Submit.",
     "fix": "Use a native date input or a keyboard-operable picker; test with Tab/Shift+Tab/Esc."}
  ]
}
```

`result` is `pass | fail | na | notrun`. Severity: **critical** blocks a task entirely for
some users; **serious** makes a task very hard; **moderate** is friction; **minor** is polish.
Never put a real member of the public's name, email or case details into a note — the
report is shared.
