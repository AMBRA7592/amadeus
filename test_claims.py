#!/usr/bin/env python3
"""Verify that every headline claim remains equal to its runnable proof.

The suite has two deliberately separate layers:

* invariant checks recompute results from functions or fresh temporary artifacts;
* prose pins require the essays to keep quoting those recomputed results.

It uses only the standard library.  Full JSON Schema validation runs when the
optional ``jsonschema`` package is importable and otherwise skips cleanly.
"""

import atexit
import copy
import hashlib
import json
import math
import random
import shutil
import statistics
import subprocess
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path

import aggregation
import bayes_optimal
import disagreement
import frustration
import geometry
import resolution
import topology
from adapters import chaosnli as chaosnli_adapter
from adapters import mhs as mhs_adapter
from reports.mhs import metrics as mhs_metrics
from reports.mhs import run_study as mhs_study

try:
    from jsonschema import Draft202012Validator, FormatChecker

    _HAS_JSONSCHEMA = True
except ImportError:  # pragma: no cover - exercised by the zero-dependency run
    Draft202012Validator = FormatChecker = None
    _HAS_JSONSCHEMA = False


ROOT = Path(__file__).resolve().parent
REQUIRED_RECORD_KEYS = {
    "item",
    "question",
    "input",
    "rule",
    "measures",
    "authority",
    "disposition",
    "provenance",
}
FORK_STATUSES = {"none", "variation", "no_ground", "value_fork", "review"}


def _load_json(path):
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _load_jsonl(path):
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


DATASET = _load_json(ROOT / "data" / "labels.json")


def _item(item_id):
    return next(item for item in DATASET["items"] if item["id"] == item_id)


def _essay(name):
    return (ROOT / name).read_text(encoding="utf-8")


def _cohort_distribution(item, question, members):
    votes = item["labels"][question]
    present = [member for member in members if member in votes]
    weight = 1.0 / len(present)
    distribution = {}
    for member in present:
        label = votes[member]
        distribution[label] = distribution.get(label, 0.0) + weight
    return distribution


_PIPELINE = None
_PIPELINE_TEMP = None


def _cleanup_pipeline():
    global _PIPELINE_TEMP
    if _PIPELINE_TEMP is not None:
        _PIPELINE_TEMP.cleanup()
        _PIPELINE_TEMP = None


atexit.register(_cleanup_pipeline)


def _pipeline():
    """Run all artifact-producing proofs once, outside the repository tree."""
    global _PIPELINE, _PIPELINE_TEMP
    if _PIPELINE is not None:
        return _PIPELINE

    _PIPELINE_TEMP = tempfile.TemporaryDirectory(prefix="groundless-claims-")
    work = Path(_PIPELINE_TEMP.name)
    shutil.copytree(str(ROOT / "data"), str(work / "data"))
    shutil.copytree(str(ROOT / "schema"), str(work / "schema"))
    for name in (
        "disagreement.py",
        "soft_labels.py",
        "geometry.py",
        "resolution.py",
    ):
        shutil.copy2(str(ROOT / name), str(work / name))

    output = {}
    for name in ("disagreement.py", "soft_labels.py", "geometry.py", "resolution.py"):
        result = subprocess.run(
            [sys.executable, name],
            cwd=str(work),
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
        )
        output[name] = result.stdout

    first_records = _load_jsonl(work / "resolution_records.jsonl")
    first_hashes = {
        (record["item"], record["question"]): record["provenance"]["replay_hash"]
        for record in first_records
    }
    subprocess.run(
        [sys.executable, "resolution.py"],
        cwd=str(work),
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    )
    second_records = _load_jsonl(work / "resolution_records.jsonl")
    second_hashes = {
        (record["item"], record["question"]): record["provenance"]["replay_hash"]
        for record in second_records
    }

    _PIPELINE = {
        "triage": _load_json(work / "triage.json"),
        "soft": _load_jsonl(work / "soft_labels.jsonl"),
        "governance": _load_jsonl(work / "governance.jsonl"),
        "governance_bytes": (work / "governance.jsonl").read_bytes(),
        "records": first_records,
        "first_hashes": first_hashes,
        "second_hashes": second_hashes,
        "output": output,
    }
    return _PIPELINE


class DisagreementClaims(unittest.TestCase):
    def test_bill_and_confident_only_reliability(self):
        pipeline = _pipeline()
        triage = pipeline["triage"]
        cells = triage["cells"]
        verdicts = Counter(
            "CONTESTED" if cell["verdict"].startswith("CONTESTED") else cell["verdict"]
            for cell in cells
        )
        error_cells = sum(
            any(dissent["kind"] == "error" for dissent in cell["dissents"])
            for cell in cells
        )
        forks = sum(cell["value_fork"] for cell in cells)
        manufactured = sum(cell["manufactured_consensus"] for cell in cells)
        bits_lost = round(
            sum(
                cell["entropy_bits"]
                for cell in cells
                if cell["verdict"].startswith("CONTESTED")
            ),
            2,
        )

        self.assertEqual(len(cells), 18)
        self.assertEqual(verdicts, Counter({"CONFIDENT": 12, "CONTESTED": 5, "REVIEW": 1}))
        self.assertEqual(error_cells, 5)
        self.assertEqual(forks, 2)
        self.assertEqual(manufactured, 5)
        self.assertEqual(bits_lost, 5.78)

        expected_reliability = {
            "a1": 1.0,
            "a2": 1.0,
            "a3": 1.0,
            "a4": 1.0,
            "b1": 1.0,
            "b2": 11 / 12,
            "b3": 11 / 12,
            "b4": 2 / 3,
        }
        self.assertEqual(set(triage["reliability"]), set(expected_reliability))
        for annotator, expected in expected_reliability.items():
            self.assertAlmostEqual(triage["reliability"][annotator], expected, places=12)
        self.assertIn("CONFIDENT cells only", pipeline["output"]["disagreement.py"])

    def test_optimized_reliability_and_cohort_lookup_match_naive_references(self):
        def naive_cohort_of(annotator, cohorts):
            return next(
                (name for name, members in cohorts.items() if annotator in members),
                None,
            )

        def naive_reliability(items, struct_by_cell, cohorts):
            confident_cells = {
                (cell["item"], cell["question"])
                for cell in struct_by_cell.values()
                if not cell["value_fork"]
                and not cell["no_ground"]
                and not cell["structured"]
                and cell["majority_share"] >= disagreement.NEAR_CONSENSUS
            }
            hits, total = Counter(), Counter()
            for item in items:
                for question, votes in item["labels"].items():
                    if (item["id"], question) not in confident_cells:
                        continue
                    for annotator, label in votes.items():
                        others = Counter(
                            vote
                            for other_annotator, vote in votes.items()
                            if other_annotator != annotator
                        )
                        if not others:
                            continue
                        top = max(others.values())
                        modes = {
                            candidate
                            for candidate, count in others.items()
                            if count == top
                        }
                        total[annotator] += 1
                        hits[annotator] += label in modes
            return {
                annotator: (
                    hits[annotator] / total[annotator]
                    if total[annotator]
                    else 1.0
                )
                for annotator in total
            }

        forced_cohorts = {
            "first": ["ann-0", "ann-1"],
            "second": ["ann-0", "ann-2"],
        }
        forced_index = disagreement.cohort_index(forced_cohorts)
        self.assertEqual(forced_index["ann-0"], "first")
        for annotator in ("ann-0", "ann-1", "ann-2", "unknown"):
            self.assertEqual(
                disagreement.cohort_of(annotator, forced_index),
                naive_cohort_of(annotator, forced_cohorts),
            )

        forced_items = [
            {
                "id": "forced",
                "labels": {
                    "three_way_tie": {
                        "ann-0": "x",
                        "ann-1": "y",
                        "ann-2": "z",
                    },
                    "singleton": {"ann-0": "x"},
                    "repeated": {
                        "ann-0": "x",
                        "ann-1": "x",
                        "ann-2": "y",
                    },
                },
            }
        ]
        forced_structures = {
            ("forced", question): {
                "item": "forced",
                "question": question,
                "value_fork": False,
                "no_ground": False,
                "structured": False,
                "majority_share": 1.0,
            }
            for question in forced_items[0]["labels"]
        }
        self.assertEqual(
            disagreement.reliability(
                forced_items, forced_structures, forced_cohorts
            ),
            naive_reliability(forced_items, forced_structures, forced_cohorts),
        )

        rng = random.Random(8675309)
        labels = ("x", "y", "z", "w")
        for trial in range(250):
            annotators = [
                "trial-{}-ann-{}".format(trial, index)
                for index in range(rng.randint(1, 10))
            ]
            cohorts = {}
            for cohort_number in range(rng.randint(1, 4)):
                members = [
                    annotator
                    for annotator in annotators
                    if rng.random() < 0.65
                ]
                if not members:
                    members = [rng.choice(annotators)]
                cohorts["cohort-{}".format(cohort_number)] = members
            optimized_index = disagreement.cohort_index(cohorts)
            for annotator in annotators + ["unknown"]:
                self.assertEqual(
                    disagreement.cohort_of(annotator, optimized_index),
                    naive_cohort_of(annotator, cohorts),
                )

            item = {"id": "trial-{}".format(trial), "labels": {}}
            structures = {}
            for question_number in range(rng.randint(1, 5)):
                question = "q{}".format(question_number)
                voters = rng.sample(
                    annotators, rng.randint(1, len(annotators))
                )
                item["labels"][question] = {
                    annotator: rng.choice(labels) for annotator in voters
                }
                confident = rng.random() < 0.75
                structures[(item["id"], question)] = {
                    "item": item["id"],
                    "question": question,
                    "value_fork": False,
                    "no_ground": False,
                    "structured": False,
                    "majority_share": 1.0 if confident else 0.0,
                }
            self.assertEqual(
                disagreement.reliability([item], structures, cohorts),
                naive_reliability([item], structures, cohorts),
            )

    def test_bill_and_reliability_are_pinned_in_the_essay(self):
        triage = _pipeline()["triage"]
        cells = triage["cells"]
        contested = [cell for cell in cells if cell["verdict"].startswith("CONTESTED")]
        essay = _essay("the-groundless-label.md")
        readme = _essay("README.md")
        tokens = [
            "CONFIDENT  (the collapse is honest) ...... {}".format(
                sum(cell["verdict"] == "CONFIDENT" for cell in cells)
            ),
            "CONTESTED  (the collapse destroys signal)  {}".format(len(contested)),
            "VALUE FORKS (cohorts truly diverge) ...... {}".format(
                sum(cell["value_fork"] for cell in cells)
            ),
            "MANUFACTURED CONSENSUS (minority silenced)  {}".format(
                sum(cell["manufactured_consensus"] for cell in cells)
            ),
            "{:.2f} bits".format(sum(cell["entropy_bits"] for cell in contested)),
            "{:.2f} reliability".format(_pipeline()["triage"]["reliability"]["b4"]),
            "`CONFIDENT` cells only",
        ]
        for token in tokens:
            with self.subTest(token=token):
                self.assertIn(token, essay)

        readme_tokens = [
            "cells total .............................. {}".format(len(cells)),
            "CONFIDENT  (the collapse is honest) ...... {}".format(
                sum(cell["verdict"] == "CONFIDENT" for cell in cells)
            ),
            "CONTESTED  (the collapse destroys signal)  {}".format(len(contested)),
            "REVIEW     (route to a human) ............ {}".format(
                sum(cell["verdict"] == "REVIEW" for cell in cells)
            ),
            "cells with a likely ERROR (real noise) ... {}".format(
                sum(
                    any(dissent["kind"] == "error" for dissent in cell["dissents"])
                    for cell in cells
                )
            ),
            "VALUE FORKS (cohorts truly diverge) ...... {}".format(
                sum(cell["value_fork"] for cell in cells)
            ),
            "MANUFACTURED CONSENSUS (minority silenced)  {}".format(
                sum(cell["manufactured_consensus"] for cell in cells)
            ),
            "disagreement entropy discarded ........... {:.2f} bits".format(
                sum(cell["entropy_bits"] for cell in contested)
            ),
            "b4: {:.2f}".format(triage["reliability"]["b4"]),
        ]
        for token in readme_tokens:
            with self.subTest(readme_token=token):
                self.assertIn(token, readme)

        output = _pipeline()["output"]["disagreement.py"]
        bill_start = output.rfind("=" * 78, 0, output.index("THE BILL"))
        bill_end = output.index("\n\n" + "=" * 78 + "\nREAD THIS", bill_start)
        self.assertIn(output[bill_start:bill_end], readme)


class BayesClaims(unittest.TestCase):
    def test_distribution_loss_entropy_routing_and_uncertainty(self):
        counts = bayes_optimal.cell_counts(DATASET, "img1", "ribbon")
        distribution = bayes_optimal.normalize(counts)
        self.assertEqual(
            distribution,
            {
                "scarf": 0.375,
                "plastic": 0.25,
                "ribbon": 0.125,
                "choker": 0.125,
                "unknown": 0.125,
            },
        )
        entropy = bayes_optimal.entropy_bits(distribution)
        uniform = {label: 1 / len(distribution) for label in distribution}
        cross_entropy = bayes_optimal.cross_entropy_bits(distribution, uniform)
        divergence = bayes_optimal.kl_bits(distribution, uniform)
        self.assertAlmostEqual(entropy, 2.156, places=3)
        self.assertAlmostEqual(cross_entropy, 2.322, places=3)
        self.assertAlmostEqual(divergence, 0.166, places=3)
        self.assertAlmostEqual(1 - distribution["scarf"], 0.625, places=3)

        explicit_entropies = [
            bayes_optimal.entropy_bits(
                bayes_optimal.normalize(bayes_optimal.cell_counts(DATASET, item_id, "explicit"))
            )
            for item_id in ("img3", "img1", "img2")
        ]
        self.assertAlmostEqual(explicit_entropies[0], 0.0, places=3)
        self.assertAlmostEqual(explicit_entropies[1], 0.544, places=3)
        self.assertAlmostEqual(explicit_entropies[2], 1.0, places=3)

        routed = Counter()
        review_cost = 0.2
        for item in DATASET["items"]:
            for question in DATASET["questions"]:
                q = bayes_optimal.normalize(
                    bayes_optimal.cell_counts(DATASET, item["id"], question)
                )
                classes = sorted(q)
                costs = [
                    {label: (0 if label == chosen else 1) for label in classes}
                    for chosen in classes
                ] + [review_cost]
                action, _ = bayes_optimal.bayes_action(q, costs)
                routed["label" if action < len(classes) else "review"] += 1
        self.assertEqual(routed, Counter({"label": 12, "review": 6}))

        small = bayes_optimal.dirichlet_mean_sd({0: 1, 1: 1}, [0, 1])[0][1]
        large = bayes_optimal.dirichlet_mean_sd({0: 500, 1: 500}, [0, 1])[0][1]
        self.assertAlmostEqual(small, 0.2236, places=4)
        self.assertAlmostEqual(large, 0.0158, places=4)

    def test_bayes_values_are_pinned_in_the_essay(self):
        distribution = bayes_optimal.normalize(
            bayes_optimal.cell_counts(DATASET, "img1", "ribbon")
        )
        entropy = bayes_optimal.entropy_bits(distribution)
        uniform = {label: 1 / len(distribution) for label in distribution}
        essay = _essay("the-bayes-optimal-label.md")
        small = bayes_optimal.dirichlet_mean_sd({0: 1, 1: 1}, [0, 1])[0][1]
        large = bayes_optimal.dirichlet_mean_sd({0: 500, 1: 500}, [0, 1])[0][1]
        tokens = [
            "H = {:.3f}".format(entropy),
            "{:.3f}` (`KL = {:.3f}`)".format(
                bayes_optimal.cross_entropy_bits(distribution, uniform),
                bayes_optimal.kl_bits(distribution, uniform),
            ),
            "expected loss `{:.3f}`".format(1 - distribution["scarf"]),
            "`H = {:.3f}`".format(
                bayes_optimal.entropy_bits(
                    bayes_optimal.normalize(
                        bayes_optimal.cell_counts(DATASET, "img1", "explicit")
                    )
                )
            ),
            "6 cells route to review",
            "other 12 collapse to a label",
            "`{:.3f}` versus `{:.3f}`".format(small, large),
        ]
        for token in tokens:
            with self.subTest(token=token):
                self.assertIn(token, essay)


class AggregationClaims(unittest.TestCase):
    def test_regimes_forks_and_condorcet_sequences(self):
        may = sum(
            DATASET["questions"][question]["type"] == "binary"
            for item in DATASET["items"]
            for question in item["labels"]
        )
        arrow = 18 - may
        self.assertEqual((may, arrow), (12, 6))

        ribbon_counts = aggregation.cell_counts(_item("img1")["labels"]["ribbon"])
        winner, top, tie, _ = aggregation.plurality(ribbon_counts)
        self.assertEqual(winner, "scarf")
        self.assertFalse(tie)
        self.assertEqual(top / sum(ribbon_counts.values()), 0.375)

        forks = []
        for item in DATASET["items"]:
            for question, votes in item["labels"].items():
                if DATASET["questions"][question]["type"] != "binary":
                    continue
                counts = aggregation.cell_counts(votes)
                shipped, _, is_tie, _ = aggregation.plurality(counts)
                if is_tie:
                    cohort_a = Counter(votes[a] for a in DATASET["cohorts"]["A"])
                    a_winner = str(max(cohort_a, key=cohort_a.get))
                    labels = DATASET["questions"][question]["labels"]
                    forks.append(
                        (
                            item["id"],
                            question,
                            labels[shipped],
                            shipped == a_winner,
                        )
                    )
        self.assertEqual([fork[0] for fork in forks], ["img2", "img4"])
        self.assertEqual([fork[2] for fork in forks], ["safe", "safe"])
        self.assertTrue(all(fork[3] for fork in forks))

        ns = [1, 3, 9, 27, 81]
        good = [aggregation.majority_correct(n, 0.6) for n in ns]
        bad = [aggregation.majority_correct(n, 0.4) for n in ns]
        for actual, expected in zip(good, [0.6000, 0.6480, 0.7334, 0.8553, 0.9659]):
            self.assertAlmostEqual(actual, expected, places=4)
        for actual, expected in zip(bad, [0.4000, 0.3520, 0.2666, 0.1447, 0.0341]):
            self.assertAlmostEqual(actual, expected, places=4)
        self.assertAlmostEqual(aggregation.effective_n(81, 0.3), 3.24, places=2)
        self.assertAlmostEqual(1 / 0.3, 3.33, places=2)
        self.assertEqual(aggregation.nearest_odd(aggregation.effective_n(81, 0.3)), 3)

    def test_aggregation_values_are_pinned_in_the_essay(self):
        ns = [1, 3, 9, 27, 81]
        good = [aggregation.majority_correct(n, 0.6) for n in ns]
        bad = [aggregation.majority_correct(n, 0.4) for n in ns]
        ribbon_counts = aggregation.cell_counts(_item("img1")["labels"]["ribbon"])
        _, top, _, _ = aggregation.plurality(ribbon_counts)
        essay = _essay("the-aggregation-theorem.md")
        tokens = [
            "12\ncells in May's world, 6 in Arrow's",
            "{:.1f}%".format(100 * top / sum(ribbon_counts.values())),
            "`img2 / explicit`: ships **safe**",
            "`img4 / explicit`: ships **safe**",
            " → ".join("{:.2f}".format(value) for value in good),
            "1/ρ ≈ {:.1f}".format(1 / 0.3),
            " → ".join("{:.2f}".format(value) for value in bad),
        ]
        for token in tokens:
            with self.subTest(token=token):
                self.assertIn(token, essay)


class FrustrationClaims(unittest.TestCase):
    def test_ground_states_and_zero_temperature_quench(self):
        explicit_j, explicit_annotators = frustration.coupling(DATASET, "explicit")
        explicit_blobs, explicit_frustration, explicit_total = frustration.ground_state(
            explicit_j, explicit_annotators
        )
        expected_cohorts = {
            frozenset(DATASET["cohorts"]["A"]),
            frozenset(DATASET["cohorts"]["B"]),
        }
        self.assertEqual({frozenset(blob) for blob in explicit_blobs}, expected_cohorts)
        self.assertAlmostEqual(explicit_frustration, 0.46875, places=5)
        self.assertAlmostEqual(explicit_total, 9.0625, places=4)
        self.assertAlmostEqual(explicit_frustration / explicit_total, 0.05, places=2)

        synthetic_j, synthetic_annotators = frustration.coupling(DATASET, "synthetic")
        synthetic_blobs, synthetic_frustration, synthetic_total = frustration.ground_state(
            synthetic_j, synthetic_annotators
        )
        expected_synthetic_partition = {
            frozenset({"a3", "b3", "b4"}),
            frozenset({"a1", "a2", "a4", "b1", "b2"}),
        }
        self.assertEqual(
            {frozenset(blob) for blob in synthetic_blobs},
            expected_synthetic_partition,
        )
        self.assertAlmostEqual(synthetic_frustration, 1.03125, places=5)
        self.assertAlmostEqual(synthetic_total, 5.46875, places=5)
        self.assertAlmostEqual(synthetic_frustration / synthetic_total, 0.19, places=2)
        self.assertGreater(synthetic_frustration / synthetic_total, 0.15)

        cells = [
            ("img2", "synthetic", 0.00, 1),
            ("img1", "ribbon", 2.16, 1),
            ("img2", "explicit", 1.00, 2),
        ]
        for item_id, question, expected_entropy, expected_degeneracy in cells:
            counts = Counter(_item(item_id)["labels"][question].values())
            soft, _ = frustration.temper(counts, 1.0)
            _, degeneracy = frustration.temper(counts, 0.0)
            self.assertAlmostEqual(
                frustration.entropy_bits(soft.values()), expected_entropy, places=2
            )
            self.assertEqual(degeneracy, expected_degeneracy)

    def test_frustration_values_are_pinned_in_the_essay(self):
        explicit_j, annotators = frustration.coupling(DATASET, "explicit")
        _, residual, total = frustration.ground_state(explicit_j, annotators)
        synthetic_j, synthetic_annotators = frustration.coupling(DATASET, "synthetic")
        synthetic_blobs, _, _ = frustration.ground_state(
            synthetic_j, synthetic_annotators
        )
        dissenters = min(synthetic_blobs, key=lambda blob: (len(blob), blob))
        ribbon = Counter(_item("img1")["labels"]["ribbon"].values())
        soft, _ = frustration.temper(ribbon, 1.0)
        entropy = frustration.entropy_bits(soft.values())
        essay = _essay("the-frustrated-label.md")
        self.assertIn("{}% residual frustration".format(round(100 * residual / total)), essay)
        self.assertIn("{:.2f} bits".format(entropy), essay)
        self.assertIn("destroys **all {:.2f}**".format(entropy), essay)
        self.assertIn("37.5% minority", essay)
        self.assertIn("**degenerate**", essay)
        self.assertIn(
            "scattered dissent ({})".format(
                ", ".join("`{}`".format(annotator) for annotator in dissenters)
            ),
            essay,
        )
        self.assertNotIn("lone contrarian", essay)
        self.assertIn("impurities, not a fork", essay)


class TopologyClaims(unittest.TestCase):
    @staticmethod
    def _complex(question, floor):
        vertices, edges, triangles, unaligned, _ = topology.agreement_complex(
            DATASET, question, noise_floor=floor
        )
        return (
            topology.betti(vertices, edges, triangles),
            topology.components_of(vertices, edges),
            unaligned,
        )

    def test_circulation_complexes_and_ring(self):
        transitive = {(0, 1): 1, (1, 2): 1, (2, 0): -2}
        cycle = {(0, 1): 1, (1, 2): 1, (2, 0): 1}
        self.assertEqual(topology.circulation(transitive), 0)
        self.assertEqual(topology.circulation(cycle), 3)
        rewards, circulation_component = topology.best_reward(cycle)
        self.assertEqual(rewards, {0: 0.0, 1: 0.0, 2: 0.0})
        self.assertEqual(circulation_component, 1.0)
        self.assertEqual(
            abs(topology.circulation(cycle)) / sum(abs(value) for value in cycle.values()),
            1.0,
        )

        explicit = self._complex("explicit", topology.NOISE_FLOOR)
        self.assertEqual(explicit[0], (2, 0))
        self.assertEqual(
            explicit[1],
            [["a1", "a2", "a4"], ["b1", "b2", "b4"]],
        )
        self.assertEqual(explicit[2], ["a3", "b3"])

        synthetic = self._complex("synthetic", topology.NOISE_FLOOR)
        self.assertEqual(synthetic[0], (1, 0))
        self.assertEqual(synthetic[1], [["a3", "b3"]])
        self.assertEqual(synthetic[2], ["a1", "a2", "a4", "b1", "b2", "b4"])

        ring_vertices = ["c1", "c2", "c3", "c4"]
        ring_edges = [("c1", "c2"), ("c2", "c3"), ("c3", "c4"), ("c1", "c4")]
        self.assertEqual(topology.betti(ring_vertices, ring_edges, []), (1, 1))
        self.assertEqual(topology.NOISE_FLOOR, 0.25)

    def test_floor_sensitivity_and_boundary_failures(self):
        expected_cores = [["a1", "a2", "a4"], ["b1", "b2", "b4"]]

        for hundredths in range(10, 76, 5):
            floor = hundredths / 100.0
            with self.subTest(question="explicit", floor=floor):
                betti, components, _ = self._complex("explicit", floor)
                self.assertEqual(betti, (2, 0))
                self.assertEqual(components, expected_cores)

        for hundredths in range(20, 101, 5):
            floor = hundredths / 100.0
            with self.subTest(question="synthetic", floor=floor):
                betti, _, _ = self._complex("synthetic", floor)
                self.assertEqual(betti, (1, 0))

        joint_floors = []
        for hundredths in range(0, 101, 5):
            floor = hundredths / 100.0
            explicit_betti, explicit_components, _ = self._complex("explicit", floor)
            synthetic_betti, _, _ = self._complex("synthetic", floor)
            if (
                explicit_betti == (2, 0)
                and explicit_components == expected_cores
                and synthetic_betti == (1, 0)
            ):
                joint_floors.append(floor)
        self.assertEqual(joint_floors, [value / 100.0 for value in range(20, 76, 5)])
        stable_band = (min(joint_floors), max(joint_floors))
        self.assertEqual(stable_band, (0.20, 0.75))
        self.assertGreater(topology.NOISE_FLOOR, stable_band[0])
        self.assertLess(topology.NOISE_FLOOR, stable_band[1])

        for floor in (0.00, 0.05):
            with self.subTest(boundary="low-explicit", floor=floor):
                self.assertEqual(self._complex("explicit", floor)[0][0], 1)
        for floor in (0.80, 0.85, 0.90, 0.95, 1.00):
            with self.subTest(boundary="high-explicit", floor=floor):
                _, components, unaligned = self._complex("explicit", floor)
                self.assertEqual(components, [["a1", "a2", "a4"], ["b1", "b2"]])
                self.assertIn("b4", unaligned)
        for floor in (0.00, 0.05, 0.10, 0.15):
            with self.subTest(boundary="low-synthetic", floor=floor):
                self.assertEqual(self._complex("synthetic", floor)[0][0], 2)

    def test_topology_values_are_pinned_in_the_essay(self):
        explicit_betti, explicit_components, _ = self._complex(
            "explicit", topology.NOISE_FLOOR
        )
        synthetic_betti, synthetic_components, _ = self._complex(
            "synthetic", topology.NOISE_FLOOR
        )
        essay = _essay("the-topological-label.md")
        self.assertIn(
            "{}, not 0".format(topology.circulation({(0, 1): 1, (1, 2): 1, (2, 0): 1})),
            essay,
        )
        self.assertIn(
            "(b₀, b₁) = ({}, {})".format(synthetic_betti[0], synthetic_betti[1]), essay
        )
        self.assertIn(
            "(b₀, b₁) = ({}, {})".format(explicit_betti[0], explicit_betti[1]), essay
        )
        self.assertIn("{a3, b3}", essay)
        self.assertEqual(synthetic_components, [["a3", "b3"]])
        for component in explicit_components:
            self.assertIn("{" + ", ".join(component) + "}", essay)
        self.assertIn("(b₀, b₁) = (1, 1)", essay)
        self.assertIn("{:.0%}".format(topology.NOISE_FLOOR), essay)

        expected_cores = [["a1", "a2", "a4"], ["b1", "b2", "b4"]]
        joint_floors = []
        for hundredths in range(0, 101, 5):
            floor = hundredths / 100.0
            explicit_state = self._complex("explicit", floor)
            synthetic_state = self._complex("synthetic", floor)
            if (
                explicit_state[0] == (2, 0)
                and explicit_state[1] == expected_cores
                and synthetic_state[0] == (1, 0)
            ):
                joint_floors.append(floor)
        stable_band = (min(joint_floors), max(joint_floors))
        self.assertIn(
            "stable from {:.2f} through {:.2f}".format(*stable_band), essay
        )
        self.assertIn("shipped {:.2f} sits".format(topology.NOISE_FLOOR), essay)


class GeometryClaims(unittest.TestCase):
    def test_centres_gaps_and_disjoint_support(self):
        item = _item("img1")
        cohort_a = _cohort_distribution(item, "ribbon", DATASET["cohorts"]["A"])
        cohort_b = _cohort_distribution(item, "ribbon", DATASET["cohorts"]["B"])
        arithmetic = geometry.arithmetic_mean([cohort_a, cohort_b])
        geometric = geometry.geometric_mean([cohort_a, cohort_b])
        self.assertEqual(len(arithmetic), 5)
        self.assertEqual(set(geometric), {"scarf", "plastic"})
        self.assertAlmostEqual(geometry.tv(arithmetic, geometric), 0.375, places=3)

        ordinal_a = {0: 0.7, 1: 0.3, 2: 0.0}
        ordinal_b = {0: 0.0, 1: 0.3, 2: 0.7}
        ordinal_arithmetic = geometry.arithmetic_mean([ordinal_a, ordinal_b])
        ordinal_geometric = geometry.geometric_mean([ordinal_a, ordinal_b])
        self.assertAlmostEqual(
            geometry.tv(ordinal_arithmetic, ordinal_geometric), 0.70, places=2
        )
        wasserstein = geometry.wasserstein_bary_1d(ordinal_a, ordinal_b)
        self.assertAlmostEqual(sum(wasserstein.values()), 1.0)
        self.assertAlmostEqual(sum(rank * mass for rank, mass in wasserstein.items()), 1.0)
        fisher_rao = geometry.fisher_rao_mean(ordinal_a, ordinal_b)
        self.assertEqual(max(fisher_rao, key=fisher_rao.get), 1)

        fork = _item("img2")
        fork_a = _cohort_distribution(fork, "explicit", DATASET["cohorts"]["A"])
        fork_b = _cohort_distribution(fork, "explicit", DATASET["cohorts"]["B"])
        self.assertIsNone(geometry.geometric_mean([fork_a, fork_b]))
        self.assertIn("gap = undefined", _pipeline()["output"]["geometry.py"])
        record = next(
            record
            for record in _pipeline()["records"]
            if record["item"] == "img2" and record["question"] == "explicit"
        )
        self.assertIsNone(record["measures"]["geometry_gap"])

        gaps = {}
        for candidate in DATASET["items"]:
            for question in DATASET["questions"]:
                a = _cohort_distribution(candidate, question, DATASET["cohorts"]["A"])
                b = _cohort_distribution(candidate, question, DATASET["cohorts"]["B"])
                am = geometry.arithmetic_mean([a, b])
                gm = geometry.geometric_mean([a, b])
                gap = None if gm is None else geometry.tv(am, gm)
                if gap is None or gap > 1e-9:
                    gaps["{}/{}".format(candidate["id"], question)] = gap
        self.assertEqual(gaps["img2/explicit"], None)
        self.assertAlmostEqual(gaps["img1/ribbon"], 0.375, places=3)
        self.assertAlmostEqual(gaps["img3/ribbon"], 0.250, places=3)
        remainder = {
            key: value
            for key, value in gaps.items()
            if key not in {"img2/explicit", "img1/ribbon", "img3/ribbon"}
        }
        self.assertEqual(len(remainder), 6)
        for gap in remainder.values():
            self.assertAlmostEqual(gap, 0.125, places=3)

    def test_geometry_values_are_pinned_in_the_essay(self):
        item = _item("img1")
        a = _cohort_distribution(item, "ribbon", DATASET["cohorts"]["A"])
        b = _cohort_distribution(item, "ribbon", DATASET["cohorts"]["B"])
        arithmetic = geometry.arithmetic_mean([a, b])
        geometric = geometry.geometric_mean([a, b])
        essay = _essay("the-geometric-label.md")
        number_words = {5: "five"}
        self.assertIn("keeps all {}".format(number_words[len(arithmetic)]), essay)
        self.assertIn("keeps only `scarf` and `plastic`", essay)
        self.assertIn("`{:.3f}`".format(geometry.tv(arithmetic, geometric)), essay)
        ordinal_a = {0: 0.7, 1: 0.3, 2: 0.0}
        ordinal_b = {0: 0.0, 1: 0.3, 2: 0.7}
        ordinal_gap = geometry.tv(
            geometry.arithmetic_mean([ordinal_a, ordinal_b]),
            geometry.geometric_mean([ordinal_a, ordinal_b]),
        )
        self.assertIn("= {:.2f}".format(ordinal_gap), essay)
        self.assertIn("**undefined**, not `0.500`", essay)


class BringYourOwnDataClaims(unittest.TestCase):
    TOOLS = ("disagreement.py", "soft_labels.py", "resolution.py")

    def test_default_output_is_the_callers_working_directory(self):
        with tempfile.TemporaryDirectory(prefix="groundless-default-out-") as temp:
            caller_dir = Path(temp)
            for tool in self.TOOLS:
                subprocess.run(
                    [sys.executable, str(ROOT / tool)],
                    cwd=str(caller_dir),
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    universal_newlines=True,
                )

            self.assertTrue((caller_dir / "triage.json").is_file())
            self.assertTrue((caller_dir / "soft_labels.jsonl").is_file())
            self.assertTrue((caller_dir / "soft_labels.csv").is_file())
            self.assertTrue((caller_dir / "governance.jsonl").is_file())
            self.assertEqual(
                len(_load_jsonl(caller_dir / "resolution_records.jsonl")),
                18,
            )

    def test_data_and_out_round_trip(self):
        with tempfile.TemporaryDirectory(prefix="groundless-byod-") as temp:
            temp_path = Path(temp)
            data_path = temp_path / "inputs" / "custom-labels.json"
            out_dir = temp_path / "generated"
            caller_dir = temp_path / "caller"
            data_path.parent.mkdir()
            caller_dir.mkdir()
            shutil.copy2(str(ROOT / "data" / "labels.json"), str(data_path))

            for tool in self.TOOLS:
                subprocess.run(
                    [
                        sys.executable,
                        str(ROOT / tool),
                        "--data",
                        str(data_path),
                        "--out",
                        str(out_dir),
                    ],
                    cwd=str(caller_dir),
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    universal_newlines=True,
                )

            self.assertTrue((out_dir / "triage.json").is_file())
            self.assertTrue((out_dir / "soft_labels.jsonl").is_file())
            self.assertTrue((out_dir / "soft_labels.csv").is_file())
            self.assertTrue((out_dir / "governance.jsonl").is_file())
            self.assertTrue((out_dir / "resolution_records.jsonl").is_file())
            self.assertEqual(list(caller_dir.iterdir()), [])

            byod_triage = _load_json(out_dir / "triage.json")
            no_arg_triage = _pipeline()["triage"]
            self.assertEqual(len(byod_triage["cells"]), 18)
            self.assertEqual(
                Counter(cell["verdict"] for cell in byod_triage["cells"]),
                Counter(cell["verdict"] for cell in no_arg_triage["cells"]),
            )
            self.assertEqual(len(_load_jsonl(out_dir / "resolution_records.jsonl")), 18)

    def test_bad_inputs_are_rejected_with_specific_messages(self):
        cases = []
        missing_questions = copy.deepcopy(DATASET)
        del missing_questions["questions"]
        cases.append((missing_questions, "missing required field(s): questions"))

        unknown_annotator = copy.deepcopy(DATASET)
        unknown_annotator["items"][0]["labels"]["explicit"]["ghost"] = 0
        cases.append((unknown_annotator, "references unknown annotator(s): ghost"))

        with tempfile.TemporaryDirectory(prefix="groundless-bad-input-") as temp:
            temp_path = Path(temp)
            for index, (dataset, expected) in enumerate(cases):
                data_path = temp_path / "bad-{}.json".format(index)
                data_path.write_text(json.dumps(dataset), encoding="utf-8")
                result = subprocess.run(
                    [
                        sys.executable,
                        str(ROOT / "disagreement.py"),
                        "--data",
                        str(data_path),
                        "--out",
                        str(temp_path / "out-{}".format(index)),
                    ],
                    cwd=str(temp_path),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    universal_newlines=True,
                )
                with self.subTest(case=index):
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn("labels.json:", result.stderr)
                    self.assertIn(expected, result.stderr)

    def test_single_cohort_input_reaches_resolution(self):
        dataset = {
            "questions": {
                "sentiment": {
                    "type": "binary",
                    "labels": {"0": "negative", "1": "positive"},
                }
            },
            "annotators": ["ann-a", "ann-b"],
            "cohorts": {"all": ["ann-a", "ann-b"]},
            "items": [
                {
                    "id": "case-1",
                    "labels": {"sentiment": {"ann-a": 1, "ann-b": 0}},
                },
                {
                    "id": "case-2",
                    "labels": {"sentiment": {"ann-a": 0, "ann-b": 0}},
                },
            ],
        }
        with tempfile.TemporaryDirectory(prefix="groundless-one-cohort-") as temp:
            temp_path = Path(temp)
            data_path = temp_path / "labels.json"
            out_dir = temp_path / "out"
            data_path.write_text(json.dumps(dataset), encoding="utf-8")
            for tool in self.TOOLS:
                subprocess.run(
                    [
                        sys.executable,
                        str(ROOT / tool),
                        "--data",
                        str(data_path),
                        "--out",
                        str(out_dir),
                    ],
                    cwd=str(temp_path),
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    universal_newlines=True,
                )
            records = _load_jsonl(out_dir / "resolution_records.jsonl")
            self.assertEqual(len(records), 2)
            self.assertTrue(
                all(record["measures"]["geometry_gap"] is None for record in records)
            )

    def test_cli_help_and_demo_pinned_proofs(self):
        for tool in self.TOOLS:
            result = subprocess.run(
                [sys.executable, str(ROOT / tool), "--help"],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
            )
            with self.subTest(tool=tool):
                self.assertIn("--data", result.stdout)
                self.assertIn("--out", result.stdout)
                self.assertIn("same --data and --out", result.stdout)

        for proof in (
            "aggregation.py",
            "frustration.py",
            "topology.py",
            "geometry.py",
            "bayes_optimal.py",
        ):
            source = (ROOT / proof).read_text(encoding="utf-8")
            with self.subTest(proof=proof):
                self.assertIn("intentionally pinned to data/labels.json", source)


class ChaosNLIAdapterClaims(unittest.TestCase):
    ADAPTER = ROOT / "adapters" / "chaosnli.py"
    FIXTURE = ROOT / "adapters" / "fixtures" / "chaosnli_sample.jsonl"

    def _convert(self, directory):
        output = directory / "labels.json"
        subprocess.run(
            [
                sys.executable,
                str(self.ADAPTER),
                str(self.FIXTURE),
                "--out",
                str(output),
            ],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
        )
        return output

    def test_anonymous_counts_round_trip_to_exact_soft_labels(self):
        source = _load_jsonl(self.FIXTURE)
        source_counts = {
            record["uid"]: {str(label): count for label, count in record["label_counter"].items()}
            for record in source
        }
        with tempfile.TemporaryDirectory(prefix="groundless-chaosnli-") as temp:
            temp_path = Path(temp)
            labels_path = self._convert(temp_path)
            dataset = _load_json(labels_path)

            self.assertEqual(
                dataset["questions"]["nli_label"],
                {
                    "type": "categorical",
                    "labels": ["e", "n", "c", "1", "2"],
                    "note": (
                        "Raw ChaosNLI categories: e=entailment, n=neutral, "
                        "c=contradiction; alphaNLI uses 1=hypothesis 1 and "
                        "2=hypothesis 2."
                    ),
                },
            )
            about = dataset["_about"].lower()
            for caveat in (
                "unique to each item",
                "reliability",
                "value-fork",
                "not meaningful",
                "distribution, entropy, and soft labels",
            ):
                self.assertIn(caveat, about)

            self.assertEqual(len(dataset["items"]), len(source))
            self.assertEqual(len(dataset["annotators"]), 70)
            self.assertEqual(dataset["cohorts"], {"crowd": dataset["annotators"]})
            annotators_by_item = []
            for item in dataset["items"]:
                votes = item["labels"]["nli_label"]
                annotators_by_item.append(set(votes))
                self.assertEqual(Counter(votes.values()), Counter(source_counts[item["id"]]))
            for index, annotators in enumerate(annotators_by_item):
                self.assertTrue(
                    annotators.isdisjoint(
                        set().union(*annotators_by_item[:index])
                        if index
                        else set()
                    )
                )

            out_dir = temp_path / "run"
            for tool in ("disagreement.py", "soft_labels.py", "resolution.py"):
                subprocess.run(
                    [
                        sys.executable,
                        str(ROOT / tool),
                        "--data",
                        str(labels_path),
                        "--out",
                        str(out_dir),
                    ],
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    universal_newlines=True,
                )

            triage = _load_json(out_dir / "triage.json")
            soft = {
                record["item_id"]: record
                for record in _load_jsonl(out_dir / "soft_labels.jsonl")
            }
            for cell in triage["cells"]:
                counts = source_counts[cell["item"]]
                total = sum(counts.values())
                expected = {
                    label: count / total
                    for label, count in counts.items()
                    if count
                }
                entropy = -sum(
                    probability * math.log2(probability)
                    for probability in expected.values()
                )
                self.assertEqual(soft[cell["item"]]["soft_label"], expected)
                self.assertAlmostEqual(cell["entropy_bits"], entropy, places=3)
                self.assertFalse(cell["value_fork"])
            records = _load_jsonl(out_dir / "resolution_records.jsonl")
            self.assertEqual(len(records), len(source))
            self.assertTrue(
                all(record["measures"]["geometry_gap"] is None for record in records)
            )

    def test_shards_cover_fixture_exactly_and_reject_corruption(self):
        source = _load_jsonl(self.FIXTURE)
        source_uids = [record["uid"] for record in source]
        with tempfile.TemporaryDirectory(prefix="groundless-chaosnli-shards-") as temp:
            temp_path = Path(temp)
            manifests = []
            shard_uids = []
            for index in range(3):
                output = temp_path / "shard-{}.json".format(index)
                subprocess.run(
                    [
                        sys.executable,
                        str(self.ADAPTER),
                        str(self.FIXTURE),
                        "--shard-index",
                        str(index),
                        "--shard-count",
                        "3",
                        "--out",
                        str(output),
                    ],
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    universal_newlines=True,
                )
                manifest = _load_json(Path(str(output) + ".manifest.json"))
                manifests.append(manifest)
                shard_uids.append(manifest["uids"])

            self.assertEqual([len(uids) for uids in shard_uids], [2, 2, 3])
            self.assertEqual(
                [uid for uids in shard_uids for uid in uids], source_uids
            )
            self.assertEqual(
                len({uid for uids in shard_uids for uid in uids}), len(source_uids)
            )
            aggregate = chaosnli_adapter.aggregate_shard_manifests(
                manifests, source_uids
            )
            self.assertEqual(aggregate["record_count"], 7)
            self.assertEqual(aggregate["uids"], source_uids)

            duplicate = copy.deepcopy(manifests)
            duplicate[1]["uids"][0] = duplicate[0]["uids"][-1]
            duplicate[1]["uid_first"] = duplicate[1]["uids"][0]
            duplicate[1]["uids_sha256"] = chaosnli_adapter._uids_sha256(
                duplicate[1]["uids"]
            )
            with self.assertRaisesRegex(
                chaosnli_adapter.ManifestError, "duplicate uid"
            ):
                chaosnli_adapter.aggregate_shard_manifests(duplicate, source_uids)

            gap = copy.deepcopy(manifests)
            gap[1]["uids"][0] = "synthetic-missing-uid"
            gap[1]["uid_first"] = gap[1]["uids"][0]
            gap[1]["uids_sha256"] = chaosnli_adapter._uids_sha256(gap[1]["uids"])
            with self.assertRaisesRegex(
                chaosnli_adapter.ManifestError, "gap, overlap, or order change"
            ):
                chaosnli_adapter.aggregate_shard_manifests(gap, source_uids)

    def test_offset_limit_matches_shard_math_and_manifests_are_deterministic(self):
        with tempfile.TemporaryDirectory(prefix="groundless-chaosnli-ranges-") as temp:
            temp_path = Path(temp)
            for index, (offset, limit) in enumerate(((0, 2), (2, 2), (4, 3))):
                shard = temp_path / "shard-{}.json".format(index)
                ranged = temp_path / "range-{}.json".format(index)
                subprocess.run(
                    [
                        sys.executable,
                        str(self.ADAPTER),
                        str(self.FIXTURE),
                        "--shard-index",
                        str(index),
                        "--shard-count",
                        "3",
                        "--out",
                        str(shard),
                    ],
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    universal_newlines=True,
                )
                subprocess.run(
                    [
                        sys.executable,
                        str(self.ADAPTER),
                        str(self.FIXTURE),
                        "--offset",
                        str(offset),
                        "--limit",
                        str(limit),
                        "--out",
                        str(ranged),
                    ],
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    universal_newlines=True,
                )
                self.assertEqual(shard.read_bytes(), ranged.read_bytes())

            first = temp_path / "first.json"
            second = temp_path / "second.json"
            for output in (first, second):
                subprocess.run(
                    [
                        sys.executable,
                        str(self.ADAPTER),
                        str(self.FIXTURE),
                        "--shard-index",
                        "2",
                        "--shard-count",
                        "3",
                        "--out",
                        str(output),
                    ],
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    universal_newlines=True,
                )
            self.assertEqual(
                Path(str(first) + ".manifest.json").read_bytes(),
                Path(str(second) + ".manifest.json").read_bytes(),
            )

    def test_distribution_verifier_rejects_a_broken_converted_record(self):
        records = chaosnli_adapter.load_records(str(self.FIXTURE))
        dataset = chaosnli_adapter.convert(records)
        first_votes = dataset["items"][0]["labels"]["nli_label"]
        first_annotator = next(iter(first_votes))
        first_votes[first_annotator] = "n"
        with self.assertRaisesRegex(ValueError, "distribution mismatch"):
            chaosnli_adapter.verify_converted_distributions(records, dataset)

    def test_bad_counter_and_duplicate_uid_are_rejected(self):
        source = _load_jsonl(self.FIXTURE)
        cases = []
        bad_counter = copy.deepcopy(source[:1])
        bad_counter[0]["label_counter"] = {"e": 4, "1": 6}
        cases.append((bad_counter, "mixes or uses unsupported labels"))
        duplicate = copy.deepcopy(source)
        duplicate[1]["uid"] = duplicate[0]["uid"]
        cases.append((duplicate, "repeats uid"))

        with tempfile.TemporaryDirectory(prefix="groundless-chaosnli-bad-") as temp:
            temp_path = Path(temp)
            for index, (rows, expected) in enumerate(cases):
                input_path = temp_path / "bad-{}.jsonl".format(index)
                output_path = temp_path / "out-{}.json".format(index)
                input_path.write_text(
                    "".join(json.dumps(row) + "\n" for row in rows),
                    encoding="utf-8",
                )
                result = subprocess.run(
                    [
                        sys.executable,
                        str(self.ADAPTER),
                        str(input_path),
                        "--out",
                        str(output_path),
                    ],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    universal_newlines=True,
                )
                with self.subTest(case=index):
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn(expected, result.stderr)
                    self.assertFalse(output_path.exists())

    @unittest.skipUnless(_HAS_JSONSCHEMA, "jsonschema is not installed")
    def test_converted_fixture_matches_the_input_schema(self):
        with tempfile.TemporaryDirectory(prefix="groundless-chaosnli-schema-") as temp:
            labels_path = self._convert(Path(temp))
            schema = _load_json(ROOT / "schema" / "labels.schema.json")
            Draft202012Validator.check_schema(schema)
            Draft202012Validator(schema).validate(_load_json(labels_path))


class MHSPhaseOneClaims(unittest.TestCase):
    FIXTURE = ROOT / "reports" / "mhs" / "fixtures" / "mhs_sample.jsonl"

    @classmethod
    def setUpClass(cls):
        cls.records = mhs_adapter.load_jsonl(str(cls.FIXTURE))
        cls.converted = mhs_adapter.convert_records(cls.records)

    def test_frozen_eligibility_cohorts_primary_filter_and_halt(self):
        converted = self.converted
        self.assertEqual(converted["status"], "ready")
        self.assertIsNone(converted["halt_reason"])
        self.assertEqual(
            converted["counts"],
            {
                "source_records": 245,
                "non_null_judgments": 244,
                "eligible_annotators": 5,
                "conservative_annotators": 2,
                "liberal_annotators": 2,
                "excluded_eligible_annotators": 1,
                "primary_items": 50,
                "reliability_items": 51,
            },
        )
        self.assertEqual(
            converted["primary"]["cohorts"],
            {
                "Conservative": ["c-extreme", "c-slight"],
                "Liberal": ["l-extreme", "l-slight"],
            },
        )
        for ideology in mhs_adapter.CONSERVATIVE_IDEOLOGIES:
            self.assertEqual(
                mhs_adapter.cohort_for_ideology(ideology), "Conservative"
            )
        for ideology in mhs_adapter.LIBERAL_IDEOLOGIES:
            self.assertEqual(mhs_adapter.cohort_for_ideology(ideology), "Liberal")
        for ideology in ("neutral", "no_opinion", None, "Conservative"):
            self.assertIsNone(mhs_adapter.cohort_for_ideology(ideology))

        primary_ids = [item["id"] for item in converted["primary"]["items"]]
        reliability_ids = [
            item["id"] for item in converted["reliability"]["items"]
        ]
        self.assertNotIn("synthetic-filter-fail", primary_ids)
        self.assertIn("synthetic-filter-fail", reliability_ids)
        self.assertEqual(
            converted["primary"]["questions"]["hatespeech"]["labels"],
            ["0", "1", "2"],
        )
        observed_labels = {
            label
            for item in converted["primary"]["items"]
            for label in item["labels"]["hatespeech"].values()
        }
        self.assertEqual(observed_labels, {"0", "1", "2"})
        self.assertFalse(
            {
                "c-below-floor",
                "null-judgment",
                "excluded-neutral",
                "excluded-no-opinion",
                "excluded-null",
            }
            & set(converted["reliability"]["annotators"])
        )

        below_fifty = [
            record
            for record in self.records
            if record["comment_id"]
            not in ("synthetic-050", "synthetic-filter-fail")
        ]
        halted = mhs_adapter.convert_records(below_fifty)
        self.assertEqual(halted["status"], "halt")
        self.assertEqual(halted["counts"]["primary_items"], 49)
        self.assertIn("below the frozen minimum 50", halted["halt_reason"])

    def test_label_normalizes_only_finite_integral_parquet_floats(self):
        self.assertIsNone(mhs_adapter._label(None, 1))
        for value, expected in (
            (0.0, "0"),
            (1.0, "1"),
            (2.0, "2"),
            (0, "0"),
            (1, "1"),
            (2, "2"),
            ("0", "0"),
            ("1", "1"),
            ("2", "2"),
        ):
            self.assertEqual(mhs_adapter._label(value, 1), expected)

        for value in (
            0.5,
            3.0,
            -1.0,
            math.nan,
            math.inf,
            -math.inf,
            True,
            False,
            3,
            -1,
            "0.0",
            "3",
            "-1",
        ):
            with self.subTest(value=value):
                with self.assertRaisesRegex(
                    mhs_adapter.MHSInputError, "one of 0, 1, 2"
                ):
                    mhs_adapter._label(value, 1)

    def test_synthetic_tool_wiring_and_frozen_metric_results(self):
        with tempfile.TemporaryDirectory(prefix="groundless-mhs-") as temp:
            temp_path = Path(temp)
            primary_path = temp_path / "primary-labels.json"
            reliability_path = temp_path / "reliability-labels.json"
            mhs_adapter.write_dataset(self.converted["primary"], primary_path)
            mhs_adapter.write_dataset(
                self.converted["reliability"], reliability_path
            )
            primary_out = temp_path / "primary"
            reliability_out = temp_path / "reliability"
            for data_path, out_dir in (
                (primary_path, primary_out),
                (reliability_path, reliability_out),
            ):
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
                        check=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        universal_newlines=True,
                    )

            triage = _load_json(primary_out / "triage.json")
            by_item = {cell["item"]: cell for cell in triage["cells"]}
            self.assertTrue(by_item["synthetic-001"]["value_fork"])
            self.assertEqual(
                by_item["synthetic-001"]["cohort_majorities"],
                {"Conservative": "0", "Liberal": "2"},
            )
            self.assertFalse(by_item["synthetic-002"]["value_fork"])
            self.assertFalse(by_item["synthetic-003"]["value_fork"])
            self.assertEqual(
                by_item["synthetic-003"]["cohort_majorities"],
                {"Conservative": None, "Liberal": "2"},
            )

            primary_metrics = mhs_study.aggregate_primary(
                self.converted["primary"], triage
            )
            self.assertEqual(primary_metrics["value_fork"]["count"], 1)
            self.assertEqual(primary_metrics["value_fork"]["total"], 50)
            self.assertEqual(
                primary_metrics["manufactured_consensus"]["count"], 1
            )
            self.assertEqual(
                primary_metrics["geometry_gap"]["undefined_count"], 2
            )
            self.assertEqual(
                primary_metrics["geometry_gap"]["defined_count"], 48
            )
            self.assertEqual(
                primary_metrics["geometry_gap"]["defined"]["median"], 0.0
            )

            reliability = mhs_study.aggregate_reliability(
                self.converted["reliability"],
                _load_json(reliability_out / "triage.json"),
            )
            self.assertEqual(reliability["status"], "underpowered/non-applicable")
            self.assertEqual(
                reliability["coverage"],
                {
                    "Conservative": {"eligible": 2, "qualifying": 2},
                    "Liberal": {"eligible": 2, "qualifying": 2},
                },
            )
            self.assertIsNone(reliability["bootstrap_95"])
            underpowered_report = mhs_study.render_report(
                {"primary": primary_metrics, "reliability": reliability},
                self.converted["counts"],
                "synthetic-tool-commit",
            )
            self.assertIn(
                "item-bootstrap 95% [not applicable, not applicable] "
                "(status not applicable; total draws not applicable; valid "
                "estimates not applicable; degenerate resamples not applicable)",
                underpowered_report,
            )

    def test_powered_reliability_mirror_and_production_bootstrap(self):
        conservative = ["fake-c-{:02d}".format(index) for index in range(30)]
        liberal = ["fake-l-{:02d}".format(index) for index in range(30)]
        annotators = conservative + liberal
        items = []
        for index in range(24):
            items.append(
                {
                    "id": "fake-powered-{:02d}".format(index),
                    "desc": "Synthetic powered reliability cell {}".format(index),
                    "labels": {
                        "hatespeech": {annotator: "0" for annotator in annotators}
                    },
                    "reasons": {},
                }
            )

        for index, annotator in enumerate(conservative[:16]):
            items[index]["labels"]["hatespeech"][annotator] = "1"
        for index, annotator in enumerate(liberal[:16]):
            distinct_cells = ((16 + index) % 24, (8 + index) % 24)
            self.assertNotEqual(*distinct_cells)
            for cell in distinct_cells:
                items[cell]["labels"]["hatespeech"][annotator] = "1"

        self.assertLessEqual(
            max(
                sum(label != "0" for label in item["labels"]["hatespeech"].values())
                for item in items
            ),
            3,
        )

        dataset = {
            "questions": {
                "hatespeech": {
                    "type": "categorical",
                    "labels": ["0", "1", "2"],
                }
            },
            "annotators": annotators,
            "cohorts": {
                "Conservative": conservative,
                "Liberal": liberal,
            },
            "items": items,
        }

        with tempfile.TemporaryDirectory(prefix="groundless-mhs-powered-") as temp:
            temp_path = Path(temp)
            data_path = temp_path / "powered-labels.json"
            data_path.write_text(
                json.dumps(dataset, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "disagreement.py"),
                    "--data",
                    str(data_path),
                    "--out",
                    str(temp_path / "out"),
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
            )
            triage = _load_json(temp_path / "out" / "triage.json")

        self.assertEqual(len(triage["cells"]), 24)
        self.assertTrue(all(cell["verdict"] == "CONFIDENT" for cell in triage["cells"]))
        contributions = mhs_study._confident_contributions(dataset, triage)
        self.assertEqual(len(contributions), 24)
        scored_counts = Counter(
            annotator
            for contribution in contributions
            for annotator in contribution
        )
        self.assertEqual(set(scored_counts.values()), {24})
        self.assertEqual(set(scored_counts), set(annotators))
        mirror = mhs_study._reliability_by_annotator(contributions, annotators)
        self.assertEqual(mirror, triage["reliability"])
        self.assertEqual(set(mirror), set(annotators))

        conservative_median = statistics.median(
            mirror[annotator] for annotator in conservative
        )
        liberal_median = statistics.median(mirror[annotator] for annotator in liberal)
        self.assertEqual(conservative_median, 23 / 24)
        self.assertEqual(liberal_median, 22 / 24)
        self.assertAlmostEqual(conservative_median - liberal_median, 1 / 24)

        reliability = mhs_study.aggregate_reliability(dataset, triage)
        self.assertEqual(reliability["status"], "descriptive")
        self.assertEqual(
            reliability["coverage"],
            {
                "Conservative": {"eligible": 30, "qualifying": 30},
                "Liberal": {"eligible": 30, "qualifying": 30},
            },
        )
        self.assertEqual(
            reliability["summaries"]["Conservative"]["median"], 23 / 24
        )
        self.assertEqual(reliability["summaries"]["Liberal"]["median"], 22 / 24)
        self.assertAlmostEqual(
            reliability["median_difference_conservative_minus_liberal"], 1 / 24
        )
        interval = reliability["bootstrap_95"]
        self.assertEqual(interval["iterations"], 10000)
        self.assertEqual(interval["seed"], 20260718)
        self.assertEqual(interval["valid_estimates"], 10000)
        self.assertEqual(interval["degenerate_resamples"], 0)
        self.assertEqual(interval["status"], "ok")
        self.assertEqual(interval["lower"], 0.0)
        self.assertAlmostEqual(interval["upper"], 1 / 24)

        primary = mhs_study.aggregate_primary(dataset, triage)
        results = {"primary": primary, "reliability": reliability}
        counts = {
            "primary_items": 24,
            "reliability_items": 24,
            "conservative_annotators": 30,
            "liberal_annotators": 30,
        }
        report = mhs_study.render_report(
            results,
            counts,
            "synthetic-tool-commit",
        )
        manifest = mhs_study.build_manifest(
            "synthetic-source-sha256",
            counts,
            results,
            "synthetic-tool-commit",
            "2026-07-19T00:00:00Z",
        )
        self.assertEqual(
            manifest,
            {
                "evidence_tier": "Tier 2",
                "generated_at": "2026-07-19T00:00:00Z",
                "source_revision": mhs_study.SOURCE_REVISION,
                "source_sha256": "synthetic-source-sha256",
                "protocol": mhs_study.PROTOCOL_PATH,
                "addendum": mhs_study.ADDENDUM_PATH,
                "primary_count_addendum": (
                    mhs_study.PRIMARY_COUNT_ADDENDUM_PATH
                ),
                "tool_commit": "synthetic-tool-commit",
                "counts": counts,
                "metrics": results,
                "contains_source_rows_or_ids": False,
            },
        )
        self.assertIn("Protocol: `{}`".format(mhs_study.PROTOCOL_PATH), report)
        self.assertIn(
            "Reliability addendum: `{}`".format(mhs_study.ADDENDUM_PATH),
            report,
        )
        self.assertIn(
            "Primary-count addendum: `{}`".format(
                mhs_study.PRIMARY_COUNT_ADDENDUM_PATH
            ),
            report,
        )
        self.assertEqual(
            report.count(
                "status ok; total draws 10000; valid estimates 10000; "
                "degenerate resamples 0"
            ),
            2,
        )
        result_keys = json.dumps(
            results, sort_keys=True
        )
        self.assertNotIn("p_value", result_keys)
        self.assertNotIn("pvalue", result_keys)

    def test_degenerate_bootstrap_is_disclosed_without_redraws(self):
        fixed = {
            "Conservative": {"fake-c"},
            "Liberal": {"fake-l"},
        }
        contributions = [
            {"fake-c": (1, 1)},
            {"fake-l": (1, 1)},
        ]

        def statistic(sample):
            return mhs_study._reliability_median_difference(sample, fixed)

        first = mhs_metrics.bootstrap_statistic(
            contributions, statistic
        )
        second = mhs_metrics.bootstrap_statistic(
            contributions, statistic
        )
        self.assertEqual(first, second)
        self.assertEqual(first["iterations"], 10000)
        self.assertGreater(first["valid_estimates"], 0)
        self.assertGreater(first["degenerate_resamples"], 0)
        self.assertEqual(
            first["valid_estimates"] + first["degenerate_resamples"], 10000
        )
        self.assertIsNone(first["lower"])
        self.assertIsNone(first["upper"])
        self.assertEqual(first["status"], "degenerate/non-applicable")

        always = mhs_metrics.bootstrap_statistic(
            [{"fake-c": (1, 1)}], statistic
        )
        self.assertEqual(always["iterations"], 10000)
        self.assertEqual(always["valid_estimates"], 0)
        self.assertEqual(always["degenerate_resamples"], 10000)
        self.assertIsNone(always["lower"])
        self.assertIsNone(always["upper"])
        self.assertEqual(always["status"], "degenerate/non-applicable")

    def test_frozen_descriptive_statistics(self):
        interval = mhs_metrics.wilson_interval(5, 10)
        self.assertAlmostEqual(interval["lower"], 0.236593090512564, places=12)
        self.assertAlmostEqual(interval["upper"], 0.763406909487436, places=12)
        self.assertEqual(
            mhs_metrics.median_iqr([1, 2, 3, 4]),
            {"median": 2.5, "q1": 1.75, "q3": 3.25, "iqr": 1.5},
        )
        self.assertEqual(mhs_metrics.BOOTSTRAP_ITERATIONS, 10000)
        self.assertEqual(mhs_metrics.BOOTSTRAP_SEED, 20260718)
        first = mhs_metrics.bootstrap_median([0, 1, 2, 3])
        second = mhs_metrics.bootstrap_median([0, 1, 2, 3])
        self.assertEqual(first, second)
        self.assertEqual(first["iterations"], 10000)
        self.assertEqual(first["seed"], 20260718)
        self.assertEqual(first["valid_estimates"], 10000)
        self.assertEqual(first["degenerate_resamples"], 0)
        self.assertEqual(first["status"], "ok")
        self.assertNotIn("p_value", first)
        self.assertNotIn("pvalue", first)

    def test_adapter_rejects_ambiguous_rows_and_harness_halts_on_hash(self):
        invalid_label = copy.deepcopy(self.records)
        invalid_label[0]["hatespeech"] = 3
        with self.assertRaisesRegex(mhs_adapter.MHSInputError, "one of 0, 1, 2"):
            mhs_adapter.convert_records(invalid_label)

        inconsistent_ideology = copy.deepcopy(self.records)
        inconsistent_ideology[4]["annotator_ideology"] = "liberal"
        with self.assertRaisesRegex(
            mhs_adapter.MHSInputError, "inconsistent author-supplied ideology"
        ):
            mhs_adapter.convert_records(inconsistent_ideology)

        duplicate = copy.deepcopy(self.records)
        duplicate.append(copy.deepcopy(duplicate[0]))
        with self.assertRaisesRegex(mhs_adapter.MHSInputError, "duplicate judgment"):
            mhs_adapter.convert_records(duplicate)

        with tempfile.TemporaryDirectory(prefix="groundless-mhs-hash-") as temp:
            fake_source = Path(temp) / "not-mhs.parquet"
            fake_source.write_bytes(b"synthetic, not parquet")
            with self.assertRaisesRegex(SystemExit, "MHS source SHA-256 mismatch"):
                mhs_study.verify_source(fake_source)
            self.assertEqual(list(Path(temp).iterdir()), [fake_source])

    def test_phase_boundary_and_frozen_constants_are_explicit(self):
        adapter_source = (ROOT / "adapters" / "mhs.py").read_text(encoding="utf-8")
        harness_source = (
            ROOT / "reports" / "mhs" / "run_study.py"
        ).read_text(encoding="utf-8")
        readme = (ROOT / "reports" / "mhs" / "README.md").read_text(
            encoding="utf-8"
        )
        self.assertLess(
            harness_source.index("def load_parquet_records"),
            harness_source.index("import pyarrow.parquet as parquet"),
        )
        self.assertNotIn("pyarrow", adapter_source)
        for token in (
            "20",
            "extremely_conservative",
            "conservative",
            "slightly_conservative",
            "extremely_liberal",
            "liberal",
            "slightly_liberal",
            "50",
        ):
            self.assertIn(token, adapter_source)
        for token in ("10,000", "20260718", "30", "no null-hypothesis p-values"):
            self.assertIn(token, readme)
        tracked_parquet = subprocess.run(
            ["git", "ls-files", "*.parquet"],
            cwd=str(ROOT),
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
        ).stdout.strip()
        self.assertEqual(tracked_parquet, "")
        self.assertTrue(
            all(
                record["comment_id"].startswith("synthetic-")
                for record in self.records
            )
        )

    @unittest.skipUnless(_HAS_JSONSCHEMA, "jsonschema is not installed")
    def test_both_mhs_outputs_match_the_input_schema(self):
        schema = _load_json(ROOT / "schema" / "labels.schema.json")
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema)
        validator.validate(self.converted["primary"])
        validator.validate(self.converted["reliability"])


class GovernanceClaims(unittest.TestCase):
    def _prepare_queue(self, out_dir):
        for tool in ("disagreement.py", "soft_labels.py"):
            subprocess.run(
                [sys.executable, str(ROOT / tool), "--out", str(out_dir)],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
            )

    def test_default_governance_bytes_are_pinned(self):
        pipeline = _pipeline()
        digest = hashlib.sha256(pipeline["governance_bytes"]).hexdigest()
        self.assertEqual(
            digest,
            "91c1876d468d02694ec302158668e37d7482914be70b5ab6e8611c54cd3a8e2f",
        )
        self.assertEqual(len(pipeline["governance"]), 2)
        self.assertTrue(
            all(
                record.get("status") == "pending"
                and "decision_off_menu" not in record
                for record in pipeline["governance"]
            )
        )

    def test_decide_reaches_resolution_and_survives_exporter_rerun(self):
        with tempfile.TemporaryDirectory(prefix="groundless-govern-") as temp:
            out_dir = Path(temp)
            self._prepare_queue(out_dir)

            listed = subprocess.run(
                [sys.executable, str(ROOT / "govern.py"), "list"],
                cwd=str(out_dir),
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
            )
            self.assertIn("img2 / explicit", listed.stdout)
            self.assertIn("2 pending", listed.stdout)

            command = [
                sys.executable,
                str(ROOT / "govern.py"),
                "decide",
                "--item",
                "img2",
                "--question",
                "explicit",
                "--owner",
                "Safety policy owner",
                "--decision",
                "safe",
                "--rationale",
                "Use the editorial-context policy.",
                "--out",
                str(out_dir),
            ]
            subprocess.run(
                command,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
            )
            governance_path = out_dir / "governance.jsonl"
            decided_queue = governance_path.read_bytes()
            decision = next(
                record
                for record in _load_jsonl(governance_path)
                if record["item_id"] == "img2" and record["question"] == "explicit"
            )
            self.assertEqual(decision["decision_required_from"], "Safety policy owner")
            self.assertEqual(decision["decision_recorded"], "safe")
            self.assertEqual(
                decision["decision_rationale"],
                "Use the editorial-context policy.",
            )
            self.assertEqual(decision["status"], "decided")
            self.assertTrue(decision["decided_at"].endswith("Z"))
            self.assertNotIn("decision_off_menu", decision)

            subprocess.run(
                [sys.executable, str(ROOT / "resolution.py"), "--out", str(out_dir)],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
            )
            resolution_record = next(
                record
                for record in _load_jsonl(out_dir / "resolution_records.jsonl")
                if record["item"] == "img2" and record["question"] == "explicit"
            )
            self.assertEqual(resolution_record["disposition"]["outcome"], "decided:safe")
            self.assertEqual(
                resolution_record["authority"],
                {
                    "decided_by": "named_owner",
                    "owner": "Safety policy owner",
                    "policy_version": resolution.POLICY_VERSION,
                },
            )

            subprocess.run(
                [sys.executable, str(ROOT / "soft_labels.py"), "--out", str(out_dir)],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
            )
            self.assertEqual(governance_path.read_bytes(), decided_queue)
            self.assertEqual(
                next(
                    record
                    for record in _load_jsonl(governance_path)
                    if record["item_id"] == "img2"
                )["decided_at"],
                decision["decided_at"],
            )

            before_overwrite = governance_path.read_bytes()
            overwrite = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
            )
            self.assertNotEqual(overwrite.returncode, 0)
            self.assertIn("refusing to overwrite", overwrite.stderr)
            self.assertEqual(governance_path.read_bytes(), before_overwrite)
            self.assertEqual(list(out_dir.glob(".governance.*.tmp")), [])

    def test_off_menu_decision_requires_explicit_escape_and_persists(self):
        with tempfile.TemporaryDirectory(prefix="groundless-govern-off-menu-") as temp:
            out_dir = Path(temp)
            self._prepare_queue(out_dir)
            governance_path = out_dir / "governance.jsonl"
            original = governance_path.read_bytes()
            command = [
                sys.executable,
                str(ROOT / "govern.py"),
                "decide",
                "--item",
                "img2",
                "--question",
                "explicit",
                "--owner",
                "Safety policy owner",
                "--decision",
                "saef",
                "--rationale",
                "Apply a documented exception outside the observed labels.",
                "--out",
                str(out_dir),
            ]

            rejected = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
            )
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn("explicit / flag", rejected.stderr)
            self.assertIn("safe", rejected.stderr)
            self.assertIn("--allow-other", rejected.stderr)
            self.assertEqual(governance_path.read_bytes(), original)

            subprocess.run(
                command + ["--allow-other"],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
            )
            decision = next(
                record
                for record in _load_jsonl(governance_path)
                if record["item_id"] == "img2" and record["question"] == "explicit"
            )
            self.assertEqual(decision["decision_recorded"], "saef")
            self.assertIs(decision["decision_off_menu"], True)

            subprocess.run(
                [sys.executable, str(ROOT / "resolution.py"), "--out", str(out_dir)],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
            )
            resolution_record = next(
                record
                for record in _load_jsonl(out_dir / "resolution_records.jsonl")
                if record["item"] == "img2" and record["question"] == "explicit"
            )
            self.assertEqual(resolution_record["disposition"]["outcome"], "decided:saef")
            self.assertEqual(
                resolution_record["authority"]["owner"], "Safety policy owner"
            )
            self.assertEqual(
                resolution_record["authority"]["decided_by"], "named_owner"
            )

            subprocess.run(
                [sys.executable, str(ROOT / "soft_labels.py"), "--out", str(out_dir)],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
            )
            persisted = next(
                record
                for record in _load_jsonl(governance_path)
                if record["item_id"] == "img2" and record["question"] == "explicit"
            )
            self.assertIs(persisted["decision_off_menu"], True)
            self.assertEqual(persisted["decision_recorded"], "saef")
            self.assertEqual(persisted["decided_at"], decision["decided_at"])
            self.assertEqual(list(out_dir.glob(".governance.*.tmp")), [])

    def test_invalid_decisions_and_corrupt_decided_state_are_rejected(self):
        with tempfile.TemporaryDirectory(prefix="groundless-govern-invalid-") as temp:
            out_dir = Path(temp)
            self._prepare_queue(out_dir)
            governance_path = out_dir / "governance.jsonl"
            original = governance_path.read_bytes()
            cases = (
                (
                    "missing",
                    "explicit",
                    "Safety policy owner",
                    "safe",
                    "reason",
                    "no queue record",
                ),
                ("img2", "explicit", "<owner>", "safe", "reason", "must name"),
                (
                    "img2",
                    "explicit",
                    "Safety policy owner",
                    " ",
                    "reason",
                    "decision must",
                ),
                (
                    "img2",
                    "explicit",
                    "Safety policy owner",
                    "safe",
                    " ",
                    "rationale must",
                ),
            )
            for item, question, owner, decision, rationale, expected in cases:
                command = [
                    sys.executable,
                    str(ROOT / "govern.py"),
                    "decide",
                    "--item",
                    item,
                    "--question",
                    question,
                    "--owner",
                    owner,
                    "--decision",
                    decision,
                    "--rationale",
                    rationale,
                    "--out",
                    str(out_dir),
                ]
                result = subprocess.run(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    universal_newlines=True,
                )
                with self.subTest(expected=expected):
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn(expected, result.stderr)
                    self.assertEqual(governance_path.read_bytes(), original)

            records = _load_jsonl(governance_path)
            records[0].update(
                decision_required_from="<owner>",
                decision_recorded="safe",
                decision_rationale="reason",
                status="decided",
            )
            governance_path.write_text(
                "".join(json.dumps(record) + "\n" for record in records),
                encoding="utf-8",
            )
            corrupt = subprocess.run(
                [sys.executable, str(ROOT / "govern.py"), "list", "--out", str(out_dir)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
            )
            self.assertNotEqual(corrupt.returncode, 0)
            self.assertIn("has a decision but no named owner", corrupt.stderr)


class ResolutionClaims(unittest.TestCase):
    def test_records_hashes_structure_and_decision_guards(self):
        pipeline = _pipeline()
        records = pipeline["records"]
        self.assertEqual(len(records), 18)
        self.assertEqual(pipeline["first_hashes"], pipeline["second_hashes"])

        for record in records:
            with self.subTest(item=record["item"], question=record["question"]):
                self.assertEqual(set(record), REQUIRED_RECORD_KEYS)
                self.assertIn(record["measures"]["fork_status"], FORK_STATUSES)
                if record["disposition"]["outcome"].startswith("decided:"):
                    self.assertEqual(record["authority"]["decided_by"], "named_owner")

        schema = _load_json(ROOT / "schema" / "resolution_record.schema.json")
        example = schema["examples"][0]
        expected_hash = "sha256:02c198d88a9bd66a8df03e3a0b04b994ea4b567d3c087cf9821c5d5eec47a5d6"
        self.assertEqual(resolution.replay_hash(example), expected_hash)
        self.assertEqual(example["provenance"]["replay_hash"], expected_hash)

        governance = copy.deepcopy(pipeline["governance"])
        decision = next(
            record
            for record in governance
            if record["item_id"] == "img2" and record["question"] == "explicit"
        )
        decision.update(
            decision_required_from="Safety policy owner",
            decision_recorded="safe",
            decision_rationale="The release uses the editorial-context policy.",
        )
        decided_records = resolution.build_records(
            DATASET,
            pipeline["triage"],
            pipeline["soft"],
            governance,
            "2026-07-17T00:00:00Z",
        )
        decided = next(
            record
            for record in decided_records
            if record["item"] == "img2" and record["question"] == "explicit"
        )
        self.assertEqual(decided["disposition"]["outcome"], "decided:safe")
        self.assertEqual(decided["authority"]["decided_by"], "named_owner")
        self.assertEqual(decided["authority"]["owner"], "Safety policy owner")
        self.assertIn(
            "rationale: The release uses the editorial-context policy.",
            decided["disposition"]["conditions"],
        )

        decision_cell = next(
            cell
            for cell in pipeline["triage"]["cells"]
            if cell["item"] == "img2" and cell["question"] == "explicit"
        )
        decision_soft_record = next(
            record
            for record in pipeline["soft"]
            if record["item_id"] == "img2" and record["question"] == "explicit"
        )
        invalid = copy.deepcopy(decision)
        for invalid_owner in ("<named human owner -- to be assigned>", " "):
            invalid["decision_required_from"] = invalid_owner
            with self.subTest(invalid_owner=invalid_owner), self.assertRaises(ValueError):
                resolution.authority_and_disposition(
                    decision_cell,
                    decision_soft_record,
                    invalid,
                )
        invalid["decision_required_from"] = "Safety policy owner"
        invalid["decision_rationale"] = " "
        with self.assertRaises(ValueError):
            resolution.authority_and_disposition(
                decision_cell,
                decision_soft_record,
                invalid,
            )

    @unittest.skipUnless(_HAS_JSONSCHEMA, "jsonschema is not installed")
    def test_schema_example_and_all_emitted_records(self):
        schema = _load_json(ROOT / "schema" / "resolution_record.schema.json")
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        validator.validate(schema["examples"][0])
        for record in _pipeline()["records"]:
            validator.validate(record)

        labels_schema = _load_json(ROOT / "schema" / "labels.schema.json")
        Draft202012Validator.check_schema(labels_schema)
        Draft202012Validator(labels_schema).validate(DATASET)


if __name__ == "__main__":
    unittest.main()
