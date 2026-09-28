#!/usr/bin/env bash
# One-command audit, no agent required: work out the owner and its standards, size the site,
# scan at a chosen scope, and render the report, all recorded in a run folder.
#
#   engine/audit.sh <url> [--scope quick|standard|full] [--urls url1,url2]
#                   [--org NAME --entity TYPE --country CC --region XX --place NAME]
#                   [--population 50k+|under-50k] [--jurisdictions id1,id2] [--carry]
#
# The owner is detected from the site; pass --org/--entity/--country/--region to override it.
# Without --scope on a site over 40 pages, it prints the sizes and stops, so a person chooses.
# --urls pages (key tasks: pay, apply, register) are always scanned. --carry reuses the owner,
# standards and scope of the previous run of the same site. Runs land in ./a11y-audits, or
# $ACCESS_ATLAS_HOME. Needs Node 18+, Python 3.9+, and engine/ensure-deps.sh once.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

url="" scope="" scope_by="user" scope_why="chosen on the command line" urls="" juris="" carry=""
declare -a owner_args=()
while [ $# -gt 0 ]; do
  case "$1" in
    --scope) scope="$2"; shift 2 ;;
    --urls) urls="$2"; shift 2 ;;
    --jurisdictions) juris="$2"; shift 2 ;;
    --org|--entity|--country|--region|--place|--population) owner_args+=("${1#--}" "$2"); shift 2 ;;
    --carry) carry="--carry"; shift ;;
    http://*|https://*) url="$1"; shift ;;
    *) echo "unknown argument: $1" >&2; exit 1 ;;
  esac
done
if [ -z "$url" ]; then
  sed -n '2,13p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//' >&2
  exit 1
fi

ledger() { python3 "$here/ledger.py" "$@"; }
# shellcheck disable=SC2086  # carry is empty or a single flag
run="$(ledger open "$url" $carry)"
echo "run: $run"
has() { python3 -c 'import json,sys;print(sys.argv[2] in json.load(open(sys.argv[1]+"/run.json"))["decisions"])' "$run" "$1"; }

# 1. Owner: flags win, then carried decisions, then detection.
i=0
while [ $i -lt ${#owner_args[@]} ]; do
  key="${owner_args[$i]}"; val="${owner_args[$((i+1))]}"
  [ "$key" = org ] && key=owner
  ledger decide "$run" "$key" "\"$val\"" --why "given on the command line" --by user >/dev/null
  i=$((i+2))
done
if [ "$(has entity)" = False ]; then
  guess="$(python3 "$here/identify.py" "$url" --json)" || { echo "Owner unknown: pass --org, --entity, --country (and --region)." >&2; exit 2; }
  for key in owner entity country region place; do
    field="$key"; [ "$key" = owner ] && field=organization
    val="$(python3 -c 'import json,sys;v=json.loads(sys.argv[1]).get(sys.argv[2]);print(json.dumps(v) if v else "")' "$guess" "$field")"
    if [ -n "$val" ] && [ "$(has "$key")" = False ]; then
      ledger decide "$run" "$key" "$val" --why "detected from the site; not confirmed by a person" --by agent >/dev/null
    fi
  done
  echo "Owner detected, not confirmed. Check it in the report's audit trail, or re-run with --org/--entity/--country/--region."
fi
ledger step "$run" identify "done" >/dev/null
if [ -n "$juris" ]; then
  ledger decide "$run" standards "$(python3 -c 'import json,sys;print(json.dumps(sys.argv[1].split(",")))' "$juris")" \
    --why "given on the command line" --by user >/dev/null
fi
ledger step "$run" standards "done" >/dev/null

# 2. Size, then scope.
node "$here/scan.mjs" "$url" --plan --run "$run"
ledger step "$run" size "done" >/dev/null
pages="$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]+"/plan.json"))["urlsFound"])' "$run")"
if [ -z "$scope" ] && [ "$(has scope)" = True ]; then
  scope="$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]+"/run.json"))["decisions"]["scope"]["value"].split(":")[0])' "$run")"
  scope_why="same scope as the previous run (--carry)"
fi
if [ -z "$scope" ]; then
  if [ "$pages" -gt 40 ]; then
    ledger step "$run" scope failed --note "no scope chosen for a $pages+ page site" >/dev/null
    echo; echo "This site has $pages+ pages. Re-run with --scope quick, standard or full (sizes above)." >&2
    exit 3
  fi
  scope="full" scope_by="agent" scope_why="site has $pages pages, under the 40-page limit"
fi
flags="$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]+"/plan.json"))["options"][sys.argv[2]]["flags"])' "$run" "$scope")"
ledger decide "$run" scope "\"$scope: $flags\"" --why "$scope_why" --by "$scope_by" >/dev/null
[ -n "$urls" ] && ledger decide "$run" key_tasks "$(python3 -c 'import json,sys;print(json.dumps(sys.argv[1].split(",")))' "$urls")" --why "given on the command line" --by user >/dev/null
ledger step "$run" scope "done" >/dev/null

# 3. Scan.
# shellcheck disable=SC2086  # flags is a list of options from plan.json
node "$here/scan.mjs" "$url" $flags --run "$run"
[ -n "$urls" ] && node "$here/scan.mjs" "$url" --urls "$urls" --run "$run"
ledger step "$run" scan "done" >/dev/null
ledger step "$run" manual skipped --note "automated pass only (audit.sh)" >/dev/null

# 4. Report.
python3 "$here/render.py" --run "$run"
ledger step "$run" publish "done" --note "file only" >/dev/null
for f in "$run"/*.html; do case "$f" in *.artifact.html) ;; *) echo "report: $f" ;; esac; done
