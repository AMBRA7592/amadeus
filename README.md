# Ground truth has no ground

> **Majority vote is not a neutral way to combine human judgement. It is a
> specific, contestable rule that silently makes governance decisions and ships
> them into the model as if they were facts.**

A small, self-contained argument — with a runnable proof and a trainer-ready
export — about the most consequential and least examined act in AI data
labeling: collapsing many human judgements into one "ground truth." For
contested / aesthetic / safety / synthetic-human data there is no ground truth
to *recover* — only a distribution of human judgement to *preserve* — and the
disagreement that pipelines are built to delete is usually the most valuable
signal in the set.

### What's here

| file | what it is |
|------|------------|
| [`the-groundless-label.md`](the-groundless-label.md) | The argument. Read this first. ~10 min, grounded in current research (HLV, VariErr, pluralistic alignment, model collapse). |
| [`the-aggregation-theorem.md`](the-aggregation-theorem.md) | **The proof the argument didn't claim.** Social choice theory (Arrow 1951, May 1952, Condorcet 1785) already settled the thesis — and drew the exact line the triage draws by hand. Companion to the argument. |
| [`the-frustrated-label.md`](the-frustrated-label.md) | **The physics one layer down.** A crowd has no ground truth for the same reason a spin glass has no ground state (Parisi, Nobel 2021). The soft label is a Gibbs state at finite temperature; majority vote is the T→0 quench; model collapse is the second law applied to values. |
| `disagreement.py` | **Diagnostic.** Instead of majority vote: keeps the distribution, separates genuine *variation* from likely *error*, flags value forks and manufactured consensus, prices what the collapse to one label destroys. Writes `triage.json`. |
| `soft_labels.py` | **Operational.** Turns the triage into things a trainer consumes: per-cell soft labels + entropy-derived weights (`soft_labels.jsonl`), and a governance queue of value forks awaiting a named human owner (`governance.jsonl`). |
| `aggregation.py` | **Proof.** Runs Arrow, May, and the Condorcet Jury Theorem against the same `data/labels.json`: the ribbon's "fact" flips with the aggregation rule, both 4–4 forks are decided by alphabetical order, and "get more labels" is shown to backfire under a shared norm. |
| `frustration.py` | **Proof.** Runs the spin-glass mapping on the same data: majority vote shown as a zero-temperature quench (and the bits it destroys), and an inferred-Ising ground state that recovers the two cohorts from votes alone (fact = ferromagnet, value fork = antiferromagnet, cyclic disagreement = spin glass). |
| `data/labels.json` | A tiny hand-built annotation set modeled on the scenario this repo grew out of: AI-generated editorial portraits, 8 annotators in 2 normative cohorts, 3 questions each. |

### Run it (two steps, zero dependencies, Python 3.8+)

```bash
python3 disagreement.py     # diagnose -> triage.json
python3 soft_labels.py      # operationalize -> soft_labels.jsonl + governance.jsonl
python3 aggregation.py      # (optional) the theorem under the thesis: social choice theory on the same data
python3 frustration.py      # (optional) the physics under the thesis: the label as a frustrated (spin-glass) system
```

The first prints a per-cell triage and a "bill" — how many bits of human
disagreement a single ground-truth column would erase, and where. The second
emits trainer-ready records and, crucially, a `governance.jsonl` **queue**: every
value fork the pipeline would otherwise resolve silently, held open until a named
human records a decision and a rationale.

The full arc: **diagnostic → triage → trainer-ready export → governance queue.**
Generated files (`triage.json`, `soft_labels.*`) are git-ignored; reproduce them
by running the two scripts. `governance.jsonl` is the exception in spirit: the
exporter *merges* with any existing copy, preserving recorded decisions and owner
assignments across runs (and keeping a decided record even if a cell is no longer
a fork). Re-running never silently loses state — in production you persist this
file as a living backlog of policy decisions.

### The one thing to take away

So the honest deliverable of high-stakes labeling is not a label. It is the
**distribution + the reasons + a record of who got out-voted** — and, for
genuine value forks, a named human who owns the call.
