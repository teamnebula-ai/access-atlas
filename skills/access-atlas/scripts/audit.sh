#!/usr/bin/env bash
# One-command audit, no agent required: size the site, scan it at a chosen scope, render the report.
#
#   scripts/audit.sh <url> --jurisdictions us-co --org "City of Example" \
#                    [--scope quick|standard|full] [--urls url1,url2] [--out-dir DIR] [--product NAME]
#
# --scope defaults to quick. Without --scope on a site over 40 pages, it prints the sizes and
# stops, so a person chooses. The --urls pages (key tasks: pay, apply, register) are always
# scanned in addition to the crawl. Needs Node 18+, Python 3.9+, and scripts/ensure-deps.sh once.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

url="" juris="" org="" scope="" urls="" outdir="" product=""
while [ $# -gt 0 ]; do
  case "$1" in
    --jurisdictions) juris="$2"; shift 2 ;;
    --org) org="$2"; shift 2 ;;
    --scope) scope="$2"; shift 2 ;;
    --urls) urls="$2"; shift 2 ;;
    --out-dir) outdir="$2"; shift 2 ;;
    --product) product="$2"; shift 2 ;;
    http://*|https://*) url="$1"; shift ;;
    *) echo "unknown argument: $1" >&2; exit 1 ;;
  esac
done
if [ -z "$url" ] || [ -z "$juris" ] || [ -z "$org" ]; then
  sed -n '2,10p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//' >&2
  exit 1
fi
host="$(python3 -c 'import sys,urllib.parse;print(urllib.parse.urlparse(sys.argv[1]).hostname)' "$url")"
product="${product:-$host}"
outdir="${outdir:-a11y/$host/$(date +%Y-%m-%d)}"
mkdir -p "$outdir"
python3 "$here/jurisdictions.py" resolve "$juris" >/dev/null

node "$here/scan.mjs" "$url" --plan --out "$outdir/plan.json"
pages="$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["urlsFound"])' "$outdir/plan.json")"
if [ -z "$scope" ]; then
  if [ "$pages" -gt 40 ]; then
    echo; echo "This site has $pages+ pages. Re-run with --scope quick, standard or full (sizes above)." >&2
    exit 3
  fi
  scope="full"
fi
flags="$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["options"][sys.argv[2]]["flags"])' "$outdir/plan.json" "$scope")"

scans="$outdir/scan.json"
# shellcheck disable=SC2086  # flags is a list of options from plan.json
node "$here/scan.mjs" "$url" $flags --out "$outdir/scan.json"
if [ -n "$urls" ]; then
  node "$here/scan.mjs" "$url" --urls "$urls" --out "$outdir/tasks.json"
  scans="$scans,$outdir/tasks.json"
fi
python3 "$here/render.py" --jurisdictions "$juris" --scan "$scans" --org "$org" --product "$product" \
  --scope "Scope: $scope ($flags)${urls:+, plus task pages $urls}. Automated checks only." \
  --out "$outdir/$host.html"
echo "open $outdir/$host.html"
