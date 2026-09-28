#!/usr/bin/env python3
"""Render an Access Atlas audit: a scorecard report (HTML), findings.json and a fix prompt.

  render.py --jurisdictions us-co --scan scan.json[,tasks.json] [--manual manual.json]
            --org "City of Example" --product "example.gov" [--auditor "Name"]
            [--scope "what was and wasn't covered"] --out report.html

Every finding is mapped to its WCAG success criterion and then to each selected
jurisdiction whose standard requires it; anything required by none of them is best
practice, not a legal gap. Untested criteria stay visible. Screenshots taken by
scan.mjs are embedded, so the report is one self-contained file. Stdlib only.

Outputs next to --out:  <name>.html (full document), <name>.artifact.html (for the
Artifact tool, which adds its own skeleton), <name>.findings.json, <name>.fix-prompt.md
"""
import argparse
import base64
import html
import json
import re
import sys
from collections import OrderedDict
from datetime import date, datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from jurisdictions import applicable, load as load_registry, resolve, wcag_target  # noqa: E402
import ledger  # noqa: E402

WCAG = json.loads((HERE.parent / "data" / "wcag.json").read_text())["criteria"]
SC = {c["sc"]: c for c in WCAG}
VERSIONS = {"2.0": 0, "2.1": 1, "2.2": 2}
LEVELS = {"A": 0, "AA": 1, "AAA": 2}
SEV_ORDER = ["critical", "serious", "moderate", "minor", "review"]
SEV_LABEL = {"critical": "Critical", "serious": "Serious", "moderate": "Moderate", "minor": "Minor", "review": "Needs review"}
SEV_GLYPH = {"critical": "&#9670;", "serious": "&#9650;", "moderate": "&#9679;", "minor": "&#9675;", "review": "?"}
# Score: each page starts at 100 and loses this much per distinct failing rule on it.
WEIGHT = {"critical": 15, "serious": 8, "moderate": 3, "minor": 1, "review": 0}
GRADES = [(90, "A"), (80, "B"), (70, "C"), (60, "D"), (0, "F")]
IMG_BUDGET = 9_000_000  # bytes of embedded screenshots; the Artifact limit is 16MB for the whole page

e = lambda s: html.escape(str(s if s is not None else ""), quote=True)  # noqa: E731


def sc_key(s):
    return tuple(int(x) for x in s.split(".")) if s[0].isdigit() else (99,)


def in_scope(sc, version, level):
    c = SC.get(sc)
    if not c:
        return False
    if VERSIONS[c["since"]] > VERSIONS[version]:
        return False
    if c.get("until") and VERSIONS[version] >= VERSIONS[c["until"]]:
        return False
    return LEVELS[c["level"]] <= LEVELS[level]


def tag_to_sc(tag):
    m = re.fullmatch(r"wcag(\d)(\d)(\d+)", tag)
    return f"{m.group(1)}.{m.group(2)}.{m.group(3)}" if m else None


def grade(score):
    return next(g for t, g in GRADES if score >= t)


# ---------------------------------------------------------------- findings


def findings_from_scan(scan):
    """Aggregate axe violations across pages by rule; add reflow/keyboard checks."""
    rules = OrderedDict()
    review = OrderedDict()
    for p in scan.get("pages", []):
        for v in p.get("violations", []):
            r = rules.setdefault(v["id"], {"rule": v["id"], "title": v["help"], "detail": v["description"], "impact": v.get("impact") or "moderate",
                                           "fix_url": v.get("helpUrl"), "scs": sorted({s for s in map(tag_to_sc, v["tags"]) if s}, key=sc_key),
                                           "pages": [], "count": 0, "examples": [], "crop": None})
            r["pages"].append(p["url"])
            r["count"] += v.get("count", len(v.get("nodes", [])))
            if not r["crop"] and v.get("crop"):
                r["crop"] = {"file": v["crop"], "page": p["url"]}
            for n in v.get("nodes", [])[:2]:
                if len(r["examples"]) < 4:
                    r["examples"].append({"page": p["url"], "target": n["target"], "html": n["html"], "summary": n.get("summary", "")})
        for v in p.get("incomplete", []):
            r = review.setdefault(v["id"], {"rule": v["id"], "title": v["help"], "scs": sorted({s for s in map(tag_to_sc, v["tags"]) if s}, key=sc_key), "pages": [], "count": 0})
            r["pages"].append(p["url"])
            r["count"] += v.get("count", 0)

    out = [{"source": "automated", "severity": r["impact"], "title": r["title"], "detail": r["detail"], "scs": r["scs"] or ["unmapped"],
            "where": r["pages"], "instances": r["count"], "fix_url": r["fix_url"], "rule": r["rule"], "examples": r["examples"], "crop": r["crop"]}
           for r in rules.values()]

    reflow_fail = [p["url"] for p in scan.get("pages", []) if p.get("checks", {}).get("reflow", {}).get("pass") is False]
    if reflow_fail:
        widths = sorted({p["checks"]["reflow"]["scrollWidth"] for p in scan["pages"] if p["url"] in reflow_fail}, reverse=True)
        out.append({"source": "automated", "severity": "serious", "title": "Page scrolls sideways at 320px (400% zoom)",
                    "detail": "At a 320 CSS-pixel viewport the page is wider than the screen, so zoomed-in readers must scroll in two directions. Widest: "
                              + ", ".join(f"{w}px" for w in widths[:3]) + ".",
                    "scs": ["1.4.10"], "where": reflow_fail, "instances": len(reflow_fail), "fix_url": "https://www.w3.org/WAI/WCAG22/Understanding/reflow.html", "rule": "reflow-320"})
    no_skip = [p["url"] for p in scan.get("pages", []) if p.get("checks", {}).get("keyboard") and not p["checks"]["keyboard"]["skipLink"]]
    if no_skip:
        out.append({"source": "automated", "severity": "review", "title": "No skip link on first Tab",
                    "detail": "The first keyboard stop is not a 'skip to content' link. Landmarks can also satisfy this; confirm by hand.",
                    "scs": ["2.4.1"], "where": no_skip, "instances": len(no_skip), "fix_url": "https://www.w3.org/WAI/WCAG22/Techniques/general/G1", "rule": "skip-link"})
    focus = OrderedDict()
    for p in scan.get("pages", []):
        for s in (p.get("checks", {}).get("keyboard") or {}).get("noVisibleFocus", []):
            focus.setdefault(s, []).append(p["url"])
    if focus:
        out.append({"source": "automated", "severity": "review", "title": "Focused element may have no visible indicator",
                    "detail": "No outline or focus ring was detected on: " + "; ".join(list(focus)[:5]) + ". The site may style focus another way (border, background); confirm by tabbing.",
                    "scs": ["2.4.7"], "where": sorted({u for us in focus.values() for u in us}), "instances": len(focus), "fix_url": "https://www.w3.org/WAI/WCAG22/Understanding/focus-visible.html", "rule": "focus-visible"})
    return out, list(review.values())


def findings_from_manual(manual):
    return [{"source": "manual", "severity": f.get("severity", "serious"), "title": f["what"], "detail": f.get("detail", ""),
             "scs": [f["sc"]] if isinstance(f.get("sc"), str) else f.get("sc", ["unmapped"]), "where": [f.get("where", "")],
             "instances": f.get("instances", 1), "fix_url": f.get("fix_url"), "rule": f.get("id", "manual"), "fix": f.get("fix", "")}
            for f in manual.get("findings", [])]


def site_score(scan, manual_findings):
    """Mean page score (100 minus weights of the distinct failing rules on the page), minus manual findings once each."""
    per_page = []
    for p in scan.get("pages", []):
        if p.get("error"):
            continue
        lost = sum(WEIGHT.get(v.get("impact") or "moderate", 3) for v in p.get("violations", []))
        if p.get("checks", {}).get("reflow", {}).get("pass") is False:
            lost += WEIGHT["serious"]
        per_page.append((p["url"], max(0, 100 - lost)))
    if not per_page and not manual_findings:
        return None, []
    base = sum(s for _, s in per_page) / len(per_page) if per_page else 100
    base -= sum(WEIGHT.get(f["severity"], 3) for f in manual_findings)
    return max(0, round(base)), per_page


# ---------------------------------------------------------------- model


def owner_from(a):
    """Owner facts from the run's decisions, overridden by command-line flags."""
    d = {}
    if a.run:
        d = {k: v["value"] for k, v in ledger.load(a.run)["decisions"].items()}
    for k in ("entity", "country", "region", "place", "population"):
        if getattr(a, k, None):
            d[k] = getattr(a, k)
    if a.org:
        d["owner"] = a.org
    return d


def build(a):
    reg = load_registry()
    own = owner_from(a)
    a.org = a.org or own.get("owner") or "Unknown organization"
    requested = a.jurisdictions.split(",") if a.jurisdictions else (own.get("standards") or [])
    if isinstance(requested, dict):
        requested = requested.get("binding", []) + requested.get("conditional", []) + requested.get("reference", [])
    cls = {}
    if own.get("entity") and own.get("country"):
        b, c, r = applicable(reg, own["country"], own["entity"], own.get("region"), own.get("place"))
        cls.update({i: "binding" for i in b}); cls.update({i: "conditional" for i in c}); cls.update({i: "reference" for i in r})
        requested = requested or (b + c + r)
    if not requested:
        sys.exit("no standards: pass --jurisdictions, or record owner/entity/country in the run (ledger.py decide)")
    jids, missing = resolve(requested, reg)
    if missing:
        sys.exit(f"unknown jurisdiction(s): {', '.join(missing)} — run jurisdictions.py list")
    # Without owner facts every selected law is treated as binding (the caller chose them).
    role = {i: (cls.get(i, "reference") if cls else "binding") for i in jids}
    juris = [reg[i] for i in jids]
    binding = [j for j in juris if role[j["id"]] == "binding"]
    if not binding:
        sys.exit("none of the selected laws binds this organization; check the owner decisions")
    targets = {j["id"]: wcag_target(j.get("standard")) for j in juris}
    top_version = max((targets[j["id"]][0] for j in binding), key=lambda v: VERSIONS[v])

    scan = {}
    for i, f in enumerate(a.scan.split(",") if a.scan else []):  # several scans (crawl + task flows) merge into one
        part = json.loads(Path(f).read_text())
        if not i:
            scan = part
            continue
        have = {p["url"] for p in scan["pages"]}
        scan["pages"] += [p for p in part["pages"] if p["url"] not in have]
        scan["pagesDiscovered"] = scan.get("pagesDiscovered", 0) + part.get("pagesDiscovered", 0)
        scan["documentsFound"] = sorted(set(scan.get("documentsFound", [])) | set(part.get("documentsFound", [])))
    manual = json.loads(Path(a.manual).read_text()) if a.manual else {}
    auto, review = findings_from_scan(scan) if scan else ([], [])
    manual_f = findings_from_manual(manual)
    findings = auto + manual_f
    for f in findings:
        f["required_by"] = [j["id"] for j in binding if any(in_scope(s, *targets[j["id"]][:2]) for s in f["scs"])]
    findings.sort(key=lambda f: (SEV_ORDER.index(f["severity"]) if f["severity"] in SEV_ORDER else 9, -len(f["where"]), -f["instances"]))
    for n, f in enumerate(findings, 1):
        f["id"] = f"A11Y-{n:03d}"

    mres = manual.get("results", {})
    status = {}
    for f in findings:
        for s in f["scs"]:
            if status.get(s) != "fail":
                status[s] = "review" if f["severity"] == "review" else "fail"
    for r in review:
        for s in r["scs"]:
            status.setdefault(s, "review")
    for s, r in mres.items():
        if status.get(s) != "fail":
            status[s] = {"pass": "pass", "fail": "fail", "na": "na"}.get(r.get("result"), "untested")
    scope_scs = sorted([c["sc"] for c in WCAG if in_scope(c["sc"], top_version, "AA")], key=sc_key)
    for s in scope_scs:
        if s not in status:
            status[s] = "pass-auto" if scan and SC[s]["auto"] == "full" else "untested"
    counts = {k: sum(1 for s in scope_scs if status[s] == k) for k in ["fail", "review", "pass", "pass-auto", "na", "untested"]}

    today = date.today()
    deadlines = []
    pop = (own.get("population") or "").lower()
    for j in binding:
        for d in j.get("deadlines", []) or []:
            what = (d.get("what") or "").lower()
            if pop.startswith("50k") and re.search(r"under 50|fewer than 50|less than 50|smaller|special district", what):
                continue
            if pop.startswith("under") and re.search(r"50,000 or more|50,000\+|50k\+|more than 50", what):
                continue
            try:
                deadlines.append((date.fromisoformat(d["date"]), j["name"], d.get("what", "")))
            except Exception:
                continue
    deadlines.sort()
    score, per_page = site_score(scan, manual_f)
    return {
        "a": a, "reg": reg, "jids": jids, "juris": juris, "binding": binding, "role": role, "own": own, "targets": targets, "top": top_version, "scan": scan, "manual": manual,
        "findings": findings, "review": review, "status": status, "scope_scs": scope_scs, "counts": counts, "mres": mres,
        "legal": [f for f in findings if f["required_by"] and f["severity"] != "review"],
        "sev": {s: sum(1 for f in findings if f["severity"] == s) for s in SEV_ORDER},
        "upcoming": [d for d in deadlines if d[0] >= today], "passed": [d for d in deadlines if d[0] < today], "today": today,
        "score": score, "per_page": per_page, "stamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    }


# ---------------------------------------------------------------- images

class Images:
    """Embeds screenshot files as data URIs within a total byte budget."""

    def __init__(self, budget=IMG_BUDGET):
        self.left = budget
        self.dropped = 0

    def uri(self, path):
        p = Path(path) if path else None
        if not p or not p.exists():
            return None
        b = p.read_bytes()
        if len(b) * 1.37 > self.left:
            self.dropped += 1
            return None
        self.left -= int(len(b) * 1.37)
        return "data:image/jpeg;base64," + base64.b64encode(b).decode()


# ---------------------------------------------------------------- fix prompt


def fix_prompt(m):
    a, top = m["a"], m["top"]
    target = m["scan"].get("target") or a.product
    laws = "; ".join(f"{j['name']} (WCAG {m['targets'][j['id']][0]} {m['targets'][j['id']][1]})" for j in m["binding"])
    lines = [
        f"# Fix the accessibility issues on {a.product}",
        "",
        f"You are working on the code for {target} ({a.org}). An accessibility audit on {m['today'].isoformat()} found the issues below.",
        f"The legal target is **WCAG {top} Level AA**, required by: {laws}.",
    ]
    if m["upcoming"]:
        d = m["upcoming"][0]
        lines.append(f"Next compliance deadline: {d[0].isoformat()} ({d[2]}).")
    lines += [
        "",
        "## How to work",
        "1. Fix the source, not the page: find the template, component, or stylesheet that produces each failing element. One component fix usually clears every page listed.",
        "2. Work in the order below (most severe first). Keep the visual design; where contrast fails, adjust the colour tokens until text is 4.5:1 (3:1 for large text and UI parts).",
        "3. Do not add an accessibility overlay or widget. Overlays do not make a site conform and are a known source of complaints.",
        "4. Use native HTML before ARIA: a real <button>, <label>, <a href>, heading levels in order.",
        "5. After each fix, re-run an automated check (axe-core) on the listed pages and add a regression test for the component (e.g. jest-axe or @axe-core/playwright).",
        "6. When done, list each issue ID below with what you changed and where. If an issue lives in third-party content you cannot change, say so instead of hiding it.",
        "",
        "## Issues",
    ]
    for f in m["findings"]:
        if f["severity"] == "review":
            continue
        c = SC.get(f["scs"][0], {})
        where = [u for u in f["where"] if u]
        lines += ["", f"### {f['id']} · {f['title']}",
                  f"- WCAG {', '.join(f['scs'])} {c.get('name', '')} (Level {c.get('level', '?')}) · {SEV_LABEL.get(f['severity'], f['severity'])} · "
                  f"{'legally required' if f['required_by'] else 'best practice'} · {f['instances']} instance(s) on {len(where)} page(s)"]
        if c.get("plain"):
            lines.append(f"- What it means: {c['plain']}")
        if f.get("detail"):
            lines.append(f"- Detail: {f['detail']}")
        lines.append("- Pages: " + ", ".join(where[:8]) + (f" (+{len(where) - 8} more)" if len(where) > 8 else ""))
        for x in (f.get("examples") or [])[:2]:
            lines += [f"- Element `{x['target']}`:", "  ```html", "  " + x["html"].replace("\n", " "), "  ```"]
            if x.get("summary"):
                lines.append("  Why it fails: " + " ".join(x["summary"].split()))
        if f.get("fix"):
            lines.append(f"- Fix: {f['fix']}")
        if f.get("fix_url"):
            lines.append(f"- Reference: {f['fix_url']}")
    reviews = [f for f in m["findings"] if f["severity"] == "review"]
    if reviews:
        lines += ["", "## Check these and fix if they fail"]
        lines += [f"- {f['id']} {f['title']} (WCAG {', '.join(f['scs'])}): {f['detail']}" for f in reviews]
    untested = [s for s in m["scope_scs"] if m["status"][s] == "untested"]
    if untested:
        lines += ["", "## Not tested yet: verify while you are in the code",
                  "These criteria need a person or a closer look. Fix anything you find, and say which you checked:"]
        lines += [f"- {s} {SC[s]['name']}: {SC[s]['test']}" for s in untested]
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------- html

CSS = """
:root{--ground:#ffffff;--panel:#f2f5f7;--ink:#13202a;--ink-2:#44545f;--rule:#d3dce2;--accent:#0b5c73;--accent-ink:#ffffff;
--crit:#a3231b;--seri:#9a4a06;--mod:#6a5a00;--min:#44545f;--rev:#5b3f8c;--pass:#1d6b3a;--shade:rgba(16,32,42,.10);
--display:"Iowan Old Style","Charter","Palatino Linotype","Book Antiqua",Georgia,serif;
--sans:system-ui,-apple-system,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;--mono:ui-monospace,"SF Mono",Menlo,Consolas,monospace}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){color-scheme:dark;--ground:#0d1011;--panel:#161c1f;--ink:#e4eaee;--ink-2:#a9b6be;--rule:#2a3439;--accent:#5fc0d6;--accent-ink:#0d1011;
--crit:#ff8a80;--seri:#ffb870;--mod:#e6d267;--min:#b7c3ca;--rev:#c5a8ff;--pass:#7ad69a;--shade:rgba(0,0,0,.45)}}
:root[data-theme="dark"]{color-scheme:dark;--ground:#0d1011;--panel:#161c1f;--ink:#e4eaee;--ink-2:#a9b6be;--rule:#2a3439;--accent:#5fc0d6;--accent-ink:#0d1011;
--crit:#ff8a80;--seri:#ffb870;--mod:#e6d267;--min:#b7c3ca;--rev:#c5a8ff;--pass:#7ad69a;--shade:rgba(0,0,0,.45)}
*{box-sizing:border-box}
body{background:var(--ground);color:var(--ink);font:18px/1.68 var(--sans);margin:0;padding-inline:16px}
.wrap{max-width:1080px;margin:0 auto;padding-block:40px 64px}
h1,h2,h3{font-family:var(--display);line-height:1.18;text-wrap:balance;margin:0}
h1{font-size:2.35rem;font-weight:600}h2{font-size:1.6rem;font-weight:600;margin-top:56px;padding-top:12px;border-top:2px solid var(--ink)}
h3{font-size:1.2rem;font-weight:600}
p{margin:0;max-width:68ch}.muted{color:var(--ink-2);font-size:15.5px}
a{color:var(--accent);text-underline-offset:3px}a:focus-visible,summary:focus-visible,button:focus-visible{outline:3px solid var(--accent);outline-offset:2px}
.skip{position:absolute;left:-9999px}.skip:focus{left:16px;top:16px;background:var(--accent);color:var(--accent-ink);padding:8px 12px;z-index:9}
.mast{display:grid;gap:10px}
.eyebrow{font:600 14px/1.4 var(--sans);letter-spacing:.08em;text-transform:uppercase;color:var(--accent)}
.meta{display:flex;flex-wrap:wrap;gap:6px 22px;font-size:15.5px;color:var(--ink-2)}.meta b{color:var(--ink);font-weight:600}
.card{margin-top:26px;display:grid;grid-template-columns:minmax(0,1fr) minmax(0,340px);gap:28px;border:1px solid var(--rule);border-radius:6px;padding:26px;background:var(--panel)}
.gradebox{display:flex;gap:22px;align-items:center;flex-wrap:wrap}.gradebox>div:last-child{flex:1 1 220px}
.grade{width:118px;height:118px;border-radius:50%;display:grid;place-items:center;border:6px solid currentColor;font:600 3.4rem/1 var(--display);flex:none}
.grade.g-A,.grade.g-B{color:var(--pass)}.grade.g-C{color:var(--mod)}.grade.g-D{color:var(--seri)}.grade.g-F{color:var(--crit)}.grade.g-none{color:var(--ink-2)}
.score{font:600 2rem/1.1 var(--sans);font-variant-numeric:tabular-nums}.score small{font-size:1rem;color:var(--ink-2);font-weight:400}
.tiles{grid-column:1/-1;display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px}
.tile{background:var(--ground);border:1px solid var(--rule);border-radius:4px;padding:12px 14px;display:grid;gap:2px}
.tile b{font:600 1.7rem/1.1 var(--sans);font-variant-numeric:tabular-nums}.tile span{font-size:15.5px;color:var(--ink-2);line-height:1.35}
.tile.bad b{color:var(--crit)}.tile.warn b{color:var(--seri)}
.thumb{margin:0;display:grid;gap:6px;align-content:start}.thumb img{width:100%;max-height:300px;object-fit:cover;object-position:top;border:1px solid var(--rule);border-radius:4px;box-shadow:0 6px 22px var(--shade)}
.graded{grid-column:1/-1;border-top:1px solid var(--rule);padding-top:14px;display:grid;gap:4px;font-size:16px}.graded b{font-weight:600}
.delta{display:flex;flex-wrap:wrap;gap:8px 18px;font-size:16px}.delta b{font-variant-numeric:tabular-nums}
.role{font:600 13px/1 var(--sans);letter-spacing:.06em;text-transform:uppercase;padding:4px 8px;border-radius:3px;border:1px solid currentColor}
.role.binding{color:var(--crit)}.role.conditional{color:var(--seri)}.role.reference{color:var(--ink-2)}
.trail li{margin:2px 0}.trail{font-size:15.5px;padding-left:20px}
.banner{margin-top:20px;border:1px solid var(--rule);border-left:6px solid var(--seri);background:var(--panel);padding:14px 18px;font-size:16px}
.answer{margin-top:28px;display:grid;gap:10px}.answer p{font-size:1.1rem}
.tally{display:flex;flex-wrap:wrap;gap:10px;align-items:center}
.sev{display:inline-flex;align-items:center;gap:6px;font:600 15.5px/1.2 var(--sans);padding:4px 10px;border:1.5px solid currentColor;border-radius:3px;white-space:nowrap}
.sev.critical{color:var(--crit)}.sev.serious{color:var(--seri)}.sev.moderate{color:var(--mod)}.sev.minor{color:var(--min)}.sev.review{color:var(--rev)}
.toc{margin-top:28px;font-size:16px}.toc ol{display:flex;flex-wrap:wrap;gap:4px 20px;padding:0;margin:6px 0 0;list-style:none}
section>p,section>.lead{margin-top:14px}
.tablewrap{overflow-x:auto;margin-top:18px}
table{border-collapse:collapse;width:100%;font-size:16px;font-variant-numeric:tabular-nums}
th,td{text-align:left;vertical-align:top;padding:9px 12px;border-bottom:1px solid var(--rule)}
thead th{font:600 14px/1.3 var(--sans);letter-spacing:.05em;text-transform:uppercase;color:var(--ink-2);border-bottom:2px solid var(--ink)}
.bar{display:inline-block;height:10px;border-radius:5px;background:var(--accent);vertical-align:middle;margin-right:8px}
.gallery{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:22px;margin-top:20px}
.shot{margin:0;display:grid;gap:8px;align-content:start}.shot img{width:100%;border:1px solid var(--rule);border-radius:4px}
.shot figcaption{font-size:15.5px;color:var(--ink-2)}.shot ol{margin:4px 0 0;padding-left:22px}
.cite{display:grid;grid-template-columns:92px 1fr;gap:0 20px;margin-top:22px;padding-top:18px;border-top:1px solid var(--rule)}
.cite .sc{font:600 1.35rem/1.1 var(--mono);color:var(--accent)}.cite .sc small{display:block;font:400 14px/1.35 var(--sans);color:var(--ink-2);margin-top:6px}
.cite .body{display:grid;gap:10px;min-width:0}
.cite .top{display:flex;flex-wrap:wrap;gap:8px 14px;align-items:center}
.cite img{max-width:min(100%,560px);border:1px solid var(--rule);border-radius:4px}
.req{font-size:15.5px}
.law{display:inline-block;margin:2px 6px 2px 0;padding:1px 8px;border:1px solid var(--rule);border-radius:3px;font-size:15.5px}
.bp{color:var(--ink-2);font-style:italic}
details{font-size:15.5px}summary{cursor:pointer;color:var(--accent)}
code,pre{font-family:var(--mono);font-size:14.5px}pre{white-space:pre-wrap;word-break:break-word;background:var(--panel);padding:10px 12px;margin:6px 0;border-radius:3px}
.juris{margin-top:22px;padding:18px 20px;border:1px solid var(--rule);border-radius:4px;display:grid;gap:10px}
.juris dl{display:grid;grid-template-columns:minmax(120px,170px) 1fr;gap:6px 18px;margin:0;font-size:16px}.juris dt{color:var(--ink-2)}.juris dd{margin:0;overflow-wrap:anywhere}
.conf-low{color:var(--crit);font-weight:600}
.st{font-weight:600;white-space:nowrap}.st.fail{color:var(--crit)}.st.review{color:var(--rev)}.st.pass{color:var(--pass)}.st.untested,.st.na{color:var(--ink-2);font-weight:400}
.prompt{margin-top:18px;border:1px solid var(--rule);border-radius:6px;overflow:hidden}
.prompt .bar2{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap;padding:10px 14px;background:var(--panel);border-bottom:1px solid var(--rule)}
.prompt pre{margin:0;max-height:520px;overflow:auto;border-radius:0;background:var(--ground);font-size:14px;line-height:1.55}
button.copy{font:600 15.5px/1 var(--sans);padding:9px 14px;border-radius:4px;border:0;background:var(--accent);color:var(--accent-ink);cursor:pointer}
footer{margin-top:64px;padding-top:18px;border-top:1px solid var(--rule);font-size:15.5px;color:var(--ink-2);display:grid;gap:6px}
@media (max-width:760px){h1{font-size:1.8rem}.card{grid-template-columns:1fr}.cite{grid-template-columns:1fr}.juris dl{grid-template-columns:1fr}}
@media print{body{font-size:12pt}.skip,.toc,button.copy{display:none}a{color:inherit}.prompt pre{max-height:none}}
"""

COPY_JS = """
document.querySelectorAll('button.copy').forEach(function(b){b.addEventListener('click',function(){
var pre=document.getElementById(b.getAttribute('data-target')),s=document.getElementById(b.getAttribute('data-status'));
function sel(){var r=document.createRange();r.selectNodeContents(pre);var x=getSelection();x.removeAllRanges();x.addRange(r);s.textContent='Selected. Press Ctrl+C or Cmd+C to copy.';}
try{navigator.clipboard.writeText(pre.textContent).then(function(){s.textContent='Copied to clipboard.';},sel);}catch(err){sel();}
});});
"""


def sev_badge(s):
    return f'<span class="sev {e(s)}"><span aria-hidden="true">{SEV_GLYPH.get(s, "")}</span>{e(SEV_LABEL.get(s, s))}</span>'


def short(url, target):
    return (url.replace(target.rstrip("/"), "") or "/") if target else url


def render_html(m, prompt_text):
    a, scan, findings = m["a"], m["scan"], m["findings"]
    target = scan.get("target", "")
    pages = scan.get("pages", [])
    docs = scan.get("documentsFound", [])
    scope = scan.get("scope", {})
    imgs = Images()
    fid_by_rule = {f["rule"]: f["id"] for f in findings}
    H = []
    w = H.append

    w(f"<title>{e(a.org)} Accessibility Scorecard</title><style>{CSS}</style>")
    w('<a class="skip" href="#answer">Skip to the summary</a><div class="wrap"><header class="mast">')
    w(f'<p class="eyebrow">Accessibility scorecard &middot; {e(a.kind)}</p><h1>{e(a.org)}: {e(a.product)}</h1>')
    w('<div class="meta">' + f"<span><b>Date</b> {e(m['today'].isoformat())}</span><span><b>Status</b> draft for review</span>"
      + f"<span><b>Measured against</b> WCAG {e(m['top'])} AA</span>" + (f"<span><b>Pages scanned</b> {len(pages)}</span>" if pages else "")
      + (f"<span><b>Auditor</b> {e(a.auditor)}</span>" if a.auditor else "") + "</div></header>")

    # --- scorecard
    score = m["score"]
    g = grade(score) if score is not None else None
    tested = len(m["scope_scs"]) - m["counts"]["untested"]
    affected = {short(u, target) for f in m["legal"] for u in f["where"] if u}
    w('<section class="card" aria-labelledby="card-h"><div>')
    w('<h2 id="card-h" style="margin:0;border:0;padding:0;font-size:1.05rem;font-family:var(--sans);letter-spacing:.06em;text-transform:uppercase;color:var(--ink-2)">Scorecard</h2>')
    w('<div class="gradebox" style="margin-top:14px">')
    if g:
        w(f'<div class="grade g-{g}" role="img" aria-label="Grade {g}">{g}</div><div><p class="score">{score}<small> / 100</small></p>'
          f'<p class="muted">Automated score across {len(m["per_page"])} page{"s" if len(m["per_page"]) != 1 else ""}. It measures only what a scanner can see; '
          f'see coverage below.</p></div>')
    else:
        w('<div class="grade g-none" role="img" aria-label="No score">&ndash;</div><p class="muted">No automated scan was run, so there is no score. Findings come from manual checks only.</p>')
    w("</div></div>")
    first_shot = next((p.get("shot") for p in pages if p.get("shot")), None)
    uri = imgs.uri(first_shot["file"]) if first_shot else None
    if uri:
        w(f'<figure class="thumb"><img src="{uri}" alt="Screenshot of {e(short(pages[0]["url"], target))} as scanned"><figcaption class="muted">{e(target or a.product)}</figcaption></figure>')
    w('<div class="tiles">')
    deadline_tile = ""
    if m["upcoming"]:
        days = (m["upcoming"][0][0] - m["today"]).days
        deadline_tile = f'<div class="tile{" warn" if days < 365 else ""}"><b>{days}</b><span>days to the next deadline ({e(m["upcoming"][0][0].strftime("%b %-d, %Y"))})</span></div>'
    elif m["passed"]:
        deadline_tile = f'<div class="tile bad"><b>Passed</b><span>last deadline was {e(m["passed"][-1][0].strftime("%b %-d, %Y"))}</span></div>'
    tiles = [
        f'<div class="tile{" bad" if m["legal"] else ""}"><b>{len(m["legal"])}</b><span>issues that break a legal requirement</span></div>',
        f'<div class="tile{" bad" if m["sev"]["critical"] else ""}"><b>{m["sev"]["critical"]}</b><span>critical: blocks some people completely</span></div>',
        f'<div class="tile"><b>{len(affected)}</b><span>pages with a legal failure</span></div>' if pages else "",
        f'<div class="tile{" warn" if tested < len(m["scope_scs"]) / 2 else ""}"><b>{tested}/{len(m["scope_scs"])}</b><span>WCAG criteria tested so far</span></div>',
        deadline_tile,
    ]
    w("".join(t for t in tiles if t) + "</div>")
    own = m["own"]
    who = ", ".join(x for x in [own.get("entity", "").replace("-", " "), own.get("region") or "", own.get("country") or ""] if x)
    b_names = "; ".join(f'{e(j["name"])}' for j in m["binding"])
    others = [j for j in m["juris"] if m["role"][j["id"]] != "binding"]
    w(f'<div class="graded"><p><b>Graded against WCAG {e(m["top"])} Level AA</b>, the standard required of {e(a.org)}'
      + (f" ({e(who)})" if who else "") + f" by: {b_names}.</p>")
    for j in others:
        why = (j.get("covers_conditionally") or {}).get("when") if m["role"][j["id"]] == "conditional" else "applies to " + ", ".join(c.replace("-", " ") for c in j.get("covers", [])) or "no organizations"
        w(f'<p class="muted">{e(j["name"])}: {"may also apply, " if m["role"][j["id"]] == "conditional" else "reviewed but not binding here; "}{e(why)}.</p>')
    if m.get("delta"):
        d = m["delta"]
        w(f'<p class="delta"><b>Since the last audit ({e(d["older_name"])}):</b><span><b>{len(d["fixed"])}</b> fixed</span><span><b>{len(d["new"])}</b> new</span>'
          f'<span><b>{len(d["still"])}</b> still failing</span><span>score {e(d["score"]["before"])} &rarr; {e(d["score"]["after"])}</span></p>')
        if d.get("scope_changed") or d.get("pages_before") != d.get("pages_after"):
            w('<p class="muted">The two audits scanned different pages, so part of this change reflects what was scanned, not only the site. Compare like with like by re-running the same scope.</p>')
    w("</div>")
    w("</section>")

    w('<p class="banner"><b>Not a conformance statement and not legal advice.</b> Automated tools find roughly a third of accessibility barriers. '
      f'This report shows {"the automated results plus " if scan else ""}{"the manual checks that were done" if m["mres"] or m["manual"].get("findings") else "which checks still need a person"}; '
      "every criterion not tested is listed as untested, not as passing.</p>")

    # --- short answer
    w('<section id="answer" class="answer" aria-labelledby="answer-h"><h2 id="answer-h">The short answer</h2>')
    if m["legal"]:
        n = len(m["legal"])
        w(f"<p><b>{n} issue{'s' if n != 1 else ''} break{'' if n != 1 else 's'} a legal requirement</b>{', on ' + str(len(affected)) + ' pages' if pages else ''}. "
          "Most come from shared templates, so fixing the component fixes every page. Start with the critical ones.</p>")
    else:
        w("<p><b>No failures of a legal requirement were found by the checks that ran.</b> That is not the same as compliant; see the untested criteria below.</p>")
    c = m["counts"]
    w(f"<p>{c['fail']} of {len(m['scope_scs'])} WCAG {e(m['top'])} AA criteria have a failure, {c['review']} need a person to decide, and {c['untested']} were not tested yet.</p>")
    if m["upcoming"]:
        d0 = m["upcoming"][0]
        w(f"<p>Next deadline: <b>{e(d0[0].strftime('%B %-d, %Y'))}</b>. {e(d0[2])} <span class=\"muted\">Source: {e(d0[1])}.</span></p>")
    w('<div class="tally" role="group" aria-label="Findings by severity">' + "".join(
        f'{sev_badge(s)}<span class="muted">&times; {m["sev"][s]}</span>' for s in SEV_ORDER if m["sev"][s]) + "</div></section>")

    w('<nav class="toc" aria-label="Contents"><b>Contents</b><ol><li><a href="#fix-first">What to fix first</a></li>'
      + ('<li><a href="#seen">What we saw</a></li>' if any(p.get("shot") and p["shot"]["legend"] for p in pages) else "")
      + '<li><a href="#findings">All findings</a></li><li><a href="#pages">Page scores</a></li><li><a href="#law">What the law requires</a></li>'
      '<li><a href="#coverage">What was and wasn\'t tested</a></li>' + ('<li><a href="#documents">Documents</a></li>' if docs else "")
      + '<li><a href="#method">How this was measured</a></li>' + ('<li><a href="#trail">Audit trail</a></li>' if a.run else '') + '<li><a href="#prompt">Fix prompt</a></li></ol></nav>')

    # --- fix first
    w('<section aria-labelledby="fix-first"><h2 id="fix-first">What to fix first</h2>')
    top = [f for f in findings if f["severity"] in ("critical", "serious") and f["required_by"]][:6] or [f for f in findings if f["severity"] != "review"][:6]
    if top:
        w('<div class="tablewrap"><table><caption class="muted" style="text-align:left;caption-side:top;padding-bottom:6px">Ordered by severity, then how many pages it affects.</caption>'
          '<thead><tr><th scope="col">#</th><th scope="col">Issue</th><th scope="col">Criterion</th><th scope="col">Severity</th><th scope="col">Pages</th></tr></thead><tbody>')
        for f in top:
            w(f'<tr><td><a href="#{e(f["id"])}">{e(f["id"])}</a></td><td>{e(f["title"])}</td><td>{e(", ".join(f["scs"]))}</td><td>{sev_badge(f["severity"])}</td><td>{len([u for u in f["where"] if u])}</td></tr>')
        w("</tbody></table></div>")
    else:
        w("<p>Nothing to fix from the checks that ran. Start the manual checks in the coverage table.</p>")
    w("</section>")

    # --- gallery
    shots = [p for p in pages if p.get("shot") and p["shot"]["legend"]]
    if shots:
        w('<section aria-labelledby="seen"><h2 id="seen">What we saw</h2><p class="lead">Screenshots taken during the scan. Failing elements are outlined in red and numbered; the numbers match the list under each picture.</p><div class="gallery">')
        for p in shots:
            uri = imgs.uri(p["shot"]["file"])
            if not uri:
                continue
            leg = [(x["n"], fid_by_rule.get(x["rule"], x["rule"]), next((f["title"] for f in findings if f["rule"] == x["rule"]), x["rule"])) for x in p["shot"]["legend"]]
            alt = f"Screenshot of {short(p['url'], target)} with {len(leg)} issue types outlined: " + "; ".join(f"{n} {t}" for n, _, t in leg[:6])
            w(f'<figure class="shot"><img src="{uri}" alt="{e(alt)}" loading="lazy"><figcaption><b>{e(short(p["url"], target))}</b> '
              f'<span>{e(p.get("title", ""))}</span><ol>' + "".join(f'<li value="{n}"><a href="#{e(fid)}">{e(fid)}</a> {e(t)}</li>' for n, fid, t in leg) + "</ol></figcaption></figure>")
        w("</div></section>")

    # --- findings
    w('<section aria-labelledby="findings"><h2 id="findings">All findings</h2>')
    w('<p class="lead">Each finding names the WCAG success criterion it fails and which of the selected laws or policies require that criterion. A finding required by none of them is best practice, not a legal gap.</p>')
    for f in findings:
        c = SC.get(f["scs"][0], {})
        w(f'<article class="cite" id="{e(f["id"])}"><div class="sc">{e(f["scs"][0])}<small>{e(c.get("name", "Unmapped"))} &middot; Level {e(c.get("level", "–"))}</small></div><div class="body">')
        w(f'<div class="top"><h3>{e(f["title"])}</h3>{sev_badge(f["severity"])}</div>')
        if c.get("plain"):
            w(f"<p><b>What this means:</b> {e(c['plain'])}</p>")
        if f.get("detail"):
            w(f'<p class="muted">{e(f["detail"])}</p>')
        crop = imgs.uri(f["crop"]["file"]) if f.get("crop") else None
        if crop:
            w(f'<img src="{crop}" alt="Close-up of the failing element on {e(short(f["crop"]["page"], target))}" loading="lazy">')
        if f["required_by"]:
            w('<p class="req"><b>Required by:</b> ' + "".join(f'<span class="law">{e(m["reg"][i]["name"])}</span>' for i in f["required_by"]) + "</p>")
        else:
            w('<p class="req bp">Best practice: not required by the selected standards.</p>')
        where = [short(u, target) for u in f["where"] if u]
        meta = f'{e(f["id"])} &middot; {e(f["source"])} &middot; {f["instances"]} instance{"s" if f["instances"] != 1 else ""}'
        if where:
            meta += " on " + e(", ".join(where[:5])) + (f" and {len(where) - 5} more" if len(where) > 5 else "")
        w(f'<p class="muted">{meta}</p>')
        if f.get("fix"):
            w(f"<p><b>Fix:</b> {e(f['fix'])}</p>")
        if f.get("examples"):
            w("<details><summary>Show where in the code</summary>")
            for x in f["examples"]:
                w(f'<p class="muted" style="margin-top:8px">{e(short(x["page"], target))} &middot; <code>{e(x["target"])}</code></p><pre>{e(x["html"])}</pre>')
                if x.get("summary"):
                    w(f'<pre>{e(x["summary"])}</pre>')
            w("</details>")
        if f.get("fix_url"):
            w(f'<p class="muted"><a href="{e(f["fix_url"])}">How to fix {e(f["scs"][0])}</a></p>')
        w("</div></article>")
    if not findings:
        w("<p>No findings from the checks that ran.</p>")
    w("</section>")

    # --- page scores
    if m["per_page"]:
        w('<section aria-labelledby="pages"><h2 id="pages">Page scores</h2><p class="lead">Each page starts at 100 and loses 15 per critical, 8 per serious, 3 per moderate and 1 per minor issue type on it. Lowest first.</p>')
        w('<div class="tablewrap"><table><thead><tr><th scope="col">Page</th><th scope="col">Score</th></tr></thead><tbody>')
        for u, s in sorted(m["per_page"], key=lambda x: x[1])[:40]:
            w(f'<tr><th scope="row" style="font-weight:400"><a href="{e(u)}">{e(short(u, target))}</a></th><td><span class="bar" style="width:{max(2, s)}px" aria-hidden="true"></span>{s} ({grade(s)})</td></tr>')
        w("</tbody></table></div>")
        if len(m["per_page"]) > 40:
            w(f'<p class="muted">{len(m["per_page"]) - 40} more pages in findings.json.</p>')
        w("</section>")

    # --- law
    w('<section aria-labelledby="law"><h2 id="law">What the law requires</h2>')
    w('<p class="lead">The standards that apply to this organization, with the documents to cite. Registry entries carry their research date and confidence; anything marked low confidence needs a check against the source before it is quoted.</p>')
    order = {"binding": 0, "conditional": 1, "reference": 2}
    for j in sorted(m["juris"], key=lambda j: order[m["role"][j["id"]]]):
        v, lvl, known = m["targets"][j["id"]]
        conf = j.get("confidence", "?")
        rl = m["role"][j["id"]]
        label = {"binding": "Binding", "conditional": "May apply", "reference": "Reference only"}[rl]
        w(f'<div class="juris" id="j-{e(j["id"])}"><div class="top" style="display:flex;gap:12px;align-items:center;flex-wrap:wrap"><h3>{e(j["name"])}</h3><span class="role {rl}">{label}</span></div><dl>')
        w(f"<dt>Standard</dt><dd>{e(j.get('standard'))}" + ("" if known else ' <span class="conf-low">(mapped to WCAG 2.1 AA by default)</span>') + "</dd>")
        if j.get("applies_to"):
            w(f"<dt>Applies to</dt><dd>{e(j['applies_to'])}</dd>")
        if j.get("laws") or j.get("policy_docs"):
            items = [(l.get("cite"), l.get("url"), l.get("summary")) for l in j.get("laws") or []] + [(d.get("title"), d.get("url"), None) for d in j.get("policy_docs") or []]
            w("<dt>Law and policy</dt><dd>" + "<br>".join((f'<a href="{e(u)}">{e(t)}</a>' if u else e(t)) + (f": {e(s)}" if s else "") for t, u, s in items) + "</dd>")
        if j.get("deadlines"):
            w("<dt>Deadlines</dt><dd>" + "<br>".join(f"{e(d.get('date'))}: {e(d.get('what'))}" for d in j["deadlines"]) + "</dd>")
        if j.get("requires"):
            w("<dt>Also requires</dt><dd>" + "; ".join(e(r) for r in j["requires"]) + "</dd>")
        if j.get("exceptions"):
            w("<dt>Exceptions</dt><dd>" + "; ".join(e(r) for r in j["exceptions"]) + "</dd>")
        for k, label in (("mobile", "Mobile apps"), ("procurement", "Procurement"), ("enforcement", "Enforcement")):
            if j.get(k):
                w(f"<dt>{label}</dt><dd>{e(j[k])}</dd>")
        if j.get("office_url"):
            w(f'<dt>Office</dt><dd><a href="{e(j["office_url"])}">{e(j["office_url"])}</a></dd>')
        w(f"<dt>Research</dt><dd>as of {e(j.get('as_of'))}, confidence <span class=\"{'conf-low' if conf == 'low' else ''}\">{e(conf)}</span>"
          + (f". {e(j['notes'])}" if j.get("notes") else "") + "</dd></dl></div>")
    w("</section>")

    # --- coverage
    labels = {"fail": ("fail", "Fails"), "review": ("review", "Needs review"), "pass": ("pass", "Passes (manual)"),
              "pass-auto": ("pass", "No failures found (automated)"), "na": ("na", "Not applicable"), "untested": ("untested", "Not tested")}
    w('<section aria-labelledby="coverage"><h2 id="coverage">What was and wasn\'t tested</h2>')
    w(f'<p class="lead">Every WCAG {e(m["top"])} Level A and AA criterion. "Not tested" means nobody has checked it yet; it is a to-do, not a pass. The last column is the manual check a tester runs.</p>')
    w('<div class="tablewrap"><table><thead><tr><th scope="col">Criterion</th><th scope="col">Level</th><th scope="col">Result</th><th scope="col">How to check</th></tr></thead><tbody>')
    for s in m["scope_scs"]:
        c = SC[s]
        cls, lab = labels[m["status"][s]]
        note = (m["mres"].get(s) or {}).get("note")
        w(f'<tr><th scope="row" style="font-weight:600">{e(s)} {e(c["name"])}</th><td>{e(c["level"])}</td><td><span class="st {cls}">{e(lab)}</span>'
          + (f'<br><span class="muted">{e(note)}</span>' if note else "") + f'</td><td class="muted">{e(c["test"])}</td></tr>')
    w("</tbody></table></div></section>")

    if docs:
        w('<section aria-labelledby="documents"><h2 id="documents">Documents linked from the site</h2>')
        w(f'<p class="lead">{len(docs)} PDF or Office documents were found. Documents are covered by the same rules as web pages (unless an archive or pre-existing-document exception applies) and were not scanned here. Check them with a PDF accessibility checker.</p>')
        w("<details><summary>List the documents</summary><ul>" + "".join(f'<li><a href="{e(d)}">{e(d.rsplit("/", 1)[-1][:90])}</a></li>' for d in docs[:100]) + "</ul></details></section>")

    # --- method
    lim = scope.get("limits", {})
    w('<section aria-labelledby="method"><h2 id="method">How this was measured</h2><div class="tablewrap"><table><tbody>')
    rows = [("Target", target or a.product),
            ("Scope", a.scope or ("Same-site pages reachable from the start page" if scan else "Manual review only")),
            ("Scan limits", ", ".join(f"{k} {v}" for k, v in lim.items()) if lim else "–"),
            ("Why the scan stopped", scope.get("stopReason", "–")),
            ("Pages", f"{len(pages)} scanned of {scan.get('pagesDiscovered', 0)} discovered; {scope.get('notYetScanned', 0)} discovered but not scanned" if scan else "–"),
            ("Skipped", ", ".join(f"{v} {k}" for k, v in (scope.get("skipped") or {}).items()) or "–"),
            ("Automated engine", f"axe-core via Playwright, tags {', '.join(scan.get('tool', {}).get('tags', []))}; 320px reflow; keyboard sample" if scan else "none"),
            ("Score", "Mean of page scores; each page starts at 100 and loses 15/8/3/1 per critical/serious/moderate/minor issue type. Manual findings subtract once each. Grades: A 90+, B 80+, C 70+, D 60+, F below 60."),
            ("Manual checks", f"{len(m['mres'])} criteria recorded, {len(m['manual'].get('findings', []))} manual findings" if m["manual"] else "none recorded"),
            ("Engine 'needs review' items", str(sum(r["count"] for r in m["review"])) if m["review"] else "0"),
            ("Report generated", m["stamp"])]
    for k, v in rows:
        w(f'<tr><th scope="row">{e(k)}</th><td>{e(v)}</td></tr>')
    w("</tbody></table></div>")
    errs = [p for p in pages if p.get("error")]
    if errs:
        w(f'<p class="muted">{len(errs)} page(s) could not be scanned: ' + e("; ".join(f"{p['url']} ({p['error'][:80]})" for p in errs[:5])) + "</p>")
    if imgs.dropped:
        w(f'<p class="muted">{imgs.dropped} screenshot(s) left out to keep the report under its size limit; they are in the scan folder.</p>')
    w("</section>")

    # --- audit trail
    if m["a"].run:
        r = ledger.load(m["a"].run)
        w('<section aria-labelledby="trail"><h2 id="trail">Audit trail</h2><p class="lead">What was decided, by whom and why, and every step of this run. '
          'The full log is <code>log.jsonl</code> in the run folder.</p>')
        if r["decisions"]:
            w('<div class="tablewrap"><table><thead><tr><th scope="col">Decision</th><th scope="col">Value</th><th scope="col">Why</th><th scope="col">By</th><th scope="col">When (UTC)</th></tr></thead><tbody>')
            for k, v in r["decisions"].items():
                val = v["value"]
                if isinstance(val, dict):
                    val = "; ".join(f"{kk}: {', '.join(vv) if isinstance(vv, list) else vv}" for kk, vv in val.items())
                elif not isinstance(val, str):
                    val = json.dumps(val)
                by = v["by"] + (f" (carried from {v['carried_from']})" if v.get("carried_from") else "")
                w(f'<tr><th scope="row">{e(k)}</th><td>{e(val[:160])}</td><td>{e(v["why"])}</td><td>{e(by)}</td><td>{e(v["at"].replace("T", " ").rstrip("Z"))}</td></tr>')
            w("</tbody></table></div>")
        logp = Path(m["a"].run) / "log.jsonl"
        events = [json.loads(x) for x in logp.read_text().splitlines() if x.strip()] if logp.exists() else []
        events = [ev for ev in events if ev.get("step") != "scan-page"]
        if events:
            w('<details style="margin-top:14px"><summary>Show the run log (' + str(len(events)) + ' events)</summary><ol class="trail">'
              + "".join(f'<li><code>{e(ev["at"][11:19])}</code> {e(ev["step"])}: {e(ev["event"])} <span class="muted">({e(ev["by"])})</span></li>' for ev in events[-200:]) + "</ol></details>")
        w(f'<p class="muted" style="margin-top:10px">Run folder: <code>{e(Path(m["a"].run).name)}</code> in <code>{e(r["site"])}</code>.</p></section>')

    # --- fix prompt
    w('<section aria-labelledby="prompt"><h2 id="prompt">Fix prompt</h2>')
    w('<p class="lead">Paste this into an AI coding agent (Claude Code, Cursor, Copilot) working in the site&rsquo;s code. It lists every issue with the failing elements, '
      'the legal target, and how to verify each fix. The same text is saved next to this report as a Markdown file.</p>')
    w('<div class="prompt"><div class="bar2"><b>Fix every issue in this report</b><span><button class="copy" type="button" data-target="fixprompt" data-status="copystatus">Copy prompt</button> '
      '<span id="copystatus" class="muted" role="status" aria-live="polite"></span></span></div>'
      f'<pre id="fixprompt" tabindex="0" aria-label="Fix prompt text">{e(prompt_text)}</pre></div></section>')

    w('<footer><p>Made with Access Atlas, an open-source accessibility audit that maps findings to the laws that require them. '
      "Confirm legal interpretation with counsel or the jurisdiction&rsquo;s accessibility office.</p></footer></div>")
    w(f"<script>{COPY_JS}</script>")
    return "\n".join(H)


def main():
    ap = argparse.ArgumentParser(description="Render an Access Atlas report. With --run, owner, standards and scope come from the run's decisions.")
    ap.add_argument("--run", help="run folder from ledger.py open; outputs go there and the audit trail is included")
    ap.add_argument("--jurisdictions", help="comma-separated registry ids; optional when the run records the owner")
    ap.add_argument("--scan", help="scan.json files, comma-separated (default: scan*.json and tasks*.json in the run)")
    ap.add_argument("--manual")
    ap.add_argument("--org")
    ap.add_argument("--product")
    ap.add_argument("--entity")
    ap.add_argument("--country")
    ap.add_argument("--region")
    ap.add_argument("--place")
    ap.add_argument("--population", choices=["50k+", "under-50k"], help="US local governments: picks the right ADA Title II deadline")
    ap.add_argument("--auditor", default="")
    ap.add_argument("--scope", default="")
    ap.add_argument("--kind", default="website", choices=["website", "mobile app", "website and mobile app"])
    ap.add_argument("--out")
    a = ap.parse_args()
    if a.run:
        r = ledger.load(a.run)
        if not a.scan:
            found = sorted(Path(a.run).glob("scan*.json")) + sorted(Path(a.run).glob("tasks*.json"))
            a.scan = ",".join(str(x) for x in found) or None
        if not a.manual and (Path(a.run) / "manual.json").exists():
            a.manual = str(Path(a.run) / "manual.json")
        a.product = a.product or r["site"]
        a.out = a.out or str(Path(a.run) / f"{r['site']}.html")
        if not a.scope and r["decisions"].get("scope"):
            sc = r["decisions"]["scope"]
            a.scope = f"{sc['value'] if isinstance(sc['value'], str) else json.dumps(sc['value'])} ({sc['why']})"
    if not a.product:
        ap.error("--product is required without --run")
    a.out = a.out or "a11y-report.html"
    m = build(a)

    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fj = out.with_name(out.stem + ".findings.json")
    fj.write_text(json.dumps({"org": a.org, "product": a.product, "generated": m["stamp"], "standard": f"WCAG {m['top']} AA",
                              "jurisdictions": m["jids"], "binding": [j["id"] for j in m["binding"]], "owner": m["own"],
                              "score": m["score"], "grade": grade(m["score"]) if m["score"] is not None else None,
                              "pages": [{"url": u, "score": s} for u, s in m["per_page"]],
                              "coverage": {s: m["status"][s] for s in m["scope_scs"]},
                              "findings": [{k: f.get(k) for k in ("id", "severity", "title", "detail", "scs", "required_by", "where", "instances", "fix_url", "source", "rule")} for f in m["findings"]]},
                             indent=2))
    if a.run:
        prev = ledger.previous(a.run)
        d = ledger.compare(prev, a.run) if prev else None
        if d:
            d["older_name"] = prev.name
            m["delta"] = d
            (Path(a.run) / "compare.json").write_text(json.dumps(d, indent=2) + "\n")
    prompt_text = fix_prompt(m)
    body = render_html(m, prompt_text)
    # Disk copy is a full document (emailed, printed, opened offline). The Artifact tool
    # wraps its own skeleton, so it gets the fragment.
    out.write_text('<!doctype html>\n<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">\n'
                   + body.replace("</style>", "</style></head><body>", 1) + "\n</body></html>")
    out.with_name(out.stem + ".artifact.html").write_text(body)
    out.with_name(out.stem + ".fix-prompt.md").write_text(prompt_text)
    g = grade(m["score"]) if m["score"] is not None else "-"
    if a.run:
        ledger.main(["ledger.py", "attach", a.run, "report", str(out), str(out.with_name(out.stem + ".artifact.html")),
                     str(fj), str(out.with_name(out.stem + ".fix-prompt.md"))])
        ledger.main(["ledger.py", "step", a.run, "render", "done", "--note",
                     f"grade {g} ({m['score']}), {len(m['legal'])} legal findings, WCAG {m['top']} AA"])
    size = out.stat().st_size / 1e6
    print(f"wrote {out} ({size:.1f} MB) + .artifact.html, .findings.json, .fix-prompt.md: score {m['score']} ({g}), "
          f"{len(m['findings'])} findings ({len(m['legal'])} legal), coverage fail={m['counts']['fail']} review={m['counts']['review']} untested={m['counts']['untested']}"
          + (f"; since last run: {len(m['delta']['fixed'])} fixed, {len(m['delta']['new'])} new" if m.get("delta") else ""))


if __name__ == "__main__":
    main()
