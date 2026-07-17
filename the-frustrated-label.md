# The Frustrated Label

### Why a crowd has no ground truth for the same reason a spin glass has no ground state — and what the 2021 Nobel Prize says to ship instead

---

> **A value fork is not a measurement that came out noisy. It is a frustrated
> physical system, and "collapse it to one label" is a request for something
> the system provably does not have: a unique ground state. Majority vote is a
> zero-temperature quench — it freezes the crowd into one arbitrary valley and
> reports the discarded entropy as error.**

[`the-groundless-label.md`](the-groundless-label.md) shows, by argument, that
much of what we label has no single right answer. [`the-aggregation-theorem.md`](the-aggregation-theorem.md)
shows that no aggregation rule is neutral. This is the layer underneath both:
the *physics* of why, where the same structure has been studied for fifty years
under a different name, and where understanding it earned a Nobel Prize in 2021.
[`frustration.py`](frustration.py) runs it against `data/labels.json`.

---

## 1. The shape is frustration

Take three readings of the ribbon and three annotators who rank them
`scarf > plastic > ribbon`, `plastic > ribbon > scarf`, `ribbon > scarf >
plastic`. Every *pairwise* majority is decisive — scarf beats plastic 2–1, plastic
beats ribbon 2–1, ribbon beats scarf 2–1 — and they close into a loop with no
top. There is no winner, not because the data is thin but because, *as a
configuration, a winner does not exist.* (`frustration.py` §3 prints exactly
this cycle.)

Physics has a one-word name for a set of locally satisfiable constraints with no
globally consistent solution: **frustration** (Toulouse, 1977). The textbook
case is three spins on a triangle that all want to point opposite their
neighbours — pick any two and the third is stuck. A **spin glass** is a large
disordered system built from competing couplings like these, and its defining
property is the one that matters here: **it has no unique ground state.** The
energy landscape does not fall to a single bottom; it shatters into a vast
number of valleys of nearly equal depth.

"Ground truth has no ground" and "this system has no ground state" are not a
pun. They are the same sentence about the same object.

---

## 2. What won the 2021 Nobel Prize — and why it is about your annotators

For a long time it was not even clear that spin glasses *had* a sensible
description. Giorgio Parisi found it, and in 2021 the Nobel Prize in Physics
recognised the result. His **replica symmetry breaking** says that a frustrated
disordered system, rather than choosing one state, lives across **many** of
them — and, crucially, that those states are not scattered at random. They are
organised **ultrametrically**: into clusters, and clusters of clusters, a
hierarchy of "pure states," each an internally-consistent way the whole system
can settle.

Read that back as a sentence about labeling and it is uncannily exact. A
contested item does not have one true reading with noise around it. It has
**several coherent readings**, and they come pre-sorted into camps — the
cohorts. The "art/editorial" frame and the "platform-safety" frame are not two
error rates around a hidden truth; they are two **pure states** of a frustrated
system, two valleys the crowd can fall into, each self-consistent. Parisi's
picture is the precise mathematical form of the essay's claim that the
disagreement has *structure* and is *signal* — the structure is the ultrametric
tree of pure states, and the cohorts are its leaves.

`frustration.py` §2 makes this concrete without being told the cohorts. It
infers a coupling between every pair of annotators from how they *co-deviate
from consensus* — literally the coupling J_ij of an Ising model fit to the data
— and finds the ground state. On the contested `explicit` question the ground
state splits cleanly into two opposed domains at only 5% residual frustration,
and the split **is exactly the two cohorts**. The system handed back its own
pure states. The consensus `synthetic` question supports no such split: one
domain, plus a lone contrarian — a ferromagnet with an impurity, not a fork.

Three phases, three kinds of question:

| physics | the labeling | ground states |
|---|---|---|
| **ferromagnet** | a real fact (consensus) | **one** — collapse it honestly |
| **antiferromagnet** | a value fork (two coherent camps) | **two** — the cohorts; choose on the record |
| **spin glass** | irreducible / cyclic disagreement | **many** — there is no label, only a distribution |

The diagnostic the companion essay built by hand — *confident / contested /
value-fork* — is this phase diagram, rediscovered. "Is there a ground truth?" is
the physicist's question "is this system ordered, or frustrated?"

---

## 3. Majority vote is a quench — and the soft label is the temperature

Here is the part that turns the analogy into an instrument, and it is exact, not
poetic. In 1957 E. T. Jaynes proved that the distribution of maximum entropy
consistent with what you know is precisely the **Gibbs–Boltzmann distribution**
of statistical mechanics — the two fields are one mathematics. So the honest
summary of a vote, the distribution that assumes nothing beyond the frequencies
you observed, *is* a Gibbs state. The soft label is not a softer version of the
truth. It is the system's thermal state.

And that gives "collapse to one label" a temperature. `frustration.py` §1 cools
each cell: at T = 1 you have the observed soft label; as T → 0 the mass races to
the single most-voted option. **Majority vote is the T → 0 limit — a quench.**
Watch what the quench costs:

- `img2 / synthetic` (a real fact): soft-label entropy ≈ 0. Cooling to T = 0
  destroys **0.00 bits.** A ferromagnet has one valley; freezing it loses
  nothing. This is the only regime where "ground truth" is not a figure of
  speech.
- `img1 / ribbon` (the floating signifier): soft-label entropy ≈ 2.16 bits.
  Cooling to T = 0 destroys **all 2.16** — a violent freeze that picks `scarf`
  (a 37.5% minority) and discards the rest as if it were thermal noise.
- `img2 / explicit` (the 4–4 fork): at T = 0 the ground state is **degenerate**
  — two valleys of identical depth. The quench *cannot choose* without an
  **external field**. That field is the tie-break; `sorted()[0]` is a magnet
  held to the data from outside, and the essay already caught it deciding the
  fork by alphabetical order.

So the bits the original `disagreement.py` bill prices are not a metaphor for
lost information — they *are* entropy, in the thermodynamic sense, and majority
vote is the cooling that destroys them. "Keep the distribution" is, precisely,
**keep the temperature above zero.**

And the recursive sting of the first essay now has a thermodynamic name. Label
contested items by majority, train the next generator on the result, repeat: you
are quenching the same system every generation, and **entropy can only fall.**
Model collapse is not a mysterious degeneration; it is the second law applied to
value diversity, running one quench per model generation, until the ensemble of
human readings has been annealed down to a single frozen valley that the system
then reports back to us as "what people think."

---

## 4. The honest caveat (again, because it is what separates this from a vibe)

The analogy earns its keep only where it computes, and it does not compute
everywhere. Three honest limits:

- **The exact parts are exact; the evocative parts are evocative.** Jaynes
  (soft label = Gibbs state, majority = T → 0) is an identity. The frustration
  index and the ground-state bipartition are quantities you can and do compute
  (`frustration.py` brute-forces all 256 spin configurations). Full replica
  symmetry breaking, with provable ultrametricity, is a theorem about specific
  models (Sherrington–Kirkpatrick), not a proof about an eight-person annotator
  pool. What transfers rigorously is the *qualitative* claim — frustration
  implies many pure states in clusters — and that is the claim doing the work.
- **Not all frustration is a value fork.** Some is just noise: a genuinely
  careless triangle of clicks also fails to close. The spin-glass frame does not
  excuse you from the `VariErr` problem of separating variation from error — it
  reframes it as "is this frustration *structured* (low residual, clean domains
  → signal) or *disordered* (high residual, no clean domains → suspect)?", which
  is exactly what §2's frustration index measures.
- **Temperature is a choice, not a discovery.** Saying "keep T > 0" does not
  tell you *which* T to ship. That is real, and it is the point: the choice of
  temperature is now an explicit, visible knob with a name, instead of a default
  quench hiding inside `argmax`. You have relocated the decision to where it can
  be argued about, which is the whole program.

---

## 5. What this adds to "What to do on Monday"

1. **Treat the soft label as a temperature, and ship T, not just the mode.** The
   collapse to one class is the T → 0 corner of a dial you are allowed to turn.
   Pick the temperature deliberately, per axis, and record it. `argmax` is a
   policy ("freeze everything"), not the absence of one.
2. **Report a frustration index next to the entropy.** Entropy says *how much*
   the crowd disagrees; frustration says *whether the disagreement is ordered*.
   A high-entropy, low-frustration cell is a clean value fork (two domains) —
   escalate it. A high-entropy, high-frustration cell is a spin glass or a mess
   — inspect it. They are different physics and need different handling.
3. **Read a value fork as a broken symmetry, and resolve it like one.**
   Two degenerate ground states do not get "averaged"; one is selected by an
   external field. In a pipeline that field must be a **named human** applying a
   stated policy on the record — not `sorted()`, not the pool-wide prior. This
   is the deepest reason `governance.jsonl` is mandatory: at a degeneracy, the
   physics is silent, so something outside the data must speak, and it had
   better be accountable.
4. **Monitor entropy across generations as a collapse alarm.** If the labeled
   distribution for an axis loses entropy model-over-model, you are quenching the
   ensemble. Diversity decay is measurable in bits before it is visible in
   behaviour.

---

## Coda

The wider source series that inspired this demonstrator included frames with a
surveillance camera in the corner and a bank of monitors on the wall; those
source images are not distributed in this repository. One scene rendered as a
grid of simultaneous angles is the right emblem to end on, because it is the
opposite of a quench. A control room does not collapse its twelve feeds into one "true" frame
and delete the rest; it keeps the ensemble on the wall, because the truth of
the room *is* the set of views, and any single frame is already a choice of
where to stand. The grid is the distribution, displayed instead of averaged —
the replicas of a system that has more than one valid state.

That is the whole argument, compressed to an image. A crowd of judgements is a
frustrated system; its honest description is a thermal distribution over many
pure states, not a frozen one; and the act of forcing it to one — the quench we
perform ten million times a day and call "ground truth" — destroys, in literal
bits, the structure that was the most valuable thing in the data. Keep the
temperature up. Keep the grid on the wall. **Keep the cloud.**

---

### Sources from the wild

- G. Parisi, *Infinite Number of Order Parameters for Spin-Glasses*, Phys. Rev.
  Lett., 1979; Nobel Prize in Physics, 2021 (for the theory of disordered and
  frustrated systems).
- D. Sherrington & S. Kirkpatrick, *Solvable Model of a Spin-Glass*, Phys. Rev.
  Lett., 1975 (the canonical frustrated-disorder model).
- M. Mézard, G. Parisi, M. A. Virasoro, *Spin Glass Theory and Beyond*, 1987
  (the ultrametric organisation of pure states).
- G. Toulouse, *Theory of the frustration effect in spin glasses*, 1977 (names
  frustration; the triangle).
- E. T. Jaynes, *Information Theory and Statistical Mechanics*, Phys. Rev., 1957
  (maximum entropy = the Gibbs distribution; why the soft label is a thermal
  state and the majority vote a T → 0 limit).
- F. Heider (1946); D. Cartwright & F. Harary, *Structural Balance*, 1956 (signed
  graphs, balance, and the frustration index that detects coherent blocs).
- I. Shumailov et al., *AI models collapse when trained on recursively generated
  data*, Nature, 2024 (model collapse — here, the second law applied to values).
