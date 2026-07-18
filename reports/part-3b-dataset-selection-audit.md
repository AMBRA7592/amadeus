# Part 3b dataset-selection audit

**Status:** HALT FOR OWNER REVIEW — dataset selected and analysis pre-registered;
no adapter or outcome run is authorized by this report.

**Repository base:** `3dd8726514ba5c01145b3cd83612e937e4657f34`
(`main`, after Part 3a)  
**Audit date:** 2026-07-18  
**Evidence tier:** selection logic and the frozen protocol are reviewable in the
repository; any later real-data result will be Tier 2, reproducible by source
revision and checksum but not run in CI.

## Verdict

None of the eight named candidates clears all four hard gates. The recurring
blockers are not data quality: most have no explicit dataset license permitting
the proposed local analysis and aggregate publication, and several lack
authentic, replicated cohorts.

The audit found one additional candidate that does clear all four gates:
**UC Berkeley's Measuring Hate Speech (MHS) dataset**. It is the single
recommendation for a bounded first study of political-ideology cohorts. The
primary analysis would cover the 77 comments that, under the frozen structural
filter below, have at least two eligible conservative and two eligible liberal
annotators. That is a useful pilot, not a measurement of universal or
"production" prevalence.

No Part-3b outcome metric was computed. In particular, this audit did not
compute fork rates, manufactured-consensus rates, geometry gaps, reliability
spreads, or cohort-conditioned label rates. While inspecting the MHS schema, a
category-enumeration query incidentally returned global label counts. Those
counts are deliberately omitted and were not used to choose the dataset,
contrast, filter, or metrics.

## Method: four hard gates

A candidate is rejected if any gate fails or remains unresolved.

1. **Authentic cohorts.** Cohort membership must be supplied before this study
   by the dataset authors or collection design. Post-hoc clustering on labels,
   explanations, or embeddings is disqualifying. A single annotator with a
   demographic profile is not a replicated cohort.
2. **Repeated identities.** Stable annotator identifiers must support
   leave-one-out reliability. The declared floor is **20 judgments per
   included annotator**; the floor is not lowered after seeing outcomes.
3. **Compatible license.** An explicit dataset license or terms must permit
   local analysis and publication of aggregate results and a non-row-level
   reproducibility manifest. A paper saying data are "available," a public
   download link, or a license on the paper does not substitute for a dataset
   license. A failure here means *clearance was not demonstrated*, not that use
   is necessarily forbidden.
4. **Pre-registered comparison.** The cohort contrast and metrics must be
   declarable from collection metadata before examining cohort-conditioned
   outcomes. The precise protocol for the selected dataset is frozen below.

The evidence review used papers, official dataset pages, and author repositories
at the pinned revisions listed in the source ledger. Repository-level license
checks were made at those revisions rather than inferred from GitHub visibility.

## Gate results

| Candidate | G1 authentic cohorts | G2 repeated IDs, floor 20 | G3 explicit compatible license | G4 prospective contrast | Decision |
|---|---|---|---|---|---|
| POPQUORN | PASS — author-recorded demographics | PASS — repeated workers, 50 items each | FAIL — no dataset license found at audited release | PASS — an author-defined demographic contrast can be frozen prospectively | REJECT |
| VariErr NLI | FAIL — four annotators, no demographic or designed cohorts | PASS — the same four annotate 500 items | FAIL — no dataset license found | FAIL — no authentic cohort contrast | REJECT |
| HS-Brexit | PASS — designed target/control groups | PASS — six annotators label all 1,120 items | FAIL — neither the paper nor audited LeWiDi release supplies a dataset license | PASS — target versus control is pre-existing | REJECT |
| MD-Agreement | FAIL — worker IDs, but no authentic annotator cohorts | UNRESOLVED — IDs repeat, but the audited sources do not establish a qualifying floor-20 subset | FAIL — audited release has no dataset license | FAIL — item domains are not annotator cohorts | REJECT |
| ConvAbuse | FAIL — expert panel, but no pre-existing subcohorts | PASS — stable expert identifiers with repeated judgments | PASS — dataset repository carries CC BY 4.0 | FAIL — splitting experts after collection would be post hoc | REJECT |
| ArMIS | FAIL — three full-corpus profiles are three individuals, not replicated cohorts | PASS — each of the three labels 964 items; the 32-person extension is below the floor | FAIL — availability language is not a dataset license | FAIL — a singleton comparison would confound person and cohort | REJECT |
| Kumar et al. 2021 | PASS — author-recorded demographics and attitudes | PASS — each participant rates 20 items | FAIL — official data page provides access but no dataset-use license | PASS — an author-defined demographic contrast can be frozen prospectively | REJECT |
| Sap et al. 2022 | PASS — designed race/ideology strata | FAIL — the documented designs do not establish a floor-20 qualifying subset | FAIL — data are contact-gated and no dataset license is stated | PASS — designed strata support a prospective contrast | REJECT |
| **Measuring Hate Speech** | **PASS — author-recorded political ideology** | **PASS — 2,316 annotators meet the frozen floor** | **PASS — CC BY 4.0** | **PASS — exact conservative/liberal contrast frozen below** | **SELECT** |

## Candidate evidence

### POPQUORN

The [POPQUORN paper](https://aclanthology.org/2023.law-1.25/) reports
authentic demographic attributes and repeated workers: the offensiveness task
has 262 participants, 13,036 annotations, and 50 comments presented to each
participant. This is a strong cohort-and-power fit. However, the
[audited author repository](https://github.com/Jiaxin-Pei/Potato-Prolific-Dataset/tree/dbb118c29b3d9bcce5aa172d8249ded9ece4df84)
contains no dataset license. Release and availability statements do not clear
Gate 3.

### VariErr NLI

The [VariErr NLI paper](https://aclanthology.org/2024.acl-long.123/) and
[author repository](https://github.com/mainlp/VariErr-NLI/tree/b2cbdd3bc3ca2a618fc16ac078f471623152c923)
document four stable annotators who label and explain all 500 items. The reasons
make it an attractive companion for variation-versus-error research, but the
four people are not author-defined cohorts. The audited release also has no
dataset license. It cannot support the proposed prevalence study without
inventing cohorts.

### HS-Brexit

The [HS-Brexit paper](https://arxiv.org/abs/2106.15896) has the cleanest
designed two-group structure among the named candidates: three target-group and
three control-group annotators label the same 1,120 tweets. The official
[LeWiDi task page](https://codalab.lisn.upsaclay.fr/competitions/6146) and
[audited LeWiDi repository](https://github.com/Le-Wi-Di/le-wi-di.github.io/tree/45d7b06e4c36b59472d6bdf9281f7f1e395eb0e0)
make the files accessible, but neither supplies an explicit dataset-use
license. Public access alone does not clear Gate 3.

### MD-Agreement

The [MD-Agreement paper](https://aclanthology.org/2021.emnlp-main.822/)
describes 10,753 tweets with five crowd judgments each and hundreds of workers.
The release preserves worker identifiers, but provides neither authentic
annotator cohorts nor evidence in the audited sources that identifies a
specific floor-20 subset. Item domains are not a substitute for annotator
cohorts. The LeWiDi release is also unlicensed.

### ConvAbuse

The [ConvAbuse paper](https://aclanthology.org/2021.emnlp-main.587/) uses a
small panel of expert gender-studies annotators with stable identities. Its
[official repository](https://github.com/amandacurry/convabuse/tree/c0a9469f48956e868276c605d499010ea3c7c0d0)
has an explicit [CC BY 4.0 license](https://github.com/amandacurry/convabuse/blob/c0a9469f48956e868276c605d499010ea3c7c0d0/LICENSE),
so licensing is not the blocker. The experts are not divided into authentic,
replicated subcohorts. Constructing groups from their observed labels would
violate the anti-circularity gate.

### ArMIS

The [ArMIS paper](https://aclanthology.org/2022.lrec-1.244/) records profiles
for three annotators who each label the full 964-item corpus: a liberal woman,
a moderate woman, and a conservative man. Those are three confounded
individuals, not replicated cohorts; a group contrast would be indistinguishable
from an individual-annotator contrast. A further 32 annotators label only 11
items, below the frozen reliability floor. The paper's availability language
does not provide a dataset license.

### Kumar et al. 2021

[Kumar et al.'s study](https://www.usenix.org/system/files/soups2021-kumar.pdf)
collects 20 ratings from each of 17,280 participants and records detailed
demographics and beliefs. It is methodologically promising and exactly meets
the repeated-judgment floor. The
[official data page](https://data.esrg.stanford.edu/study/toxicity-perspectives)
provides a contact-mediated encrypted download but states no dataset license or
terms that clear the proposed use. The report therefore does not infer
permission from accessibility.

### Sap et al. 2022

The [Sap et al. paper](https://aclanthology.org/2022.naacl-main.431/) uses
authentic race and ideology strata. Its breadth-of-workers study gives 641
participants 15 posts each; its breadth-of-posts study has 173 participants and
3,171 ratings, averaging 18.3 per participant with varying participation. The
paper does not establish a qualifying floor-20 subset, and tells readers to
contact the authors for anonymized data without stating a dataset license. It
therefore fails Gates 2 and 3 even though its collection design avoids
post-hoc cohorts.

### UC Berkeley Measuring Hate Speech (selected)

The [MHS paper](https://aclanthology.org/2022.nlperspectives-1.11/),
[project site](https://hatespeech.berkeley.edu/), and
[official dataset card](https://huggingface.co/datasets/ucberkeley-dlab/measuring-hate-speech)
document stable annotator identifiers, author-recorded demographic and
political attributes, repeated ordinal hate-speech judgments, and a
**CC BY 4.0** dataset license. The
[license terms](https://creativecommons.org/licenses/by/4.0/) permit sharing
and adaptation with attribution, satisfying the local-analysis and aggregate
reporting use contemplated here.

Structural checks were performed against official revision
[`5468f6e`](https://huggingface.co/datasets/ucberkeley-dlab/measuring-hate-speech/tree/5468f6e):

- source file: `measuring-hate-speech.parquet`
- SHA-256: `6819525ce61bc24344df9fc3f7bf48270b31038273cc27c67fc225b51433b0e1`
- source size: 14,123,673 bytes
- 135,556 annotation rows, 39,565 comments, 7,912 annotators
- 2,316 annotators have at least 20 judgments; their observed judgment counts
  range from 20 to 26 (median 21)
- under the ideology assignment frozen below, the eligible population contains
  662 conservative, 1,215 liberal, and 439 excluded neutral/no-opinion/null
  annotators
- 77 comments have at least two eligible conservative and two eligible liberal
  judgments

These are source-structure and eligibility counts, not outcome measurements.
No licensed rows or annotator/comment identifiers are committed to this
repository.

## Scoring the gate-passer

Only hard-gate passers are scored. Because MHS is the only passer, the scoring
does not manufacture a ranking among rejected datasets.

| Criterion | Range | MHS | Reason |
|---|---:|---:|---|
| Reasons/rationales | 0–4 | 2 | Ten ordinal dimensions provide richer context, but there are no free-text reasons |
| Statistical power | 0–3 | 2 | Large corpus and repeated raters, but only 77 items clear the primary two-sided cohort filter |
| Domain fit | 0–3 | 3 | Subjective hate-speech judgments directly exercise contested-label and manufactured-consensus instruments |
| Cohort granularity | 0–3 | 2 | Authentic, sizeable ideology cohorts; within-item cohort coverage is sparse |
| Operational tractability | 0–2 | 2 | Explicit license, fixed downloadable artifact, row-level stable IDs and categorical fields |
| **Total** | **0–15** | **11** | **Best and only hard-gate passer** |

The ten ordinal dimensions are not annotator reasons. Consequently,
variation-versus-error attribution is outside the primary claim set.

## Frozen prospective protocol

This protocol is fixed before any cohort-conditioned outcome is calculated.
Changing it requires a new dated pre-registration and an explanation made
before rerunning the study.

### Source and integrity

- Dataset: UC Berkeley Measuring Hate Speech, official Hugging Face revision
  `5468f6e`.
- Input artifact SHA-256:
  `6819525ce61bc24344df9fc3f7bf48270b31038273cc27c67fc225b51433b0e1`.
- No source rows are committed. A later adapter/run may commit code, aggregate
  results, and a manifest of hashes and counts only.
- If the source revision or checksum changes, freeze the new revision and hash,
  repeat the structural gate, and obtain owner approval before outcomes.

### Eligibility and cohorts

1. Include only annotators with at least **20 total non-null `hatespeech`
   judgments** in the fixed source artifact.
2. Assign **Conservative** only when the author-supplied political-ideology
   value is exactly `extremely_conservative`, `conservative`, or
   `slightly_conservative`.
3. Assign **Liberal** only when it is exactly `extremely_liberal`, `liberal`,
   or `slightly_liberal`.
4. Exclude neutral, no-opinion, and null ideology values. Do not infer or impute
   cohort membership.
5. The primary item set contains comments with at least two eligible
   Conservative and at least two eligible Liberal judgments. If a fresh
   integrity-equivalent structural pass yields fewer than **50** primary items,
   halt and return to the owner rather than weakening the filter.
6. Preserve raw ordinal `hatespeech` values `{0, 1, 2}` as categorical strings.
   Do not binarize, substitute an IRT score, or filter items using labels.

### Primary metrics

1. **Value-fork rate.** Use the current `disagreement.py` rule: each cohort
   must have a unique plurality and the two cohort pluralities must differ.
   Denominator: all primary items. A tied cohort has no cohort opinion and does
   not create a fork.
2. **Manufactured-consensus rate.** Use the current
   `manufactured_consensus` field produced by `disagreement.py` over all primary
   items, without changing its thresholds.
3. **Geometry gap.** For each primary item, form the two cohort label
   distributions and compute total variation between their arithmetic and
   normalized geometric centres using `geometry.py`. Report the share with
   disjoint support/undefined geometric centre separately. For defined values,
   report median and interquartile range; do not replace undefined cases with a
   maximum distance.
4. **Reliability spread.** Use the current CONFIDENT-only, leave-one-out
   reliability definition over the full converted corpus for eligible
   annotators. Report only annotators with at least 20 cells actually scored as
   CONFIDENT, including cohort coverage, cohort medians and interquartile
   ranges, and the difference in cohort medians. If either cohort has fewer
   than 30 qualifying annotators, label this comparison underpowered and
   non-applicable; do not lower the floor.

### Uncertainty and multiplicity

- Report Wilson 95% intervals for fork and manufactured-consensus rates.
- Use no null-hypothesis p-values in the initial study.
- If an interval is reported for a median gap or cohort median difference, use
  an item-level bootstrap with 10,000 resamples and fixed seed `20260718`.
- Do not add gender, race, age, or intersections, and do not analyze the other
  ordinal dimensions in the initial run. Any secondary contrast requires its
  own prospective protocol. This excludes silent subgroup search and
  result-dependent cohort selection.

## Permitted claims and non-claims

If the frozen study is approved and successfully run, it may report only:

- dataset-specific, topology-qualified descriptive rates for the pinned MHS
  revision and the exact Conservative/Liberal contrast above;
- reproducible aggregate results tied to the source checksum, tool commit,
  protocol, and run manifest; and
- operational observations about whether the repository's instruments execute
  on this bounded empirical case.

It must not claim:

- universal, population, or "production" prevalence of value forks or
  manufactured consensus;
- a causal effect of political ideology;
- representation of every political group, platform, population, or time;
- that any label is the correct ground truth;
- validation of the repository's mathematical results by one dataset;
- variation-versus-error attribution without annotator reasons; or
- generalization beyond the pinned corpus and topology-qualified subset.

The README's current statement that the repository ships the instruments rather
than the empirical measurement remains correct and should not change now. No
measurement has been run. If the owner later approves and publishes the study,
retain that hedge and add an adjacent link to a separately labelled Tier-2
appendix: one bounded dataset-specific measurement, not general production
prevalence.

## Decision requested; work stops here

Owner review is required on exactly three points:

1. approve or reject MHS as the Part-3b dataset;
2. approve or revise the frozen Conservative/Liberal contrast and primary
   metrics *before* any outcome run; and
3. accept the Tier-2 evidence boundary and the non-claims above.

Until that approval, do not build an MHS adapter, compute outcome metrics,
change the README, or publish prevalence numbers. This report intentionally
halts at dataset selection and pre-registration.

## Source snapshot

| Source | Audited locator |
|---|---|
| POPQUORN | [paper](https://aclanthology.org/2023.law-1.25/); [repository commit `dbb118c`](https://github.com/Jiaxin-Pei/Potato-Prolific-Dataset/tree/dbb118c29b3d9bcce5aa172d8249ded9ece4df84) |
| VariErr NLI | [paper](https://aclanthology.org/2024.acl-long.123/); [repository commit `b2cbdd3`](https://github.com/mainlp/VariErr-NLI/tree/b2cbdd3bc3ca2a618fc16ac078f471623152c923) |
| HS-Brexit / LeWiDi | [paper](https://arxiv.org/abs/2106.15896); [task](https://codalab.lisn.upsaclay.fr/competitions/6146); [repository commit `45d7b06`](https://github.com/Le-Wi-Di/le-wi-di.github.io/tree/45d7b06e4c36b59472d6bdf9281f7f1e395eb0e0) |
| MD-Agreement | [paper](https://aclanthology.org/2021.emnlp-main.822/) |
| ConvAbuse | [paper](https://aclanthology.org/2021.emnlp-main.587/); [repository commit `c0a9469`](https://github.com/amandacurry/convabuse/tree/c0a9469f48956e868276c605d499010ea3c7c0d0); [license](https://github.com/amandacurry/convabuse/blob/c0a9469f48956e868276c605d499010ea3c7c0d0/LICENSE) |
| ArMIS | [paper](https://aclanthology.org/2022.lrec-1.244/) |
| Kumar et al. | [paper](https://www.usenix.org/system/files/soups2021-kumar.pdf); [official data page](https://data.esrg.stanford.edu/study/toxicity-perspectives) |
| Sap et al. | [paper](https://aclanthology.org/2022.naacl-main.431/) |
| Measuring Hate Speech | [paper](https://aclanthology.org/2022.nlperspectives-1.11/); [project](https://hatespeech.berkeley.edu/); [dataset card](https://huggingface.co/datasets/ucberkeley-dlab/measuring-hate-speech); [revision `5468f6e`](https://huggingface.co/datasets/ucberkeley-dlab/measuring-hate-speech/tree/5468f6e); [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) |
