# The Bayes-Optimal Label

### A label is not ground truth — it is a Bayes action: an aggregation rule applied to evidence under a declared cost model

---

> *This note shows that hard labels are zero-entropy special cases of label
> distributions, that log-loss training is Bayes-optimal when it predicts the
> full conditional label distribution, that 0–1 loss and other cost models
> produce different optimal actions, and that majority vote should be treated as
> one Bayes action under a declared cost model — not as ground truth.*

The other documents here argue that "ground truth" is contestable
([the argument](the-groundless-label.md)), that no aggregation rule is neutral
([Arrow](the-aggregation-theorem.md)), that the disagreement is a frustrated
system ([Parisi](the-frustrated-label.md)) with a hole
([Chichilnisky](the-topological-label.md)), and that even the kept distribution
has no canonical centre ([information geometry](the-geometric-label.md)). This is
the spine they hang on, and it is the most elementary statement of all: a label
is a *decision*, and decision theory already tells you exactly what a good one
is. [`bayes_optimal.py`](bayes_optimal.py) runs every line below against
`data/labels.json`.

---

## Lemma 1 — a hard label is a zero-entropy point on the simplex

A distribution over `k` labels is a point in the `(k−1)`-simplex. A *hard* label
is the special case that sits on a vertex: a one-hot vector, entropy 0. So
hard-label training is not a different activity from distributional training —
it is distributional training under the assertion that **every target has
entropy zero.** On `img1 / ribbon` the human distribution is `{scarf .375,
plastic .25, ribbon .125, choker .125, unknown .125}`, `H = 2.156` bits; the hard
label `scarf` is `{scarf 1.0}`, `H = 0`. The pipeline feeds the model the vertex
and tells it the cloud was never there.

---

## Theorem 1 — under log loss, the Bayes-optimal prediction is `P(Y|X=x)`

Cross-entropy decomposes exactly:

```
    CE(q, p) = H(q) + KL(q ‖ p),     KL ≥ 0,  with equality iff p = q.
```

So expected log loss is minimized **uniquely** at `p = q` — the full conditional
distribution. Log loss is a *strictly proper scoring rule* (Gneiting & Raftery,
2007); it is built to be honest only when you report what you actually believe.
On `img1 / ribbon`: predicting `q` costs `2.156` bits (`= H(q)`, `KL = 0`);
predicting uniform costs `2.322` (`KL = 0.166`); predicting the **hard label**
costs **∞** — the instant one annotator disagreed, the one-hot target assigns
probability zero to an outcome that occurred, and log loss punishes that without
mercy. This is the same fact [`geometry.py`](geometry.py) states from the other
side: cross-entropy training converges to the *arithmetic centre* of the
annotators' distributions, so the target it is reaching for is the distribution,
not the mode.

---

## Theorem 2 — under 0–1 loss, the Bayes-optimal action is `argmax q`

Commit to a single class `a` and your expected 0–1 loss is `1 − q[a]`, minimized
at `a = argmax q`. On `img1 / ribbon` that is `scarf`, expected loss `0.625`.
**So majority vote is Bayes-optimal — as an *action*, under 0–1 loss.** Theorem 1
showed it is not a valid prediction *target*. The same number does two different
jobs: the distribution is what you *predict*, the mode is what you *do*. "Ground
truth" smuggles the second into the first and loses the distinction.

---

## Theorem 3 — majority vote collapses uncertainty

Three real cells on the `explicit` question: `8–0` (`H = 0`), `7–1`
(`H = 0.544`), `4–4` (`H = 1.0`). Three different epistemic states. Majority vote
maps the first two to the same word, `safe`, and the third to that word as well
(via an arbitrary tie-break) — erasing entropy, the one number that says how far
to trust the label. `51/49` and `99/1` ship identically and mean opposite things.

---

## Theorem 4 — empirical frequencies are the multinomial MLE

Under exchangeable annotator sampling, `q̂ = counts / n` is the maximum-likelihood
estimate of the multinomial: the log-likelihood of the observed counts is
maximized exactly at the empirical distribution, and `bayes_optimal.py` shows it
falling as the estimate is dragged toward uniform. **Caveat — and it is
load-bearing:** this holds under *exchangeability*. When annotators differ in
reliability (a chronic outlier, an expert beside a guesser), the flat count is
biased and you need a reliability-corrected estimate (Dawid & Skene, 1979) —
which is precisely what [`disagreement.py`](disagreement.py) computes before it
trusts a tally.

---

## Theorem 5 — a hard label is a Bayes action under a declared cost model

This is the decisive one. Given a distribution `q`, an action set `A`, and a cost
matrix `C(a, k)`, the Bayes action is

```
    a* = argmin_a  Σ_k  C(a, k) · q_k.
```

**Majority vote is the special case** where the actions *are* the classes and
`C(a, k) = 1[a ≠ k]` (symmetric 0–1 loss). It is one cell of a much larger table.
Now add a single action everyone actually has — **review** (abstain / hold /
escalate), at a flat cost `r`. The Bayes action becomes *review* exactly when no
label clears `1 − r` of the mass (this is Chow's reject rule, 1970). With the
cost rows `[[0,1],[1,0],[0.2,0.2]]`:

- `q = [0.51, 0.49]` → **review** (expected cost `0.20` vs `0.49` for the
  majority label).
- `q = [0.99, 0.01]` → **predict class 0** (cost `0.01`): when the evidence is
  decisive, the label wins.

Run the same rule across all 18 real cells (`r = 0.2`, so review wins below 80%
support) and **6 cells route to review — precisely the value forks and the
floating-signifier ribbon**, the cells the triage already calls contested; the
other 12 collapse to a label. The proof is therefore not "majority vote is
wrong." It is sharper, and it concedes more: **majority vote is Bayes-optimal in
exactly one regime — symmetric 0–1 costs with no review option — and
Bayes-suboptimal in every cost model that admits abstention.** Real pipelines can
always abstain. So the correct output of aggregation is *not always a label*;
sometimes it is review, and a cost model tells you which, on the record.

---

## Theorem 6 — same distribution, different evidentiary strength

Two cells with counts `[1, 1]` and `[500, 500]` have the *same* empirical
distribution, `[0.5, 0.5]`. They are not the same evidence. The Dirichlet
posterior `q ~ Dirichlet(counts + 1)` has the same mean for both (`0.5`) but a
posterior standard deviation of `0.224` versus `0.016` — a ~14× difference. One is
a shrug; the other is a measured standoff. Reporting "50/50" cannot tell them
apart; the posterior can. (Every cell in this repo has `n = 8`, so every estimate
here is wide — `P(safe) ≈ 0.50 ± 0.15` on the 4–4 fork — which is itself worth
saying out loud.) This finally separates four things the word "label" routinely
fuses into one:

| concept | what it is | where |
|---|---|---|
| **label ambiguity** | entropy of `q` | Theorem 3 |
| **estimation uncertainty** | posterior standard deviation | Theorem 6 |
| **disagreement** | the raw fact that annotators differ | the data |
| **admissible decision** | the Bayes action under a cost model | Theorem 5 |

---

## The four objects — and why this is the spine

A label is not ground truth. **A label is the output of an aggregation rule
applied to evidence under a task definition.** Decomposed, it is four objects,
and the repository already produces each one:

| object | role | produced by |
|---|---|---|
| the distribution `P(Y|X)` | the **statistical** object | `triage.json` ([`disagreement.py`](disagreement.py)) |
| the hard label / action | the **decision** object | `soft_labels.jsonl` ([`soft_labels.py`](soft_labels.py)) |
| the aggregation rule | the **governance** object | the four foundations (Arrow / Parisi / Chichilnisky / information geometry) |
| the record | what makes it **auditable** | `resolution_records.jsonl` ([`resolution.py`](resolution.py), validated by [`resolution_record.schema.json`](schema/resolution_record.schema.json)) |

Read this way, the rest of the repository snaps into place. The four foundation
essays are not four separate analogies; they are four **expansions of the
admissibility question raised in Theorem 5** — four mathematical accounts of why
an aggregation rule's cost model is never neutral (it must break an Arrow axiom,
it is frustrated, it spans a topological hole, it picks a geometry). The schema
is the **operational form of the record demand** the closing makes. The
distribution is the statistical object; the hard label is a decision object; the
aggregation rule is a governance object; the record is what makes the decision
auditable. Everything else in this repository is one of those four, examined
closely.

And it answers the one objection this whole project invites — *"majority vote
works fine, you're attacking a strawman."* No: majority vote is **proven
correct**, here, in runnable code — for 0–1 loss with no review option. The claim
is only that this regime is narrow, that it ends the moment a pipeline can
abstain, and that calling the rule's output "ground truth" hides the cost model
that made it correct. Concede the rule its regime; then show, with a three-row
cost matrix, exactly where the regime ends.

---

### Sources from the wild

- L. J. Savage, *The Foundations of Statistics*, 1954 (acts, consequences, and
  the Bayes action minimizing expected loss).
- J. O. Berger, *Statistical Decision Theory and Bayesian Analysis*, 2nd ed.,
  1985 (Bayes risk; the optimal action under an arbitrary cost matrix; the
  reject/abstain action).
- T. Gneiting & A. E. Raftery, *Strictly Proper Scoring Rules, Prediction, and
  Estimation*, JASA, 2007 (log loss is strictly proper — minimized only at the
  true distribution; Theorem 1).
- C. K. Chow, *On Optimum Recognition Error and Reject Tradeoff*, IEEE Trans.
  Information Theory, 1970 (the optimal reject rule: abstain when the top
  posterior falls below a cost-set threshold; Theorem 5).
- A. P. Dawid & A. M. Skene, *Maximum Likelihood Estimation of Observer
  Error-Rates Using the EM Algorithm*, JRSS-C, 1979 (reliability-corrected
  estimates when annotators are not exchangeable; Theorem 4's caveat).
- A. Gelman, J. Carlin, H. Stern, D. Dunson, A. Vehtari, D. Rubin, *Bayesian Data
  Analysis*, 3rd ed., 2013 (the Dirichlet–multinomial posterior; Theorem 6).
