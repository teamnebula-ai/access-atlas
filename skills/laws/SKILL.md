---
name: laws
description: "Look up, explain, add or update the accessibility laws and policies in the Access Atlas registry: what standard a US state, city, country or agency requires, deadlines, exceptions, who it covers, and adding a missing jurisdiction with sources. Use when someone asks \"what does <state/country> require for web accessibility\", \"when is the ADA Title II deadline\", \"does the Texas rule apply to counties\", \"add <jurisdiction> to the registry\", \"this law changed\", or an audit found no binding law."
argument-hint: "<jurisdiction, question, or 'add <place>'>"
---

# Laws — the registry of who must meet which standard

> **Clarify first.** For an addition, ask where the user's information comes from. Every entry
> needs a primary source (statute, regulation, or official policy page).

`E=${CLAUDE_PLUGIN_ROOT}/engine`, registry at `${CLAUDE_PLUGIN_ROOT}/data/registry/<country>/…/<id>.json`,
one jurisdiction per file.

## Look up

```bash
python3 $E/jurisdictions.py list texas                     # find ids
python3 $E/jurisdictions.py show us-tx                      # the full entry
python3 $E/jurisdictions.py applicable --country US --region TX --entity county --place "Travis County"
```

Answer from the entry: the standard, who it **covers** (and `covers_conditionally`), deadlines,
exceptions, other duties (statement, coordinator, procurement), mobile coverage, and its `as_of`
date and `confidence`. Quote the source link. **Low** confidence means "verify before relying on
this"; say so. Never fill a gap from memory; record it as an open question.

## Add or update

1. Find the primary source and open it.
2. Copy a sibling file and name it after its `id` (`us-xx`, `<cc>`, `<cc>-<region>`,
   `<cc>-local-<place>`).
3. Fill every field in `CONTRIBUTING.md`, especially:
   - `standard`: name the WCAG version and level so it can be graded.
   - `covers`: who it binds (`federal-agency`, `state-agency`, `county`, `city`, `special-district`,
     `public-school`, `public-university`, `court`, `public-sector-body`, `private-business`).
     This decides whether an audit of a given organization is graded against it.
   - `covers_conditionally`: `{entities, when}`, for coverage that depends on a condition.
   - `region` / `place`: US state code, and the city or county for local entries.
   - `sources` (only pages you opened), `as_of` (today), `confidence` (never above what a primary
     source supports).
4. Validate: `python3 $E/jurisdictions.py check` must report 0 schema errors.
5. Law changed? Update the fields, `as_of` and `sources`, and say what changed in `notes`.

Changes to the registry are contributions to a shared, public dataset: propose them as a pull
request to the project, with the source, rather than only editing a local copy.
