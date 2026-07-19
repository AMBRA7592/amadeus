#!/usr/bin/env python3
"""Phase-2 MHS study harness.  Present for audit; do not run in Phase 1."""

import argparse
import datetime
import hashlib
import json
import os
import statistics
import subprocess
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import disagreement  # noqa: E402 - imported from the repository root
import geometry  # noqa: E402 - pure frozen centre/TV functions
from adapters import mhs  # noqa: E402
from reports.mhs import metrics  # noqa: E402


SOURCE_REVISION = "5468f6e"
SOURCE_SHA256 = "6819525ce61bc24344df9fc3f7bf48270b31038273cc27c67fc225b51433b0e1"
PROTOCOL_PATH = "reports/part-3b-dataset-selection-audit.md"
ADDENDUM_PATH = "reports/part-3b-reliability-corpus-addendum-2026-07-19.md"
RELIABILITY_MIN_CONFIDENT = 20
RELIABILITY_MIN_PER_COHORT = 30
PARQUET_COLUMNS = (
    "annotator_id",
    "comment_id",
    "hatespeech",
    "annotator_ideology",
)


def _parse_args(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", help="local measuring-hate-speech.parquet")
    parser.add_argument(
        "--work-dir",
        default=str(ROOT / "reports" / "mhs" / "work"),
        help="git-ignored generated-data directory",
    )
    parser.add_argument(
        "--report-dir",
        default=str(ROOT / "reports" / "mhs"),
        help="directory for Phase-2 report.md and manifest.json",
    )
    return parser.parse_args(argv)


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_source(path):
    observed = _sha256(path)
    if observed != SOURCE_SHA256:
        raise SystemExit(
            "MHS source SHA-256 mismatch: expected {}, observed {}. Halt: "
            "freeze the new revision/hash, repeat the structural gate, and "
            "obtain owner approval before outcomes.".format(SOURCE_SHA256, observed)
        )
    return observed


def load_parquet_records(path):
    """Thin dependency boundary; pyarrow is never imported by CI/module import."""
    try:
        import pyarrow.parquet as parquet
    except ImportError:
        raise SystemExit(
            "Phase 2 requires pyarrow to read the local parquet. Install it in "
            "a separate environment; CI does not need it. Expected source "
            "SHA-256: {}".format(SOURCE_SHA256)
        )
    table = parquet.read_table(path, columns=list(PARQUET_COLUMNS))
    return table.to_pylist()


def _write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")


def _load_json(path):
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _run_instruments(data_path, out_dir):
    out_dir.mkdir(parents=True, exist_ok=True)
    for tool in ("disagreement.py", "soft_labels.py"):
        subprocess.run(
            [
                sys.executable,
                str(ROOT / tool),
                "--data",
                str(data_path),
                "--out",
                str(out_dir),
            ],
            cwd=str(ROOT),
            check=True,
        )
    return _load_json(out_dir / "triage.json")


def _cohort_distribution(item, members):
    votes = item["labels"][mhs.QUESTION]
    present = [member for member in members if member in votes]
    if not present:
        raise ValueError("primary item has no votes for a frozen cohort")
    counts = Counter(votes[member] for member in present)
    total = sum(counts.values())
    return {label: count / total for label, count in counts.items()}


def aggregate_primary(dataset, triage):
    """Aggregate the three primary-item metrics without changing instruments."""
    cells = triage["cells"]
    total = len(dataset["items"])
    if total != len(cells):
        raise ValueError("primary dataset and triage cell counts differ")
    fork_count = sum(bool(cell["value_fork"]) for cell in cells)
    manufactured_count = sum(
        bool(cell["manufactured_consensus"]) for cell in cells
    )
    gaps = []
    undefined = 0
    for item in dataset["items"]:
        conservative = _cohort_distribution(
            item, dataset["cohorts"]["Conservative"]
        )
        liberal = _cohort_distribution(item, dataset["cohorts"]["Liberal"])
        arithmetic = geometry.arithmetic_mean([conservative, liberal])
        geometric = geometry.geometric_mean([conservative, liberal])
        if geometric is None:
            undefined += 1
        else:
            gaps.append(geometry.tv(arithmetic, geometric))
    gap_summary = None
    if gaps:
        gap_summary = metrics.median_iqr(gaps)
        gap_summary["bootstrap_95"] = metrics.bootstrap_median(gaps)
    return {
        "value_fork": {
            "count": fork_count,
            "total": total,
            "rate": fork_count / total,
            "wilson_95": metrics.wilson_interval(fork_count, total),
        },
        "manufactured_consensus": {
            "count": manufactured_count,
            "total": total,
            "rate": manufactured_count / total,
            "wilson_95": metrics.wilson_interval(manufactured_count, total),
        },
        "geometry_gap": {
            "defined_count": len(gaps),
            "undefined_count": undefined,
            "undefined_share": undefined / total,
            "defined": gap_summary,
        },
    }


def _confident_contributions(dataset, triage):
    items = {item["id"]: item for item in dataset["items"]}
    contributions = []
    for cell in triage["cells"]:
        if cell["verdict"] != "CONFIDENT":
            continue
        votes = items[cell["item"]]["labels"][cell["question"]]
        full = Counter(votes.values())
        contribution = {}
        for annotator, label in votes.items():
            others = full.copy()
            others[label] -= 1
            if not others[label]:
                del others[label]
            if not others:
                continue
            top = max(others.values())
            modes = {candidate for candidate, count in others.items() if count == top}
            contribution[annotator] = (1 if label in modes else 0, 1)
        contributions.append(contribution)
    return contributions


def _reliability_by_annotator(contributions, annotators):
    hits, totals = Counter(), Counter()
    for contribution in contributions:
        for annotator, (hit, total) in contribution.items():
            if annotator in annotators:
                hits[annotator] += hit
                totals[annotator] += total
    return {
        annotator: hits[annotator] / totals[annotator]
        for annotator in sorted(annotators)
        if totals[annotator]
    }


def _reliability_values(contributions, annotators):
    return list(_reliability_by_annotator(contributions, annotators).values())


def _reliability_median_difference(sample, fixed_cohorts):
    conservative = _reliability_values(sample, fixed_cohorts["Conservative"])
    liberal = _reliability_values(sample, fixed_cohorts["Liberal"])
    if not conservative or not liberal:
        return None
    return statistics.median(conservative) - statistics.median(liberal)


def aggregate_reliability(dataset, triage):
    contributions = _confident_contributions(dataset, triage)
    scored_counts = Counter()
    for contribution in contributions:
        scored_counts.update(contribution.keys())
    qualifying = {
        cohort: [
            annotator
            for annotator in dataset["cohorts"][cohort]
            if scored_counts[annotator] >= RELIABILITY_MIN_CONFIDENT
        ]
        for cohort in mhs.COHORTS
    }
    values = {
        cohort: [triage["reliability"][annotator] for annotator in qualifying[cohort]]
        for cohort in mhs.COHORTS
    }
    summaries = {
        cohort: (metrics.median_iqr(values[cohort]) if values[cohort] else None)
        for cohort in mhs.COHORTS
    }
    powered = all(
        len(qualifying[cohort]) >= RELIABILITY_MIN_PER_COHORT
        for cohort in mhs.COHORTS
    )
    difference = None
    if all(values.values()):
        difference = statistics.median(values["Conservative"]) - statistics.median(
            values["Liberal"]
        )
    interval = None
    if powered:
        fixed = {cohort: set(qualifying[cohort]) for cohort in mhs.COHORTS}
        interval = metrics.bootstrap_statistic(
            contributions,
            lambda sample: _reliability_median_difference(sample, fixed),
        )
    return {
        "status": "descriptive" if powered else "underpowered/non-applicable",
        "minimum_confident_cells": RELIABILITY_MIN_CONFIDENT,
        "minimum_qualifying_annotators_per_cohort": RELIABILITY_MIN_PER_COHORT,
        "coverage": {
            cohort: {
                "eligible": len(dataset["cohorts"][cohort]),
                "qualifying": len(qualifying[cohort]),
            }
            for cohort in mhs.COHORTS
        },
        "summaries": summaries,
        "median_difference_conservative_minus_liberal": difference,
        "bootstrap_95": interval,
    }


def _tool_commit():
    return subprocess.check_output(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
        universal_newlines=True,
    ).strip()


def _fmt(number):
    return "not applicable" if number is None else "{:.6f}".format(number)


def _bootstrap_field(interval, key):
    if interval is None:
        return "not applicable"
    value = interval[key]
    return "not applicable" if value is None else str(value)


def render_report(results, counts, tool_commit):
    primary = results["primary"]
    reliability = results["reliability"]
    geometry_result = primary["geometry_gap"]
    return """# MHS bounded Tier-2 pilot

**Evidence boundary:** dataset-specific, topology-qualified descriptive results
for MHS revision `{revision}` and the frozen Conservative/Liberal contrast. This
is not universal or production prevalence, a causal ideology effect, a correct
ground truth, or variation-versus-error attribution.

Protocol: `{protocol}`<br>
Reliability addendum: `{addendum}`<br>
Tool commit: `{commit}`

## Structural counts

- Primary items: {primary_items}
- Reliability-corpus items: {reliability_items}
- Conservative annotators: {conservative}
- Liberal annotators: {liberal}

## Frozen metrics

- Value forks: {fork_count}/{fork_total} ({fork_rate:.6f}); Wilson 95% [{fork_lo:.6f}, {fork_hi:.6f}]
- Manufactured consensus: {manufactured_count}/{manufactured_total} ({manufactured_rate:.6f}); Wilson 95% [{manufactured_lo:.6f}, {manufactured_hi:.6f}]
- Geometry: {undefined} undefined/disjoint-support items ({undefined_share:.6f}); defined-gap median {gap_median}, Q1 {gap_q1}, Q3 {gap_q3}, IQR {gap_iqr}, item-bootstrap 95% [{gap_boot_lo}, {gap_boot_hi}] (status {gap_boot_status}; total draws {gap_boot_iterations}; valid estimates {gap_boot_valid}; degenerate resamples {gap_boot_degenerate})
- Reliability: {reliability_status}; coverage Conservative {conservative_qualifying}/{conservative_eligible}, Liberal {liberal_qualifying}/{liberal_eligible}; Conservative median {conservative_median} (IQR {conservative_iqr}), Liberal median {liberal_median} (IQR {liberal_iqr}); Conservative-minus-Liberal median difference {reliability_difference}, item-bootstrap 95% [{reliability_boot_lo}, {reliability_boot_hi}] (status {reliability_boot_status}; total draws {reliability_boot_iterations}; valid estimates {reliability_boot_valid}; degenerate resamples {reliability_boot_degenerate})

No source rows or identifiers are published. The source checksum and aggregate
results are recorded in `manifest.json`. No null-hypothesis p-values are used.
""".format(
        revision=SOURCE_REVISION,
        protocol=PROTOCOL_PATH,
        addendum=ADDENDUM_PATH,
        commit=tool_commit,
        primary_items=counts["primary_items"],
        reliability_items=counts["reliability_items"],
        conservative=counts["conservative_annotators"],
        liberal=counts["liberal_annotators"],
        fork_count=primary["value_fork"]["count"],
        fork_total=primary["value_fork"]["total"],
        fork_rate=primary["value_fork"]["rate"],
        fork_lo=primary["value_fork"]["wilson_95"]["lower"],
        fork_hi=primary["value_fork"]["wilson_95"]["upper"],
        manufactured_count=primary["manufactured_consensus"]["count"],
        manufactured_total=primary["manufactured_consensus"]["total"],
        manufactured_rate=primary["manufactured_consensus"]["rate"],
        manufactured_lo=primary["manufactured_consensus"]["wilson_95"]["lower"],
        manufactured_hi=primary["manufactured_consensus"]["wilson_95"]["upper"],
        undefined=geometry_result["undefined_count"],
        undefined_share=geometry_result["undefined_share"],
        gap_median=_fmt(
            geometry_result["defined"]["median"] if geometry_result["defined"] else None
        ),
        gap_q1=_fmt(
            geometry_result["defined"]["q1"] if geometry_result["defined"] else None
        ),
        gap_q3=_fmt(
            geometry_result["defined"]["q3"] if geometry_result["defined"] else None
        ),
        gap_iqr=_fmt(
            geometry_result["defined"]["iqr"] if geometry_result["defined"] else None
        ),
        gap_boot_lo=_fmt(
            geometry_result["defined"]["bootstrap_95"]["lower"]
            if geometry_result["defined"]
            else None
        ),
        gap_boot_hi=_fmt(
            geometry_result["defined"]["bootstrap_95"]["upper"]
            if geometry_result["defined"]
            else None
        ),
        gap_boot_status=_bootstrap_field(
            geometry_result["defined"]["bootstrap_95"]
            if geometry_result["defined"]
            else None,
            "status",
        ),
        gap_boot_iterations=_bootstrap_field(
            geometry_result["defined"]["bootstrap_95"]
            if geometry_result["defined"]
            else None,
            "iterations",
        ),
        gap_boot_valid=_bootstrap_field(
            geometry_result["defined"]["bootstrap_95"]
            if geometry_result["defined"]
            else None,
            "valid_estimates",
        ),
        gap_boot_degenerate=_bootstrap_field(
            geometry_result["defined"]["bootstrap_95"]
            if geometry_result["defined"]
            else None,
            "degenerate_resamples",
        ),
        reliability_status=reliability["status"],
        conservative_qualifying=reliability["coverage"]["Conservative"]["qualifying"],
        conservative_eligible=reliability["coverage"]["Conservative"]["eligible"],
        liberal_qualifying=reliability["coverage"]["Liberal"]["qualifying"],
        liberal_eligible=reliability["coverage"]["Liberal"]["eligible"],
        conservative_median=_fmt(
            reliability["summaries"]["Conservative"]["median"]
            if reliability["summaries"]["Conservative"]
            else None
        ),
        conservative_iqr=_fmt(
            reliability["summaries"]["Conservative"]["iqr"]
            if reliability["summaries"]["Conservative"]
            else None
        ),
        liberal_median=_fmt(
            reliability["summaries"]["Liberal"]["median"]
            if reliability["summaries"]["Liberal"]
            else None
        ),
        liberal_iqr=_fmt(
            reliability["summaries"]["Liberal"]["iqr"]
            if reliability["summaries"]["Liberal"]
            else None
        ),
        reliability_difference=_fmt(
            reliability["median_difference_conservative_minus_liberal"]
        ),
        reliability_boot_lo=_fmt(
            reliability["bootstrap_95"]["lower"]
            if reliability["bootstrap_95"]
            else None
        ),
        reliability_boot_hi=_fmt(
            reliability["bootstrap_95"]["upper"]
            if reliability["bootstrap_95"]
            else None
        ),
        reliability_boot_status=_bootstrap_field(
            reliability["bootstrap_95"], "status"
        ),
        reliability_boot_iterations=_bootstrap_field(
            reliability["bootstrap_95"], "iterations"
        ),
        reliability_boot_valid=_bootstrap_field(
            reliability["bootstrap_95"], "valid_estimates"
        ),
        reliability_boot_degenerate=_bootstrap_field(
            reliability["bootstrap_95"], "degenerate_resamples"
        ),
    )


def build_manifest(source_hash, counts, results, tool_commit, generated_at):
    """Build the aggregate evidence object without reading source data."""
    return {
        "evidence_tier": "Tier 2",
        "generated_at": generated_at,
        "source_revision": SOURCE_REVISION,
        "source_sha256": source_hash,
        "protocol": PROTOCOL_PATH,
        "addendum": ADDENDUM_PATH,
        "tool_commit": tool_commit,
        "counts": counts,
        "metrics": results,
        "contains_source_rows_or_ids": False,
    }


def main(argv=None):
    args = _parse_args(argv)
    source = Path(args.source).resolve()
    source_hash = verify_source(source)
    records = load_parquet_records(source)
    converted = mhs.convert_records(records)
    if converted["status"] == "halt":
        raise SystemExit("MHS protocol halt: " + converted["halt_reason"])

    work = Path(args.work_dir).resolve()
    work.mkdir(parents=True, exist_ok=True)
    primary_path = work / "primary-labels.json"
    reliability_path = work / "reliability-labels.json"
    mhs.write_dataset(converted["primary"], primary_path)
    mhs.write_dataset(converted["reliability"], reliability_path)
    primary_triage = _run_instruments(primary_path, work / "primary")
    reliability_triage = _run_instruments(reliability_path, work / "reliability")
    results = {
        "primary": aggregate_primary(converted["primary"], primary_triage),
        "reliability": aggregate_reliability(
            converted["reliability"], reliability_triage
        ),
    }
    commit = _tool_commit()
    generated_at = (
        datetime.datetime.now(datetime.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )
    manifest = build_manifest(
        source_hash,
        converted["counts"],
        results,
        commit,
        generated_at,
    )
    report_dir = Path(args.report_dir).resolve()
    report_dir.mkdir(parents=True, exist_ok=True)
    _write_json(report_dir / "manifest.json", manifest)
    (report_dir / "report.md").write_text(
        render_report(results, converted["counts"], commit), encoding="utf-8"
    )
    print("Tier-2 report -> {}".format(report_dir / "report.md"))
    print("aggregate manifest -> {}".format(report_dir / "manifest.json"))


if __name__ == "__main__":
    main()
