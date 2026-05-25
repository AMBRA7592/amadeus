# Ground truth has no ground

A small, self-contained argument — with a runnable proof and a trainer-ready
export — about the most consequential and least examined act in AI data
labeling: collapsing many human judgements into one "ground truth" via majority
vote.

**The claim, in one line:** for contested / aesthetic / safety / synthetic-human
data, there is no ground truth to *recover* — only a distribution of human
judgement to *preserve* — and the disagreement that pipelines are built to
delete is usually the most valuable signal in the set.

### What's here

| file | what it is |
|------|------------|
| [`the-groundless-label.md`](the-groundless-label.md) | The argument. Read this first. ~10 min, grounded in current research (HLV, VariErr, pluralistic alignment, model collapse). |
| `disagreement.py` | **Diagnostic.** Instead of majority vote: keeps the distribution, separates genuine *variation* from likely *error*, flags value forks and manufactured consensus, prices what the collapse to one label destroys. Writes `triage.json`. |
| `soft_labels.py` | **Operational.** Turns the triage into things a trainer consumes: per-cell soft labels + entropy-derived weights (`soft_labels.jsonl`), and a governance queue of value forks awaiting a named human owner (`governance.jsonl`). |
| `data/labels.json` | A tiny hand-built annotation set modeled on the scenario this repo grew out of: AI-generated editorial portraits, 8 annotators in 2 normative cohorts, 3 questions each. |

### Run it (two steps, zero dependencies, Python 3.8+)

```bash
python3 disagreement.py     # diagnose -> triage.json
python3 soft_labels.py      # operationalize -> soft_labels.jsonl + governance.jsonl
```

The first prints a per-cell triage and a "bill" — how many bits of human
disagreement a single ground-truth column would erase, and where. The second
emits trainer-ready records and, crucially, a `governance.jsonl` **queue**: every
value fork the pipeline would otherwise resolve silently, held open until a named
human records a decision and a rationale.

The full arc: **diagnostic → triage → trainer-ready export → governance queue.**
Generated files (`triage.json`, `soft_labels.*`, `governance.jsonl`) are
git-ignored; reproduce them by running the two scripts. In production you would
*persist* `governance.jsonl` so the backlog of policy decisions stays visible.

### The one thing to take away

Majority vote is not a neutral way to combine human judgement. It is a specific,
contestable rule that silently makes governance decisions and ships them into
the model as if they were facts. The honest deliverable of high-stakes labeling
is not a label. It is the **distribution + the reasons + a record of who got
out-voted** — and, for genuine value forks, a named human who owns the call.
