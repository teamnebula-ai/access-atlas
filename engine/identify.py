#!/usr/bin/env python3
"""Guess who owns a website, so the right laws can be applied.

  identify.py https://www.traviscountytx.gov/ [--json]

Reads the home page (title, site name, header, footer) and the domain, and proposes the
organization, its type (county, city, state agency...), country, state/region and place,
plus the laws that would bind it. It is a proposal with evidence, never a verdict: the
person running the audit confirms it before anything is graded. Stdlib only.
"""
import json
import re
import sys
import urllib.request
from html import unescape
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from jurisdictions import applicable, load  # noqa: E402

STATES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California", "CO": "Colorado", "CT": "Connecticut",
    "DE": "Delaware", "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa",
    "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland", "MA": "Massachusetts", "MI": "Michigan",
    "MN": "Minnesota", "MS": "Mississippi", "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire",
    "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York", "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota", "TN": "Tennessee",
    "TX": "Texas", "UT": "Utah", "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia", "WI": "Wisconsin",
    "WY": "Wyoming", "DC": "District of Columbia", "PR": "Puerto Rico", "GU": "Guam", "VI": "Virgin Islands", "AS": "American Samoa",
    "MP": "Northern Mariana Islands",
}
# Country-code second-level government domains (gov.uk, gc.ca, gov.au, ...).
GOV_SUFFIX = {"gov.uk": "GB", "gc.ca": "CA", "canada.ca": "CA", "gov.au": "AU", "govt.nz": "NZ", "gov.ie": "IE", "gov.in": "IN",
              "gov.br": "BR", "go.jp": "JP", "go.kr": "KR", "gov.il": "IL", "europa.eu": "EU", "gouv.fr": "FR", "bund.de": "DE",
              "overheid.nl": "NL", "gob.es": "ES", "gov.it": "IT", "gov.se": "SE"}


def fetch(url):
    # Identify honestly first; some government sites refuse non-browser clients, so retry once as a browser.
    for ua in ("Access Atlas accessibility audit", "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": ua, "Accept": "text/html"})
            with urllib.request.urlopen(req, timeout=20) as r:
                return r.read(600_000).decode("utf-8", "replace"), r.geturl()
        except Exception as ex:  # noqa: BLE001
            err = ex
    raise err


def text_of(html):
    html = re.sub(r"(?is)<(script|style|noscript|svg)[^>]*>.*?</\1>", " ", html)
    return re.sub(r"\s+", " ", unescape(re.sub(r"(?s)<[^>]+>", " ", html))).strip()


def guess(url, html):
    host = re.sub(r"^www\.", "", (re.match(r"https?://([^/:]+)", url) or [None, ""])[1].lower())
    title = unescape((re.search(r"(?is)<title[^>]*>(.*?)</title>", html) or [None, ""])[1]).strip()
    site = (re.search(r'(?i)<meta[^>]+property=["\']og:site_name["\'][^>]+content=["\']([^"\']+)', html) or [None, ""])[1]
    body = text_of(html)
    head, foot = body[:1500], body[-2500:]
    hay = " ".join([title, site, head, foot])
    ev = []

    country = None
    for suf, cc in GOV_SUFFIX.items():
        if host.endswith(suf):
            country = cc
            ev.append(f"domain ends in {suf}")
    if not country and re.search(r"\.(gov|mil|us)$", host):
        country = "US"
        ev.append(f"US government domain ({host})")

    region = None
    m = re.search(r"\.([a-z]{2})\.us$", host)  # e.g. co.travis.tx.us
    if m and m.group(1).upper() in STATES:
        region = m.group(1).upper()
        ev.append(f"state code in domain ({host})")
    if not region:  # full state name in the domain: austintexas.gov, colorado.gov
        for k, v in sorted(STATES.items(), key=lambda kv: -len(kv[1])):
            if re.search(re.escape(v.lower().replace(" ", "")) + r"\.(gov|us|org)$", host.replace("-", "")):
                region = k
                ev.append(f"'{v}' in the domain ({host})")
                break
    if not region:  # county/city + state code: traviscountytx.gov, cityofxyztx.gov
        m = re.search(r"(county|city|co|parish|borough)([a-z]{2})\.(gov|us|org)$", host)
        if m and m.group(2).upper() in STATES:
            region = m.group(2).upper()
            ev.append(f"state code after '{m.group(1)}' in the domain ({host})")
    if not region:
        counts = {k: len(re.findall(r"\b" + re.escape(v) + r"\b", hay)) + len(re.findall(r",\s*" + k + r"\b", hay)) for k, v in STATES.items()}
        best = max(counts, key=counts.get)
        if counts[best]:
            region = best
            ev.append(f"'{STATES[best]}' / '{best}' appears {counts[best]}x in title, header or footer")
    if region and not country:
        country = "US"

    entity, org = None, None
    pats = [
        ("county", r"\b((?:[A-Z][a-z]+[ -]){1,3}County)\b"),
        ("city", r"\b(City (?:and County )?of (?:[A-Z][a-z]+ ?){1,3})"),
        ("city", r"\b(Town of (?:[A-Z][a-z]+ ?){1,3})"),
        ("state-agency", r"\b(State of (?:[A-Z][a-z]+ ?){1,2})"),
        ("public-school", r"\b((?:[A-Z][a-z]+ ){1,3}(?:Independent |Unified |Public )?School District)\b"),
        ("public-university", r"\b(University of (?:[A-Z][a-z]+ ?){1,3}|(?:[A-Z][a-z]+ ){1,3}(?:State University|Community College))"),
        ("special-district", r"\b((?:[A-Z][a-z]+ ){1,3}(?:Transit Authority|Water District|Utility District|Port Authority|Housing Authority))\b"),
        ("court", r"\b((?:[A-Z][a-z]+ ){0,3}(?:District|Superior|Municipal) Court)\b"),
    ]
    for kind, pat in pats:
        for src, txt in (("title", title), ("site name", site), ("header", head), ("footer", foot)):
            m = re.search(pat, txt)
            if m:
                entity, org = kind, m.group(1).strip()
                ev.append(f"'{org}' in the {src}")
                break
        if entity:
            break
    if not entity and host.endswith(".gov") and "county" in host:
        entity = "county"
        ev.append("'county' in the domain")
    if not entity and country and country != "US":
        entity = "public-sector-body"
    if not entity and host.endswith(".fed.us"):
        entity = "federal-agency"
    return {"url": url, "host": host, "title": title, "organization": org or site or title, "entity": entity,
            "country": country, "region": region, "place": org if entity in ("county", "city") else None, "evidence": ev,
            "confidence": "medium" if entity and country and (region or country != "US") else "low"}


def main(argv):
    if len(argv) < 2:
        sys.exit(__doc__)
    url = argv[1]
    try:
        html, final = fetch(url)
    except Exception as ex:  # noqa: BLE001
        sys.exit(f"could not fetch {url}: {ex}. Ask the user who owns the site instead.")
    g = guess(final, html)
    if g["entity"] and g["country"]:
        b, c, r = applicable(load(), g["country"], g["entity"], g["region"], g["place"])
        g.update({"binding": b, "conditional": c, "reference": r})
    if "--json" in argv:
        print(json.dumps(g, indent=2))
        return
    print(f"Site:          {g['host']}  ({g['title'][:70]})")
    print(f"Owner (guess): {g['organization']}  ·  type: {g['entity'] or '?'}  ·  {g['country'] or '?'}{'-' + g['region'] if g['region'] else ''}  ·  confidence {g['confidence']}")
    print("Evidence:      " + ("; ".join(g["evidence"]) or "none found"))
    if "binding" in g:
        print(f"Binding laws:  {', '.join(g['binding']) or 'none in registry'}")
        if g["conditional"]:
            print(f"May apply:     {', '.join(g['conditional'])}")
        if g["reference"]:
            print(f"Reference:     {', '.join(g['reference'])}")
    print("Confirm this with the user before grading. Population matters for US deadlines: ask whether it serves 50,000+ people.")


if __name__ == "__main__":
    main(sys.argv)
