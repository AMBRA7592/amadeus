# The Theorem Under the Thesis

### Social choice theory already proved "ground truth has no ground" — and drew the exact line your triage draws by hand

---

> **"Majority vote is not a neutral way to combine human judgement" is not an
> opinion you have to defend. For three or more options it is a theorem (Arrow,
> 1951). For two options its precise converse is also a theorem (May, 1952).
> Together they draw, in axioms, the same line [`the-groundless-label.md`](the-groundless-label.md)
> draws in prose — between the cells where the vote is honest and the cells
> where it is a casting vote dressed as a measurement.**

The companion essay makes its case the hard way — by argument, by example, by a
runnable triage. It is right. What it does not say is that it never needed to
fight: the result it argues for was settled, with Nobel-grade finality, by the
mathematicians who spent the 20th century studying the *only* thing a labeling
pipeline ever does — turn many judgements into one. That field is **social
choice theory**, and three of its oldest results say, in order: there is no
neutral way to do this; here is the single exception; and here is exactly when
adding more judges stops helping. [`aggregation.py`](aggregation.py) runs all
three against `data/labels.json`. This is the map.

---

## 1. The argument already has a proof — and it is an impossibility theorem

Kenneth Arrow asked, in 1951, whether *any* rule could aggregate individual
rankings of three or more options into a group ranking while satisfying four
almost embarrassingly modest conditions: it works for all inputs (unrestricted
domain); if everyone prefers A to B the group does too (Pareto); the group's
choice between A and B depends only on how people rank A vs. B, not on some
irrelevant C (independence of irrelevant alternatives); and no single person
dictates the outcome (non-dictatorship).

**No such rule exists.** Not "none is convenient" — none *can* exist; the four
axioms are jointly contradictory for three or more alternatives. Its
choice-function cousin, the Gibbard–Satterthwaite theorem (1973–75), lands the
same blow from another side: every non-dictatorial rule that can return three or
more outcomes is *manipulable*. The lesson both teach is the one the essay
reaches for and names "contestable": **with three or more options, every
aggregation rule sacrifices one of the things you'd want a fair rule to have.
The only choice you are making is which one to break — and you are making it
whether or not you notice.**

That is the ribbon. The "object at the neck" question has five live answers
(`scarf, plastic, ribbon, choker, unknown`), so it lives squarely in Arrow's
world. Run §1 of the demonstrator and watch the consequence with nothing but the
real ballots from `img1`:

- **Plurality** ("majority vote") stamps `scarf` — at **37.5%**. The single word
  shipped as *ground truth* is the modal **minority** opinion; 62.5% of the room
  said something else.
- **Random dictatorship** — a rule with impeccable credentials (anonymous,
  Pareto-efficient, strategyproof) — returns `scarf` only **37.5%** of the time
  and one of four other words the rest.

Nobody changed their mind between those two lines. The "ground truth" moved
because the *rule* moved. In Arrow's world the label is never a property of the
data alone; it is always, partly, a property of the aggregator you didn't know
you were choosing.

---

## 2. The one place the vote is provably right — say it louder

Here is the half a good critique is tempted to skip, and the half that makes
this one unkillable. In 1952 Kenneth May proved that for **exactly two**
options, simple majority rule is not just *a* fair rule — it is the **unique**
rule satisfying three conditions everyone wants: anonymity (no voter is
special), neutrality (no option is special), and positive responsiveness (one
more vote for a winner can never make it lose). For a binary decision among
equals, majority vote is the *only* defensible answer. There is no better rule
to switch to, because there is no other rule that is fair at all.

So the `CONFIDENT` binary cells in the companion essay are not a grudging
concession to practicality. They are **theorem-backed**. "Is this AI-generated?"
on `img2` — eight votes, all `1` — is a question with two options and a fact of
the matter; May says collapse it and never look back. The essay should not
apologize for majority vote there. It should cite May and move on.

This is exactly the discipline the companion essay calls "what separates an
insight from a slogan": you concede precisely, and *only*, what the mathematics
forces you to concede. Give majority vote everything May proves it deserves, and
your fire is now aimed where no theorem can defend it.

---

## 3. The line you drew by hand is the border between two theorems

Now put §1 and §2 together and look back at the triage in `disagreement.py`. It
sorts cells into "collapse this one honestly" versus "preserve this one as a
distribution." That sort is not a heuristic you invented. **It is the frontier
between May's world and Arrow's world**, rediscovered operationally:

- **binary + a fact of the matter** → May's world → the vote is the unique fair
  answer → collapse it.
- **three or more live options, or a value-laden binary with no fact** →
  Arrow's world → no rule is neutral → keep the distribution, name the rule.

`aggregation.py` §0 prints the whole dataset under exactly this split: **12
cells in May's world, 6 in Arrow's.** You built, by intuition and a few
thresholds, the boundary that Arrow and May drew in 1951–52. Naming it does real
work: a boundary with a theorem on each side is *principled*, and survives the
reviewer who calls your thresholds arbitrary.

---

## 4. Where May goes silent, a casting vote speaks

May's guarantee has a hairline crack, and your data falls straight into it.
Positive responsiveness only bites when one side has *more* votes. At an exact
tie the theorem is **silent** — it does not name a winner, because by its own
symmetry there isn't one. Something else has to break the tie, and whatever does
is acting with no axiom behind it.

Both value forks in the set are 4–4 ties on the `explicit / safe` question
(`img2`, `img4`) — cohort A reading "editorial, safe," cohort B reading "flag
it." Watch §2 of the demonstrator resolve them. The tie-break in
`disagreement.py` is `sorted(...)[0]`; the label keys are `"0"=safe` and
`"1"=flag`; `"0"` sorts first. So:

- `img2 / explicit`: ships **safe**.
- `img4 / explicit`: ships **safe**.
- **Cohort A wins both forks — 2 for 2 — not on the merits, but because its
  label alphabetizes first.** Rename the keys so `flag` sorts first, change not
  one human judgement, re-run: both ship **flag**.

A pipeline that believes it "has no policy on the safe/flag boundary" has in
fact adopted the most arbitrary policy imaginable — *whatever sorts lowest* —
and applied it consistently against one cohort. This is the companion essay's
"unelected legislator" caught mid-vote. The legislator's name is `sorted()`.

---

## 5. When more annotators make it *worse*

The industry's reflex for a hard cell is "get more labels." The Condorcet Jury
Theorem (1785) says exactly when that reflex is sound — and the conditions are
brutal. If each annotator is independently right with probability p > ½ **on a
question that has a right answer**, majority vote converges to that answer as
you add voters. §3 of the demonstrator shows it climbing: at p = 0.6, majority
accuracy goes 0.60 → 0.65 → 0.73 → 0.86 → 0.97 as n goes 1 → 81. *This is the
case the words "ground truth" were minted for.* Where there is dirt to drive to,
the crowd finds it.

Break any one precondition and the theorem turns on you:

- **No right answer** (the ribbon, the value fork): the premise is void.
  Convergence "to the truth" is convergence to nothing.
- **Correlated voters** (a shared cohort norm — the San-Francisco-vs-Tokyo
  effect, made local in this dataset): annotators in the same normative frame
  err *together*, so the crowd carries far less independent information than its
  headcount suggests. With intraclass correlation ρ = 0.3, the effective crowd
  size **saturates at 1/ρ ≈ 3.3**: hire 81 annotators and you get the wisdom of
  about three (Ladha, 1992). §3 prints the flat line.
- **A biased shared norm** (p < ½): the jury theorem runs *in reverse*. Majority
  vote converges to the **wrong** answer with rising confidence — at p = 0.4,
  accuracy *falls* 0.40 → 0.35 → 0.27 → 0.14 → 0.03 as the crowd grows.

That last line is **manufactured consensus, quantified.** "Get more labels" on a
correlated, value-laden cell does not find a truer answer; it makes the dominant
norm look *more certain*. It is the same loop the companion essay's §6 calls
model collapse — here given its mechanism and its rate.

---

## 6. The sting that closes the loop: the model is a voting rule

The companion essay ends on the recursive sting — synthetic humans, labeled by
humans, training the next generator. Social choice theory sharpens it to a
point. **A reward model trained on aggregated human preferences *is* an
aggregation rule** — a social welfare function compiled into weights. So Arrow
and Gibbard–Satterthwaite do not stop at your labels. They bind **the model you
ship.** No model that aggregates three-or-more-way diverse human values can
satisfy all of Arrow's axioms, any more than your label pipeline can — because
*it is the same operation*, performed in float32.

The bridge from labels to the systems we ship is not new, and saying so plainly
is the point. A **2024 line of work already makes it explicit**: Conitzer,
Procaccia, and colleagues argue that social choice theory *should be* the formal
foundation for aligning AI to diverse human feedback, and Ge et al. carry the
social-choice axioms directly into RLHF reward learning. So the contribution
here is not the observation that alignment is aggregation — the literature got
there. It is **operationalization**: turning a known impossibility into a
runnable governance artifact — a triage that names each contested cell, prices
the bits a collapse destroys, and routes every value fork to a named owner
instead of an aggregation default. Seen this way, data labeling and model
alignment are not "the same problem"; they **share the same irreducible
primitive — the consequential aggregation of plural judgement under a
non-neutral rule** — and Arrow binds both. Every aligned model still embeds a
specific, non-neutral resolution of Arrow's impossibility, a choice of which
axiom to break; the "unelected legislator" at the annotation desk has a
counterpart in the trained model, an **Arrovian dictator installed by default**.
The machinery in this repo exists to elect it on purpose.

---

## 7. What this adds to "What to do on Monday"

The companion essay's five moves stand. The theorems add four that are sharper
because they are not advice — they are forced:

1. **Tag every cell with its regime.** `MAY` (binary, fact of the matter) or
   `ARROW` (≥3 options, or value-laden). Treat a single label as a measurement
   *only* in May's world. `aggregation.py` §0 is a 10-line starting point.
2. **Run a rule-sensitivity check before you ship a label.** Does the "winner"
   survive a change of aggregation rule, or of tie-break order? If `scarf`
   becomes `plastic` under random dictatorship, or `safe` becomes `flag` under a
   relabel, you are shipping a *casting vote*, not a fact. Report it as such.
3. **Never break a value-fork tie with a default.** Sort order, the pool-wide
   prior, `sorted()[0]` — each is an Arrovian dictator hiding in a utility
   function. This is *why* your `governance.jsonl` queue is mandatory rather than
   nice-to-have: at a true tie, May is silent, so a *named human* must speak, on
   the record, or an alphabet does.
4. **Report rule-dependence next to the groundlessness budget.** "k of n cells
   would change their ground-truth label under at least one equally-valid
   aggregation rule." A high, invisible number there means you are shipping
   casting votes labeled "ground truth."

---

## Coda

The companion essay proved its thesis the honest way, from the data up. But the
proof was already there, a half-century old, waiting under the argument with the
names of the axioms you'd have to break. "Ground truth has no ground" is the
prose translation of three theorems: **Arrow** (no neutral rule for ≥3 options),
**May** (one fair rule for 2, silent at a tie), **Condorcet** (more judges find
truth only where a truth exists and the judges are independent). The most honest
label, then, is not the distribution alone. It is **the distribution plus the
name of the rule used to collapse it** — because in Arrow's world the rule is
part of the answer, and a result that hides its rule is hiding a vote.

And one turn further, because it is the same lesson: this repository's owner
handed me a set of images and a deliberately groundless prompt — *find something
valuable, but not the obvious thing* — and dared me not to collapse it to its
plurality label ("mood board," "editorial"). The most faithful confirmation of
the whole argument is that the valuable thing was never on the surface where the
vote would land. It was one layer down, in the distribution. **Keep the cloud.**

---

### Sources from the wild

- K. J. Arrow, *Social Choice and Individual Values*, 1951 (the impossibility
  theorem).
- K. O. May, *A Set of Independent Necessary and Sufficient Conditions for
  Simple Majority Decision*, Econometrica, 1952 (majority rule is unique for two
  options).
- Marquis de Condorcet, *Essai sur l'application de l'analyse à la probabilité
  des décisions rendues à la pluralité des voix*, 1785 (the jury theorem).
- A. Gibbard, *Manipulation of Voting Schemes*, Econometrica, 1973; M.
  Satterthwaite, *Strategy-proofness and Arrow's Conditions*, J. Economic
  Theory, 1975 (every non-dictatorial choice rule over ≥3 options is
  manipulable).
- K. K. Ladha, *The Condorcet Jury Theorem, Free Speech, and Correlated Votes*,
  American Journal of Political Science, 1992 (correlation destroys the
  convergence).
- V. Conitzer, A. Procaccia, et al., *Social Choice Should Guide AI Alignment in
  Dealing with Diverse Human Feedback*, ICML 2024 (the aggregation a reward model
  performs is a social-welfare function, and inherits the impossibilities).
- L. Ge, D. Halpern, E. Micha, A. D. Procaccia, et al., *Axioms for AI Alignment
  from Human Feedback*, NeurIPS 2024 (social-choice axioms carried directly into
  RLHF reward learning).
