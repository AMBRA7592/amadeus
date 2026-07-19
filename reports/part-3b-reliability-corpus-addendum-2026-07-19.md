# Part 3b reliability-corpus addendum

**Date:** 2026-07-19<br>
**Status:** binding prospective clarification, approved before any MHS outcome run<br>
**Applies to:** [`part-3b-dataset-selection-audit.md`](part-3b-dataset-selection-audit.md), Primary metric 4<br>
**Repository base:** `af34ebdd6b11a1f42eb86584c96613fc3835df76`

## Reliability-corpus disambiguation

Primary metric 4—“the current CONFIDENT-only, leave-one-out reliability
definition over the full converted corpus for eligible annotators”—is read as
follows:

> The converted reliability corpus contains only eligible cohort annotators.
> Consistent with Eligibility rule 4, annotators with neutral, no-opinion, or
> null ideology are excluded entirely: their judgments enter neither the
> reliability corpus, the CONFIDENT-cell determination, nor any leave-one-out
> computation.

This is the interpretation implemented in `adapters/mhs.py` and independently
audited in PR #15. It is recorded prospectively, before any real-MHS outcome is
computed.

## Effect on the protocol

This clarification changes no eligibility floor, cohort definition, primary-item
filter, metric, threshold, bootstrap rule, evidence tier, permitted claim, or
non-claim. It resolves only which already-excluded annotators can contribute to
the reliability corpus.

Phase 2 remains separately gated. This addendum authorizes neither a real-data
run nor publication of an outcome.
