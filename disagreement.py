#!/usr/bin/env python3
"""
disagreement.py -- treat the label as a distribution, not a fact.

Standard pipelines collapse N annotators into one "ground truth" via majority
vote. For contested / aesthetic / safety / synthetic-human data that step
destroys the most valuable signal in the set: the SHAPE of the disagreement.

This tool does the opposite. In three passes it:
  1. keeps the full label distribution (a "soft label") and its entropy;
  2. tells genuine human label VARIATION apart from likely annotation ERROR
     (after VariErr, ACL 2024) -- because not all disagreement is signal, and
     pretending it all is repeats the original sin from the other side;
  3. flags VALUE FORKS (cohorts that coherently diverge) and MANUFACTURED
     CONSENSUS (a majority vote that would silence a real minority -- the
     majority-bias baked into RLHF preference aggregation); then
  4. prices the damage: how many bits and how many decisions the collapse
     to one column would throw away.

A deliberate refusal: annotator reliability is measured only on CONFIDENT
cells. These have no value fork, no "no ground" verdict, no structured
minority, and at least the near-consensus vote share. Scoring people on
contested or review items would turn reliability into conformity.

No third-party dependencies.  Run:  python3 disagreement.py
"""

import argparse
import json
import math
import os
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data", "labels.json")
PIPELINE_EPILOG = (
    "Run disagreement.py, soft_labels.py, and resolution.py in that order "
    "with the same --data and --out values. Later stages read artifacts from --out."
)

# --- thresholds (transparent on purpose; tune to your risk appetite) -------
NEAR_CONSENSUS = 0.875   # >= this share agree -> the collapse to one label is honest
STRUCTURED_MIN = 0.25    # a coherent minority this large is a stakeholder, not noise
UNRELIABLE = 0.70        # below this (on CONFIDENT cells only) -> audit the annotator


def _parse_args(argv):
    parser = argparse.ArgumentParser(
        description=__doc__.strip().splitlines()[0],
        epilog=PIPELINE_EPILOG,
    )
    parser.add_argument(
        "--data",
        default=DATA,
        help="input labels.json (default: the bundled demo dataset)",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="directory for generated artifacts (default: current directory)",
    )
    return parser.parse_args(argv)


def _invalid_labels(message):
    raise SystemExit("labels.json: " + message)


def validate_dataset(ds):
    """Apply the cross-field checks JSON Schema cannot express cheaply."""
    if not isinstance(ds, dict):
        _invalid_labels("root must be an object")
    required = ("questions", "annotators", "cohorts", "items")
    missing = [key for key in required if key not in ds]
    if missing:
        _invalid_labels("missing required field(s): " + ", ".join(missing))

    questions = ds["questions"]
    if not isinstance(questions, dict) or not questions:
        _invalid_labels("questions must be a non-empty object")
    for question, spec in questions.items():
        if not isinstance(question, str) or not question:
            _invalid_labels("question names must be non-empty strings")
        if not isinstance(spec, dict):
            _invalid_labels("question {!r} must be an object".format(question))
        if spec.get("type") not in ("binary", "categorical"):
            _invalid_labels(
                "question {!r} type must be binary or categorical".format(question)
            )
        labels = spec.get("labels")
        if spec["type"] == "binary":
            if (
                not isinstance(labels, dict)
                or not labels
                or any(
                    not isinstance(key, str) or not isinstance(value, str)
                    for key, value in labels.items()
                )
            ):
                _invalid_labels(
                    "binary question {!r} labels must map strings to strings".format(question)
                )
        elif (
            not isinstance(labels, list)
            or not labels
            or any(not isinstance(label, str) for label in labels)
            or len(set(labels)) != len(labels)
        ):
            _invalid_labels(
                "categorical question {!r} labels must be unique strings".format(question)
            )

    annotators = ds["annotators"]
    if (
        not isinstance(annotators, list)
        or not annotators
        or any(not isinstance(annotator, str) or not annotator for annotator in annotators)
        or len(set(annotators)) != len(annotators)
    ):
        _invalid_labels("annotators must be a non-empty array of unique strings")
    known_annotators = set(annotators)

    cohorts = ds["cohorts"]
    if not isinstance(cohorts, dict) or not cohorts:
        _invalid_labels("cohorts must be a non-empty object")
    for cohort, members in cohorts.items():
        if (
            not isinstance(cohort, str)
            or not cohort
            or not isinstance(members, list)
            or not members
            or any(not isinstance(member, str) or not member for member in members)
            or len(set(members)) != len(members)
        ):
            _invalid_labels(
                "cohort names must be non-empty strings with unique annotator arrays"
            )
        unknown = sorted(set(members) - known_annotators)
        if unknown:
            _invalid_labels(
                "cohort {!r} references unknown annotator(s): {}".format(
                    cohort, ", ".join(unknown)
                )
            )

    items = ds["items"]
    if not isinstance(items, list) or not items:
        _invalid_labels("items must be a non-empty array")
    seen_ids = set()
    for index, item in enumerate(items):
        where = "items[{}]".format(index)
        if not isinstance(item, dict):
            _invalid_labels(where + " must be an object")
        item_id = item.get("id")
        if not isinstance(item_id, str) or not item_id:
            _invalid_labels(where + ".id must be a non-empty string")
        if item_id in seen_ids:
            _invalid_labels("duplicate item id {!r}".format(item_id))
        seen_ids.add(item_id)
        labels_by_question = item.get("labels")
        if not isinstance(labels_by_question, dict):
            _invalid_labels("item {!r}.labels must be an object".format(item_id))
        missing_questions = sorted(set(questions) - set(labels_by_question))
        unknown_questions = sorted(set(labels_by_question) - set(questions))
        if missing_questions:
            _invalid_labels(
                "item {!r} is missing question(s): {}".format(
                    item_id, ", ".join(missing_questions)
                )
            )
        if unknown_questions:
            _invalid_labels(
                "item {!r} has unknown question(s): {}".format(
                    item_id, ", ".join(unknown_questions)
                )
            )
        for question, votes in labels_by_question.items():
            if not isinstance(votes, dict) or not votes:
                _invalid_labels(
                    "item {!r} question {!r} must have at least one vote".format(
                        item_id, question
                    )
                )
            unknown = sorted(set(votes) - known_annotators)
            if unknown:
                _invalid_labels(
                    "item {!r} question {!r} references unknown annotator(s): {}".format(
                        item_id, question, ", ".join(unknown)
                    )
                )
            question_spec = questions[question]
            for annotator, value in votes.items():
                if question_spec["type"] == "binary":
                    if type(value) is not int or value not in (0, 1):
                        _invalid_labels(
                            "item {!r} question {!r} annotator {!r} must use 0 or 1".format(
                                item_id, question, annotator
                            )
                        )
                elif not isinstance(value, str) or value not in question_spec["labels"]:
                    _invalid_labels(
                        "item {!r} question {!r} annotator {!r} has unknown label {!r}".format(
                            item_id, question, annotator, value
                        )
                    )
        reasons = item.get("reasons", {})
        if not isinstance(reasons, dict):
            _invalid_labels("item {!r}.reasons must be an object".format(item_id))
        for question, by_annotator in reasons.items():
            if question not in questions or not isinstance(by_annotator, dict):
                _invalid_labels(
                    "item {!r} has invalid reasons for question {!r}".format(
                        item_id, question
                    )
                )
            unknown = sorted(set(by_annotator) - known_annotators)
            if unknown:
                _invalid_labels(
                    "item {!r} reasons reference unknown annotator(s): {}".format(
                        item_id, ", ".join(unknown)
                    )
                )
            if any(not isinstance(reason, str) for reason in by_annotator.values()):
                _invalid_labels(
                    "item {!r} reasons for {!r} must be strings".format(
                        item_id, question
                    )
                )
    return ds


def load_dataset(path):
    try:
        with open(path, encoding="utf-8") as handle:
            return validate_dataset(json.load(handle))
    except (OSError, json.JSONDecodeError) as exc:
        _invalid_labels(str(exc))


# --------------------------------------------------------------------------- #
# small stats helpers
# --------------------------------------------------------------------------- #
def entropy_bits(counts):
    n = sum(counts.values())
    if n == 0:
        return 0.0
    return -sum((c / n) * math.log2(c / n) for c in counts.values() if c) + 0.0


def norm_entropy(counts):
    support = sum(1 for c in counts.values() if c)
    return entropy_bits(counts) / math.log2(support) if support > 1 else 0.0


def plurality(counts):
    """Deterministic 'majority vote' pick + tie flag."""
    top = max(counts.values())
    winners = sorted(str(l) for l, c in counts.items() if c == top)
    return winners[0], top, len(winners) > 1


def unique_plurality(counts):
    """The label with a STRICT plurality, or None if it's a tie.
    Used for cohort majorities: an all-singleton cohort has no opinion,
    so it must not manufacture a phantom 'fork'."""
    if not counts:
        return None
    top = max(counts.values())
    winners = [l for l, c in counts.items() if c == top]
    return winners[0] if len(winners) == 1 else None


def cohort_index(cohorts):
    """Annotator -> first declared cohort, preserving the prior scan semantics."""
    by_annotator = {}
    for name, members in cohorts.items():
        for annotator in members:
            by_annotator.setdefault(annotator, name)
    return by_annotator


def cohort_of(ann, by_annotator):
    return by_annotator.get(ann)


# --------------------------------------------------------------------------- #
# pass 1: structure of each cell -- needs no reliability estimate
# --------------------------------------------------------------------------- #
def structure(item, q, votes, cohorts):
    counts = Counter(votes.values())
    n = sum(counts.values())
    maj, maj_count, tie = plurality(counts)

    cohort_maj = {name: unique_plurality(Counter(votes[m] for m in mem if m in votes))
                  for name, mem in cohorts.items()}
    real = [v for v in cohort_maj.values() if v is not None]
    value_fork = len(set(real)) >= 2

    max_share = maj_count / n
    distinct = sum(1 for c in counts.values() if c)
    no_ground = (max_share < 0.5) and (distinct >= 3)

    minority_share = (n - maj_count) / n
    coherent_minority = any(str(l) != maj and c >= 2 for l, c in counts.items())
    structured = coherent_minority and minority_share >= STRUCTURED_MIN

    return {
        "item": item["id"], "question": q, "n": n, "counts": counts,
        "distribution": {str(k): v for k, v in counts.items()},
        "majority_vote": maj, "majority_share": round(max_share, 3), "tie": tie,
        "entropy_bits": round(entropy_bits(counts), 3),
        "norm_entropy": round(norm_entropy(counts), 3),
        "cohort_majorities": {k: (str(v) if v is not None else None)
                              for k, v in cohort_maj.items()},
        "value_fork": value_fork, "no_ground": no_ground,
        "structured": structured, "minority_share": round(minority_share, 3),
        "reasons": item.get("reasons", {}).get(q, {}),
    }


# --------------------------------------------------------------------------- #
# pass 2: annotator reliability, on CONFIDENT cells only
# --------------------------------------------------------------------------- #
def reliability(items, struct_by_cell, cohorts):
    """Leave-one-out agreement on cells that will receive CONFIDENT verdicts.

    This mirrors ``classify()`` without depending on reliability itself:
    CONFIDENT requires no value fork, no no-ground condition, no structured
    minority, and a majority share at or above ``NEAR_CONSENSUS``.
    """
    confident_cells = {
        (s["item"], s["question"])
        for s in struct_by_cell.values()
        if not s["value_fork"]
        and not s["no_ground"]
        and not s["structured"]
        and s["majority_share"] >= NEAR_CONSENSUS
    }
    hits, total = Counter(), Counter()
    for it in items:
        for q, votes in it["labels"].items():
            if (it["id"], q) not in confident_cells:
                continue
            full = Counter(votes.values())
            for ann, lab in votes.items():
                others = full.copy()
                others[lab] -= 1
                if not others[lab]:
                    del others[lab]
                if not others:
                    continue
                top = max(others.values())
                modes = {l for l, c in others.items() if c == top}
                total[ann] += 1
                hits[ann] += (lab in modes)
    return {a: (hits[a] / total[a] if total[a] else 1.0) for a in total}


# --------------------------------------------------------------------------- #
# pass 3: classify dissents + final verdict
# --------------------------------------------------------------------------- #
def classify(s, votes, rel, by_annotator):
    maj = s["majority_vote"]
    dissents = []
    for ann, lab in votes.items():
        if str(lab) == maj and not s["tie"]:
            continue
        shared = s["counts"][lab]
        coh = cohort_of(ann, by_annotator)
        cohort_backed = s["cohort_majorities"].get(coh) == str(lab) and s["value_fork"]
        if shared >= 2 or cohort_backed:
            kind = "variation"                       # coherent bloc -> signal
        elif rel.get(ann, 1.0) < UNRELIABLE:
            kind = "error"                           # lone + audited-unreliable -> noise
        else:
            kind = "review"                          # lone but credible -> a human looks
        dissents.append({"annotator": ann, "label": str(lab), "kind": kind,
                         "shared_by": shared, "cohort_backed": cohort_backed})

    if s["value_fork"]:
        verdict = "CONTESTED:VALUE-FORK"
    elif s["no_ground"]:
        verdict = "CONTESTED:NO-GROUND"
    elif s["structured"]:
        verdict = "CONTESTED:VARIATION"
    elif s["majority_share"] >= NEAR_CONSENSUS:
        verdict = "CONFIDENT"
    else:
        verdict = "REVIEW"

    manufactured = verdict.startswith("CONTESTED") and s["minority_share"] >= STRUCTURED_MIN
    return verdict, manufactured, dissents


# --------------------------------------------------------------------------- #
def main(argv=None):
    args = _parse_args(argv)
    data_path = args.data
    out_dir = os.path.abspath(args.out or os.getcwd())
    os.makedirs(out_dir, exist_ok=True)
    ds = load_dataset(data_path)
    items, cohorts, questions = ds["items"], ds["cohorts"], ds["questions"]
    by_annotator = cohort_index(cohorts)

    struct_by_cell = {(it["id"], q): structure(it, q, it["labels"][q], cohorts)
                      for it in items for q in questions}
    rel = reliability(items, struct_by_cell, cohorts)

    cells = []
    for it in items:
        for q in questions:
            s = struct_by_cell[(it["id"], q)]
            verdict, manufactured, dissents = classify(
                s, it["labels"][q], rel, by_annotator
            )
            s.update(verdict=verdict, manufactured_consensus=manufactured,
                     dissents=dissents)
            cells.append(s)

    bar = "=" * 78
    print(bar + "\nLABELS AS DISTRIBUTIONS  --  what a single 'ground truth' hides\n" + bar)
    for c in cells:
        flag = "   <-- MANUFACTURED CONSENSUS" if c["manufactured_consensus"] else ""
        print(f"\n{c['item']} / {c['question']:9s}  {c['verdict']}{flag}")
        print(f"    distribution : {c['distribution']}")
        print(f"    majority vote: {c['majority_vote']!r} "
              f"({c['majority_share']*100:.0f}% mandate"
              f"{', TIE broken arbitrarily' if c['tie'] else ''})   "
              f"entropy {c['entropy_bits']} bits")
        if c["value_fork"]:
            print(f"    VALUE FORK   : cohorts diverge -> {c['cohort_majorities']}")
        for d in c["dissents"]:
            tag = {"variation": "signal", "error": "ERROR ", "review": "review"}[d["kind"]]
            extra = " (cohort-backed)" if d["cohort_backed"] else ""
            print(f"      - {d['annotator']} said {d['label']!r}  [{tag}]{extra}")
        for ann, why in c["reasons"].items():
            print(f"        reason {ann}: {why}")

    confident = [c for c in cells if c["verdict"] == "CONFIDENT"]
    contested = [c for c in cells if c["verdict"].startswith("CONTESTED")]
    review = [c for c in cells if c["verdict"] == "REVIEW"]
    error_cells = [c for c in cells if any(d["kind"] == "error" for d in c["dissents"])]
    forks = [c for c in cells if c["value_fork"]]
    manufactured = [c for c in cells if c["manufactured_consensus"]]
    bits_lost = sum(c["entropy_bits"] for c in contested)

    print("\n" + bar + "\nTHE BILL  --  what one 'ground truth' column would have erased\n" + bar)
    print(f"  cells total .............................. {len(cells)}")
    print(f"  CONFIDENT  (the collapse is honest) ...... {len(confident)}")
    print(f"  CONTESTED  (the collapse destroys signal)  {len(contested)}")
    print(f"  REVIEW     (route to a human) ............ {len(review)}")
    print(f"  cells with a likely ERROR (real noise) ... {len(error_cells)}  <- the few you DO fix")
    print(f"  VALUE FORKS (cohorts truly diverge) ...... {len(forks)}  <- governance decisions, not labels")
    print(f"  MANUFACTURED CONSENSUS (minority silenced)  {len(manufactured)}")
    print(f"  disagreement entropy discarded ........... {bits_lost:.2f} bits across the set")
    print("\n  annotator reliability (leave-one-out, CONFIDENT cells only):")
    for a in sorted(rel, key=rel.get):
        mark = "  <- below audit line; inspect, do not silently drop" if rel[a] < UNRELIABLE else ""
        print(f"    {a}: {rel[a]:.2f}{mark}")

    print("\n" + bar + "\nREAD THIS\n" + bar)
    print("  The CONFIDENT rows are the only ones where 'ground truth' is not a")
    print("  figure of speech. Everywhere else the honest deliverable is the")
    print("  DISTRIBUTION + the REASONS + a record of who got out-voted. A value")
    print("  fork is not an annotation to fix; it is a governance decision being")
    print("  made by default. Decide it on purpose -- or the aggregation function")
    print("  decides it for you, and ships it into the model as if it were a fact.")

    out = os.path.join(out_dir, "triage.json")
    with open(out, "w") as f:
        json.dump({"reliability": rel,
                   "cells": [{k: v for k, v in c.items() if k != "counts"} for c in cells]},
                  f, indent=2)
    print(f"\n  machine-readable triage -> {os.path.relpath(out, out_dir)}")


if __name__ == "__main__":
    main()
