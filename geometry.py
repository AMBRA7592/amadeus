#!/usr/bin/env python3
"""
geometry.py -- which cloud? the soft label is not unique either.

The triptych (essays 1-3) proves WHEN you must keep the distribution instead of
collapsing to a point. This is the constructive turn that begins where it ends:
given that you keep a cloud, WHICH cloud -- and which loss trains it?

A set of human judgements is a set of points on the probability simplex, a
*curved* statistical manifold (its natural metric is Fisher information). On a
curved space "the centre" is not one thing. At least three canonical centres
disagree, and the disagreement is operational, not cosmetic:

  ARITHMETIC mean   = the right-sided KL centroid = exactly what CROSS-ENTROPY
                      training converges to. The universal default loss already
                      chose this centre, silently.
  GEOMETRIC mean    = the left-sided KL centroid (normalised geo-mean). Keeps
                      only what every cohort gave mass to; drops the rest.
  FISHER-RAO mean   = the Riemannian (Frechet) centre on the Fisher manifold.
  WASSERSTEIN bary  = the optimal-transport centre; needs a metric ON the labels
                      and, when they are ordered, moves mass to the MIDDLE
                      instead of splitting it between the ends.

The operator's new quantity: the GEOMETRY GAP, the divergence between the
cross-entropy target and the metric-respecting centre. When it is large on a
structured axis, "ship the soft label" is underspecified and the choice of loss
is a governance decision. No third-party deps (Python 3.8+). Run: python3 geometry.py
"""

import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data", "labels.json")
BAR = "=" * 78


# --------------------------------------------------------------------------- #
# the centres
# --------------------------------------------------------------------------- #
def arithmetic_mean(dists):
    """Right-sided KL centroid argmin_c sum KL(p_i || c). Equals the mixture --
    and equals what cross-entropy training converges to."""
    keys = set().union(*dists)
    n = len(dists)
    return {k: sum(d.get(k, 0.0) for d in dists) / n for k in keys}


def geometric_mean(dists):
    """Left-sided KL centroid argmin_c sum KL(c || p_i). Normalised geometric
    mean; zero wherever ANY distribution is zero (keeps only common support)."""
    keys = set().union(*dists)
    g = {}
    for k in keys:
        vals = [d.get(k, 0.0) for d in dists]
        g[k] = 0.0 if any(v <= 0 for v in vals) else math.exp(sum(math.log(v) for v in vals) / len(vals))
    s = sum(g.values())
    return {k: v / s for k, v in g.items() if s > 0 and v / s > 1e-12}


def fisher_rao_mean(p, q):
    """Frechet centre of two distributions under the Fisher-Rao metric: the
    geodesic midpoint on the sphere of sqrt-amplitudes (p -> sqrt(p) is an
    isometry of the simplex onto the positive orthant of a sphere)."""
    keys = set(p) | set(q)
    num = {k: (math.sqrt(p.get(k, 0.0)) + math.sqrt(q.get(k, 0.0))) ** 2 for k in keys}
    s = sum(num.values())
    return {k: v / s for k, v in num.items()}


def wasserstein_bary_1d(p, q):
    """W2 barycenter of two equally-weighted distributions on an ordered axis,
    via quantile averaging (exact in 1D). Returns mass on the averaged support
    points -- which sit BETWEEN the inputs, not at both ends."""
    def quantile_steps(d):
        cum, steps = 0.0, []
        for k in sorted(d):
            steps.append((cum, cum + d[k], k))
            cum += d[k]
        return steps
    sp, sq = quantile_steps(p), quantile_steps(q)
    cuts = sorted(set([s[0] for s in sp] + [s[1] for s in sp] +
                      [s[0] for s in sq] + [s[1] for s in sq]))
    bary = {}
    for lo, hi in zip(cuts, cuts[1:]):
        if hi - lo < 1e-12:
            continue
        u = (lo + hi) / 2
        a = next(k for c0, c1, k in sp if c0 - 1e-12 <= u <= c1 + 1e-12)
        b = next(k for c0, c1, k in sq if c0 - 1e-12 <= u <= c1 + 1e-12)
        mid = (a + b) / 2
        bary[mid] = bary.get(mid, 0.0) + (hi - lo)
    return bary


def tv(p, q):
    keys = set(p) | set(q)
    return 0.5 * sum(abs(p.get(k, 0.0) - q.get(k, 0.0)) for k in keys)


def fmt(d, r=3):
    return {(k if isinstance(k, str) else round(k, 2)): round(v, r) for k, v in sorted(d.items(), key=str)}


# --------------------------------------------------------------------------- #
# 1. real data: even a categorical centre is not unique
# --------------------------------------------------------------------------- #
def section_real(ds):
    print(BAR + "\n1. WHICH CENTRE?  --  the kept cloud is not unique either\n" + BAR)
    it = next(i for i in ds["items"] if i["id"] == "img1")
    cohorts = ds["cohorts"]

    def cohort_dist(members):
        c = {}
        for m in members:
            lab = it["labels"]["ribbon"][m]
            c[lab] = c.get(lab, 0.0) + 1.0 / len(members)
        return c

    A, B = cohort_dist(cohorts["A"]), cohort_dist(cohorts["B"])
    am, gm = arithmetic_mean([A, B]), geometric_mean([A, B])
    print(f"  img1 / ribbon, the two cohorts' distributions:")
    print(f"     cohort A: {fmt(A)}")
    print(f"     cohort B: {fmt(B)}")
    print(f"\n  ARITHMETIC mean (= cross-entropy target): {fmt(am)}")
    print(f"  GEOMETRIC  mean (= left-KL centroid)    : {fmt(gm)}")
    print(f"\n  They do not even agree on the SUPPORT: the arithmetic centre keeps all")
    print(f"  {len(am)} readings; the geometric centre keeps only the {len(gm)} both cohorts")
    print(f"  gave mass to, and calls the rest noise. TV(arithmetic, geometric) = {tv(am, gm):.3f}.")
    print(f"  Two defensible 'soft labels' for one cell -- and cross-entropy quietly picks")
    print(f"  the first, because that is the centre its gradient happens to roll toward.")


# --------------------------------------------------------------------------- #
# 2. the structured-axis payoff: the centre flips the decision
# --------------------------------------------------------------------------- #
def section_ordinal():
    print("\n" + BAR + "\n2. ON A STRUCTURED AXIS  --  the centre flips the moderation decision\n" + BAR)
    print("  Many real axes are ORDERED: safe < borderline < flag, a 1-5 severity, a")
    print("  Likert scale. Take a polarized split -- cohort A leans safe, cohort B leans")
    print("  flag -- and ask for the consensus:\n")
    names = {0: "safe", 1: "borderline", 2: "flag"}
    A = {0: 0.7, 1: 0.3, 2: 0.0}
    B = {0: 0.0, 1: 0.3, 2: 0.7}
    am = arithmetic_mean([A, B])
    fm = fisher_rao_mean(A, B)
    gm = geometric_mean([A, B])
    wb = wasserstein_bary_1d(A, B)
    show = lambda d: {names.get(k, k): round(v, 3) for k, v in sorted(d.items(), key=str)}
    print(f"     cohort A: {show(A)}      cohort B: {show(B)}\n")
    print(f"  ARITHMETIC (cross-entropy target): {show(am)}")
    print(f"       -> BIMODAL: 'people are split between safe and flag; borderline is rare.'")
    print(f"  FISHER-RAO  (Frechet centre)     : {show(fm)}")
    print(f"       -> unimodal, centred on borderline.")
    print(f"  GEOMETRIC   (left-KL centroid)   : {show(gm)}")
    print(f"       -> 'the consensus is borderline,' full stop.")
    print(f"  WASSERSTEIN (order-aware bary)   : {{{', '.join(f'{k}:{round(v,3)}' for k,v in sorted(wb.items()))}}}")
    print(f"       -> mass MOVES to the middle (rank ~1.0), not split to the ends.")
    print(f"\n  Same eight votes. The cross-entropy target says 'never borderline, it's")
    print(f"  polarizing'; every order-aware centre says 'the agreed answer IS borderline.'")
    print(f"  TV(arithmetic, geometric) = {tv(am, gm):.2f}. These are opposite policies -- one")
    print(f"  routes to a two-sided review queue, the other auto-labels borderline -- and")
    print(f"  the default loss chooses between them with nobody in the room.")


# --------------------------------------------------------------------------- #
# 3. the operator's quantity and decision
# --------------------------------------------------------------------------- #
def section_operator(ds):
    print("\n" + BAR + "\n3. THE GEOMETRY GAP  --  a number to compute, a decision to make\n" + BAR)
    print("  For any cell, the geometry gap is the divergence between the centres a")
    print("  trainer might use. A large gap means 'soft label' is underspecified until")
    print("  you name a geometry. Per cell here (arithmetic vs geometric centre of the")
    print("  two cohorts), in total variation:\n")
    rows = []
    for it in ds["items"]:
        for q in ds["questions"]:
            cohorts = ds["cohorts"]

            def cdist(members):
                c = {}
                present = [m for m in members if m in it["labels"][q]]
                for m in present:
                    lab = it["labels"][q][m]
                    c[lab] = c.get(lab, 0.0) + 1.0 / len(present)
                return c
            A, B = cdist(cohorts["A"]), cdist(cohorts["B"])
            am, gm = arithmetic_mean([A, B]), geometric_mean([A, B])
            gap = tv(am, gm)
            if gap > 1e-9:
                rows.append((f"{it['id']}/{q}", gap))
    rows.sort(key=lambda r: -r[1])
    for name, gap in rows:
        flag = "   <- geometry-dependent: name the loss on the record" if gap >= 0.3 else ""
        print(f"    {name:16s} gap = {gap:.3f}{flag}")
    print("\n  THE DECISION (the part the first three essays do not give you):")
    print("    - The training loss IS a choice of geometry. Cross-entropy = the")
    print("      arithmetic centre; an EMD/Wasserstein loss = the order-aware centre.")
    print("    - If the label axis has order or metric structure AND the gap is large,")
    print("      do not default to cross-entropy: it can ship a bimodal target where the")
    print("      consensus is the middle. Choose the loss to match the label's meaning,")
    print("      and record the choice -- it is a governance decision, like a value fork.")
    print("    - Report this gap next to the entropy (essay 2) and the curl (essay 3).")


def main():
    with open(DATA) as f:
        ds = json.load(f)
    print(BAR + "\nWHICH CLOUD?  --  the geometry of the soft label"
          "\ninformation geometry (Amari; HodgeRank's cousins), on data/labels.json\n" + BAR)
    section_real(ds)
    section_ordinal()
    section_operator(ds)
    print("\n" + BAR + "\nTAKEAWAY\n" + BAR)
    print("  The triptych proved the destination is a cloud, not a point. This is the")
    print("  next question, and it is constructive, not another impossibility: a cloud")
    print("  on a curved manifold has no canonical centre, so 'ship the distribution'")
    print("  still hides a choice -- the loss you train with. Cross-entropy chose the")
    print("  arithmetic mean before you woke up. On a structured axis that is often the")
    print("  wrong centre. Name the geometry. It is the last silent default in the stack.")


if __name__ == "__main__":
    main()
