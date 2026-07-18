#!/usr/bin/env python3
"""Convert ChaosNLI label counters into groundless-truth labels.json.

ChaosNLI releases anonymous aggregate counts, not stable annotator identities.
This adapter therefore creates item-scoped virtual voter ids and one crowd
cohort. It performs no network access and uses only the Python standard library.
"""

import argparse
import hashlib
import json
import os
import subprocess
from collections import Counter
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
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST_VERSION = 1


class ManifestError(ValueError):
    """A shard manifest set does not prove complete, ordered coverage."""


def _parse_args(argv):
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument("input", help="ChaosNLI JSONL file")
    parser.add_argument(
        "--out",
        default="labels.json",
        help="output labels.json path (default: ./labels.json)",
    )
    parser.add_argument(
        "--shard-index",
        type=int,
        default=None,
        help="zero-based contiguous shard index (requires --shard-count)",
    )
    parser.add_argument(
        "--shard-count",
        type=int,
        default=None,
        help="number of contiguous shards (requires --shard-index)",
    )
    parser.add_argument(
        "--offset",
        type=int,
        default=None,
        help="zero-based record offset (mutually exclusive with shard mode)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="maximum records from --offset (default: through end)",
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


def _record_uids(records):
    uids = []
    seen = set()
    for line_number, record in records:
        uid = record.get("uid") if isinstance(record, dict) else None
        if not isinstance(uid, str) or not uid.strip():
            _fail("line {} needs a non-empty string uid".format(line_number))
        if uid in seen:
            _fail("line {} repeats uid {!r}".format(line_number, uid))
        seen.add(uid)
        uids.append(uid)
    return uids


def select_records(records, shard_index=None, shard_count=None, offset=None, limit=None):
    """Return one contiguous selection and deterministic selection metadata."""
    has_shard = shard_index is not None or shard_count is not None
    has_range = offset is not None or limit is not None
    if has_shard and has_range:
        _fail("shard mode and offset/limit mode are mutually exclusive")
    if has_shard:
        if shard_index is None or shard_count is None:
            _fail("--shard-index and --shard-count must be supplied together")
        if shard_count <= 0:
            _fail("--shard-count must be greater than zero")
        if shard_index < 0 or shard_index >= shard_count:
            _fail("--shard-index must satisfy 0 <= index < shard-count")
        total = len(records)
        start = shard_index * total // shard_count
        stop = (shard_index + 1) * total // shard_count
        selected = records[start:stop]
        metadata = {
            "mode": "shard",
            "shard_index": shard_index,
            "shard_count": shard_count,
            "offset": start,
            "limit": stop - start,
        }
    elif has_range:
        if offset is None:
            _fail("--limit requires --offset")
        if offset < 0:
            _fail("--offset must be non-negative")
        if limit is not None and limit < 0:
            _fail("--limit must be non-negative")
        stop = len(records) if limit is None else offset + limit
        selected = records[offset:stop]
        metadata = {
            "mode": "range",
            "shard_index": None,
            "shard_count": None,
            "offset": offset,
            "limit": limit,
        }
    else:
        return records, None
    if not selected:
        _fail("selection contains no records")
    return selected, metadata


def _sha256_bytes(content):
    return hashlib.sha256(content).hexdigest()


def _sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _uids_sha256(uids):
    payload = json.dumps(
        list(uids), ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    return _sha256_bytes(payload)


def _tool_commit():
    try:
        return subprocess.check_output(
            ["git", "-C", ROOT, "rev-parse", "HEAD"],
            stderr=subprocess.DEVNULL,
            universal_newlines=True,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def build_manifest(input_path, output_path, source_uids, dataset, selection):
    selected_uids = [item["id"] for item in dataset["items"]]
    votes = sum(
        len(item["labels"][QUESTION]) for item in dataset["items"]
    )
    return {
        "manifest_version": MANIFEST_VERSION,
        "source_path": os.path.abspath(input_path),
        "source_sha256": _sha256_file(input_path),
        "total_records": len(source_uids),
        "mode": selection["mode"],
        "shard_index": selection["shard_index"],
        "shard_count": selection["shard_count"],
        "offset": selection["offset"],
        "limit": selection["limit"],
        "record_count": len(selected_uids),
        "uid_first": selected_uids[0],
        "uid_last": selected_uids[-1],
        "uids": selected_uids,
        "uids_sha256": _uids_sha256(selected_uids),
        "annotator_count": len(dataset["annotators"]),
        "vote_count": votes,
        "label_set": sorted(
            {
                label
                for item in dataset["items"]
                for label in item["labels"][QUESTION].values()
            }
        ),
        "tool_commit": _tool_commit(),
        "output_sha256": _sha256_file(output_path),
    }


def aggregate_shard_manifests(manifests, source_uids):
    """Validate shard manifests and return a whole-source coverage manifest."""
    if not manifests:
        raise ManifestError("no shard manifests supplied")
    if len(set(source_uids)) != len(source_uids):
        raise ManifestError("source uid list contains a duplicate")
    if any(manifest.get("mode") != "shard" for manifest in manifests):
        raise ManifestError("all manifests must use shard mode")
    shard_counts = {manifest.get("shard_count") for manifest in manifests}
    if len(shard_counts) != 1:
        raise ManifestError("shard_count disagrees across manifests")
    shard_count = next(iter(shard_counts))
    if type(shard_count) is not int or shard_count <= 0:
        raise ManifestError("invalid shard_count")
    by_index = {}
    for manifest in manifests:
        index = manifest.get("shard_index")
        if type(index) is not int:
            raise ManifestError("invalid shard index")
        if index in by_index:
            raise ManifestError("duplicate shard index {}".format(index))
        by_index[index] = manifest
    expected_indices = list(range(shard_count))
    if sorted(by_index) != expected_indices:
        raise ManifestError(
            "shard indices must cover 0..{} exactly".format(shard_count - 1)
        )

    totals = {manifest.get("total_records") for manifest in manifests}
    source_hashes = {manifest.get("source_sha256") for manifest in manifests}
    if totals != {len(source_uids)}:
        raise ManifestError("total_records does not match the source")
    if len(source_hashes) != 1:
        raise ManifestError("source_sha256 disagrees across manifests")
    if not all(
        isinstance(source_hash, str) and len(source_hash) == 64
        for source_hash in source_hashes
    ):
        raise ManifestError("invalid source_sha256")

    ordered = [by_index[index] for index in expected_indices]
    concatenated = []
    for manifest in ordered:
        uids = manifest.get("uids")
        if not isinstance(uids, list):
            raise ManifestError("each shard manifest needs an ordered uids list")
        if manifest.get("record_count") != len(uids):
            raise ManifestError("record_count does not match a shard's uids")
        if not uids or manifest.get("uid_first") != uids[0] or manifest.get("uid_last") != uids[-1]:
            raise ManifestError("uid boundary metadata does not match a shard")
        if manifest.get("uids_sha256") != _uids_sha256(uids):
            raise ManifestError("uids_sha256 does not match a shard's uids")
        concatenated.extend(uids)
    if sum(manifest["record_count"] for manifest in ordered) != len(source_uids):
        raise ManifestError("shard record counts do not sum to total_records")
    if len(set(concatenated)) != len(concatenated):
        raise ManifestError("shard coverage contains a duplicate uid")
    if concatenated != list(source_uids):
        raise ManifestError("shard coverage has a gap, overlap, or order change")

    return {
        "manifest_version": MANIFEST_VERSION,
        "source_path": ordered[0].get("source_path"),
        "source_sha256": next(iter(source_hashes)),
        "total_records": len(source_uids),
        "shard_count": shard_count,
        "record_count": sum(manifest["record_count"] for manifest in ordered),
        "uids": concatenated,
        "uids_sha256": _uids_sha256(concatenated),
        "annotator_count": sum(manifest["annotator_count"] for manifest in ordered),
        "vote_count": sum(manifest["vote_count"] for manifest in ordered),
        "label_set": sorted(
            {label for manifest in ordered for label in manifest["label_set"]}
        ),
        "tool_commits": sorted({manifest["tool_commit"] for manifest in ordered}),
        "shards": [
            {
                "shard_index": manifest["shard_index"],
                "record_count": manifest["record_count"],
                "uid_first": manifest["uid_first"],
                "uid_last": manifest["uid_last"],
                "uids_sha256": manifest["uids_sha256"],
                "output_sha256": manifest["output_sha256"],
            }
            for manifest in ordered
        ],
    }


def verify_converted_distributions(records, dataset):
    """Prove that each converted vote multiset equals its source counter."""
    expected_uids = _record_uids(records)
    items = dataset.get("items", [])
    actual_uids = [item.get("id") for item in items]
    if actual_uids != expected_uids:
        raise ValueError("converted item order/uids do not match the source selection")
    vote_count = 0
    for (line_number, source), item in zip(records, items):
        counter, _ = _counter(source, line_number)
        observed = Counter(item["labels"][QUESTION].values())
        labels = set(counter) | set(observed)
        expected = {label: counter.get(label, 0) for label in labels}
        actual = {label: observed.get(label, 0) for label in labels}
        if actual != expected:
            raise ValueError(
                "uid {!r} distribution mismatch: expected {}, observed {}".format(
                    item["id"], expected, actual
                )
            )
        vote_count += sum(actual.values())
    return {"record_count": len(records), "vote_count": vote_count}


def convert(records):
    if not records:
        _fail("selection contains no records")
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
    records = load_records(args.input)
    source_uids = _record_uids(records)
    selected, selection = select_records(
        records,
        shard_index=args.shard_index,
        shard_count=args.shard_count,
        offset=args.offset,
        limit=args.limit,
    )
    dataset = convert(selected)
    verify_converted_distributions(selected, dataset)
    output = os.path.abspath(args.out)
    directory = os.path.dirname(output)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(output, "w", encoding="utf-8") as handle:
        json.dump(dataset, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    if selection is not None:
        manifest = build_manifest(
            args.input, output, source_uids, dataset, selection
        )
        manifest_path = output + ".manifest.json"
        with open(manifest_path, "w", encoding="utf-8") as handle:
            json.dump(manifest, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
    print(
        "converted {} of {} item(s), {} anonymous vote(s) -> {}".format(
            len(dataset["items"]), len(records), len(dataset["annotators"]), output
        )
    )
    if selection is not None:
        print("manifest -> {}".format(manifest_path))
    print(
        "caveat: reliability and value forks are not meaningful; "
        "use distributions, entropy, and soft labels"
    )


if __name__ == "__main__":
    main()
