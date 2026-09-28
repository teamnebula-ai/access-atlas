---
name: scope
description: "Work out who owns a website and which accessibility laws bind them (ADA Title II, Section 508, a state or city policy, the EU directive…), then size the site and agree how deep an audit should go. Use when someone asks \"what accessibility law applies to us\", \"what standard does <county/city/agency> have to meet\", \"which WCAG version applies\", \"how big is this site\", or as step 1–2 of an audit."
argument-hint: "<url or run folder>"
---

# Scope — whose rules, and how much to scan

> **Clarify first.** If the owner can't be confirmed from evidence, ask. Guessing the owner wrong
> grades the site against the wrong law.

`E=${CLAUDE_PLUGIN_ROOT}/engine`. Work inside a run folder (`RUN=$(python3 $E/ledger.py open <url>)`).
Record every answer as a decision with `--why` and `--by user|agent`.

## 1. Who owns the site

```bash
python3 $E/identify.py <url>          # --json for the full proposal
```

It reads the domain and the home page and proposes the **organization**, its **type**, and the
**country / state / place**, with the evidence behind each. Types: `federal-agency`, `state-agency`,
`county`, `city`, `special-district`, `public-school`, `public-university`, `court`,
`public-sector-body` (outside the US), `private-business`.

- Evidence is strong (the name in the title and a state code in the domain) → record it
  `--by agent` and tell the user what you concluded, so they can correct you.
- Weak or missing (a vendor-hosted portal, a generic title, a 403) → ask the user.
- A site run *for* a government by a vendor belongs to the government.

```bash
python3 $E/ledger.py decide $RUN owner "Travis County" --why "'Travis County' in title, tx in domain" --by agent
python3 $E/ledger.py decide $RUN entity county --why "county government" --by agent
python3 $E/ledger.py decide $RUN country US --why ".gov domain" --by agent
python3 $E/ledger.py decide $RUN region TX --why "state code in domain" --by agent
python3 $E/ledger.py decide $RUN place "Travis County" --why "owner" --by agent
```

**US local governments: population.** ADA Title II has different deadlines for 50,000+ and smaller
governments and special districts. If you know it from a reliable source, record it with that
source; otherwise ask. Values: `50k+`, `under-50k`.

## 2. Which laws bind them

```bash
python3 $E/jurisdictions.py applicable --country US --region TX --entity county --place "Travis County"
```

It sorts the registry into **Binding** (graded against), **May apply** (only in some conditions,
with the condition), and **Reference only** (the state or national rule that exists but doesn't
cover this kind of organization). Record it:

```bash
python3 $E/ledger.py decide $RUN standards '{"binding":["us-ada-title-ii"],"reference":["us-tx"]}' \
  --why "counties are bound by Title II; the Texas rule covers state agencies and universities" --by agent
python3 $E/ledger.py step $RUN standards done
```

Read each binding entry (`jurisdictions.py show <id>`) before you quote it. Its `confidence` and
`as_of` travel into the report. Nothing binding found? Say so; don't substitute a guess. Offer
the **laws** skill to add the missing entry.

## 3. Size the site

```bash
node $E/scan.mjs <url> --plan --run $RUN
```

Plain HTTP, no browser, about a minute. It prints the page count (from the sitemap, or a link crawl
capped at 600), the biggest sections, and three ready-made scopes with time estimates.
`python3 $E/ledger.py step $RUN size done`.

## 4. Agree the scope

Under ~40 pages: scan it all, say so, and record the decision `--by agent`.

Otherwise **ask** (a multiple-choice question if your harness has one, else a short numbered list),
showing the real numbers:

- **Quick**: ~25 pages, 2 levels, 3 per folder. A first look.
- **Standard** (most sites): up to 150 pages, 5 per folder, sitemap included. Every kind of page,
  without 900 near-identical news posts.
- **Full**: every discovered page, with a time budget. For a formal audit or a small site.
- **Sections**: named folders only (`--include-path /services,/permits`).

Also ask for the **key tasks** people come to do (pay a bill, apply for a permit, find a meeting,
report a problem). Those pages get scanned by URL whatever the crawl scope. Record both:

```bash
python3 $E/ledger.py decide $RUN scope '"standard: 150 pages, 5 per folder"' --why "user chose standard" --by user
python3 $E/ledger.py decide $RUN key_tasks '["https://…/pay","https://…/permits/apply"]' --why "user named them" --by user
python3 $E/ledger.py step $RUN scope done
```

Repeat audit meant to measure progress? Propose the same scope as last time
(`ledger.py history a11y-audits/<site>`), since a different scope makes the comparison unfair.
