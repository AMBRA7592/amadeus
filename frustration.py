#!/usr/bin/env python3
"""
frustration.py -- the label as a frustrated system.

"Ground Truth Has No Ground" argues a crowd often has no single right answer.
Statistical physics has a precise name for a system whose competing constraints
admit no single consistent solution: FRUSTRATION, and the disordered systems
built from it -- SPIN GLASSES -- are exactly what Giorgio Parisi won the 2021
Nobel Prize in Physics for understanding. The mapping is not a metaphor you have
to squint at; it computes. This script makes three pieces of it run against the
same data/labels.json:

  1. TEMPERATURE  The honest summary of a vote is its maximum-entropy (= Gibbs)
                  distribution -- the soft label. Majority vote is its T -> 0
                  limit: a quench. On a frustrated cell the quench freezes you
                  into one arbitrary valley and discards the rest as entropy.
                  (Jaynes 1957 made max-entropy and statistical mechanics the
                  same mathematics; this is that identity, on your labels.)

  2. COUPLINGS    Infer the coupling J_ij between annotators from how they
                  co-deviate from consensus (the inferred-Ising coupling). The
                  ground state of that system is the labeling that best fits the
                  crowd. A real fact is a system that settles into one bloc (a
                  FERROMAGNET: one ground state). A value fork is a system whose
                  ground state splits into two opposed domains (an
                  ANTIFERROMAGNET: two ground states, no single truth) -- and the
                  split is recovered from votes alone, so the data reveals its
                  own pure states. Irreducible, cyclic disagreement is the third
                  phase, a SPIN GLASS: many incongruent ground states.

  3. CYCLES       A Condorcet cycle (A>B>C>A) is a frustrated triad: three
                  pairwise-consistent constraints with no globally consistent
                  ordering. Frustration is why "the answer" can fail to exist
                  even when every pairwise comparison is decisive.

This proof/illustration is intentionally pinned to data/labels.json: its printed
narrative names the demo's cohorts, ribbon, and 4-4 forks. For arbitrary
annotations use disagreement.py, soft_labels.py, and resolution.py with --data.

No third-party dependencies (stdlib only; Python 3.8+). Run: python3 frustration.py
"""

import itertools
import json
import math
import os
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data", "labels.json")
BAR = "=" * 78


def load():
    with open(DATA) as f:
        ds = json.load(f)
    return ds


def entropy_bits(probs):
    h = -sum(p * math.log2(p) for p in probs if p > 0)
    return h if h > 1e-12 else 0.0


# --------------------------------------------------------------------------- #
# 1. TEMPERATURE: majority vote is the T -> 0 limit of the soft label
# --------------------------------------------------------------------------- #
def temper(counts, T):
    """Boltzmann tempering of the observed distribution: q_i ~ p_i ** (1/T).
    T = 1 -> the soft label (observed frequencies). T -> 0 -> the argmax
    (majority vote). T -> inf -> uniform over the support. This is the
    softmax-temperature / simulated-annealing family; the T -> 0 limit IS the
    'collapse to one label' the pipeline performs by default."""
    n = sum(counts.values())
    p = {k: c / n for k, c in counts.items() if c > 0}
    if T <= 1e-9:
        top = max(p.values())
        winners = [k for k, v in p.items() if abs(v - top) < 1e-12]
        return {k: 1.0 / len(winners) for k in winners}, len(winners)
    raw = {k: v ** (1.0 / T) for k, v in p.items()}
    z = sum(raw.values())
    return {k: v / z for k, v in raw.items()}, 1


def temperature_section(ds):
    print(BAR + "\n1. TEMPERATURE  --  majority vote is a zero-temperature quench\n" + BAR)
    print("  The soft label is the crowd's max-entropy (Gibbs) state. 'Collapsing to")
    print("  ground truth' is cooling it to T=0. Watch the entropy you destroy by")
    print("  cooling -- and notice it is exactly the 'bits' the bill already prices.\n")

    cells = {
        "img2/synthetic (a real fact)": Counter(_votes(ds, "img2", "synthetic")),
        "img1/ribbon   (a floating signifier)": Counter(_votes(ds, "img1", "ribbon")),
        "img2/explicit (a 4-4 value fork)": Counter(_votes(ds, "img2", "explicit")),
    }
    Ts = [8.0, 2.0, 1.0, 0.5, 0.2, 0.0]
    for label, counts in cells.items():
        print(f"  {label}   votes={dict(counts)}")
        header = "      T:    " + "  ".join(f"{('quench' if T==0 else T):>6}" for T in Ts)
        print(header)
        ent_row, deg = [], 1
        for T in Ts:
            q, d = temper(counts, T)
            if T == 0.0:
                deg = d
            ent_row.append(entropy_bits(q.values()))
        print("      H(bits):" + "  ".join(f"{h:6.2f}" for h in ent_row))
        soft_H = ent_row[2]                       # T = 1
        note = ""
        if deg > 1:
            note = (f"   <- T=0 is DEGENERATE ({deg} tied ground states): the quench "
                    f"needs an\n         external field (the casting vote) to choose one.")
        print(f"      cooling to T=0 (majority vote) destroys {soft_H:5.2f} bits of "
              f"disagreement.{note}\n")
    print("  -> where the soft label already has ~0 entropy (a real fact), the quench is")
    print("     free. Where it is high (the floating signifier), majority vote is a")
    print("     violent, lossy cooling -- and at an exact tie it cannot even pick without")
    print("     an outside field. Keeping T>0 *is* 'keep the distribution'.")


def _votes(ds, item_id, q):
    it = next(i for i in ds["items"] if i["id"] == item_id)
    return list(it["labels"][q].values())


# --------------------------------------------------------------------------- #
# 2. COUPLINGS: ground states, ferromagnets, and spin glasses
# --------------------------------------------------------------------------- #
def coupling(ds, q):
    """J_ij from co-deviation: center each item by its mean, then J_ij is the
    annotators' residual covariance. Centering removes the trivial shared signal
    ('everyone agrees it's safe') so only structured disagreement couples people
    -- this is, exactly, the coupling of an Ising model inferred from the data."""
    anns = ds["annotators"]
    vecs = {a: [it["labels"][q][a] for it in ds["items"]] for a in anns}
    n_items = len(ds["items"])
    means = [sum(vecs[a][k] for a in anns) / len(anns) for k in range(n_items)]
    J = {}
    for i in range(len(anns)):
        for j in range(i + 1, len(anns)):
            a, b = anns[i], anns[j]
            J[(a, b)] = sum((vecs[a][k] - means[k]) * (vecs[b][k] - means[k])
                            for k in range(n_items))
    return J, anns


def ground_state(J, anns):
    """Minimize the Ising energy E(s) = - sum J_ij s_i s_j over s in {+1,-1}^n.
    Brute force (n=8 -> 256 states). Returns the two blocs, the residual
    'frustration' (coupling weight left unsatisfied), and the total weight."""
    best = None
    for bits in itertools.product((1, -1), repeat=len(anns)):
        s = dict(zip(anns, bits))
        E = -sum(j * s[a] * s[b] for (a, b), j in J.items())
        if best is None or E < best[0] - 1e-12:
            best = (E, s)
    _, s = best
    plus = sorted(a for a in anns if s[a] == 1)
    minus = sorted(a for a in anns if s[a] == -1)
    frustration = sum(abs(j) for (a, b), j in J.items() if j * s[a] * s[b] < -1e-12)
    total = sum(abs(j) for j in J.values())
    return sorted([plus, minus], key=lambda x: (len(x), x)), frustration, total


def coupling_section(ds):
    print("\n" + BAR + "\n2. COUPLINGS  --  a fact is a ferromagnet; a value fork is an antiferromagnet\n" + BAR)
    print("  Infer the coupling between annotators from how they co-deviate from")
    print("  consensus, then find the ground state -- the labeling that best satisfies")
    print("  the crowd. Two questions, two phases (and sections 1 & 3 show the third):\n")
    cohorts = ds["cohorts"]
    findings = {}
    for q in ("explicit", "synthetic"):
        J, anns = coupling(ds, q)
        blocs, frust, total = ground_state(J, anns)
        rel = frust / total if total else 0.0
        recovers = ({frozenset(b) for b in blocs} ==
                    {frozenset(cohorts["A"]), frozenset(cohorts["B"])})
        smallest = min(len(b) for b in blocs)
        if recovers and rel < 0.10:
            kind = "ANTIFERROMAGNET (two opposed domains -> two ground states -> a VALUE FORK)"
            phase = "value_fork"
        elif smallest <= 1 or rel > 0.15:
            kind = "FERROMAGNET (one consensus ground state, plus a frustrated impurity)"
            phase = "consensus_with_dissent"
        else:
            kind = "SPIN GLASS (many incongruent ground states)"
            phase = "disordered"
        findings[q] = {"phase": phase, "recovers": recovers, "blocs": blocs,
                       "frustration": rel}
        print(f"  {q}:")
        print(f"     ground state -> {blocs}")
        print(f"     residual frustration {frust:.2f}/{total:.2f} = {rel*100:.0f}%   [{kind}]")
        if recovers:
            print(f"     ^ this bipartition was recovered from the votes alone -- and it is")
            print(f"       exactly the two cohorts. The data revealed its own pure states.")
        else:
            dissenters = min(blocs, key=lambda b: (len(b), b))
            print(f"     ^ the minimum-energy split is forced and high-frustration: really one")
            print(f"       consensus bloc plus scattered dissent ({', '.join(dissenters)}), not two camps.")
        print()
    explicit = findings.get("explicit", {})
    synthetic = findings.get("synthetic", {})
    if explicit.get("phase") == "value_fork" and explicit.get("recovers"):
        print("  On these data the contested question orders into two low-frustration")
        print("  domains that reconstruct the two named cohorts without being given them.")
    else:
        print("  On these data the contested question does not cleanly recover the two")
        print("  named cohorts; the output above is the result, not a hardcoded story.")
    if synthetic.get("phase") == "consensus_with_dissent":
        dissenters = min(synthetic["blocs"], key=lambda b: (len(b), b))
        print("  The consensus question supports no clean two-cohort order: it has one")
        print(f"  dominant bloc plus scattered dissent ({', '.join(dissenters)}).")
    else:
        print("  The consensus question's computed phase is reported above; no")
        print("  ferromagnetic conclusion is inserted unless the diagnostic supports it.")
    print("  In this diagnostic, 'no unique ground state' is evidence to preserve the")
    print("  plurality of states rather than silently force a single label.")


# --------------------------------------------------------------------------- #
# 3. CYCLES: a Condorcet cycle is a frustrated triad (illustrative)
# --------------------------------------------------------------------------- #
def condorcet_cycle_section():
    print("\n" + BAR + "\n3. CYCLES  --  why 'the answer' can fail to exist (illustrative)\n" + BAR)
    print("  Three annotators rank three readings of the ribbon. Every pairwise")
    print("  majority is decisive -- yet they chain into a loop with no top:\n")
    ballots = {
        "annotator 1": ["scarf", "plastic", "ribbon"],
        "annotator 2": ["plastic", "ribbon", "scarf"],
        "annotator 3": ["ribbon", "scarf", "plastic"],
    }
    for a, r in ballots.items():
        print(f"     {a}: {' > '.join(r)}")
    opts = ["scarf", "plastic", "ribbon"]

    def prefers(x, y):  # how many ballots rank x above y
        return sum(1 for r in ballots.values() if r.index(x) < r.index(y))

    print()
    for x, y in [("scarf", "plastic"), ("plastic", "ribbon"), ("ribbon", "scarf")]:
        print(f"     {x:7s} beats {y:7s} by {prefers(x, y)}-{prefers(y, x)}")
    print("\n  scarf > plastic > ribbon > scarf: a frustrated triad. There is no")
    print("  Condorcet winner -- the collective preference is intransitive. No")
    print("  aggregation 'recovers the truth' because, as a configuration, it does")
    print("  not exist. This is the exact 3-spin frustration of an odd loop with")
    print("  antiferromagnetic bonds: locally satisfiable, globally impossible.")


# --------------------------------------------------------------------------- #
def dictionary():
    print("\n" + BAR + "\nTHE DICTIONARY  --  the mapping that does the work\n" + BAR)
    rows = [
        ("annotators / their judgements", "spins / their states"),
        ("how strongly two annotators co-move", "coupling J_ij"),
        ("the labeling that best fits the crowd", "the ground state"),
        ("a real fact (consensus)", "a ferromagnet: one ground state"),
        ("a value fork (two coherent camps)", "an antiferromagnet: two ground states"),
        ("irreducible / cyclic disagreement", "a spin glass: many incongruent states"),
        ("the soft label (kept distribution)", "the Gibbs state at temperature T"),
        ("entropy of disagreement (the bits)", "thermodynamic entropy"),
        ("majority vote / collapse to one label", "the T -> 0 quench"),
        ("the tie-break that picks a winner", "an external symmetry-breaking field"),
        ("model collapse over generations", "repeated quenching: entropy only falls"),
    ]
    w = max(len(a) for a, _ in rows)
    for a, b in rows:
        print(f"  {a:<{w}}   ~   {b}")


def main():
    ds = load()
    print(BAR + "\nTHE LABEL AS A FRUSTRATED SYSTEM"
          "\nspin-glass physics (Parisi, Nobel 2021), run against data/labels.json\n" + BAR)
    temperature_section(ds)
    coupling_section(ds)
    condorcet_cycle_section()
    dictionary()
    print("\n" + BAR + "\nTAKEAWAY\n" + BAR)
    print("  A crowd has no ground truth for the same reason a frustrated magnet has")
    print("  no ground state: the constraints are incompatible, so the honest object")
    print("  is not a configuration but a DISTRIBUTION OVER configurations at finite")
    print("  temperature -- the soft label. Majority vote is the zero-temperature")
    print("  quench: it freezes one arbitrary valley and calls the lost entropy noise.")
    print("  Keep the temperature up. Keep the cloud.")


if __name__ == "__main__":
    main()
