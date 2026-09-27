# Auditing a native mobile app

The scanner reads web pages. A native iOS or Android app can't be axe-scanned, so a
mobile audit is manual checks plus each platform's own inspector. The legal bar is the
same: ADA Title II names mobile apps explicitly (WCAG 2.1 AA), Section 508 covers them as
software, and the EU directive and EN 301 549 clause 11 cover them. W3C's guidance for
applying WCAG to apps is **WCAG2ICT** (https://www.w3.org/TR/wcag2ict-22/) — cite it when
a criterion's web wording ("page", "site") needs translating.

If the "app" is a web view or PWA, also run `scan.mjs <url> --mobile` against the web
content it loads — that part is scannable.

## Tools

| Platform | Inspector | Screen reader | Other |
|---|---|---|---|
| iOS | Xcode › Accessibility Inspector (audit tab) | VoiceOver | Settings › Accessibility › Display & Text Size › Larger Text (max) |
| Android | Accessibility Scanner (Play Store), Android Studio layout inspector | TalkBack | Settings › Display › Font size + Display size (max); Switch Access |

Record the device, OS version and app build in `manual.json` → `assistive_tech`.

## Checks, mapped to WCAG

- **Screen reader walk of each key task** (1.1.1, 1.3.1, 2.4.3, 4.1.2): every control
  announces a name, role and state; swipe order follows the visual order; no unlabeled
  "button" announcements; images described or hidden.
- **Largest text size** (1.4.4, 1.4.10): text scales with the system setting (Dynamic
  Type / sp units) and nothing truncates or overlaps at the maximum.
- **Orientation** (1.3.4): both portrait and landscape work unless essential.
- **Touch targets** (2.5.8): at least 24×24 CSS px equivalent; platform guidance is
  44×44 pt (iOS) and 48×48 dp (Android) — report against WCAG, recommend the platform size.
- **Gestures and motion** (2.5.1, 2.5.4, 2.5.7): every swipe, pinch, drag or shake has a
  single-tap alternative.
- **Contrast** (1.4.3, 1.4.11): inspector contrast audit, plus dark mode.
- **External keyboard and Switch Access** (2.1.1, 2.1.2, 2.4.7): pair a Bluetooth keyboard;
  every task completes and focus is visible.
- **Status and errors** (3.3.1, 4.1.3): form errors and "saved" confirmations are announced.
- **Authentication** (3.3.8): password managers and paste work in login fields; biometric
  or code alternatives exist.
- **Time-outs** (2.2.1): session expiry warns and extends.
- **Captions** (1.2.x): in-app video has captions.

Record each as a result in `manual.json` and each failure as a finding with
`"where": "iOS 18 · Pay a bill · Amount screen"`. Render with `--kind "mobile app"`.
