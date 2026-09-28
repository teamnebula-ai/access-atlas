#!/usr/bin/env python3
"""Look up the Access Atlas law registry (registry/<country>/.../<id>.json).

  jurisdictions.py list [text]      # ids + names + standard, optionally filtered
  jurisdictions.py show <id>        # one entry, pretty
  jurisdictions.py resolve <id,...> # the ids plus every parent they inherit (e.g. a state pulls in ADA Title II)
  jurisdictions.py applicable --country US --region TX --entity county [--place "Travis County"]
                                    # which laws bind this organization, which may, which are reference only
  jurisdictions.py check            # registry health: schema, stale as_of, low-confidence entries
"""
import json
import os
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(os.environ.get("ACCESS_ATLAS_REGISTRY") or Path(__file__).resolve().parent.parent / "data" / "registry")
# Research files name the federal floor loosely; these map to the concrete entries.
ALIASES = {"us-federal": "us-ada-title-ii", "us-ada": "us-ada-title-ii", "us-508": "us-federal-508", "eu": "eu-wad"}
REQUIRED = ["id", "name", "level", "standard", "as_of", "confidence", "sources"]
STALE_DAYS = 365
# Who a law can bind. Outside the US, "public-sector-body" in an entry's covers means any government body.
GOVERNMENT = ["federal-agency", "state-agency", "county", "city", "special-district", "public-school", "public-university", "court"]
ENTITIES = GOVERNMENT + ["public-sector-body", "private-business"]
EU = {"AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE", "GR", "HU", "IE", "IT", "LV", "LT", "LU", "MT", "NL", "PL", "PT", "RO", "SK", "SI", "ES", "SE"}


def load(root=None):
    """Every *.json under the registry: one jurisdiction per file (a list is also accepted)."""
    reg = {}
    root = Path(root) if root else ROOT
    for f in sorted(root.rglob("*.json")):
        data = json.loads(f.read_text())
        for e in data if isinstance(data, list) else [data]:
            if e["id"] in reg:
                raise SystemExit(f"duplicate id {e['id']} in {f} and {reg[e['id']]['_file']}")
            e["_file"] = str(f.relative_to(root))
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


def core(name):
    """'City of New York', 'New York City' and 'NYC' all reduce to 'new york'."""
    n = re.sub(r"[^a-z ]", " ", name.lower())
    n = re.sub(r"\b(city and county of|city of|county of|town of|the|city|county|parish|borough)\b", " ", n)
    n = " ".join(n.split())
    return {"nyc": "new york", "sf": "san francisco", "la": "los angeles"}.get(n, n)


def applicable(reg, country, entity, region=None, place=None):
    """Split the registry into laws that bind this organization, may bind it, or are context only.

    Geography first (country, EU membership, US state, city), then who the law covers.
    Returns (binding, conditional, reference) as lists of ids."""
    country = (country or "").upper()
    region = (region or "").upper()
    place = (place or "").lower()
    binding, conditional, reference = [], [], []
    for e in reg.values():
        ec = (e.get("country") or "").upper()
        if not (ec == country or (ec == "EU" and country in EU)):
            continue
        if e.get("region") and e["region"] != region:
            continue
        if e.get("place") and (not place or core(e["place"]) != core(place)):
            continue
        covers = e.get("covers", [])
        cond = (e.get("covers_conditionally") or {}).get("entities", [])
        if entity in covers or ("public-sector-body" in covers and entity in GOVERNMENT and ec != "US"):
            binding.append(e["id"])
        elif entity in cond:
            conditional.append(e["id"])
        elif e.get("level") in ("state", "territory", "district", "provincial", "national", "standard"):
            reference.append(e["id"])
    return binding, conditional, reference


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
    elif cmd == "applicable":
        import argparse
        ap = argparse.ArgumentParser(prog="jurisdictions.py applicable")
        ap.add_argument("--country", required=True)
        ap.add_argument("--entity", required=True, choices=ENTITIES)
        ap.add_argument("--region")
        ap.add_argument("--place")
        ap.add_argument("--json", action="store_true")
        a = ap.parse_args(argv[2:])
        b, c, r = applicable(reg, a.country, a.entity, a.region, a.place)
        if a.json:
            print(json.dumps({"binding": b, "conditional": c, "reference": r}))
            return
        for label, ids in (("Binding", b), ("May apply", c), ("Reference only", r)):
            print(f"{label}:")
            for i in ids:
                e = reg[i]
                why = (e.get("covers_conditionally") or {}).get("when", "") if label == "May apply" else ", ".join(e.get("covers", []))
                print(f"  {i:<22} {e['name'][:48]:<48} {wcag_target(e.get('standard'))[0]}  [{why}]")
            if not ids:
                print("  (none)")
        if not b:
            sys.exit("No binding law found in the registry for this organization. Say so in the report; don't guess.")
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
            unknown = [c for c in e.get("covers", []) + (e.get("covers_conditionally") or {}).get("entities", []) if c not in ENTITIES]
            if "covers" not in e:
                miss.append("covers")
            if unknown:
                miss.append(f"unknown covers {unknown}")
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
