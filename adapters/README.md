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
large `labels.json` files. Use deterministic, contiguous shards to bound each
pipeline run without dropping or reordering records:

```bash
for shard in 0 1 2 3; do
  python3 adapters/chaosnli.py path/to/chaosNLI_snli.jsonl \
    --shard-index "$shard" --shard-count 4 \
    --out "/tmp/chaos-shard-$shard.json"
done
```

For `M` source records, shard `K` contains
`[floor(K*M/N):floor((K+1)*M/N)]`. Each selected conversion writes an ordered,
deterministic `<out>.manifest.json` containing source/output hashes, record and
vote counts, UID coverage, and the tool commit. The alternative
`--offset O [--limit L]` mode selects the same contiguous ranges directly; it
cannot be combined with shard mode. Omitting all selection flags preserves the
whole-file behavior.

The external-data harness in [`reports/chaosnli/`](../reports/chaosnli/)
constructs every shard, proves that their manifests cover every source UID once
and in order, validates the schema, checks every converted counter and soft
label, and runs the operational pipeline. Only its report and hash/count
manifest are committed—not the licensed rows or converted outputs.

To exercise the conversion without downloading anything:

```bash
python3 adapters/chaosnli.py adapters/fixtures/chaosnli_sample.jsonl --out /tmp/chaos-labels.json
```

The seven-row synthetic fixture includes both `e/n/c` and αNLI `1/2` examples
and exercises uneven full-coverage sharding in CI.
