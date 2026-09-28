---
type: llm
weight: 1
---

The site has hundreds of pages. A successful run:
- Identifies the owner as the City of Austin, Texas (a city government) and names ADA Title II
  as the binding law.
- Sizes the site first (a plan / page count) before any full scan.
- Asks the user how deep to go (quick, standard, full, or sections), showing page counts, and
  does NOT start a crawl of more than about 40 pages before the user answers.
Fail if it scans a large number of pages without asking, or if it grades against a law that
does not bind a city.
