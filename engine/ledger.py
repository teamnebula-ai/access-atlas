#!/usr/bin/env python3
"""The audit ledger: every run gets a folder that records what was decided, by whom, and what came out.

  ledger.py open <url> [--home DIR] [--carry]         create a run folder, print its path; --carry copies the
                                                      owner and standards decisions from the last finished run
  ledger.py decide <run> <key> <value> --why TEXT --by user|agent
                                                      record a decision (owner, standards, scope, population...)
  ledger.py note <run> <step> <text> [--by tool|agent|user] [--data JSON]
                                                      append an event to the run's log
  ledger.py step <run> <step> done|skipped|failed [--note TEXT]
  ledger.py attach <run> <kind> <file> [<file>...]    register an output with its sha256
  ledger.py show <run>                                decisions, steps, outputs, in plain text
  ledger.py history <site-folder>                     every run of a site: date, grade, score, legal issues, scope
  ledger.py compare <older-run> <newer-run>           fixed / new / still failing; writes compare.json in the newer run
  ledger.py previous <run>                            path of the last finished run of the same site, if any

Layout (default home ./a11y-audits, or $ACCESS_ATLAS_HOME):
  <home>/<host>/<YYYY-MM-DD_HHMMSS>/run.json   decisions, step status, outputs
                                    log.jsonl  one event per line, append-only
                                    ...        scans, screenshots, the report
Stdlib only. Nothing here is rewritten once written except run.json's current-state fields;
the log is the history.
"""
import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

STEPS = ["identify", "standards", "size", "scope", "scan", "manual", "render", "publish", "handback"]
DECISIONS = {"owner", "entity", "country", "region", "place", "population", "standards", "scope", "key_tasks", "auth"}


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def host_of(url):
    m = re.match(r"https?://([^/:]+)", url)
    return re.sub(r"^www\.", "", m.group(1).lower()) if m else re.sub(r"[^a-z0-9.-]+", "-", url.lower())


def load(run):
    p = Path(run) / "run.json"
    if not p.exists():
        sys.exit(f"not a run folder: {run} (no run.json)")
    return json.loads(p.read_text())


def save(run, data):
    p = Path(run) / "run.json"
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n")
    tmp.replace(p)


def log(run, step, event, by="tool", data=None):
    rec = {"at": now(), "step": step, "event": event, "by": by}
    if data is not None:
        rec["data"] = data
    with open(Path(run) / "log.jsonl", "a") as f:
        f.write(json.dumps(rec) + "\n")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def finding_key(f):
    """Stable identity for a finding across runs: the rule (or criterion + title for manual ones)."""
    return f.get("rule") if f.get("source") == "automated" else f"{','.join(f.get('scs', []))}|{f.get('title', '').lower()}"


def scope_of(run):
    d = load(run)["decisions"].get("scope")
    return json.dumps(d["value"]) if d else None


def compare(old_run, new_run):
    def findings(run):
        p = Path(run) / "findings.json"
        if not p.exists():
            cands = sorted(Path(run).glob("*.findings.json"))
            p = cands[0] if cands else None
        return json.loads(p.read_text()) if p else None
    a, b = findings(old_run), findings(new_run)
    if not a or not b:
        return None
    ka = {finding_key(f): f for f in a["findings"] if f["severity"] != "review"}
    kb = {finding_key(f): f for f in b["findings"] if f["severity"] != "review"}
    out = {
        "older": str(old_run), "newer": str(new_run),
        "score": {"before": a.get("score"), "after": b.get("score")},
        "scope_changed": scope_of(old_run) != scope_of(new_run),
        "pages_before": sorted(p["url"] for p in a.get("pages", [])), "pages_after": sorted(p["url"] for p in b.get("pages", [])),
        "fixed": [{"title": ka[k]["title"], "scs": ka[k]["scs"], "severity": ka[k]["severity"]} for k in ka if k not in kb],
        "new": [{"id": kb[k]["id"], "title": kb[k]["title"], "scs": kb[k]["scs"], "severity": kb[k]["severity"]} for k in kb if k not in ka],
        "still": [{"id": kb[k]["id"], "title": kb[k]["title"], "pages_before": len(ka[k]["where"]), "pages_now": len(kb[k]["where"])} for k in kb if k in ka],
    }
    return out


def previous(run):
    run = Path(run).resolve()
    sibs = sorted(p for p in run.parent.iterdir() if p.is_dir() and p != run and p.name < run.name and (p / "run.json").exists())
    for p in reversed(sibs):
        if load(p).get("steps", {}).get("render", {}).get("status") == "done":
            return p
    return None


def main(argv):
    ap = argparse.ArgumentParser(prog="ledger.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    o = sub.add_parser("open"); o.add_argument("url"); o.add_argument("--carry", action="store_true"); o.add_argument("--home", default=os.environ.get("ACCESS_ATLAS_HOME", "a11y-audits"))
    d = sub.add_parser("decide"); d.add_argument("run"); d.add_argument("key"); d.add_argument("value"); d.add_argument("--why", required=True); d.add_argument("--by", required=True, choices=["user", "agent"])
    n = sub.add_parser("note"); n.add_argument("run"); n.add_argument("step"); n.add_argument("text"); n.add_argument("--by", default="agent", choices=["tool", "agent", "user"]); n.add_argument("--data")
    s = sub.add_parser("step"); s.add_argument("run"); s.add_argument("step", choices=STEPS); s.add_argument("status", choices=["done", "skipped", "failed"]); s.add_argument("--note", default="")
    t = sub.add_parser("attach"); t.add_argument("run"); t.add_argument("kind"); t.add_argument("files", nargs="+")
    sh = sub.add_parser("show"); sh.add_argument("run")
    hi = sub.add_parser("history"); hi.add_argument("site")
    c = sub.add_parser("compare"); c.add_argument("older"); c.add_argument("newer")
    pv = sub.add_parser("previous"); pv.add_argument("run")
    a = ap.parse_args(argv[1:])

    if a.cmd == "open":
        run = Path(a.home) / host_of(a.url) / datetime.now().strftime("%Y-%m-%d_%H%M%S")
        run.mkdir(parents=True, exist_ok=False)
        save(run, {"schema": 1, "url": a.url, "site": host_of(a.url), "opened": now(), "decisions": {},
                   "steps": {k: {"status": "pending"} for k in STEPS}, "outputs": []})
        log(run, "open", f"run opened for {a.url}")
        prev = previous(run)
        if prev:
            log(run, "open", f"previous finished run: {prev.name}")
            if a.carry:
                r = load(run)
                keep = {k: v for k, v in load(prev)["decisions"].items() if k != "scope"}
                for k, v in keep.items():
                    r["decisions"][k] = {**v, "carried_from": prev.name}
                save(run, r)
                log(run, "decide", f"carried {', '.join(keep)} from {prev.name}; scope is decided fresh each run", by="agent")
        elif a.carry:
            print("no finished earlier run to carry decisions from", file=sys.stderr)
        print(run)
    elif a.cmd == "decide":
        r = load(a.run)
        if a.key not in DECISIONS:
            print(f"note: '{a.key}' is not a standard decision key ({', '.join(sorted(DECISIONS))})", file=sys.stderr)
        try:
            value = json.loads(a.value)
        except json.JSONDecodeError:
            value = a.value
        old = r["decisions"].get(a.key)
        r["decisions"][a.key] = {"value": value, "why": a.why, "by": a.by, "at": now()}
        save(a.run, r)
        log(a.run, "decide", f"{a.key} = {json.dumps(value)}" + (f" (was {json.dumps(old['value'])})" if old else ""), by=a.by, data={"why": a.why})
    elif a.cmd == "note":
        log(a.run, a.step, a.text, by=a.by, data=json.loads(a.data) if a.data else None)
    elif a.cmd == "step":
        r = load(a.run)
        r["steps"][a.step] = {"status": a.status, "at": now(), **({"note": a.note} if a.note else {})}
        save(a.run, r)
        log(a.run, a.step, f"{a.step} {a.status}" + (f": {a.note}" if a.note else ""))
    elif a.cmd == "attach":
        r = load(a.run)
        for f in a.files:
            p = Path(f)
            if not p.exists():
                sys.exit(f"no such file: {f}")
            rel = os.path.relpath(p.resolve(), Path(a.run).resolve())
            r["outputs"] = [x for x in r["outputs"] if x["path"] != rel]
            r["outputs"].append({"kind": a.kind, "path": rel, "sha256": sha256(p), "bytes": p.stat().st_size, "at": now()})
            log(a.run, "attach", f"{a.kind}: {rel}")
        save(a.run, r)
    elif a.cmd == "show":
        r = load(a.run)
        print(f"{r['site']}  run {Path(a.run).name}  ({r['url']})")
        print("Decisions:")
        for k, v in r["decisions"].items():
            print(f"  {k:<11} {json.dumps(v['value'])[:70]:<70} by {v['by']}: {v['why'][:60]}")
        print("Steps:    " + "  ".join(f"{k}:{v['status']}" for k, v in r["steps"].items()))
        for x in r["outputs"]:
            print(f"  {x['kind']:<10} {x['path']}  {x['sha256'][:12]}")
    elif a.cmd == "history":
        rows = []
        for p in sorted(Path(a.site).iterdir()):
            if not (p / "run.json").exists():
                continue
            r = load(p)
            fj = next(iter(sorted(p.glob("*.findings.json"))), None)
            f = json.loads(fj.read_text()) if fj else {}
            legal = sum(1 for x in f.get("findings", []) if x.get("required_by") and x.get("severity") != "review")
            scope = (r["decisions"].get("scope") or {}).get("value", "")
            rows.append((p.name, f.get("grade") or "-", f.get("score") if f.get("score") is not None else "-", legal if f else "-", f.get("standard", "-"), str(scope)[:40]))
        print(f"{'run':<19} {'grade':<6}{'score':<7}{'legal':<7}{'standard':<15} scope")
        for row in rows:
            print(f"{row[0]:<19} {row[1]:<6}{str(row[2]):<7}{str(row[3]):<7}{row[4]:<15} {row[5]}")
    elif a.cmd == "compare":
        out = compare(a.older, a.newer)
        if not out:
            sys.exit("both runs need a rendered report (findings.json) to compare")
        (Path(a.newer) / "compare.json").write_text(json.dumps(out, indent=2) + "\n")
        log(a.newer, "compare", f"vs {Path(a.older).name}: {len(out['fixed'])} fixed, {len(out['new'])} new, {len(out['still'])} still failing")
        print(f"score {out['score']['before']} -> {out['score']['after']}: {len(out['fixed'])} fixed, {len(out['new'])} new, {len(out['still'])} still failing")
    elif a.cmd == "previous":
        p = previous(a.run)
        if p:
            print(p)
        else:
            sys.exit(1)


if __name__ == "__main__":
    main(sys.argv)
