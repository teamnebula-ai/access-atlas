#!/usr/bin/env python3
"""Look up the Access Atlas law registry (registry/<country>/.../<id>.json).

  jurisdictions.py list [text]      # ids + names + standard, optionally filtered
  jurisdictions.py show <id>        # one entry, pretty
  jurisdictions.py resolve <id,...> # the ids plus every parent they inherit (e.g. a state pulls in ADA Title II)
  jurisdictions.py check            # registry health: schema, stale as_of, low-confidence entries
"""
import json
import os
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(os.environ.get("ACCESS_ATLAS_REGISTRY") or Path(__file__).resolve().parent.parent / "registry")
# Research files name the federal floor loosely; these map to the concrete entries.
ALIASES = {"us-federal": "us-ada-title-ii", "us-ada": "us-ada-title-ii", "us-508": "us-federal-508", "eu": "eu-wad"}
REQUIRED = ["id", "name", "level", "standard", "as_of", "confidence", "sources"]
STALE_DAYS = 365


def load():
    """Every *.json under the registry: one jurisdiction per file (a list is also accepted)."""
    reg = {}
    for f in sorted(ROOT.rglob("*.json")):
        data = json.loads(f.read_text())
        for e in data if isinstance(data, list) else [data]:
            if e["id"] in reg:
                raise SystemExit(f"duplicate id {e['id']} in {f} and {reg[e['id']]['_file']}")
            e["_file"] = str(f.relative_to(ROOT))
            e["_in_list"] = isinstance(data, list)
            reg[e["id"]] = e
    return reg


def canon(i, reg):
    i = i.strip().lower()
    i = ALIASES.get(i, i)
    return i if i in reg else None


def resolve(ids, reg):
    out, missing = [], []
    for raw in ids:
        i = canon(raw, reg)
        if not i:
            missing.append(raw)
            continue
        while i and i not in out:
            out.append(i)
            p = reg[i].get("parent")
            i = canon(p, reg) if p else None
    return out, missing


def wcag_target(standard):
    """Map a standard string to (version, level). Section 508 = WCAG 2.0 AA; EN 301 549 v3.x = 2.1 AA."""
    s = (standard or "").upper()
    m = re.search(r"WCAG\s*(2\.[0-2])\s*(?:LEVEL\s*)?(AAA|AA|A)?", s)
    if m:
        return m.group(1), (m.group(2) or "AA"), True
    if "508" in s:
        return "2.0", "AA", True
    if "301 549" in s or "301549" in s:
        return "2.1", "AA", True
    return "2.1", "AA", False  # unknown: assume the ADA Title II floor, and say so


def main(argv):
    reg = load()
    cmd = argv[1] if len(argv) > 1 else "list"
    if cmd == "list":
        q = " ".join(argv[2:]).lower()
        for e in reg.values():
            line = f"{e['id']:<24} {e['name'][:44]:<44} {e.get('standard', '')[:40]}  [{e.get('confidence', '?')}]"
            if not q or q in line.lower():
                print(line)
    elif cmd == "show":
        i = canon(argv[2], reg)
        if not i:
            sys.exit(f"unknown jurisdiction: {argv[2]} (try: jurisdictions.py list {argv[2]})")
        e = dict(reg[i])
        e.pop("_file")
        e.pop("_in_list")
        print(json.dumps(e, indent=2))
    elif cmd == "resolve":
        out, missing = resolve(argv[2].split(","), reg)
        print(",".join(out))
        if missing:
            sys.exit(f"unknown: {', '.join(missing)}")
    elif cmd == "check":
        bad = 0
        today = date.today()
        for e in reg.values():
            miss = [k for k in REQUIRED if not e.get(k)]
            if "sources" in miss and e.get("confidence") == "low":
                miss.remove("sources")  # allowed only when labelled low; the report shows the label
                print(f"UNSOURCED {e['id']}: no primary source opened — verify before quoting")
            if not (e.get("laws") or e.get("policy_docs")):
                miss.append("laws or policy_docs")
            if not e.get("_in_list") and Path(e["_file"]).stem != e["id"]:
                miss.append(f"file name to match id ({e['_file']})")
            if miss:
                bad += 1
                print(f"SCHEMA  {e['id']}: missing {', '.join(miss)}")
            try:
                age = (today - date.fromisoformat(e["as_of"])).days
                if age > STALE_DAYS:
                    print(f"STALE   {e['id']}: as_of {e['as_of']} ({age} days)")
            except Exception:
                print(f"DATE    {e['id']}: bad as_of {e.get('as_of')}")
            if e.get("confidence") == "low":
                print(f"LOW     {e['id']}: {e.get('notes', '')[:110]}")
            if not wcag_target(e.get("standard"))[2]:
                print(f"STD     {e['id']}: standard '{e.get('standard')}' not mapped to a WCAG version")
        print(f"{len(reg)} entries, {bad} schema errors")
        sys.exit(1 if bad else 0)
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv)
