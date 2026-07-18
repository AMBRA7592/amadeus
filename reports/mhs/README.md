# Measuring Hate Speech: Phase 1 build only

This directory contains the audited-to-be **Phase 1** adapter logic and dormant
Phase-2 harness for the bounded Measuring Hate Speech (MHS) pilot. No real MHS
row, identifier, or study outcome is committed or computed by CI.

The binding protocol is
[`reports/part-3b-dataset-selection-audit.md`](../part-3b-dataset-selection-audit.md).
Its frozen parameters are implemented verbatim:

- annotators need at least **20** non-null `hatespeech` judgments;
- Conservative is exactly `extremely_conservative`, `conservative`, or
  `slightly_conservative`;
- Liberal is exactly `extremely_liberal`, `liberal`, or `slightly_liberal`;
- neutral, no-opinion, null, and every other ideology value are excluded with
  no inference or imputation;
- primary items need at least **2 Conservative + 2 Liberal** judgments;
- fewer than **50** primary items halts the study and returns to the owner;
- labels remain categorical strings `"0"`, `"1"`, and `"2"`;
- intervals use an item-level bootstrap with **10,000** resamples and seed
  **`20260718`**; there are no null-hypothesis p-values;
- reliability requires at least 20 actually scored CONFIDENT cells per
  annotator and at least **30 qualifying annotators per cohort**, or it is
  labelled underpowered/non-applicable;
- disjoint cohort support is reported as undefined, never replaced by a maximum
  geometry gap.

## Evidence tiers and execution boundary

Tier 1 is the synthetic fixture and standard-library logic exercised in CI.
Tier 2 begins only after Claude audits this Phase-1 PR and the owner separately
authorizes the real run. `run_study.py` is therefore present but never executed
in CI.

The adapter accepts already-parsed records and has no parquet or network
dependency. Only the dormant loader needs `pyarrow`; its import is guarded and
occurs only when Phase 2 is explicitly run. `disagreement.py` and
`soft_labels.py` are called unchanged with `--data/--out`. `geometry.py` is
intentionally demo-pinned and has no BYOD CLI, so the harness calls its existing
`arithmetic_mean`, `geometric_mean`, and `tv` functions directly without
modifying it.

## Phase-2 reproduction (not yet authorized)

After separate authorization, obtain the official MHS parquet at revision
`5468f6e` outside the repository and verify:

```text
SHA-256  6819525ce61bc24344df9fc3f7bf48270b31038273cc27c67fc225b51433b0e1
```

Install `pyarrow` in a separate local environment and run:

```text
python3 reports/mhs/run_study.py /absolute/path/to/measuring-hate-speech.parquet
```

The harness has no network path. A checksum mismatch or fewer than 50 primary
items halts before outcomes. Its local source/work directories are ignored.
Only a separately reviewed aggregate `report.md` and `manifest.json` may be
committed in Phase 2; no source rows or identifiers may be published.
