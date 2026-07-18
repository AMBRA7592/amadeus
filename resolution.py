#!/usr/bin/env python3
"""Emit the resolution records specified by the repository's fourth object.

Run after the diagnostic and exporter:

    python3 disagreement.py
    python3 soft_labels.py
    python3 resolution.py

The output is one JSON object per (item, question) in
``resolution_records.jsonl``. Runtime remains standard-library only. CI uses
``jsonschema`` separately to validate the emitted records.

The replay hash intentionally identifies the evidence, aggregation rule, and
policy version. It is deterministic across runs and changes when any of those
inputs changes. It does not attest a later human decision or rationale; those
remain explicit fields in the record.
"""

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone

from disagreement import PIPELINE_EPILOG, load_dataset
from geometry import arithmetic_mean, geometric_mean, tv


HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data", "labels.json")
TRIAGE = os.path.join(HERE, "triage.json")
SOFT_LABELS = os.path.join(HERE, "soft_labels.jsonl")
GOVERNANCE = os.path.join(HERE, "governance.jsonl")
OUTPUT = os.path.join(HERE, "resolution_records.jsonl")
SCHEMA = os.path.join(HERE, "schema", "resolution_record.schema.json")
POLICY_VERSION = "groundless-truth-demo-2026.05"
PRODUCED_BY = "resolution.py (groundless-truth v1.3.0)"
BAR = "=" * 78


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


def load_jsonl(path):
    records = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))
    return records


def label_name(question, key, questions):
    labels = questions[question]["labels"]
    return labels.get(str(key), str(key)) if isinstance(labels, dict) else str(key)


def canonical_replay_bytes(record):
    """Canonical UTF-8 bytes for {input, rule, policy_version}.

    JSON object keys are sorted recursively, separators are exactly `,` and
    `:`, non-ASCII characters are encoded directly as UTF-8, and no trailing
    newline is included.
    """
    payload = {
        "input": record["input"],
        "policy_version": record["authority"]["policy_version"],
        "rule": record["rule"],
    }
    text = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return text.encode("utf-8")


def replay_hash(record):
    return "sha256:" + hashlib.sha256(canonical_replay_bytes(record)).hexdigest()


def cohort_distribution(item, question, members):
    votes = item["labels"][question]
    present = [member for member in members if member in votes]
    if not present:
        return {}
    weight = 1.0 / len(present)
    dist = {}
    for member in present:
        label = votes[member]
        dist[label] = dist.get(label, 0.0) + weight
    return dist


def geometry_gap(item, question, cohorts):
    distributions = [
        cohort_distribution(item, question, members)
        for members in cohorts.values()
    ]
    distributions = [distribution for distribution in distributions if distribution]
    if len(distributions) < 2:
        return None
    arithmetic = arithmetic_mean(distributions)
    geometric = geometric_mean(distributions)
    if geometric is None:
        return None
    return round(tv(arithmetic, geometric), 3)


def input_object(item, question, cohorts, questions):
    votes = item["labels"][question]
    reasons = item.get("reasons", {}).get(question, {})
    judgments = []
    for annotator in sorted(votes):
        judgment = {
            "annotator": annotator,
            "label": label_name(question, votes[annotator], questions),
        }
        if annotator in reasons:
            judgment["reason"] = reasons[annotator]
        judgments.append(judgment)
    return {
        "judgments": judgments,
        "cohorts": {name: list(members) for name, members in cohorts.items()},
        "n_annotators": len(votes),
    }


def fork_status(verdict):
    return {
        "CONFIDENT": "none",
        "CONTESTED:VARIATION": "variation",
        "CONTESTED:NO-GROUND": "no_ground",
        "CONTESTED:VALUE-FORK": "value_fork",
        "REVIEW": "review",
    }[verdict]


def rule_for(cell, soft_record):
    routing = soft_record["routing"]
    if routing == "supervised":
        return {
            "aggregation": "majority",
            "tie_break": "alphabetical" if cell["tie"] else None,
            "loss_geometry": "0-1/argmax",
        }
    if routing == "soft_label_only":
        return {
            "aggregation": "soft_label",
            "tie_break": None,
            "loss_geometry": "cross_entropy/arithmetic",
        }
    return {
        "aggregation": "escalate",
        "tie_break": None,
        "loss_geometry": "none/escalated",
    }


def authority_and_disposition(cell, soft_record, governance_record):
    routing = soft_record["routing"]
    authority = {
        "policy_version": POLICY_VERSION,
        "decided_by": "automated",
        "owner": None,
    }
    if routing == "supervised":
        disposition = {
            "outcome": "collapsed:" + soft_record["majority_label"],
            "conditions": [
                "eligible for confidence-weighted supervised training under the stated policy"
            ],
        }
    elif routing == "soft_label_only":
        disposition = {
            "outcome": "soft_label",
            "conditions": [
                "preserve the full distribution; do not collapse to one class"
            ],
        }
    elif routing == "human_review":
        disposition = {
            "outcome": "held_for_review",
            "conditions": [
                "excluded from training until a human reviews the dissent and reasons"
            ],
        }
    elif governance_record and governance_record.get("decision_recorded") is not None:
        owner = governance_record.get("decision_required_from")
        if (not isinstance(owner, str) or not owner.strip()
                or owner.lstrip().startswith("<")):
            raise ValueError(
                f"{cell['item']}/{cell['question']} has a decision but no named owner"
            )
        rationale = governance_record.get("decision_rationale")
        if not isinstance(rationale, str) or not rationale.strip():
            raise ValueError(
                f"{cell['item']}/{cell['question']} has a decision but no rationale"
            )
        authority.update(decided_by="named_owner", owner=owner)
        conditions = [
            f"decided under policy {POLICY_VERSION}; revisit if the policy version changes"
        ]
        conditions.append("rationale: " + rationale)
        disposition = {
            "outcome": "decided:" + str(governance_record["decision_recorded"]),
            "conditions": conditions,
        }
    else:
        disposition = {
            "outcome": "escalated",
            "conditions": [
                "excluded from training until a named owner records a decision and rationale",
                "the recorded decision must state which cohort norm the model will carry",
            ],
        }
    return authority, disposition


def build_records(ds, triage, soft_records, governance_records, timestamp):
    items = {item["id"]: item for item in ds["items"]}
    soft = {(r["item_id"], r["question"]): r for r in soft_records}
    governance = {
        (r["item_id"], r["question"]): r for r in governance_records
    }
    records = []
    for cell in triage["cells"]:
        key = (cell["item"], cell["question"])
        item = items[cell["item"]]
        soft_record = soft[key]
        authority, disposition = authority_and_disposition(
            cell, soft_record, governance.get(key)
        )
        record = {
            "item": cell["item"],
            "question": cell["question"],
            "input": input_object(
                item, cell["question"], ds["cohorts"], ds["questions"]
            ),
            "rule": rule_for(cell, soft_record),
            "measures": {
                "entropy_bits": cell["entropy_bits"],
                "fork_status": fork_status(cell["verdict"]),
                "manufactured_consensus": cell["manufactured_consensus"],
                "curl": None,
                "geometry_gap": geometry_gap(
                    item, cell["question"], ds["cohorts"]
                ),
            },
            "authority": authority,
            "disposition": disposition,
            "provenance": {
                "timestamp": timestamp,
                "replay_hash": "",
                "produced_by": PRODUCED_BY,
            },
        }
        record["provenance"]["replay_hash"] = replay_hash(record)
        records.append(record)
    return records


def utc_timestamp():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def main(argv=None):
    args = _parse_args(argv)
    data_path = args.data
    out_dir = os.path.abspath(args.out or os.getcwd())
    os.makedirs(out_dir, exist_ok=True)
    triage_path = os.path.join(out_dir, "triage.json")
    soft_labels_path = os.path.join(out_dir, "soft_labels.jsonl")
    governance_path = os.path.join(out_dir, "governance.jsonl")
    output_path = os.path.join(out_dir, "resolution_records.jsonl")
    required = [data_path, triage_path, soft_labels_path, governance_path]
    missing = [
        os.path.relpath(path, out_dir) for path in required if not os.path.exists(path)
    ]
    if missing:
        raise SystemExit(
            "missing prerequisite(s): " + ", ".join(missing)
            + " -- run disagreement.py and soft_labels.py first"
        )
    ds = load_dataset(data_path)
    with open(triage_path, encoding="utf-8") as f:
        triage = json.load(f)
    records = build_records(
        ds,
        triage,
        load_jsonl(soft_labels_path),
        load_jsonl(governance_path),
        utc_timestamp(),
    )
    with open(output_path, "w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")

    outcomes = {}
    for record in records:
        outcome = record["disposition"]["outcome"].split(":", 1)[0]
        outcomes[outcome] = outcomes.get(outcome, 0) + 1
    pending_forks = sum(
        r["measures"]["fork_status"] == "value_fork"
        and r["disposition"]["outcome"] == "escalated"
        for r in records
    )
    print(BAR + "\nRESOLUTION RECORDS  --  the fourth object, written down on purpose\n" + BAR)
    print(f"  records emitted .......................... {len(records)}")
    for outcome in ("collapsed", "soft_label", "held_for_review", "escalated", "decided"):
        if outcomes.get(outcome):
            print(f"    outcome {outcome:20s} {outcomes[outcome]}")
    print(f"  value forks still awaiting an owner ...... {pending_forks}")
    print("  replay hash: canonical SHA-256 over {input, rule, policy_version}")
    print("  (identifies replay inputs; it does not attest a later human decision)")
    print(f"\n  auditable records -> {os.path.relpath(output_path, out_dir)}")
    print(f"  schema            -> {os.path.relpath(SCHEMA, HERE)} (CI validates)")


if __name__ == "__main__":
    main()
