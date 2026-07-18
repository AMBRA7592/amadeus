#!/usr/bin/env python3
"""List value-fork decisions and record a named owner's decision atomically.

Run ``disagreement.py`` and ``soft_labels.py`` first. This CLI operates on the
``governance.jsonl`` queue in ``--out`` (the current directory by default).
After recording a decision, run ``resolution.py`` with the same data and output
directory to emit the owned resolution record.
"""

import argparse
import json
import os
import stat
import tempfile
from datetime import datetime, timezone


def _parse_args(argv):
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)

    list_parser = commands.add_parser("list", help="list the governance queue")
    list_parser.add_argument(
        "--out",
        default=None,
        help="directory containing governance.jsonl (default: current directory)",
    )
    list_parser.set_defaults(handler=list_queue)

    decide_parser = commands.add_parser(
        "decide", help="record a decision for one pending value fork"
    )
    decide_parser.add_argument("--item", required=True, help="queue item id")
    decide_parser.add_argument("--question", required=True, help="question name")
    decide_parser.add_argument("--owner", required=True, help="named decision owner")
    decide_parser.add_argument("--decision", required=True, help="recorded decision")
    decide_parser.add_argument("--rationale", required=True, help="decision rationale")
    decide_parser.add_argument(
        "--out",
        default=None,
        help="directory containing governance.jsonl (default: current directory)",
    )
    decide_parser.set_defaults(handler=decide)
    return parser.parse_args(argv)


def _fail(message):
    raise SystemExit("governance.jsonl: " + message)


def _named_owner(owner):
    return (
        isinstance(owner, str)
        and bool(owner.strip())
        and not owner.lstrip().startswith("<")
    )


def _nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def _validate_decided(record):
    if record.get("decision_recorded") is None:
        return
    if not _named_owner(record.get("decision_required_from")):
        _fail(
            "{}/{} has a decision but no named owner".format(
                record["item_id"], record["question"]
            )
        )
    if not _nonempty(record.get("decision_rationale")):
        _fail(
            "{}/{} has a decision but no rationale".format(
                record["item_id"], record["question"]
            )
        )


def load_queue(path):
    if not os.path.isfile(path):
        _fail("not found -- run disagreement.py and soft_labels.py first")
    records = []
    seen = set()
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
                item = record.get("item_id")
                question = record.get("question")
                if not _nonempty(item) or not _nonempty(question):
                    _fail(
                        "line {} needs non-empty item_id and question".format(
                            line_number
                        )
                    )
                key = (item, question)
                if key in seen:
                    _fail("duplicate queue key {}/{}".format(item, question))
                seen.add(key)
                _validate_decided(record)
                records.append(record)
    except OSError as exc:
        _fail(str(exc))
    return records


def _queue_path(out):
    out_dir = os.path.abspath(out or os.getcwd())
    return out_dir, os.path.join(out_dir, "governance.jsonl")


def list_queue(args):
    _, path = _queue_path(args.out)
    records = load_queue(path)
    counts = {"pending": 0, "decided": 0, "resolved_no_longer_fork": 0}
    print("GOVERNANCE QUEUE")
    for record in records:
        status = record.get("status", "pending")
        counts[status] = counts.get(status, 0) + 1
        owner = record.get("decision_required_from") or "-"
        decision = record.get("decision_recorded")
        options = ", ".join(sorted(record.get("soft_label", {}))) or "-"
        print(
            "  {status:23s} {item} / {question}  owner={owner}  "
            "decision={decision}  options={options}".format(
                status=status,
                item=record["item_id"],
                question=record["question"],
                owner=owner,
                decision="-" if decision is None else decision,
                options=options,
            )
        )
    print(
        "{} record(s): {} pending, {} decided, {} resolved".format(
            len(records),
            counts.get("pending", 0),
            counts.get("decided", 0),
            counts.get("resolved_no_longer_fork", 0),
        )
    )


def utc_timestamp():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


def _atomic_write(path, records):
    directory = os.path.dirname(path)
    mode = stat.S_IMODE(os.stat(path).st_mode)
    descriptor, temporary_path = tempfile.mkstemp(
        prefix=".governance.", suffix=".tmp", dir=directory, text=True
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            for record in records:
                handle.write(json.dumps(record) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary_path, mode)
        os.replace(temporary_path, path)
    except BaseException:
        try:
            os.unlink(temporary_path)
        except FileNotFoundError:
            pass
        raise


def decide(args):
    _, path = _queue_path(args.out)
    records = load_queue(path)
    owner = args.owner.strip()
    decision = args.decision.strip()
    rationale = args.rationale.strip()
    if not _named_owner(owner):
        _fail("owner must name a human or accountable role, not a placeholder")
    if not _nonempty(decision):
        _fail("decision must be non-empty")
    if not _nonempty(rationale):
        _fail("rationale must be non-empty")

    target = None
    for record in records:
        if record["item_id"] == args.item and record["question"] == args.question:
            target = record
            break
    if target is None:
        _fail("no queue record for {}/{}".format(args.item, args.question))
    if target.get("decision_recorded") is not None:
        _fail(
            "{}/{} is already decided; refusing to overwrite its audit trail".format(
                args.item, args.question
            )
        )

    target["decision_required_from"] = owner
    target["decision_recorded"] = decision
    target["decision_rationale"] = rationale
    target.pop("status", None)
    target["decided_at"] = utc_timestamp()
    target["status"] = "decided"
    _validate_decided(target)
    _atomic_write(path, records)
    print(
        "recorded {}/{} -> {} (owner: {})".format(
            args.item, args.question, decision, owner
        )
    )
    print("run resolution.py with the same --data and --out to emit the decision")


def main(argv=None):
    args = _parse_args(argv)
    args.handler(args)


if __name__ == "__main__":
    main()
