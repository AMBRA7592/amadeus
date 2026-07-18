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
import shutil
import subprocess
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path

import aggregation
import bayes_optimal
import frustration
import geometry
import resolution
import topology

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

    def test_bill_and_reliability_are_pinned_in_the_essay(self):
        triage = _pipeline()["triage"]
        cells = triage["cells"]
        contested = [cell for cell in cells if cell["verdict"].startswith("CONTESTED")]
        essay = _essay("the-groundless-label.md")
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
        digest = hashlib.sha256(_pipeline()["governance_bytes"]).hexdigest()
        self.assertEqual(
            digest,
            "91c1876d468d02694ec302158668e37d7482914be70b5ab6e8611c54cd3a8e2f",
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
