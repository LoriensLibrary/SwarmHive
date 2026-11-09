| arm | what the reviewer sees | enforcement | registered | complete | unsafe proposals | rejected at the gate | stopped before the gate | lineage-invalid commits | correct publications |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| current | queued drafts, current source, correction notice; no lineage | model proposes; gate decides | 900 | 784 | 264 | 258 | 6 | 0 | 372 |
| current + lookup | current, plus one optional authenticated lookup of the lineage records | model proposes; gate decides | 900 | 784 | 151 | 82 | 69 | 0 | 532 |
| compact | current, plus lineage records preloaded (versions, delivered inputs, invalidation status) | model proposes; gate decides | 900 | 884 | 7 | 5 | 2 | 0 | 686 |
| full | compact, plus the historical bodies as recorded inputs | model proposes; gate decides | 900 | 874 | 6 | 3 | 3 | 0 | 687 |
| rule | lineage records only; approves the queued draft whose closure is valid | deterministic; gate decides | 900 | 900 | 0 | 0 | 0 | 0 | 900 |
| rule + content | rule, plus a check of the figure against the current source | deterministic; gate decides | 900 | 900 | 0 | 0 | 0 | 0 | 900 |
| all | | | 5400 | 5126 | 428 | 348 | 80 | 0 | 4077 |
