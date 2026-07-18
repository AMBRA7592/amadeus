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
3. Run from the exact tool commit recorded in the manifest
   (`b6b9914552d7200c6dc8ffdec193a6cc390e3e9b`), preferably in a detached
   worktree so your current checkout is untouched.
4. From that worktree's root, with `jsonschema` installed, run:

   ```bash
   python3 reports/chaosnli/run_report.py \
     /path/to/chaosNLI_snli.jsonl \
     --expected-source-sha256 99f9015ddda7d85f66a087452bc30d53974314fe27e7d589e2f41ad44bd509c1 \
     --shard-count 16
   ```

5. Compare the regenerated deterministic `manifest.json` with the committed
   one. Runtime and memory belong only to the human-readable report because
   they vary by machine.

The report cannot measure annotator reliability, distinguish variation from
error, or estimate cohort value-fork prevalence. ChaosNLI's counts do not carry
stable annotator identities across items, and the conversion faithfully uses a
single crowd cohort. Those quantities are undefined for this dataset, not zero.
