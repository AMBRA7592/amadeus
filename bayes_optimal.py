#!/usr/bin/env python3
"""
bayes_optimal.py -- the decision-theoretic spine.

A hard label is not ground truth. It is a Bayes action: the output of a decision
rule applied to a distribution under a declared cost model. This script proves
that, end to end, against data/labels.json.

  Lemma 1    A hard label is a zero-entropy point on the simplex; hard-label
             training is distributional training that asserts every target has
             entropy 0.
  Theorem 1  Under log loss the Bayes-optimal prediction is the FULL conditional
             P(Y|X=x).  CE(q,p) = H(q) + KL(q||p), minimized only at p = q.
  Theorem 2  Under 0-1 loss the Bayes-optimal ACTION is argmax q. Majority vote is
             a valid action rule, never a valid target.
  Theorem 3  Majority vote collapses uncertainty: different evidence, same label.
  Theorem 4  Under exchangeable sampling, empirical frequencies are the
             multinomial MLE (reliability-correct when exchangeability fails).
  Theorem 5  A hard label is a Bayes action under a declared cost model. Admit a
             review option and the optimal action at a value fork is REVIEW, not
             a label. <- the operationally decisive result.
  Theorem 6  Same empirical distribution, different evidentiary strength: the
             Dirichlet posterior variance separates [1,1] from [500,500].

No third-party dependencies (stdlib only; Python 3.8+). Run: python3 bayes_optimal.py
"""

import json
import math
import os
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data", "labels.json")
BAR = "=" * 78
INF = float("inf")


# --------------------------------------------------------------------------- #
def load():
    with open(DATA) as f:
        return json.load(f)


def cell_counts(ds, item_id, q):
    it = next(i for i in ds["items"] if i["id"] == item_id)
    return Counter(it["labels"][q].values())


def name(ds, q, key):
    spec = ds["questions"][q]["labels"]
    return spec.get(str(key), str(key)) if isinstance(spec, dict) else str(key)


def normalize(counts):
    n = sum(counts.values())
    return {k: c / n for k, c in counts.items()}


def entropy_bits(q):
    h = -sum(p * math.log2(p) for p in q.values() if p > 0)
    return h if h > 1e-12 else 0.0


def cross_entropy_bits(q, p):
    total = 0.0
    for k, qk in q.items():
        if qk <= 0:
            continue
        pk = p.get(k, 0.0)
        if pk <= 0:
            return INF                      # mass where the prediction said "impossible"
        total += -qk * math.log2(pk)
    return total


def kl_bits(q, p):
    ce = cross_entropy_bits(q, p)
    return INF if ce == INF else ce - entropy_bits(q)


def fmt_dist(q, ds=None, qn=None):
    def lab(k):
        return name(ds, qn, k) if ds else str(k)
    return "{" + ", ".join(f"{lab(k)}:{v:.3f}" for k, v in sorted(q.items(), key=lambda kv: -kv[1])) + "}"


# --------------------------------------------------------------------------- #
def lemma_1(ds):
    print(BAR + "\nLEMMA 1  --  a hard label is a zero-entropy point on the simplex\n" + BAR)
    q = normalize(cell_counts(ds, "img1", "ribbon"))
    maj = max(q, key=q.get)
    hard = {maj: 1.0}
    print(f"  img1 / ribbon, the human distribution q = {fmt_dist(q, ds, 'ribbon')}")
    print(f"      entropy H(q)        = {entropy_bits(q):.3f} bits")
    print(f"  the hard label '{maj}'   = {fmt_dist(hard, ds, 'ribbon')}  (a vertex of the simplex)")
    print(f"      entropy H(hard)     = {entropy_bits(hard):.3f} bits")
    print("\n  A hard label is not a different kind of object from a soft label -- it is a")
    print("  soft label pinned to one corner. Training on it is distributional training")
    print("  under the assertion H = 0: a certainty no annotator expressed.")


def theorem_1(ds):
    print("\n" + BAR + "\nTHEOREM 1  --  under log loss, predict the FULL distribution P(Y|X)\n" + BAR)
    q = normalize(cell_counts(ds, "img1", "ribbon"))
    maj = max(q, key=q.get)
    hard = {maj: 1.0}
    uniform = {k: 1 / len(q) for k in q}
    print("  Cross-entropy decomposes:  CE(q, p) = H(q) + KL(q || p),  and KL >= 0 with")
    print("  equality iff p = q. So expected log loss is minimized UNIQUELY at p = q.\n")
    print(f"    predict p = q (the truth) : CE = {cross_entropy_bits(q,q):.3f}  = H(q),  KL = {kl_bits(q,q):.3f}")
    print(f"    predict p = uniform       : CE = {cross_entropy_bits(q,uniform):.3f},        KL = {kl_bits(q,uniform):.3f}")
    ce_hard = cross_entropy_bits(q, hard)
    print(f"    predict p = hard '{maj}'   : CE = {'inf (infinite)' if ce_hard==INF else round(ce_hard,3)},          "
          f"KL = {'inf' if ce_hard==INF else round(kl_bits(q,hard),3)}")
    print("\n  Predicting the hard label is INFINITELY penalized under log loss the moment")
    print("  a single annotator disagreed -- it asserts zero probability for outcomes that")
    print("  actually occurred. The Bayes-optimal target is the distribution itself.")
    print("  (This is the same fact geometry.py states from the other side: cross-entropy")
    print("  training converges to the arithmetic centre of the annotator distributions.)")


def theorem_2(ds):
    print("\n" + BAR + "\nTHEOREM 2  --  under 0-1 loss, the Bayes ACTION is argmax q\n" + BAR)
    q = normalize(cell_counts(ds, "img1", "ribbon"))
    print(f"  img1 / ribbon, q = {fmt_dist(q, ds, 'ribbon')}")
    print("  Expected 0-1 loss of committing to action a is (1 - q[a]); minimized at argmax.\n")
    for k, v in sorted(q.items(), key=lambda kv: -kv[1]):
        star = "   <- argmax = the Bayes action" if k == max(q, key=q.get) else ""
        print(f"    action '{name(ds,'ribbon',k)}': expected 0-1 loss = {1-v:.3f}{star}")
    print("\n  So majority vote (= argmax) IS Bayes-optimal -- as an ACTION under 0-1 loss.")
    print("  Theorem 1 already showed it is NOT a valid prediction TARGET. Same number,")
    print("  two different jobs: the distribution is what you predict, the mode is what")
    print("  you do. Calling the mode 'the ground truth' conflates the two.")


def theorem_3(ds):
    print("\n" + BAR + "\nTHEOREM 3  --  majority vote collapses uncertainty (same label, different evidence)\n" + BAR)
    cells = [("img3", "explicit"), ("img1", "explicit"), ("img2", "explicit")]
    print("  Three real cells on the same question. Watch the majority label hide the")
    print("  evidence state behind it:\n")
    for item, q in cells:
        c = cell_counts(ds, item, q)
        dist = normalize(c)
        maj = max(dist, key=dist.get)
        tie = sum(1 for v in dist.values() if abs(v - max(dist.values())) < 1e-9) > 1
        print(f"    {item}/{q}: counts {dict(c)}  ->  majority '{name(ds,q,maj)}"
              f"{' (TIE, broken arbitrarily)' if tie else ''}'   "
              f"H = {entropy_bits(dist):.3f} bits")
    print("\n  8-0, 7-1, and 4-4 are three different epistemic states. Majority vote maps the")
    print("  first two to the same word and the third to that word too (via a tie-break),")
    print("  erasing the one number -- entropy -- that says how much to trust the label.")


def theorem_4(ds):
    print("\n" + BAR + "\nTHEOREM 4  --  empirical frequencies are the multinomial MLE\n" + BAR)
    c = cell_counts(ds, "img1", "ribbon")
    q = normalize(c)

    def loglik(p):                                  # multinomial log-likelihood of the counts
        return sum(cnt * math.log(p[k]) for k, cnt in c.items() if p.get(k, 0) > 0)

    # perturb the empirical estimate toward uniform and show the likelihood drops
    uniform = {k: 1 / len(q) for k in q}
    mixes = [0.0, 0.25, 0.5]
    print(f"  img1 / ribbon counts {dict(c)}.  Multinomial log-likelihood of these counts,")
    print(f"  as the estimate p is dragged from empirical (t=0) toward uniform (t=1):\n")
    for t in mixes:
        p = {k: (1 - t) * q[k] + t * uniform[k] for k in q}
        print(f"    t = {t:>4}:  log-lik = {loglik(p):.3f}")
    print(f"\n  The maximum is exactly at the empirical distribution q = counts/n -- that is")
    print("  the MLE. CAVEAT: this assumes exchangeable annotators. When they are not")
    print("  (a chronic outlier, an expert vs. a guesser), use a reliability-corrected")
    print("  estimate -- which is exactly what disagreement.py does before it trusts a count.")


def bayes_action(q, cost):
    """cost: list of rows, one per action; cost[a] is a dict label->cost (or a
    constant for a flat action). Returns (action_index, expected_cost)."""
    best = None
    for a, row in enumerate(cost):
        ec = sum((row if isinstance(row, (int, float)) else row.get(k, 0.0)) * qk
                 for k, qk in q.items())
        if best is None or ec < best[1] - 1e-12:
            best = (a, ec)
    return best


def theorem_5(ds, review_cost=0.2):
    print("\n" + BAR + "\nTHEOREM 5  --  a hard label is a Bayes action under a declared cost model\n" + BAR)
    print("  a* = argmin_a  sum_k C(a, k) q_k.  Majority vote is the SPECIAL CASE where the")
    print("  actions are the classes and C(a,k) = 1[a != k] (symmetric 0-1 loss).")
    print("  Add one more action -- REVIEW, flat cost r -- and the picture changes.\n")

    print("  Canonical illustration (two classes, actions = [predict-0, predict-1, review],")
    print(f"  cost rows [[0,1],[1,0],[{review_cost},{review_cost}]]):")
    for qv in ([0.51, 0.49], [0.99, 0.01]):
        q = {0: qv[0], 1: qv[1]}
        cost = [{0: 0, 1: 1}, {0: 1, 1: 0}, review_cost]
        a, ec = bayes_action(q, cost)
        act = ["predict 0", "predict 1", "REVIEW"][a]
        print(f"    q = {qv}: Bayes action = {act:<9} (expected cost {ec:.3f}; "
              f"majority would say predict {0 if qv[0] >= qv[1] else 1})")
    print(f"\n  -> at 51/49 the Bayes action is REVIEW, not the majority label. A label is")
    print("     correct output only where the cost model says so.\n")

    print(f"  The same rule on EVERY real cell (review cost r = {review_cost}; review wins")
    print(f"  exactly when no label clears {1-review_cost:.0%} support):\n")
    routed = Counter()
    for it in ds["items"]:
        for qn in ds["questions"]:
            q = normalize(cell_counts(ds, it["id"], qn))
            classes = sorted(q)
            cost = [{k: (0 if k == c else 1) for k in classes} for c in classes] + [review_cost]
            a, ec = bayes_action(q, cost)
            if a < len(classes):
                action = name(ds, qn, classes[a])
                routed["label"] += 1
            else:
                action = "REVIEW"
                routed["REVIEW"] += 1
            if action == "REVIEW" or qn != "ribbon":   # keep the print focused
                tag = "  <-- REVIEW" if action == "REVIEW" else ""
                print(f"    {it['id']}/{qn:9s} top={max(q.values()):.2f}  ->  {action}{tag}")
    print(f"\n  {routed['REVIEW']} cells route to REVIEW, {routed['label']} to a label. The review")
    print("  action fires precisely on the value forks and the floating-signifier ribbon --")
    print("  the cells the triage already calls contested. Majority vote is Bayes-optimal")
    print("  ONLY when the action set forbids 'review' and costs are symmetric. Real")
    print("  pipelines can always abstain, hold, or escalate -- so they almost never are.")


def dirichlet_mean_sd(counts, classes, prior=1.0):
    alpha = {k: counts.get(k, 0) + prior for k in classes}
    a0 = sum(alpha.values())
    out = {}
    for k in classes:
        m = alpha[k] / a0
        var = m * (1 - m) / (a0 + 1)
        out[k] = (m, math.sqrt(var))
    return out


def theorem_6(ds):
    print("\n" + BAR + "\nTHEOREM 6  --  same distribution, different evidentiary strength (Dirichlet)\n" + BAR)
    print("  Posterior q ~ Dirichlet(counts + 1). The posterior MEAN is the empirical")
    print("  frequency; the posterior VARIANCE shrinks with the number of annotations.\n")
    print("  The pedagogical case -- identical empirical [0.5, 0.5], opposite certainty:")
    for counts in ([1, 1], [500, 500]):
        c = {0: counts[0], 1: counts[1]}
        st = dirichlet_mean_sd(c, [0, 1])
        print(f"    counts {str(counts):>12}:  mean(class 0) = {st[0][0]:.3f},  "
              f"posterior sd = {st[0][1]:.4f}")
    print("\n  Same mean, ~14x different spread. [1,1] is a shrug; [500,500] is a measured")
    print("  standoff. 'Empirical 50/50' does not distinguish them -- the posterior does.\n")
    print("  On the real cells (n = 8, so every estimate here is wide):")
    for item, qn in [("img2", "explicit"), ("img1", "explicit"), ("img2", "synthetic")]:
        c = cell_counts(ds, item, qn)
        classes = sorted(set(c) | {0, 1})
        st = dirichlet_mean_sd(c, classes)
        k0 = max(c, key=c.get)
        m, sd = st[k0]
        print(f"    {item}/{qn:9s} counts {dict(c)}:  P({name(ds,qn,k0)}) ~ {m:.2f} +/- {sd:.2f}")
    print("\n  Four things the word 'label' usually fuses, now separable:")
    print("    - label ambiguity   = entropy of q              (Theorem 3)")
    print("    - estimation uncertainty = posterior sd          (here)")
    print("    - disagreement      = the raw fact annotators differ")
    print("    - admissible decision = the Bayes action under a cost model (Theorem 5)")


def closing():
    print("\n" + BAR + "\nTHE FOUR OBJECTS  --  what a 'label' actually decomposes into\n" + BAR)
    rows = [
        ("the distribution P(Y|X)", "the STATISTICAL object", "triage.json (disagreement.py)"),
        ("the hard label / action", "the DECISION object", "soft_labels.jsonl (soft_labels.py)"),
        ("the aggregation rule", "the GOVERNANCE object", "the four foundations (Arrow/Parisi/Chichilnisky/info-geometry)"),
        ("the record", "what makes it AUDITABLE", "resolution_records.jsonl (resolution.py)"),
    ]
    w = max(len(a) for a, _, _ in rows)
    for a, b, c in rows:
        print(f"  {a:<{w}}  =  {b:<22}  ->  {c}")
    print("\n  A label is not ground truth. A label is the output of an aggregation rule")
    print("  applied to evidence under a task definition. Predict the distribution; take")
    print("  the action under a stated cost model; own the rule; record all four.")


def main():
    ds = load()
    print(BAR + "\nTHE BAYES-OPTIMAL LABEL"
          "\ndecision theory, run against data/labels.json\n" + BAR)
    lemma_1(ds)
    theorem_1(ds)
    theorem_2(ds)
    theorem_3(ds)
    theorem_4(ds)
    theorem_5(ds)
    theorem_6(ds)
    closing()


if __name__ == "__main__":
    main()
