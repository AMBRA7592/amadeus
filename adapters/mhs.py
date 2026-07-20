#!/usr/bin/env python3
"""Convert already-parsed Measuring Hate Speech rows under the frozen protocol.

This module is deliberately standard-library only.  It does not read parquet,
perform network access, or compute study outcomes.  ``reports/mhs/run_study.py``
owns the separately authorized parquet-loading and orchestration boundary.
"""

import json
import math
from collections import Counter, OrderedDict


QUESTION = "hatespeech"
LABELS = ("0", "1", "2")
ELIGIBILITY_FLOOR = 20
PRIMARY_MIN_PER_COHORT = 2
PRIMARY_MIN_ITEMS = 50
CONSERVATIVE_IDEOLOGIES = frozenset(
    ("extremely_conservative", "conservative", "slightly_conservative")
)
LIBERAL_IDEOLOGIES = frozenset(
    ("extremely_liberal", "liberal", "slightly_liberal")
)
COHORTS = ("Conservative", "Liberal")
ABOUT = (
    "Measuring Hate Speech conversion under the frozen Part-3b protocol: "
    "annotators need at least 20 non-null hatespeech judgments; Conservative "
    "and Liberal cohorts use only the six exact author-supplied ideology "
    "values; primary items need at least two members of each cohort; raw "
    "ordinal values remain categorical strings 0/1/2. Real-data evidence is "
    "Tier 2 and source rows are never committed; see "
    "reports/part-3b-dataset-selection-audit.md."
)


class MHSInputError(ValueError):
    """The parsed rows cannot be converted without violating the protocol."""


def cohort_for_ideology(value):
    """Return a cohort only for one of the six exact pre-registered strings."""
    if value in CONSERVATIVE_IDEOLOGIES:
        return "Conservative"
    if value in LIBERAL_IDEOLOGIES:
        return "Liberal"
    return None


def _identifier(value, field, index):
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise MHSInputError(
            "record {} field {} must be a non-empty string or integer".format(
                index, field
            )
        )
    normalized = str(value)
    if not normalized:
        raise MHSInputError(
            "record {} field {} must not be empty".format(index, field)
        )
    return normalized


def _label(value, index):
    if value is None:
        return None
    if isinstance(value, bool):
        raise MHSInputError(
            "record {} hatespeech must be null or one of 0, 1, 2".format(index)
        )
    if isinstance(value, float):
        if not math.isfinite(value) or not value.is_integer():
            raise MHSInputError(
                "record {} hatespeech must be null or one of 0, 1, 2".format(
                    index
                )
            )
        normalized = str(int(value))
    else:
        normalized = str(value)
    if normalized not in LABELS:
        raise MHSInputError(
            "record {} hatespeech must be null or one of 0, 1, 2".format(index)
        )
    return normalized


def _normalize(records):
    if not isinstance(records, list) or not records:
        raise MHSInputError("records must be a non-empty list")
    normalized = []
    ideologies = {}
    seen_pairs = set()
    for index, record in enumerate(records, 1):
        if not isinstance(record, dict):
            raise MHSInputError("record {} must be an object".format(index))
        missing = [
            key
            for key in (
                "annotator_id",
                "comment_id",
                "hatespeech",
                "annotator_ideology",
            )
            if key not in record
        ]
        if missing:
            raise MHSInputError(
                "record {} is missing {}".format(index, ", ".join(missing))
            )
        annotator = _identifier(record["annotator_id"], "annotator_id", index)
        comment = _identifier(record["comment_id"], "comment_id", index)
        label = _label(record["hatespeech"], index)
        ideology = record["annotator_ideology"]
        if ideology is not None and not isinstance(ideology, str):
            raise MHSInputError(
                "record {} annotator_ideology must be a string or null".format(index)
            )
        if annotator in ideologies and ideologies[annotator] != ideology:
            raise MHSInputError(
                "annotator {!r} has inconsistent author-supplied ideology values".format(
                    annotator
                )
            )
        ideologies[annotator] = ideology
        pair = (annotator, comment)
        if pair in seen_pairs:
            raise MHSInputError(
                "duplicate judgment for annotator {!r}, comment {!r}".format(
                    annotator, comment
                )
            )
        seen_pairs.add(pair)
        normalized.append(
            {
                "annotator_id": annotator,
                "comment_id": comment,
                "hatespeech": label,
                "annotator_ideology": ideology,
            }
        )
    return normalized, ideologies


def _dataset(items, cohort_members, purpose):
    ordered_items = []
    for comment, votes in items.items():
        if votes:
            ordered_items.append(
                {
                    "id": comment,
                    "labels": {
                        QUESTION: {
                            annotator: votes[annotator]
                            for annotator in sorted(votes)
                        }
                    },
                }
            )
    annotators = sorted(
        set(cohort_members["Conservative"]) | set(cohort_members["Liberal"])
    )
    return {
        "_about": ABOUT + " This object is the {} corpus.".format(purpose),
        "questions": {
            QUESTION: {
                "type": "categorical",
                "labels": list(LABELS),
                "note": "Raw MHS ordinal hatespeech values; not binarized or replaced by an IRT score.",
            }
        },
        "annotators": annotators,
        "cohorts": {
            "Conservative": sorted(cohort_members["Conservative"]),
            "Liberal": sorted(cohort_members["Liberal"]),
        },
        "items": ordered_items,
    }


def convert_records(records):
    """Return primary/reliability datasets and a frozen-filter halt signal.

    The function performs structural conversion only.  It never examines a
    label to decide whether an item enters the primary set; selection depends
    exclusively on repeated-identity, ideology, and per-cohort coverage.
    """
    normalized, ideologies = _normalize(records)
    judgment_counts = Counter(
        row["annotator_id"]
        for row in normalized
        if row["hatespeech"] is not None
    )
    eligible = {
        annotator
        for annotator, count in judgment_counts.items()
        if count >= ELIGIBILITY_FLOOR
    }
    cohort_members = {name: [] for name in COHORTS}
    cohort_by_annotator = {}
    for annotator in sorted(eligible):
        cohort = cohort_for_ideology(ideologies.get(annotator))
        if cohort is not None:
            cohort_members[cohort].append(annotator)
            cohort_by_annotator[annotator] = cohort

    if not all(cohort_members.values()):
        raise MHSInputError(
            "conversion needs at least one eligible Conservative and Liberal annotator"
        )

    items = OrderedDict()
    for row in normalized:
        annotator = row["annotator_id"]
        label = row["hatespeech"]
        if label is None or annotator not in cohort_by_annotator:
            continue
        items.setdefault(row["comment_id"], {})[annotator] = label

    primary_items = OrderedDict()
    for comment, votes in items.items():
        coverage = Counter(cohort_by_annotator[annotator] for annotator in votes)
        if all(coverage[name] >= PRIMARY_MIN_PER_COHORT for name in COHORTS):
            primary_items[comment] = votes

    primary = _dataset(primary_items, cohort_members, "primary")
    reliability = _dataset(items, cohort_members, "full reliability")
    primary_count = len(primary["items"])
    status = "ready" if primary_count >= PRIMARY_MIN_ITEMS else "halt"
    halt_reason = None
    if status == "halt":
        halt_reason = (
            "primary item count {} is below the frozen minimum {}; halt and "
            "return to the owner without weakening the filter"
        ).format(primary_count, PRIMARY_MIN_ITEMS)
    return {
        "status": status,
        "halt_reason": halt_reason,
        "primary": primary,
        "reliability": reliability,
        "counts": {
            "source_records": len(normalized),
            "non_null_judgments": sum(judgment_counts.values()),
            "eligible_annotators": len(eligible),
            "conservative_annotators": len(cohort_members["Conservative"]),
            "liberal_annotators": len(cohort_members["Liberal"]),
            "excluded_eligible_annotators": len(eligible)
            - len(cohort_by_annotator),
            "primary_items": primary_count,
            "reliability_items": len(reliability["items"]),
        },
    }


def load_jsonl(path):
    """Load already-parsed JSONL records; used only for synthetic fixtures."""
    records = []
    with open(path, encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise MHSInputError(
                    "line {} is invalid JSON: {}".format(line_number, exc.msg)
                )
            records.append(record)
    return records


def write_dataset(dataset, path):
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(dataset, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
