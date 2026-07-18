# ChaosNLI real-split reproducibility report

**Evidence tier:** Tier 2 — manifest-reproducible external empirical evidence.

**Generated:** 2026-07-18T05:19:46Z

**Tool commit:** `b6b9914552d7200c6dc8ffdec193a6cc390e3e9b`

This report records one run on a separately downloaded official split. No
ChaosNLI rows, converted labels, or virtual-voter records are committed here.
The CI-pinned Tier-1 tests exercise the same sharding, coverage, distribution,
and manifest logic on a synthetic fixture.

## Source and coverage

- Source: `chaosNLI_snli.jsonl` (ChaosNLI v1.0)
- Official download: https://www.dropbox.com/s/h4j7dqszmpt2679/chaosNLI_v1.0.zip
- Dataset license: CC BY-NC 4.0
- Source SHA-256: `99f9015ddda7d85f66a087452bc30d53974314fe27e7d589e2f41ad44bd509c1`
- Committed manifest SHA-256: `1406173ca39cdf9721d0048bcbafd52f334319280fe6d7fac513d251d23672f3`
- Records: 1,514
- Anonymous votes represented: 151,400
- Shards: 16
- Coverage: every source UID appears exactly once, in source order; no gaps,
  overlaps, duplicates, or missing shard indices

## Verification results

- Converted vote distributions exactly matching source `label_counter`:
  **1,514/1,514**
- Trainer soft labels exactly matching `label_counter / sum(label_counter)`:
  **1,514/1,514**
- Recomputed entropy matching triage output at its documented 3-decimal
  precision: **1,514/1,514**
- Input-schema validation: **16/16 shards**
- Operational pipeline completion (`disagreement` → `soft_labels` →
  `resolution`): **16/16 shards**
- Source entropy range: -0.000000 to 1.583069 bits; mean
  0.798014 bits

## Runtime and resources

- Platform: macOS-15.6.1-arm64-arm-64bit-Mach-O; Python 3.14.2
- End-to-end wall time: 15.362 seconds
- Sum of measured adapter + pipeline subprocess times: 8.176 seconds
- Peak child-process resident memory: 40.50 MiB
- Peak harness-tracked Python memory: 14.09 MiB
- Converted and pipeline work-directory size: 629.12 MiB
- Pipeline artifacts alone: 606.54 MiB

Runtime and memory are observations from this machine, not deterministic claims;
the committed JSON manifest intentionally contains only reproducibility checks,
hashes, and counts.

## Non-applicable findings

**Reliability, error attribution, variation-vs-error classification, and
cohort value-fork prevalence are NON-APPLICABLE — undefined here, not zero.**
ChaosNLI exposes anonymous per-item counts rather than stable cross-item
annotator identities, and this faithful conversion uses one crowd cohort.
Accordingly, this report makes claims only about distributions, entropy, soft
labels, coverage, and reproducibility.
