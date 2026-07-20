# Addendum — MHS primary-count correction

**Date:** 2026-07-20  
**Status:** binding prospective correction, recorded before any real-MHS outcome

This addendum corrects one expected structural count in
`reports/part-3b-dataset-selection-audit.md`. It does not authorize a data run or
publication.

## Correction

For Measuring Hate Speech revision `5468f6e`, source SHA-256
`6819525ce61bc24344df9fc3f7bf48270b31038273cc27c67fc225b51433b0e1`,
the already-frozen categorical rule — at least two eligible Conservative and at
least two eligible Liberal judgments — yields **87 primary items**, not 77.

The load-bearing fact is that 87 was freshly derived from the pinned source by
the written categorical-field rule before any instrument, metric, bootstrap,
cohort-conditioned label rate, or other real-MHS outcome was run.

## Reconciliation of the former count

The exact historical SQL and its output were recovered from the original
dataset-selection audit's execution log and replayed against the same pinned
source. The historical query produced 77 by counting separate one-hot ideology
columns. The pre-registration's annotator partition, by contrast, was derived
from the categorical `annotator_ideology` field named by the frozen rule.

Those representations are inconsistent in the pinned source. The one-hot
`annotator_ideology_extremeley_liberal` column is false for every row, while the
categorical field identifies 275 eligible annotators as `extremely_liberal`.
The one-hot query therefore omitted those annotators from Liberal item coverage.

Aggregate set reconciliation:

- historical one-hot set: 77 items;
- written categorical-rule set: 87 items;
- intersection: 77 items;
- historical-only: 0 items;
- written-rule-only: 10 items.

The historical 77 are a strict subset of the written-rule 87. No comment or
annotator identifier is published here. For aggregate integrity, SHA-256 hashes
over comma-joined, lexicographically sorted comment identifiers are:

- historical 77-set:
  `28c1563203fbd93f0cd8343c96f9ae2ecba98f13bd0728db71007e94e83bb423`;
- written-rule 87-set:
  `0d93d3b1ff4d198ab315a267bb49a06e11901403c4671be0b049590b69636f17`;
- written-only 10-set:
  `7c3cdc0953987033bc6d15bc706c1ba97259b871b4f3a71563838e1c6bb38b0e`.

## Label independence

The discrepancy concerns cohort-membership representation, not `hatespeech`
values. Neither primary-set derivation inspected label values. The pinned source
contains zero null `hatespeech` rows, so the historical row-count eligibility
expression and the frozen non-null-judgment eligibility expression select the
same annotators. The separate global label-enumeration query disclosed in the
pre-registration occurred after the historical 77-count query and did not feed
either primary-set derivation.

## What does not change

This correction changes no eligibility floor, cohort definition, item filter,
metric, threshold, reliability rule, bootstrap rule, seed, evidence tier, code
behavior, permitted claim, or non-claim. `adapters/mhs.py` remains the faithful
implementation of the frozen categorical rule. Only the previously mis-derived
expected primary count is corrected from 77 to 87.

Phase 2b remains halted. Before any run, its structural gate must expect 87 and
its report and manifest must cite this addendum alongside the original
pre-registration and the 2026-07-19 reliability-corpus addendum.
