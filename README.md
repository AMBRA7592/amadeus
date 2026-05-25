# Ground truth has no ground

A small, self-contained argument — with a runnable proof — about the most
consequential and least examined act in AI data labeling: collapsing many human
judgements into one "ground truth" via majority vote.

**The claim, in one line:** for contested / aesthetic / safety / synthetic-human
data, there is no ground truth to *recover* — only a distribution of human
judgement to *preserve* — and the disagreement that pipelines are built to
delete is usually the most valuable signal in the set.

### What's here

| file | what it is |
|------|------------|
| [`the-groundless-label.md`](the-groundless-label.md) | The argument. Read this first. ~10 min, grounded in current research (HLV, VariErr, pluralistic alignment, model collapse). |
| `disagreement.py` | A 200-line, dependency-free tool that does the opposite of majority vote: keeps the distribution, separates genuine *variation* from likely *error*, flags value forks and manufactured consensus, and prices what the collapse to one label would destroy. |
| `data/labels.json` | A tiny hand-built annotation set modeled on the exact scenario this repo grew out of: AI-generated editorial portraits, 8 annotators in 2 normative cohorts, 3 questions each. |

### Run it

```bash
python3 disagreement.py     # no installs needed; Python 3.8+
```

It prints a per-cell triage and a closing "bill" — how many bits of human
disagreement a single ground-truth column would have erased, and where.

### The one thing to take away

Majority vote is not a neutral way to combine human judgement. It is a specific,
contestable rule that silently makes governance decisions and ships them into
the model as if they were facts. The honest deliverable of high-stakes labeling
is not a label. It is the **distribution + the reasons + a record of who got
out-voted** — and, for genuine value forks, a named human who owns the call.
