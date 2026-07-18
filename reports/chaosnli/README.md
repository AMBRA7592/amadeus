# ChaosNLI reproducibility evidence

This directory is deliberately split from the CI-pinned core. The adapter,
sharding, complete-coverage proof, distribution verifier, and manifest
aggregation are tested in CI using synthetic rows. The numbers in `report.md`
and `manifest.json` are **Tier 2 external empirical evidence** from an official
ChaosNLI split downloaded separately under CC BY-NC 4.0.

No official row, converted `labels.json`, or expanded virtual-voter record is
committed. The manifest contains only hashes, aggregate counts, and per-shard
output/UID-list hashes.

## Reproduce

1. Download `chaosNLI_v1.0.zip` from the
   [official ChaosNLI repository](https://github.com/easonnie/ChaosNLI) and
   extract it outside this repository.
2. Confirm the split's SHA-256 equals the value in `manifest.json`.
3. From the repository root, with `jsonschema` installed, run:

   ```bash
   python3 reports/chaosnli/run_report.py \
     /path/to/chaosNLI_snli.jsonl \
     --expected-source-sha256 SHA256_FROM_MANIFEST \
     --shard-count 16
   ```

4. Compare the regenerated deterministic `manifest.json` with the committed
   one. Runtime and memory belong only to the human-readable report because
   they vary by machine.

The report cannot measure annotator reliability, distinguish variation from
error, or estimate cohort value-fork prevalence. ChaosNLI's counts do not carry
stable annotator identities across items, and the conversion faithfully uses a
single crowd cohort. Those quantities are undefined for this dataset, not zero.
