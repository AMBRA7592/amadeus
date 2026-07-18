# ChaosNLI adapter

`chaosnli.py` converts the public ChaosNLI JSONL format into this repository's
`labels.json` contract. It is standard-library-only, performs no network access,
and accepts SNLI/MNLI counters (`e`, `n`, `c`) as well as αNLI counters (`1`,
`2`). Mixed files are supported.

## Honest modeling boundary

ChaosNLI publishes anonymous per-item `label_counter` values, not stable worker
identities. The adapter expands each count into deterministic virtual voters
whose ids are unique to that item and puts every virtual voter in one `crowd`
cohort. It does not pretend that vote 17 on one item came from the same person as
vote 17 on another.

That makes annotator reliability and cohort-based value-fork results
**not meaningful** on converted ChaosNLI data. The faithful outputs are the vote
distribution, its entropy, and the trainer-ready soft label. This caveat is also
embedded in the generated file's `_about` field.

## Get the data separately

No real ChaosNLI rows are committed here: the dataset is large and distributed
under CC BY-NC 4.0. Download the release from the
[official ChaosNLI repository](https://github.com/easonnie/ChaosNLI) and comply
with its license. This repository contains only
`fixtures/chaosnli_sample.jsonl`, a small synthetic format fixture.

The official release contains three JSONL files:

- `chaosNLI_snli.jsonl`
- `chaosNLI_mnli_m.jsonl`
- `chaosNLI_alphanli.jsonl`

## Convert and run

From the repository root:

```bash
python3 adapters/chaosnli.py path/to/chaosNLI_snli.jsonl --out /tmp/chaos-labels.json
python3 disagreement.py --data /tmp/chaos-labels.json --out /tmp/chaos-run
python3 soft_labels.py --data /tmp/chaos-labels.json --out /tmp/chaos-run
python3 resolution.py --data /tmp/chaos-labels.json --out /tmp/chaos-run
```

The adapter reads `uid`, `label_counter`, and the task text under `example`.
Other published fields such as `majority_label`, `label_dist`, and `entropy` are
not used as sources of truth: the downstream distribution and entropy are
recomputed from `label_counter`.

The input contract represents individual votes, so each published count is
expanded into that many virtual voters. Full ChaosNLI splits therefore produce
large `labels.json` files, and this repository's explanatory tools are not
optimized as a high-throughput corpus engine. Trial the workflow on a JSONL
shard before committing resources to a full split; sharding does not change any
per-item distribution.

To exercise the conversion without downloading anything:

```bash
python3 adapters/chaosnli.py adapters/fixtures/chaosnli_sample.jsonl --out /tmp/chaos-labels.json
```

The synthetic fixture includes one `e/n/c` example and one αNLI `1/2` example.
