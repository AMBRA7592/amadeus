# The Geometric Label

### The constructive turn: the triptych proves you must keep the cloud — this asks *which* cloud, and discovers that your loss function already chose

---

> **"Ship the distribution" still hides a decision. A set of human judgements
> lives on a curved manifold, where "the centre of the cloud" is not one thing:
> the KL centroid, the Fisher–Rao mean, and the Wasserstein barycenter disagree,
> sometimes by 0.70 in total variation. And the universal default loss —
> cross-entropy — is exactly one of them (the arithmetic mean). So the moment you
> train on a soft label, a geometry you never named has already chosen what
> "consensus" means.**

A word on where this sits. The three essays before it —
[social choice](the-aggregation-theorem.md), [spin glass](the-frustrated-label.md),
[topology](the-topological-label.md) — are a **closed triptych**: three proofs
of one impossibility, sealed by Baryshnikov's result that the first and the
third are literally the same theorem. This is deliberately **not a fourth side
of that shape.** It is not another impossibility; it is the first *constructive*
question, and it begins exactly where the triptych ends. The triptych proves the
destination is a cloud, not a point. This asks what kind of object the cloud is
— and finds one more silent default hiding inside the repo's own central
recommendation. [`geometry.py`](geometry.py) runs it.

---

## 1. The simplex is curved, so "the centre" is plural

A distribution over labels is a point in the probability simplex, and the
simplex is not flat. Its intrinsic, coordinate-free metric — the one any
sensible notion of statistical distance must use (Čencov's theorem) — is the
**Fisher information metric**, under which the simplex is the curved surface of a
sphere. On a curved space, the "average" of a set of points depends on *how you
measure*, and several equally principled measures give genuinely different
answers. For a set of judgement-distributions there are at least four canonical
centres:

- **Arithmetic mean** — the right-sided KL centroid, `argmin_c Σ KL(pᵢ ‖ c)`.
  The familiar mixture.
- **Geometric mean** — the left-sided KL centroid, `argmin_c Σ KL(c ‖ pᵢ)`.
  KL is asymmetric, so flipping its arguments gives a *different* centre; this
  one keeps only the labels every distribution supported and zeroes the rest.
- **Fisher–Rao mean** — the Riemannian (Fréchet) centre of mass on the Fisher
  manifold: the geodesic midpoint of the `√p` amplitudes.
- **Wasserstein barycenter** — the optimal-transport centre, which requires a
  metric *on the labels themselves* and, when they are ordered, **moves mass to
  the middle** rather than splitting it between the ends.

`geometry.py` §1 computes the first two on the real `img1 / ribbon` data and they
do not even agree on the **support**: the arithmetic centre keeps all five
readings of the ribbon; the geometric centre keeps only `scarf` and `plastic`
(the two both cohorts gave mass to) and discards the rest as noise — a total-
variation distance of `0.375` between two perfectly defensible "soft labels" for
one cell.

---

## 2. Your loss function is a choice of geometry — and you already made it

Here is the fact that turns this from a curiosity into an obligation. Training a
model `q` to match soft targets `pᵢ` under **cross-entropy** minimises
`Σ KL(pᵢ ‖ q)` — whose minimiser is exactly the **arithmetic mean**. So
cross-entropy, the default loss of essentially every classifier and every
soft-label pipeline, does not merely *use* the soft label; it converges the
model to one specific centre of the human cloud — the mixture — and to no other.

That is a choice with content, not a neutral readout. A Wasserstein/EMD loss
(Frogner et al., 2015) would pull toward the order-aware barycenter; a different
divergence, toward the Fisher centre. **The loss is the geometry, and the
geometry is the definition of "consensus" you ship.** The repo has spent three
essays exposing contestable defaults — majority vote, the tie-break, the
aggregation rule — hiding in places nobody looks. This is the same sin, found
one level deeper and pointed at the repo's *own* prescription: even after you
heed "keep the distribution," `argmax`'s quieter sibling, `cross_entropy`, is
still making the call for you.

---

## 3. On a structured axis, the centre flips the decision

When the gap is cosmetic, ignore it. The point of §3 of `geometry.py` is that on
the axes that matter most it is the opposite of cosmetic. Take an **ordered**
axis — `safe < borderline < flag`, or any 1–5 severity / Likert scale — and a
polarised split: cohort A leans `safe`, cohort B leans `flag`. Ask for the
consensus and the centres openly contradict each other:

| centre | result | what it tells a moderation system |
|---|---|---|
| **arithmetic** (cross-entropy) | `safe 0.35, borderline 0.30, flag 0.35` | *bimodal* — "people are split; borderline is rare" |
| **Fisher–Rao** | `safe 0.27, borderline 0.46, flag 0.27` | unimodal, centred on borderline |
| **geometric** | `borderline 1.0` | "the consensus is borderline" |
| **Wasserstein** (order-aware) | mass at rank ≈ 1.0 | mass *moves to the middle*, not the ends |

Same eight votes. The cross-entropy target says *never borderline, it's
polarizing*; every order-aware centre says *the agreed reading is exactly
borderline*. `TV(arithmetic, geometric) = 0.70`. These are not nuances of the
same answer — they are **opposite operational policies**: one routes the item to
a two-sided human review queue, the other auto-labels it borderline and moves
on. And on a structured axis the default loss picks the bimodal one *by
accident*, because mixing mass is what cross-entropy does, with nobody in the
room having decided that the consensus of a split should be its two extremes
rather than its middle.

---

## 4. The operator's quantity, and the decision it forces

This is the test the rest of the repo sets for any new idea: a number to compute
and a choice to make. Both exist here, and neither is delivered by the first
three essays.

**The quantity — the geometry gap.** Per cell, the divergence between the
centres a trainer might actually use (at minimum, arithmetic vs. geometric; with
an ordered axis, vs. the Wasserstein barycenter). `geometry.py` §3 prints it for
every cell; the binary value fork `img2/explicit` tops out at `0.500` (its
cohorts have disjoint support, so the geometries maximally disagree), the ribbon
at `0.375`. A large gap means **"soft label" is underspecified** until you name
a geometry.

**The decision.** It is new, and it is concrete:

1. **Pick the loss to match the label's semantics, and record it.** Unordered
   categories → cross-entropy on the mixture is defensible. **Ordered or metric
   labels with a large gap → cross-entropy is the wrong default**; it ships a
   bimodal target where the consensus may be the middle. Use an order-aware loss
   (EMD/Wasserstein), or decide on purpose to keep the bimodality — but decide.
2. **Escalate a high-gap structured axis like a value fork.** The choice of
   geometry there is a governance decision with the same standing as breaking a
   4–4 tie: it changes what the model learns "most people think." It belongs in
   `governance.jsonl`, owned by a named human, not in the loss function's
   factory settings.
3. **Report the geometry gap beside the entropy (essay 2) and the curl (essay
   3).** Three numbers, three questions: *how much* do they disagree, is the
   disagreement *cyclic*, and is the *centre* metric-dependent.

---

## 5. The honest caveat, and why this descent stops here

Two limits, stated plainly so this stays a sharp tool and not a mania.

- **Where the geometries agree, this says nothing — and that is most decidable
  cells.** A near-unanimous binary fact has all four centres on top of each
  other; the gap is ~0 and you should not give it a second thought. The geometry
  gap is valuable precisely because it is *selective*: it lights up on ordered,
  contested axes and stays dark elsewhere, telling you the few places the loss
  function is secretly legislating.
- **This is one descent, and the last one.** The triptych is closed; this is its
  single constructive complement — the move from "no point exists" to "so choose
  the cloud, and its centre, on purpose." A fifth lens that produced only another
  vocabulary for the same impossibility would be the descent too many, and should
  be declined. The discipline that made the first four worth reading is the
  discipline to stop here.

---

## Coda

Run the whole stack backwards and it is one sentence growing a clause at a time.
*Ground truth has no ground* — so the honest output is not a point but a
distribution (the thesis). It has no point because no rule, no ground state, no
contractible centre can supply one (the triptych). **And the distribution itself
has no canonical centre, so even keeping it leaves one default unspoken — the
geometry of the loss that trains on it (this).** Cross-entropy chose the
arithmetic mean before you woke up; on the axes you most care about, it is often
the wrong centre, and the right one is a decision a person should make and own.

That is the last silent default in the stack. Name the geometry. Then the cloud
you keep is finally one you *chose*, all the way down — which is the only kind of
honesty the rest of this repository was ever asking for.

---

### Sources from the wild

- S. Amari & H. Nagaoka, *Methods of Information Geometry*, 2000 (the simplex as
  a curved manifold; the Fisher metric; e- and m-geodesics).
- N. N. Čencov, *Statistical Decision Rules and Optimal Inference*, 1982 (the
  Fisher metric is the unique invariant metric on the simplex).
- F. Nielsen & R. Nock, *Sided and Symmetrized Bregman Centroids*, IEEE Trans.
  Information Theory, 2009 (left- vs right-sided KL centroids differ; closed
  forms).
- M. Agueh & G. Carlier, *Barycenters in the Wasserstein Space*, SIAM J. Math.
  Anal., 2011 (the optimal-transport centre; displacement to the middle).
- C. Frogner, C. Zhang, H. Mobahi, M. Araya-Polo, T. Poggio, *Learning with a
  Wasserstein Loss*, NeurIPS 2015 (training with the order-aware geometry instead
  of cross-entropy).
- R. Bhattacharya & V. Patrangenaru, *Large Sample Theory of Intrinsic and
  Extrinsic Sample Means on Manifolds*, Annals of Statistics, 2003 (Fréchet means
  and when they are unique).
