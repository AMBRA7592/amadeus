# Spec E (Part 3b) — Phase 2a hardening + Phase 2b real-data run

**Status:** specification only, published on an audit-only branch. No
implementation, download, parquet read, or outcome run is authorized by this
document.

**Base:** `main` @
`1e1396a162960764482e1456b04a6d5e92ff9892`.

**Owner:** Codex implements, publishes, and manages CI/PRs only after the
corresponding owner authorization. **Auditor:** Claude independently gates each
PR. **Real-data boundary:** Phase 2b does not begin until Phase 2a is merged and
verified and the owner explicitly says **Run Phase 2b**.

## Binding prospective record

The following files on the base commit are the controlling contract:

1. `reports/part-3b-dataset-selection-audit.md` — frozen dataset, source hash,
   eligibility, cohorts, metrics, uncertainty, evidence tier, and claims/non-claims.
2. `reports/part-3b-reliability-corpus-addendum-2026-07-19.md` — the converted
   reliability corpus contains only eligible Conservative/Liberal cohort
   annotators; neutral, no-opinion, and null-ideology judgments enter neither
   the corpus, CONFIDENT-cell determination, nor leave-one-out computation.

No step in this spec may alter either document. If code cannot implement them as
written, stop and return to the owner; do not reinterpret the protocol after
seeing an outcome.

## Authorization ledger

- **Authorized now:** write this specification only.
- **Not authorized:** Phase 2a code changes.
- **Not authorized:** downloading or opening the real MHS parquet.
- **Not authorized:** computing, viewing, publishing, or committing any real-MHS
  outcome.
- **Later authorization 1:** `Build Phase 2a hardening; no real data.`
- **Later authorization 2, only after Phase 2a audit/merge:**
  `Run Phase 2b on the frozen MHS revision.`

The two later authorizations produce separate PRs. Phase 2a is Tier 1 and fully
CI-pinned. Phase 2b is Tier 2 and manifest-reproducible by re-download.

---

# Phase 2a — synthetic hardening build

## Objective

Close the two non-blocking Phase-1 audit notes before any real-data run:

1. prove on a genuinely powered synthetic corpus that the harness's
   leave-one-out contribution mirror equals `disagreement.py`'s emitted
   `triage["reliability"]` for every annotator; and
2. prevent one degenerate item-bootstrap resample from crashing the study when
   it contains no calculable reliability values for one cohort, without
   silently conditioning the interval on non-degenerate draws.

This phase contains no real MHS content or outcome. It changes no instrument,
protocol, threshold, dataset adapter, schema, claim boundary, or source hash.

## Required code behavior

### 1. Make the reliability mirror directly comparable

In `reports/mhs/run_study.py`, factor the existing contribution aggregation into
a small pure helper that returns an annotator-to-reliability mapping, for example:

```text
_reliability_by_annotator(contributions, annotators) -> {annotator: score}
```

It must use the existing `(hit, total)` contribution values and exactly the same
`hits / totals` calculation already performed by `_reliability_values`. The
existing list-producing helper may delegate to this mapping helper.

The authoritative point estimates in `aggregate_reliability` remain
`triage["reliability"]`; the mirror is not allowed to replace or modify them.
Its purpose is bootstrap resampling and the Tier-1 equivalence proof.

### 2. Isolate the cohort-median-difference statistic

Factor the nested reliability-bootstrap statistic into a pure helper, for
example:

```text
_reliability_median_difference(sample, fixed_cohorts) -> float | None
```

It returns Conservative median minus Liberal median when both sides have at
least one calculable value. It returns `None` when a resample leaves either side
empty. It must not lower the 20-CONFIDENT-cell qualification floor, change the
fixed qualifying population, impute a value, or substitute zero.

### 3. Guard degenerate bootstrap resamples transparently

In `reports/mhs/metrics.py`, permit `bootstrap_statistic`'s statistic callback to
return `None` for a degenerate resample.

Required policy:

- perform exactly **10,000 total resamples** under the production default,
  matching the frozen pre-registration literally;
- never redraw or replace a degenerate resample;
- keep the frozen seed **`20260718`**;
- return `valid_estimates` and `degenerate_resamples` alongside `lower`,
  `upper`, `iterations`, `seed`, and `status`, with the invariant
  `iterations == valid_estimates + degenerate_resamples`;
- if `degenerate_resamples == 0`, compute the interval from all 10,000 finite
  estimates and return status `ok`;
- if `degenerate_resamples > 0`, return `lower: null`, `upper: null`, and status
  `degenerate/non-applicable`; do not compute a conditional interval from only
  the valid subset, impute a value, or substitute zero; and
- retain the existing rejection of non-finite numeric estimates.

`iterations` means the frozen number of **total draws**, not the number of valid
estimates. Existing non-degenerate geometry bootstraps should report 10,000
valid estimates and zero degenerate resamples.

This is the binding interpretation of the frozen phrase “an item-level
bootstrap with 10,000 resamples”: exactly 10,000 total draws, with no hidden
redraws and no interval conditioned on survival. It adds a failure-safe result
for an undefined statistic; it does not change the seed, resample count, metric,
or threshold and therefore requires no further protocol addendum.

### 4. Surface the guard in the dormant report

Update the generated report text in `reports/mhs/run_study.py` to show the total
draw count, valid-estimate count, degenerate-resample count, and status for each
reported bootstrap interval. If reliability is underpowered/non-applicable and
has no interval, all bootstrap fields remain visibly `not applicable`. If the
powered reliability bootstrap encounters any degenerate draw, show the counts
and `degenerate/non-applicable` status rather than a conditional interval.

The manifest already carries the returned bootstrap dictionaries; it must
retain the new metadata without row- or annotator-level detail.

## Powered Tier-1 synthetic fixture

Build the powered fixture programmatically inside `test_claims.py`; do not add a
second large JSONL file. It is still a fixture: deterministic, fake, declared in
one helper, and never derived from MHS rows.

Required construction:

- exactly 30 fake Conservative and 30 fake Liberal annotators;
- exactly 24 categorical `hatespeech` cells, all rated by all 60 annotators;
- every cell remains CONFIDENT under the unmodified instrument;
- every annotator therefore has 24 actually scored CONFIDENT cells and clears
  the frozen floor of 20;
- all 60 annotators qualify, so both cohorts exactly meet the powered floor of
  30;
- use only fake IDs and the categorical strings `"0"`, `"1"`, `"2"`;
- introduce sparse, deterministic deviations while keeping each cell at or
  above the existing near-consensus threshold, so annotator reliabilities are
  not all identical and the cohort median difference is non-trivial; and
- assert every cell is CONFIDENT before accepting any mirror result.

A concrete acceptable pattern is:

- default every vote to `"0"`;
- Conservative annotators 00–15 each deviate to `"1"` on one deterministic
  cell;
- Liberal annotators 00–15 each deviate to `"1"` on two deterministic cells;
- distribute those deviations so no cell has more than three dissenters.

Under this construction the expected point medians are prospectively fixed:
Conservative `23/24`, Liberal `22/24`, and Conservative-minus-Liberal `1/24`.
If the implementation chooses a different pattern, it must freeze equally
explicit hand-derived expectations in the test before running the harness.

## Phase-2a tests

Add Tier-1 tests covering all of the following:

1. Run unmodified `disagreement.py --data/--out` on the powered dataset.
2. Assert 24/24 cells are `CONFIDENT`.
3. Assert exactly 30/30 annotators qualify in each cohort.
4. Reconstruct contributions with `_confident_contributions`.
5. Compare `_reliability_by_annotator` to `triage["reliability"]` for every one
   of the 60 annotators, not merely cohort medians.
6. Assert the hand-derived cohort medians and Conservative-minus-Liberal
   difference.
7. Exercise `aggregate_reliability`'s powered path and require a deterministic
   10,000-total-draw interval with seed `20260718`, 10,000 valid estimates, zero
   degenerate resamples, and status `ok`.
8. Create a tiny artificial contribution sample in which some bootstrap draws
   contain only one cohort. Force the degenerate path and assert the run
   completes after exactly the requested number of total draws,
   `valid_estimates + degenerate_resamples == iterations`, the interval bounds
   are null, the status is `degenerate/non-applicable`, and repeated runs with
   the same seed are byte-for-byte equal.
9. Test an always-degenerate statistic with a small test-only iteration count;
   require zero valid estimates, exactly `iterations` degenerate resamples, null
   bounds, and `degenerate/non-applicable` rather than an exception or redraw.
10. Confirm a non-degenerate geometry median bootstrap has
    `valid_estimates == iterations`, `degenerate_resamples == 0`, and status
    `ok`.
11. Confirm neither results nor report fields contain p-values.

The powered test must not monkeypatch the instrument's reliability result or
lower either frozen floor. Runtime should remain reasonable on Python 3.8 and
3.12; production defaults stay at exactly 10,000 total draws even if a
deliberately small iteration count is used only for the forced-degeneracy unit
tests.

## Exact Phase-2a scope

Expected changed files:

- `reports/mhs/metrics.py`
- `reports/mhs/run_study.py`
- `test_claims.py`

No fixture-data file is needed. Do not change:

- `disagreement.py`, `soft_labels.py`, `geometry.py`, `resolution.py`, or any
  other instrument;
- `adapters/mhs.py`;
- either schema;
- either prospective protocol document;
- `reports/mhs/fixtures/mhs_sample.jsonl`;
- root `README.md`, essays, or `data/labels.json`; or
- any Phase-2 output file.

If documentation must explain the new degeneracy-status fields, a narrowly
scoped `reports/mhs/README.md` edit is allowed only if called out before the PR;
the preferred scope is the three files above.

## Phase-2a acceptance gate

- Powered per-annotator mirror equivalence passes for all 60 fake annotators.
- The partially degenerate and always-degenerate no-redraw tests pass.
- Exactly 10,000 deterministic total draws are performed on the powered path;
  it produces 10,000 valid estimates and zero degenerate resamples. Any forced
  degenerate path reports null bounds and a non-applicable status rather than a
  conditional interval.
- Existing 245-row fixture expectations remain unchanged.
- Bare suite and `jsonschema==4.23.0` suite pass.
- All four GitHub check runs pass on Python 3.8 and 3.12.
- `import reports.mhs.run_study` imports neither `pyarrow` nor `pandas`.
- Default demo artifacts remain byte-identical to `main @ 1e1396a` for
  `triage.json`, `soft_labels.jsonl`, `soft_labels.csv`, and
  `governance.jsonl`; resolution records match after removal of the dynamic
  timestamp and retain identical replay hashes.
- No parquet, real identifier, `reports/mhs/report.md`, or
  `reports/mhs/manifest.json` exists.
- Claude independently audits the actual PR head. Do not merge without a PASS.

After Phase 2a merges, verify the resulting `main` before any Phase-2b
authorization.

---

# Phase 2b — separately authorized real-data run

## Preconditions

Phase 2b may begin only when all are true:

1. Phase 2a is merged and its post-merge `main` is independently verified.
2. The owner explicitly says `Run Phase 2b on the frozen MHS revision.`
3. The working tree is clean and the run starts from that verified `main`.
4. The prospective protocol and 2026-07-19 addendum remain byte-identical.

The run authorization permits the frozen MHS execution and the bounded output
PR only. It does not authorize secondary cohorts, exploratory subgroup searches,
threshold changes, or new metrics.

## Source and dependency boundary

- Obtain UC Berkeley Measuring Hate Speech revision **`5468f6e`** outside the
  repository.
- Expected parquet SHA-256:
  `6819525ce61bc24344df9fc3f7bf48270b31038273cc27c67fc225b51433b0e1`.
- Verify the hash before parquet import. A mismatch halts before any outcome.
- Use a dedicated local environment for `pyarrow`; record the exact Python and
  `pyarrow` versions in the audit transcript. Do not add either dependency to
  CI or the repository runtime.
- No network access is permitted inside `run_study.py`; downloading and running
  are separate observable steps.
- Never place the source parquet, extracted rows, row samples, comment IDs, or
  annotator IDs under version control.

## Pre-outcome structural gate

Before invoking the outcome-producing `run_study.main`, perform a local
**structural-only preflight**: call `verify_source`, `load_parquet_records`, and
`adapters.mhs.convert_records` directly; compute only row/comment/annotator and
adapter count totals; do not call either instrument or any aggregation helper.
Check those totals against the frozen source record:

- source rows: 135,556;
- source comments: 39,565 (source-level check, not necessarily the converted
  reliability-item count);
- source annotators: 7,912;
- floor-20 eligible annotators: 2,316;
- Conservative eligible annotators: 662;
- Liberal eligible annotators: 1,215;
- excluded eligible neutral/no-opinion/null annotators: 439; and
- primary items meeting the frozen 2+2 filter: 77.

The partition must satisfy `662 + 1,215 + 439 = 2,316`. Any mismatch—even with
the expected file hash—halts for diagnosis and owner review. Never weaken the
50-primary-item floor; fewer than 50 halts the study.

These are structural integrity checks, not outcome findings. Do not inspect or
publish cohort-conditioned label rates during the gate.

## Run procedure

1. Create a clean Phase-2b branch from the verified post-Phase-2a `main`.
2. Keep the source outside the repository and generated intermediate labels,
   triage, soft labels, and governance files in the ignored
   `reports/mhs/work/` directory.
3. Run the structural-only preflight above and save only its aggregate count
   transcript outside the repository. Do not invoke `run_study.main` unless
   every frozen count matches.
4. Execute the audited `reports/mhs/run_study.py` once against the exact-hash
   parquet, using separate ignored work and report directories.
5. The harness must call the unmodified instruments and compute only the four
   frozen metrics:
   - value-fork rate with Wilson 95%;
   - manufactured-consensus rate with Wilson 95%;
   - defined geometry-gap median/IQR/bootstrap plus separately reported
     disjoint-support/undefined share; and
   - cohort-only CONFIDENT reliability coverage, medians/IQR, Conservative-minus-
     Liberal difference, and bootstrap interval only when powered.
6. If reliability remains underpowered, publish
   `underpowered/non-applicable`; do not lower the 20-cell or 30-per-cohort
   floor.
7. Run a second time into a separate ignored work/report directory. After
   removing only the generated timestamp, require identical aggregate counts,
   metric values, bootstrap intervals, degenerate-resample counts, source hash,
   protocol path, and tool commit. A nondeterministic result halts.
8. Inspect both generated result pairs for identifiers or source content.
   Select one timestamped pair only after the determinism comparison, copy just
   that `report.md` and `manifest.json` into `reports/mhs/`, and stage nothing
   else.

## Permitted Phase-2b repository changes

Exactly these three files:

- `reports/mhs/report.md` — new, claim-bounded Tier-2 result;
- `reports/mhs/manifest.json` — new, source revision/hash, aggregate counts,
  tool commit, protocol/addendum paths, four aggregate metric objects, runtime
  timestamp, and a false row/ID-content flag; and
- root `README.md` — one adjacent appendix link while preserving the existing
  “instruments rather than the measurement” hedge and stating that this is one
  bounded dataset-specific Tier-2 pilot, not general prevalence.

Do not modify the adapter, harness, metrics, tests, instruments, schemas,
prospective documents, essays, or demo data in the outcome PR. If the run
reveals a code defect, stop Phase 2b and return to a separate synthetic
hardening PR; do not patch code and outcomes together.

## Output content gates

`manifest.json` and `report.md` may contain aggregate counts, rates, intervals,
hashes, versions, and tool/protocol references only. They must contain no:

- source text or labels at row level;
- comment or annotator identifiers;
- cohort-member lists;
- source or work-directory path that identifies a local user;
- p-values or unregistered secondary analyses; or
- universal, production-prevalence, causal-ideology, correct-ground-truth,
  theorem-validation, variation-versus-error, or out-of-corpus claims.

The report must reproduce the permitted claims and non-claims from the frozen
pre-registration. The README must keep its existing hedge; the Tier-2 appendix
is adjacent evidence, not a replacement claim.

## Phase-2b acceptance gate

- Exact source revision and SHA-256 verified before reading parquet.
- Frozen structural counts and cohort partition match.
- Primary count remains at least 50; no filter or threshold changed.
- Cohort-only reliability follows the dated addendum.
- Powered mirror-check and degenerate-bootstrap guard from Phase 2a remain
  green.
- Two independent local runs agree after timestamp normalization.
- Manifest is internally self-consistent: rate numerators/denominators,
  undefined + defined geometry counts, eligibility partition, bootstrap
  metadata, source hash/revision, tool commit, and protocol paths reconcile.
- The report is derivable from the manifest and contains no unsupported number.
- No row, ID, parquet, or intermediate artifact is tracked.
- Full suite passes bare and with `jsonschema==4.23.0`; both CI matrix legs are
  green even though CI never accesses the real data or imports `pyarrow`.
- Scope is exactly the report, manifest, and one README link/edit.
- Claude audits harness logic, manifest self-consistency, claim boundaries, and
  PR scope before merge. Claude must label the real numbers Tier 2 and state
  that they were not independently regenerated in the zero-network audit
  environment.

## Required stop outcomes

Stop without an outcome PR if any of the following occurs:

- source hash mismatch;
- structural-count or cohort-partition mismatch;
- fewer than 50 primary items;
- a protocol/addendum mismatch;
- nondeterministic rerun after timestamp normalization;
- a code change is needed;
- an identifier or source row leaks into a proposed artifact; or
- the report cannot stay within the registered claims/non-claims.

## Auditor responsibilities

For Phase 2a, Claude can apply the usual trust-nothing mechanical gate: rerun the
powered synthetic case, compare all 60 mirror scores to the instrument, force
degenerate resamples, verify the byte gate, and inspect both CI modes.

For Phase 2b, Claude verifies the run procedure encoded by the audited harness,
the fixed source locator/hash claims, two-run manifest agreement, arithmetic
self-consistency, absence of rows/IDs, and claim discipline. Unless Claude can
independently obtain the exact source, the real outcome values remain Tier 2:
reproducible by re-download, not independently regenerated in Claude's audit.

## Next commands

This specification itself triggers nothing. The next valid owner commands are,
in order:

1. **`Build Phase 2a hardening; no real data.`**
2. After Claude PASS, owner-authorized merge, and post-merge verification:
   **`Run Phase 2b on the frozen MHS revision.`**

No shorter or implied instruction should be treated as permission to download
or compute real-MHS outcomes.
