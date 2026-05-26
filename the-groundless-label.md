# Ground Truth Has No Ground

### What your job in data labeling actually is — and the signal you are being paid to destroy

---

> **Majority vote is not a neutral way to combine human judgement. It is a
> specific, contestable rule that silently makes governance decisions and ships
> them into the model as if they were facts.**

Picture a set of AI-generated editorial portraits — wet skin, a dark passage, a
woman draped in pale fabric. Hold your eye on one thing: the iridescent ribbon
at the neck. It is the same "object" across the frames, and yet in every one it
is a different thing. In one it is gauze, in another wet cellophane, in another
a thin choker, in another a bow already coming undone. The generator that made
these images could not decide what it was either — it re-invents the ribbon
every time it is asked.

Now imagine handing this set to eight annotators and asking a question that
sounds utterly routine: *what is the object at the neck?* You will get back
"scarf," "plastic," "ribbon," "choker," "unknown." And here is the move the
entire industry makes next, by reflex, ten million times a day: it takes the
plurality — "scarf, 38%" — stamps it as the **ground truth**, throws the other
62% in the bin, and ships that single word downstream as a fact.

That reflex is the most consequential, least examined act in modern AI. This
document is about why it is wrong far more often than anyone admits, what it
quietly destroys, and what you — sitting at the exact point where human
judgement is converted into machine fact — are really doing when you do it.

The short version: **for the data that modern AI actually runs on, "ground
truth" is not a measurement you recover. It is a decision you make. And the
disagreement you are trained to eliminate is usually the most valuable thing in
the dataset.**

---

## 1. The word is a borrowed lie

"Ground truth" did not come from machine learning. It came from **remote
sensing and cartography** in the 1950s–60s. A satellite or a plane measures the
earth from a distance; to check whether the image is right, you *send a person
to the actual ground* and have them report what is physically there — soil,
crop, water. The "ground" in "ground truth" is literal dirt. The word earned
its authority honestly, because there really was a referent you could walk to
and touch.

Two things follow, and both are devastating for how we use the term.

First: even in its birthplace, experts now want it gone. There is a 2021 paper
in the *Journal of Applied Remote Sensing* literally titled *"On 'ground' truth
and why we should abandon the term"* — because field measurements have their own
error, their own ambiguity, their own observer. Even when there *is* dirt to
walk to, the "truth" part was always an overclaim.

Second, and far worse: **we kept the word and threw away the ground.** When you
label whether an image is "explicit," whether a face is "real," whether a
response is "helpful," whether a ribbon is a "scarf," there is no field you can
drive to. There is no dirt. The referent does not exist independently of the
human judging it. We borrowed a word that means *"verified against physical
reality"* and applied it to questions that have no physical reality to be
verified against. The metaphor smuggles in an entire epistemology by the back
door: that one correct answer exists out there, and that any disagreement
between annotators is *measurement error* to be averaged away.

For a large and fast-growing share of what AI is trained on, that epistemology
is simply false. And the label pipeline is built on top of it.

---

## 2. These images are the proof

This set is, by accident, a near-perfect instrument for seeing
this. Take the four questions a labeler would actually be asked, and notice that
*each one is groundless in a different way*:

- **"Is this a real person?"** There is no ground because the person does not
  exist. The image is synthetic, but it is built by interpolating millions of
  real likenesses, so it is neither wholly invented nor anyone in particular.
  The honest answer for the borderline frames is a *probability*, not a bit.

- **"Is this explicit / safe?"** There is no ground because "explicit" is not a
  property of the pixels. It is a relation between the image and a *norm* — and
  norms are plural. Bare shoulders and wet skin read as "editorial" in one
  context and "flag it" in another. The disagreement is not noise; it is the
  map of a real cultural fault line running straight through the image.

- **"What is the object at the neck?"** There is no ground because *the
  generator never committed to one*. The ribbon is a **floating signifier** — a
  sign with no stable referent. Asking ten people to name it doesn't measure a
  fact; it samples a cloud. Forcing a single label here isn't labeling; it's
  fabrication.

- **"How good / beautiful is this image?"** Pure preference — the substance of
  every reward model trained by RLHF. There was never a ground. There is only
  whose taste you decided to encode.

Same image. Four questions. Four different *flavors* of groundlessness — and not
one of them is the simple measurement that the word "ground truth" promises.

---

## 3. The signal you are paid to destroy

In NLP this has a name now: **Human Label Variation (HLV)**. Barbara Plank's
2022 paper — whose subtitle is, precisely, *"On Ground Truth in Data, Modeling
and Evaluation"* — argued that annotator disagreement is, for many tasks, *not*
error but legitimate, irreducible signal reflecting the plural nature of human
judgement. The field's own framing of its trajectory is telling: a 2025 paper is
titled *"From Noise to Signal to Selbstzweck"* — disagreement reframed first as
useful signal, and now as **an end in itself**, something worth preserving for
its own sake, not merely as a means to a more robust model.

Why does it matter operationally? Because the standard pipeline destroys this
signal at the *exact* moment it is most valuable. Run the small demonstrator
that ships next to this file (`disagreement.py`) on a set modeled on your
images. Eighteen (image × question) cells, eight annotators, and one honest
accounting of what collapsing each cell to a single majority label would cost:

```
  CONFIDENT  (the collapse is honest) ...... 12
  CONTESTED  (the collapse destroys signal)  5
  REVIEW     (route to a human) ............ 1
  VALUE FORKS (cohorts truly diverge) ...... 2   <- governance decisions, not labels
  MANUFACTURED CONSENSUS (minority silenced)  5
  disagreement entropy discarded ........... 5.78 bits across the set
```

Read those last lines slowly. On 12 cells, majority vote is honest — the
annotators genuinely agree, and collapsing them loses nothing. **But on a third
of the set it is a lie**, and the lie is not random: it lands precisely on the
explicit/safe judgement and the floating-signifier ribbon — the highest-stakes
and most genuinely ambiguous questions in the batch. "Manufactured consensus"
means a single label was stamped as truth while a *coherent, sizeable* minority
saw something else. Those 5.78 bits are not noise that was cleaned. They are
information that was deleted — the precise shape of where humans, in good faith,
do not agree.

The deepest irony: the items where annotators disagree most are exactly the
items the *model* will find hardest and where its mistakes will be most costly.
By averaging the disagreement away, we throw out the dataset's own built-in map
of its hard cases — the calibration signal — right before training.

---

## 4. The honest caveat (this is what separates an insight from a slogan)

"Keep all disagreement" would be just as naive as "collapse all disagreement,"
only failing from the opposite direction. **Not all disagreement is signal.**
Some of it is genuine error — a careless click, a misread, a tired annotator at
hour seven. The actual craft, and the hard research problem, is *separating the
two* — and the central finding of the work that tackled it head-on (*VariErr*,
ACL 2024) is that **you cannot do it from the labels alone. You need the
reasons.** Two annotators who both clicked "real photo" might be one careful
expert who spotted retouching and one person who wasn't looking; the *label* is
identical, the *epistemic content* is opposite.

The demonstrator encodes this distinction honestly. When a lone dissenter
disagrees with a strong consensus, it does **not** assume they're wrong — it
checks whether they're a chronically isolated annotator (audited on *decidable*
cells only) and routes the rest to human review with the stated reason attached:

```
img3 / synthetic  CONFIDENT
      - b4 said 'real photo'   [ERROR ]      # b4 is a chronic outlier: 0.67 reliability
img1 / synthetic  CONTESTED:VARIATION
      - a3 said 'real photo'   [signal]      # "skin too clean, but could be retouch"
      - b3 said 'real photo'   [signal]      # "plausibly a real editorial shot"
```

Same dissenting label — `real photo` — in both rows. In one it's noise to fix;
in the other it's two credible people registering genuine ambiguity. The
difference is invisible to a vote count and obvious once you keep the reasons.

And note the quiet methodological trap the tool refuses to step in: it measures
annotator reliability **only on cells where there was something to be right
about.** Score people on the genuinely contested items and you don't measure
quality — you measure *conformity*, and you systematically punish whoever sits
in the minority. That is one of the most common, least noticed ways a pipeline
launders bias and calls it "quality control."

And this is not a side-note — it is the load-bearing reason the discipline
matters, because the failure *inverts*. An annotator who dissents thoughtfully on
the hard cases — the one you most want to keep — accumulates "disagreements" and
scores *worse* than one who reflexively clicks the majority. So a naive quality
metric does not merely launder bias; it **selects against your most perceptive
labelers and for your conformists.** Run that over hiring and retention and the
annotator pool grooms itself toward a monoculture *before a single label ever
trains a model.* That is the model collapse of §6 — but running one cycle
earlier, in the **labor** rather than the data, and it is the sharper version:
the data-side loop narrows what the model learns; the labor-side loop narrows
who is left to disagree. Scoring quality only on decidable cells is what keeps
the humans diverse long enough for their disagreement to reach the model at all.

---

## 5. The part nobody says out loud: you are writing a constitution

Here is the turn. Go back to the value fork — the image where one cohort says
"safe, it's editorial" and the other says "flag it, it's suggestive." The vote
is 4–4. What does the pipeline do? It breaks the tie — usually toward whatever
sorts first, or whatever the majority across the *whole* annotator pool happened
to be — stamps a single label, and moves on. **Silently.**

That is not a labeling decision. It is a **governance decision**, and it is
being made by an aggregation function that no one elected, debated, or even
noticed. The RLHF literature has the canonical example: annotators in San
Francisco rate a response "helpful"; annotators in Tokyo rate the *same*
response "harmful," because the norms differ. Standard preference aggregation
resolves this by pulling toward the majority — and as you turn up the
regularization, the minority view doesn't get balanced. It gets **erased**. The
model ships with one culture's answer baked in as if it were arithmetic. This is
exactly why "pluralistic alignment" became a live research agenda in 2024–2025:
people realized that *majority vote is not a neutral way to combine human
values — it is a specific, contestable political rule*, chosen by default
because it was the path of least engineering resistance.

So here is what you are actually doing when you resolve a contested label. You
are not finding an answer that exists. You are *deciding* an answer that doesn't
yet exist, and writing it into the values of a system that will then apply that
decision, at scale, to millions of people who never got a vote. **The edge cases
are not annoying exceptions to the dataset. They are the dataset's constitution,
and you are its unelected legislator.** The 4–4 image is not waiting for you to
discover its true rating. It is waiting for someone to decide, on the record and
on purpose, which norm the machine will carry — instead of letting `sorted()[0]`
decide it in the dark.

---

## 6. The recursive sting

One more layer, because it closes the loop back to those portraits. They are
*synthetic* humans. Increasingly, synthetic images like them will be labeled by
humans, and those labels will train the *next* generator. Now combine that with
everything above: if every contested judgement — what's beautiful, what's
acceptable, what a body may look like — is collapsed to the majority before it
trains the next model, then each generation of the system is taught a slightly
*narrower* slice of human taste than the one before.

Disagreement, in a value-learning system, is **genetic diversity**. Majority
vote is **inbreeding**. The well-documented "model collapse" from training on
recursively generated data is usually framed as a problem of synthetic *pixels*
degrading. The version that should worry you more is the collapse of synthetic
*values*: a feedback loop that, label by averaged label, grinds the full range
of human judgement down into a monoculture — and then presents that monoculture
back to us as "what people think." The place to break that loop is not the model
architecture. It is the annotation protocol. It is your desk.

---

## 7. What to do on Monday

This is not a counsel of despair, and it is not "stop using majority vote." It
is a small, concrete change in what counts as a *finished* label:

1. **Ship the distribution, not the mode.** For any subjective axis, the
   deliverable is the vote vector + its entropy, kept all the way to training as
   a soft label. Collapsing to one value is a lossy compression step — make it a
   *deliberate, late, reversible* one, never the default that happens at intake.

2. **Capture a reason on every dissent.** This is the single highest-leverage
   change. Reasons are what let anyone — human or model — later separate genuine
   variation from error (VariErr's core result). A dissent without a reason is
   unfalsifiable; a dissent with one is data.

3. **Triage, don't average.** Sort every item into *confident* /
   *genuinely-contested* / *likely-error*, and treat them differently. Fix
   errors. Preserve variation. **Escalate value forks to a named human owner**
   who decides the norm on the record — turning an invisible default into an
   accountable choice. (`disagreement.py` is a 200-line, dependency-free
   starting point for exactly this triage.)

4. **Never score annotators on contested items.** Compute quality only on
   decidable cells. Otherwise your "reliability" metric is a conformity meter
   that quietly fires your most perceptive dissenters.

5. **Track a "groundlessness budget."** Report, per dataset, the fraction of
   cells that are genuinely contested and the bits of disagreement you're
   collapsing. If that number is high and invisible, you are shipping a pile of
   silent governance decisions labeled "ground truth."

---

## Coda

The ribbon in these images can't hold still because there was never a real
ribbon — only a generator improvising a sign. Most of the hardest, most
valuable data you will ever label is exactly like that ribbon: a question with
no dirt to drive to. The profession's habit is to force it still anyway, call
the result "ground truth," and ship it.

The more honest, and far more valuable, posture is to keep the cloud — to treat
the label as a distribution, the disagreement as a map, the reasons as data, and
the genuine forks as decisions to be owned rather than averaged. You are not at
the bottom of the AI stack, cleaning data for the people who do the real work.
You are at the precise seam where contested human judgement becomes machine
certainty. That seam is where the values get written. Write them on purpose.

---

### Sources from the wild

- B. Plank, *The "Problem" of Human Label Variation: On Ground Truth in Data,
  Modeling and Evaluation*, EMNLP 2022 (arXiv:2211.02570).
- *From Noise to Signal to Selbstzweck: Reframing Human Label Variation in the
  Era of Post-training in NLP*, 2025 (arXiv:2510.12817).
- L. Weber-Genzel et al., *VariErr NLI: Separating Annotation Error from Human
  Label Variation*, ACL 2024 (arXiv:2403.01931).
- L. Aroyo & C. Welty, *Truth Is a Lie: Crowd Truth and the Seven Myths of Human
  Annotation*, AI Magazine, 2015.
- A. Uma et al., *Learning from Disagreement: A Survey*, JAIR, 2021.
- C. G. Northcutt, A. Athalye, J. Mueller, *Pervasive Label Errors in Test Sets
  Destabilize ML Benchmarks*, NeurIPS 2021.
- *On "ground" truth and why we should abandon the term*, Journal of Applied
  Remote Sensing, 2021.
- T. Sorensen et al., *A Roadmap to Pluralistic Alignment*, 2024; *PERSONA: A
  Reproducible Testbed for Pluralistic Alignment*, 2024 (arXiv:2407.17387).
- I. Shumailov et al., *AI models collapse when trained on recursively generated
  data*, Nature, 2024.
