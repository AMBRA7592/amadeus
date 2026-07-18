#!/usr/bin/env python3
"""Convert ChaosNLI label counters into groundless-truth labels.json.

ChaosNLI releases anonymous aggregate counts, not stable annotator identities.
This adapter therefore creates item-scoped virtual voter ids and one crowd
cohort. It performs no network access and uses only the Python standard library.
"""

import argparse
import json
import os
from urllib.parse import quote


QUESTION = "nli_label"
NLI_LABELS = ("e", "n", "c")
ALPHA_LABELS = ("1", "2")
ABOUT = (
    "Converted from ChaosNLI anonymous per-item label counts. Virtual annotator "
    "ids are unique to each item and do not represent persistent people; all "
    "votes are placed in one crowd cohort. Annotator reliability and cohort "
    "value-fork results are therefore not meaningful for this conversion. The "
    "faithful outputs are the per-item distribution, entropy, and soft labels."
)


def _parse_args(argv):
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument("input", help="ChaosNLI JSONL file")
    parser.add_argument(
        "--out",
        default="labels.json",
        help="output labels.json path (default: ./labels.json)",
    )
    return parser.parse_args(argv)


def _fail(message):
    raise SystemExit("ChaosNLI: " + message)


def _counter(record, line_number):
    counter = record.get("label_counter")
    if not isinstance(counter, dict) or not counter:
        _fail("line {} needs a non-empty label_counter object".format(line_number))
    normalized = {}
    for label, count in counter.items():
        label = str(label)
        if type(count) is not int or count < 0:
            _fail(
                "line {} label_counter[{!r}] must be a non-negative integer".format(
                    line_number, label
                )
            )
        normalized[label] = count
    labels = set(normalized)
    if labels <= set(NLI_LABELS):
        task_labels = NLI_LABELS
    elif labels <= set(ALPHA_LABELS):
        task_labels = ALPHA_LABELS
    else:
        _fail(
            "line {} mixes or uses unsupported labels: {}".format(
                line_number, ", ".join(sorted(labels))
            )
        )
    if sum(normalized.values()) <= 0:
        _fail("line {} label_counter must contain at least one vote".format(line_number))
    return normalized, task_labels


def _description(example, task_labels, line_number):
    if not isinstance(example, dict):
        _fail("line {} needs an example object".format(line_number))
    if task_labels == NLI_LABELS:
        fields = ("premise", "hypothesis")
    else:
        fields = ("obs1", "obs2", "hyp1", "hyp2")
    missing = [field for field in fields if not isinstance(example.get(field), str)]
    if missing:
        _fail(
            "line {} example needs string field(s): {}".format(
                line_number, ", ".join(missing)
            )
        )
    return " | ".join("{}: {}".format(field, example[field]) for field in fields)


def load_records(path):
    records = []
    try:
        with open(path, encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError as exc:
                    _fail("line {} is not valid JSON: {}".format(line_number, exc.msg))
                if not isinstance(record, dict):
                    _fail("line {} must be a JSON object".format(line_number))
                records.append((line_number, record))
    except OSError as exc:
        _fail(str(exc))
    if not records:
        _fail("input contains no records")
    return records


def convert(records):
    annotators = []
    items = []
    seen_uids = set()
    label_sets = set()
    for line_number, record in records:
        uid = record.get("uid")
        if not isinstance(uid, str) or not uid.strip():
            _fail("line {} needs a non-empty string uid".format(line_number))
        if uid in seen_uids:
            _fail("line {} repeats uid {!r}".format(line_number, uid))
        seen_uids.add(uid)
        counter, task_labels = _counter(record, line_number)
        label_sets.add(task_labels)
        description = _description(record.get("example"), task_labels, line_number)

        votes = {}
        vote_number = 0
        encoded_uid = quote(uid, safe="")
        for label in task_labels:
            for _ in range(counter.get(label, 0)):
                vote_number += 1
                annotator = "chaosnli:{}:vote:{:03d}".format(
                    encoded_uid, vote_number
                )
                annotators.append(annotator)
                votes[annotator] = label
        items.append(
            {
                "id": uid,
                "desc": description,
                "labels": {QUESTION: votes},
            }
        )

    labels = []
    for candidate in (NLI_LABELS, ALPHA_LABELS):
        if candidate in label_sets:
            labels.extend(candidate)
    return {
        "_about": ABOUT,
        "questions": {
            QUESTION: {
                "type": "categorical",
                "labels": labels,
                "note": (
                    "Raw ChaosNLI categories: e=entailment, n=neutral, "
                    "c=contradiction; alphaNLI uses 1=hypothesis 1 and "
                    "2=hypothesis 2."
                ),
            }
        },
        "annotators": annotators,
        "cohorts": {"crowd": list(annotators)},
        "items": items,
    }


def main(argv=None):
    args = _parse_args(argv)
    dataset = convert(load_records(args.input))
    output = os.path.abspath(args.out)
    directory = os.path.dirname(output)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(output, "w", encoding="utf-8") as handle:
        json.dump(dataset, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(
        "converted {} item(s), {} anonymous vote(s) -> {}".format(
            len(dataset["items"]), len(dataset["annotators"]), output
        )
    )
    print(
        "caveat: reliability and value forks are not meaningful; "
        "use distributions, entropy, and soft labels"
    )


if __name__ == "__main__":
    main()
