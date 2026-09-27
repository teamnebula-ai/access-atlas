# Contributing to Access Atlas

The most useful contribution is local knowledge: the accessibility rule for *your* state,
province, country or city, with the source. You don't need to write code.

## Add a jurisdiction

1. **Find the primary source.** The statute, regulation, or official government policy page.
   Blogs and vendor pages don't count as sources (they are often wrong about versions and dates).
2. **Copy a sibling file** as a template, e.g. `skills/access-atlas/registry/us/states/us-co.json`
   for a US state or `skills/access-atlas/registry/fr/fr.json` for a country. Name the new file after its `id`:
   - Countries: ISO 3166 code in lower case (`pt`, `mx`, `za`), in `registry/<code>/<code>.json`.
   - Subdivisions: `<country>-<code>` (`ca-bc`, `au-nsw`, `us-tx`).
   - Cities: `<country>-local-<name>` (`us-local-boston`).
3. **Fill it in** (fields below). Keep summaries to one plain sentence.
4. **Validate:** `python3 skills/access-atlas/scripts/jurisdictions.py check`. It must print
   `0 schema errors` and should not flag your entry.
5. **Open a PR** titled `registry: add <name>`. Say where you work, if you're comfortable
   sharing: local practitioners' knowledge is what makes this useful.

### Fields

| Field | Required | Notes |
|---|---|---|
| `id` | yes | matches the file name |
| `name` | yes | as the jurisdiction calls itself |
| `level` | yes | `supranational`, `national`, `federal`, `state`, `provincial`, `territory`, `local`, `sector`, `standard` |
| `country` | yes | ISO 3166 alpha-2 (`EU` for EU-level) |
| `parent` | if any | the law it inherits: a US state → `us-federal`; an EU member → `eu-wad`; a province → its federal entry |
| `standard` | yes | the technical standard in its own words. **Name the WCAG version and level** (`WCAG 2.1 AA`) so the report can map it; "Section 508" is read as WCAG 2.0 AA, "EN 301 549" v3 as 2.1 AA |
| `laws` | one of these two | `[{cite, summary, url}]`: statutes and regulations |
| `policy_docs` | one of these two | `[{title, url}]`: official policies and guidelines |
| `applies_to` | recommended | who must comply |
| `deadlines` | if any | `[{date: "YYYY-MM-DD", what}]` |
| `exceptions` | if any | archived content, pre-existing documents, third-party content… |
| `requires` | if any | duties beyond conformance: accessibility statement, coordinator, reporting |
| `mobile`, `procurement`, `enforcement` | recommended | one sentence each |
| `office_url` | recommended | the accessibility office or policy page |
| `as_of` | yes | the date you checked the sources |
| `confidence` | yes | `high` (read the primary source), `medium` (one official page plus secondary), `low` (couldn't open a primary source; say why in `notes`) |
| `sources` | yes | URLs you **actually opened**. Empty is allowed only with `confidence: low` |
| `notes` | recommended | conflicts, gaps, anything you couldn't verify |

## Update a law

Deadlines and versions change. Edit the entry, set `as_of` to today, add the new source to
`sources`, and write what changed in `notes` and the PR description. `check` flags entries older
than a year as stale; refreshing one of those is a great first contribution.

## Change the code

- `scripts/scan.mjs`: crawler, axe-core run, screenshots, stop rules (Node, Playwright).
- `scripts/render.py`: law mapping, score, report and fix prompt (Python stdlib only; keep it that way).
- `scripts/jurisdictions.py`: registry loading and checks.
- Tests: `python3 -m unittest discover -s skills/access-atlas/scripts -p "test_*.py"`. Add a test
  that fails without your change.
- The report must pass its own scan: render one, serve it locally, run `scan.mjs` on it, and get
  0 violations.

## Ground rules

- Every legal claim needs a source a reviewer can open.
- No personal data in examples, fixtures or sample reports.
- Be kind in reviews. Most contributors are practitioners sharing what they know, not lawyers.
