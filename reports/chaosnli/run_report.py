#!/usr/bin/env python3
"""Run one official ChaosNLI split and emit reproducibility evidence, not data."""

import argparse
import hashlib
import json
import math
import os
import platform
import resource
import subprocess
import sys
import time
import tracemalloc
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from adapters import chaosnli as adapter  # noqa: E402


DEFAULT_SOURCE_URL = "https://www.dropbox.com/s/h4j7dqszmpt2679/chaosNLI_v1.0.zip"
DEFAULT_SOURCE_VERSION = "ChaosNLI v1.0"
DEFAULT_LICENSE = "CC BY-NC 4.0"


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="locally downloaded official ChaosNLI JSONL split")
    parser.add_argument("--source-url", default=DEFAULT_SOURCE_URL)
    parser.add_argument("--source-version", default=DEFAULT_SOURCE_VERSION)
    parser.add_argument("--license", default=DEFAULT_LICENSE)
    parser.add_argument("--expected-source-sha256", default=None)
    parser.add_argument("--shard-count", type=int, default=16)
    parser.add_argument(
        "--work-dir",
        default=str(ROOT / "reports" / "chaosnli" / "work"),
        help="ignored directory for converted data and pipeline artifacts",
    )
    parser.add_argument(
        "--manifest-out",
        default=str(ROOT / "reports" / "chaosnli" / "manifest.json"),
    )
    parser.add_argument(
        "--report-out",
        default=str(ROOT / "reports" / "chaosnli" / "report.md"),
    )
    return parser.parse_args(argv)


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_commit():
    return subprocess.check_output(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
        universal_newlines=True,
    ).strip()


def load_json(path):
    with Path(path).open(encoding="utf-8") as handle:
        return json.load(handle)


def load_jsonl(path):
    with Path(path).open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def run(command):
    started = time.perf_counter()
    result = subprocess.run(
        [str(part) for part in command],
        cwd=str(ROOT),
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    )
    return result, time.perf_counter() - started


def validate_schema(dataset, schema):
    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        raise SystemExit(
            "run_report.py requires jsonschema for the explicit schema-validation gate"
        )
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(dataset)


def expected_soft_label(record):
    counter = {str(label): count for label, count in record["label_counter"].items()}
    total = sum(counter.values())
    return {
        label: round(count / total, 3)
        for label, count in counter.items()
        if count
    }


def expected_entropy(record):
    probabilities = expected_soft_label(record).values()
    return -sum(probability * math.log2(probability) for probability in probabilities)


def directory_bytes(path):
    return sum(file.stat().st_size for file in Path(path).rglob("*") if file.is_file())


def peak_rss_bytes():
    value = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    return int(value if sys.platform == "darwin" else value * 1024)


def format_bytes(value):
    units = ("B", "KiB", "MiB", "GiB")
    amount = float(value)
    for unit in units:
        if amount < 1024 or unit == units[-1]:
            return "{:.2f} {}".format(amount, unit)
        amount /= 1024


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")


def main(argv=None):
    args = parse_args(argv)
    if args.shard_count <= 0:
        raise SystemExit("--shard-count must be greater than zero")
    source_path = Path(args.input).resolve()
    work_dir = Path(args.work_dir).resolve()
    work_dir.mkdir(parents=True, exist_ok=True)
    if any(work_dir.iterdir()):
        raise SystemExit("work directory must be empty: {}".format(work_dir))

    source_sha256 = sha256_file(source_path)
    if (
        args.expected_source_sha256
        and source_sha256 != args.expected_source_sha256
    ):
        raise SystemExit(
            "source SHA-256 mismatch: expected {}, observed {}".format(
                args.expected_source_sha256, source_sha256
            )
        )

    records = adapter.load_records(str(source_path))
    source_uids = [record["uid"] for _, record in records]
    schema = load_json(ROOT / "schema" / "labels.schema.json")
    tool_commit = git_commit()
    manifests = []
    verified_distributions = 0
    verified_soft_labels = 0
    verified_entropies = 0
    total_pipeline_bytes = 0
    total_runtime = 0.0

    tracemalloc.start()
    started_all = time.perf_counter()
    for shard_index in range(args.shard_count):
        shard_dir = work_dir / "shard-{:03d}".format(shard_index)
        pipeline_dir = shard_dir / "pipeline"
        labels_path = shard_dir / "labels.json"
        shard_dir.mkdir(parents=True)
        _, adapter_runtime = run(
            [
                sys.executable,
                ROOT / "adapters" / "chaosnli.py",
                source_path,
                "--shard-index",
                shard_index,
                "--shard-count",
                args.shard_count,
                "--out",
                labels_path,
            ]
        )
        manifest = load_json(str(labels_path) + ".manifest.json")
        manifests.append(manifest)
        start = shard_index * len(records) // args.shard_count
        stop = (shard_index + 1) * len(records) // args.shard_count
        selected = records[start:stop]
        dataset = load_json(labels_path)
        verification = adapter.verify_converted_distributions(selected, dataset)
        verified_distributions += verification["record_count"]
        validate_schema(dataset, schema)

        pipeline_runtime = 0.0
        for tool in ("disagreement.py", "soft_labels.py", "resolution.py"):
            _, elapsed = run(
                [
                    sys.executable,
                    ROOT / tool,
                    "--data",
                    labels_path,
                    "--out",
                    pipeline_dir,
                ]
            )
            pipeline_runtime += elapsed

        soft_by_uid = {
            row["item_id"]: row
            for row in load_jsonl(pipeline_dir / "soft_labels.jsonl")
        }
        triage_by_uid = {
            row["item"]: row for row in load_json(pipeline_dir / "triage.json")["cells"]
        }
        for _, source in selected:
            uid = source["uid"]
            if soft_by_uid[uid]["soft_label"] != expected_soft_label(source):
                raise ValueError("uid {!r} soft-label mismatch".format(uid))
            verified_soft_labels += 1
            if triage_by_uid[uid]["entropy_bits"] != round(expected_entropy(source), 3):
                raise ValueError("uid {!r} entropy mismatch".format(uid))
            verified_entropies += 1

        total_pipeline_bytes += directory_bytes(pipeline_dir)
        shard_runtime = adapter_runtime + pipeline_runtime
        total_runtime += shard_runtime

    wall_seconds = time.perf_counter() - started_all
    _, harness_peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    aggregate = adapter.aggregate_shard_manifests(manifests, source_uids)
    if aggregate["tool_commits"] != [tool_commit]:
        raise ValueError("shard manifests do not name the executing tool commit")

    deterministic_manifest = {
        "evidence_tier": "Tier 2 - manifest-reproducible external empirical run",
        "dataset": source_path.name,
        "source_url": args.source_url,
        "source_version": args.source_version,
        "source_license": args.license,
        "source_sha256": source_sha256,
        "tool_commit": tool_commit,
        "total_records": len(records),
        "vote_count": aggregate["vote_count"],
        "label_set": aggregate["label_set"],
        "shard_count": args.shard_count,
        "coverage": {
            "record_count": aggregate["record_count"],
            "uids_sha256": aggregate["uids_sha256"],
            "ordered_complete_unique": True,
        },
        "verification": {
            "distribution_matches": verified_distributions,
            "soft_label_matches": verified_soft_labels,
            "entropy_matches": verified_entropies,
            "schema_valid_shards": args.shard_count,
            "pipeline_complete_shards": args.shard_count,
        },
        "shards": [
            {
                "shard_index": shard["shard_index"],
                "record_count": shard["record_count"],
                "vote_count": manifests[shard["shard_index"]]["vote_count"],
                "uids_sha256": shard["uids_sha256"],
                "output_sha256": shard["output_sha256"],
            }
            for shard in aggregate["shards"]
        ],
    }
    write_json(args.manifest_out, deterministic_manifest)
    manifest_sha256 = sha256_file(args.manifest_out)

    entropies = [expected_entropy(record) for _, record in records]
    generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )
    report = """# ChaosNLI real-split reproducibility report

**Evidence tier:** Tier 2 — manifest-reproducible external empirical evidence.

**Generated:** {generated_at}

**Tool commit:** `{tool_commit}`

This report records one run on a separately downloaded official split. No
ChaosNLI rows, converted labels, or virtual-voter records are committed here.
The CI-pinned Tier-1 tests exercise the same sharding, coverage, distribution,
and manifest logic on a synthetic fixture.

## Source and coverage

- Source: `{source_name}` ({source_version})
- Official download: {source_url}
- Dataset license: {license_name}
- Source SHA-256: `{source_sha256}`
- Committed manifest SHA-256: `{manifest_sha256}`
- Records: {record_count:,}
- Anonymous votes represented: {vote_count:,}
- Shards: {shard_count}
- Coverage: every source UID appears exactly once, in source order; no gaps,
  overlaps, duplicates, or missing shard indices

## Verification results

- Converted vote distributions exactly matching source `label_counter`:
  **{distribution_matches:,}/{record_count:,}**
- Trainer soft labels exactly matching `label_counter / sum(label_counter)`:
  **{soft_label_matches:,}/{record_count:,}**
- Recomputed entropy matching triage output at its documented 3-decimal
  precision: **{entropy_matches:,}/{record_count:,}**
- Input-schema validation: **{schema_shards}/{shard_count} shards**
- Operational pipeline completion (`disagreement` → `soft_labels` →
  `resolution`): **{pipeline_shards}/{shard_count} shards**
- Source entropy range: {entropy_min:.6f} to {entropy_max:.6f} bits; mean
  {entropy_mean:.6f} bits

## Runtime and resources

- Platform: {platform_name}; Python {python_version}
- End-to-end wall time: {wall_seconds:.3f} seconds
- Sum of measured adapter + pipeline subprocess times: {total_runtime:.3f} seconds
- Peak child-process resident memory: {peak_rss}
- Peak harness-tracked Python memory: {harness_peak}
- Converted and pipeline work-directory size: {work_bytes}
- Pipeline artifacts alone: {pipeline_bytes}

Runtime and memory are observations from this machine, not deterministic claims;
the committed JSON manifest intentionally contains only reproducibility checks,
hashes, and counts.

## Non-applicable findings

**Reliability, error attribution, variation-vs-error classification, and
cohort value-fork prevalence are NON-APPLICABLE — undefined here, not zero.**
ChaosNLI exposes anonymous per-item counts rather than stable cross-item
annotator identities, and this faithful conversion uses one crowd cohort.
Accordingly, this report makes claims only about distributions, entropy, soft
labels, coverage, and reproducibility.
""".format(
        generated_at=generated_at,
        tool_commit=tool_commit,
        source_name=source_path.name,
        source_version=args.source_version,
        source_url=args.source_url,
        license_name=args.license,
        source_sha256=source_sha256,
        manifest_sha256=manifest_sha256,
        record_count=len(records),
        vote_count=aggregate["vote_count"],
        shard_count=args.shard_count,
        distribution_matches=verified_distributions,
        soft_label_matches=verified_soft_labels,
        entropy_matches=verified_entropies,
        schema_shards=args.shard_count,
        pipeline_shards=args.shard_count,
        entropy_min=min(entropies),
        entropy_max=max(entropies),
        entropy_mean=sum(entropies) / len(entropies),
        platform_name=platform.platform(),
        python_version=platform.python_version(),
        wall_seconds=wall_seconds,
        total_runtime=total_runtime,
        peak_rss=format_bytes(peak_rss_bytes()),
        harness_peak=format_bytes(harness_peak),
        work_bytes=format_bytes(directory_bytes(work_dir)),
        pipeline_bytes=format_bytes(total_pipeline_bytes),
    )
    report_path = Path(args.report_out)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")
    print("manifest -> {}".format(Path(args.manifest_out).resolve()))
    print("report -> {}".format(report_path.resolve()))


if __name__ == "__main__":
    main()
