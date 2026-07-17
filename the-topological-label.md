# The Topological Label

### Aggregation is impossible exactly when the space of preferences has a hole — and a reward model is a potential that a value fork forbids

---

> **A reward model is a scalar field: it assigns every option a number. Fitting
> it to human preference asks for a *potential* whose gradient is the preference
> field. Such a potential exists if and only if the field is curl-free — if and
> only if the preference space has no hole. A value fork is a hole. There is no
> reward function that fits it; the model can only tear the space somewhere
> arbitrary and call the tear "ground truth."**

[`the-aggregation-theorem.md`](the-aggregation-theorem.md) showed the
impossibility by counting (Arrow). [`the-frustrated-label.md`](the-frustrated-label.md)
showed it as physics (a frustrated system has no ground state). This is the same
fact a third way — by *shape* — and the third way is the deepest, because it
turns out to contain the other two. [`topology.py`](topology.py) runs it.

---

## 1. The hole is the whole story

In 1980 Graciela Chichilnisky asked Arrow's question in the language of
topology. Represent each person's preference as a point in a space `P` (for
preferences over a continuum — a budget, a colour, a face — `P` is naturally a
sphere of *directions*, the way you'd most like to move). An aggregation rule is
a continuous map that is **anonymous** (the voters are interchangeable) and
**respects unanimity** (if everyone holds `p`, the result is `p`). She proved a
clean dichotomy:

> Such a rule exists, for every number of voters, **if and only if `P` is
> contractible** — topologically trivial, shrinkable to a point, no holes.

The smallest counterexample is a circle. You cannot continuously, symmetrically
average *directions*. `topology.py` §1 makes it visible: on the interval the
mean `(x+y)/2` is continuous, anonymous, unanimous — no trouble. On the circle
the only natural candidate, the midpoint of the shorter arc, **jumps by 180° at
the antipode**. And the jump is not a defect of that candidate; Chichilnisky
proved *every* continuous anonymous unanimous rule on the circle fails. The
obstruction is a winding number forced to take a half-integer value — the
circle's hole (`π₁ = ℤ`) showing through. **Where preference space is
contractible, aggregation exists. Where it has a hole, no rule can.** The
"contestable rule" of the first essay is, geometrically, a rule trying to span a
gap that isn't there to be spanned.

---

## 2. A reward model is a potential, and a value fork is curl

Here is the bridge to the systems we actually build, and it is exact. A reward
model `r` is a scalar field on the option space. To train it on pairwise human
preference is to demand

```
    r(better) − r(worse) = margin(better, worse)
```

for every compared pair. That is the discrete statement of "the preference field
is the **gradient** of the reward." And a field is a gradient — a potential
exists — **if and only if it is curl-free: every closed loop integrates to
zero** (the discrete Hodge / Helmholtz decomposition; in statistics this is
*HodgeRank*, Jiang–Lim–Yao–Ye 2011). The circulation around a loop is precisely
the first cohomology `H¹`; a potential exists iff `H¹ = 0`.

Now feed it the value fork. `topology.py` §2 takes the three readings of the
ribbon as a Condorcet cycle — `scarf > plastic`, `plastic > ribbon`, `ribbon >
scarf`, each by a clear margin — and computes the circulation: **3, not 0.** The
field is pure curl. The best least-squares reward is the flat tie `scarf =
plastic = ribbon = 0`: the model can express *none* of the preference, because
none of it is a gradient. A transitive case, by contrast, has circulation 0, and
the reward (a clean ranking) drops right out.

So a value fork is not a hard ranking problem that more data will solve. It is a
field with **curl** — circulation around a loop in preference space — and curl
has no potential, the way a whirlpool has no "height map." To ship a reward
anyway, the model must **cut** the loop somewhere and pretend the circulation
ends there. The cut is arbitrary; slide it anywhere around the ring and the
"ranking" changes while not one human preference does. That cut is the casting
vote of essay 1 and the symmetry-breaking field of essay 2 — now revealed as a
*topological defect*, a tear the model introduces because the space it is
fitting has a hole.

This is also a *measurable* statement, which is the practical gift: compute the
circulation of your preference data over the model's embedding (HodgeRank does
exactly this). If it is non-zero, no consistent reward exists on that geometry,
and whatever you ship is a cut whose location you chose by accident. **Curl is a
groundlessness you can put a number on.**

---

## 3. A thresholded diagnostic of the real disagreement

`topology.py` §3 builds an exploratory **camp complex**: two annotators are
joined when their co-deviation from the item mean is positive and at least 25%
of the strongest positive coupling for that question. Annotators with no
above-floor tie are reported as **unaligned** instead of being counted as
one-person camps. The flag complex of the retained graph then gives `(b₀, b₁)`:
the number of connected camp components and the number of unfilled loops.

That floor fixes the original construction's concrete failure. With every
positive coupling retained, the near-unanimous `synthetic` question fragmented
into three pieces and falsely looked like three "worldviews," while the
`explicit` components were not the two cohorts the prose claimed. With the
noise floor applied:

- `synthetic` gives `(b₀, b₁) = (1, 0)` on one small retained pocket
  `{a3, b3}`; the other six annotators are unaligned. Combined with the
  near-unanimous votes, the honest conclusion is narrow: **no structured
  opposing camps are detected**.
- `explicit` gives `(b₀, b₁) = (2, 0)`: the cohort-A core
  `{a1, a2, a4}` and cohort-B core `{b1, b2, b4}`, with `a3` and `b3`
  unaligned rather than forced into either camp. Here the thresholded graph
  really does recover the two cohort cores from the votes.

Two caveats are load-bearing. First, the 25% floor is a transparent heuristic,
not a universal constant; a production analysis should report sensitivity to
it. On a 0.05-grid sweep, the joint reading — one synthetic camp plus the two
explicit cohort cores — is stable from 0.20 through 0.75; the shipped 0.25 sits
near the low edge so the near-consensus question still reads as one camp.
Second, this annotator co-deviation complex is **not itself Chichilnisky's
space of preferences**. Its Betti numbers are a useful structural diagnostic,
not an empirical proof of the theorem's hypotheses. Even `(1, 0)` only rules out
disconnection and one-dimensional holes; it does not prove contractibility in
general. The constructed four-annotator ring remains the clean illustration of
the other detected obstruction: `(b₀, b₁) = (1, 1)`, locally connected with
an unfilled loop.

---

## 4. One defect, three names

The reason to take the topology seriously is that it does not merely *agree*
with the first two essays — it *contains* them. In 1993 Yuliy Baryshnikov proved
that **Arrow's theorem and Chichilnisky's theorem are the same theorem**: build
the right space out of Arrow's discrete preferences and its non-contractibility
*is* the dictator. Arrow's impossibility is a hole, counted instead of seen.

So the three descents close into one object:

| essay | the obstruction | its name |
|---|---|---|
| 1 — social choice | no neutral rule for ≥3 options | Arrow's impossibility |
| 2 — statistical mechanics | competing constraints, no ground state | frustration / a spin glass |
| 3 — topology | preference space not contractible | a hole (`b₀>1` or `b₁>0`) |

A Condorcet cycle is a frustrated loop is a generator of `H¹` is non-zero curl
with no reward potential. **One hole, named four times.** "Ground truth has no
ground" turns out to be the literal geometric statement *the space has no
contractible centre to stand on* — and every tool in this repo is a way of
either finding that centre where it exists (a fact: collapse it) or refusing to
fake one where it doesn't (a fork: keep the distribution, and let a named human
choose where to cut).

---

## 5. What this adds to "What to do on Monday"

1. **Measure the curl, not just the spread.** Entropy says how much people
   disagree; circulation (HodgeRank's harmonic component) says whether the
   disagreement is *consistent enough to support a ranking at all*. A subjective
   axis with high circulation has no coherent reward — report that number before
   anyone trains a reward model on it.
2. **Do not fit one continuous reward across a hole.** If the preference space
   is disconnected (the cohorts) or has a loop, a single global reward must tear
   it. The honest alternatives are a *mixture* (a reward per pure state /
   cohort, kept separate — pluralistic by construction) or an explicit, recorded
   choice of where the cut goes. Never let `argmax` site the tear in the dark.
3. **Treat "the embedding has nontrivial topology" as a first-class risk.** When
   a domain's human preferences are cyclic or multi-modal (no canonical best),
   alignment on it is not merely hard, it is *ill-posed* — there is no scalar
   reward to converge to. That is diagnosable from the data's shape, ahead of
   training, and it tells you where reward hacking and boundary cliffs will come
   from: the cuts.

---

## Coda

Four ways of saying one thing. The label has no ground because the preference
space has no floor to stand on — not a missing measurement, a missing *centre*.
A fact is a space you can shrink to a point, and there the single number, the
ground truth, the reward, all exist and agree. A value fork is a space with a
hole, and over a hole there is no point, no potential, no ranking, no truth — only
the circulation itself, and the choice of where to cut it, which is a decision a
person makes and owns, not one an aggregation function should make in the dark.

The whole repository, read backwards from here, is a single instruction: **find
out whether the space has a hole, and behave differently when it does.** Where it
is contractible, collapse with a clear conscience. Where it is not, keep the
cloud — because the cloud is not your failure to find the ground. The cloud
*is* the ground, and there is no other.

---

### Sources from the wild

- G. Chichilnisky, *Social Choice and the Topology of Spaces of Preferences*,
  Advances in Mathematics, 1980 (aggregation exists iff the preference space is
  contractible).
- G. Chichilnisky & G. Heal, *Necessary and Sufficient Conditions for a
  Resolution of the Social Choice Paradox*, Journal of Economic Theory, 1983.
- Y. Baryshnikov, *Unifying Impossibility Theorems: A Topological Approach*,
  Advances in Applied Mathematics, 1993 (Arrow = Chichilnisky; the dictator is
  the hole).
- X. Jiang, L.-H. Lim, Y. Yao, Y. Ye, *Statistical Ranking and Combinatorial
  Hodge Theory*, Mathematical Programming, 2011 (HodgeRank: ranking = gradient,
  inconsistency = curl + harmonic; the circulation you can compute).
- B. Eckmann, *Harmonische Funktionen und Randwertaufgaben in einem Komplex*,
  1945 (discrete Hodge decomposition — a field is a gradient iff it is
  curl-free).
- D. G. Saari, *Geometry of Voting*, 1994 (the geometric reading of Arrow and the
  Condorcet paradox).
