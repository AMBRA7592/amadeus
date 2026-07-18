#!/usr/bin/env python3
"""
topology.py -- the hole under the impossibility.

Why is neutral aggregation impossible? Algebraic topology gives the deepest
answer: it is impossible exactly when the space of preferences has a HOLE.

  CHICHILNISKY (1980)  A continuous, anonymous, unanimity-respecting aggregation
                       rule exists (for every number of voters) IF AND ONLY IF
                       the preference space is contractible -- topologically
                       trivial, no holes. A circle has a hole, and on a circle
                       no such rule exists.

  BARYSHNIKOV  (1993)  Arrow's discrete impossibility theorem and Chichilnisky's
                       continuous one are the SAME theorem: both are the same
                       hole, detected once by counting and once by topology. The
                       Condorcet cycle is a generator of that hole.

  HODGE / HODGERANK    A reward model is a scalar field; fitting it to pairwise
  (Jiang-Lim-Yao-Ye    preferences asks for a POTENTIAL whose gradient is the
   2011)               preference field. That exists IFF the field is curl-free
                       IFF every loop has zero circulation IFF H^1 = 0. A value
                       fork / Condorcet cycle is nonzero curl -- so no reward
                       function fits it, and the model must cut the space
                       somewhere arbitrary (a dictator = a topological defect).

This proof/illustration is intentionally pinned to data/labels.json: its printed
narrative names the demo's cohorts, ribbon, and 4-4 forks. For arbitrary
annotations use disagreement.py, soft_labels.py, and resolution.py with --data.

This script runs all three against data/labels.json and the canonical examples.
No third-party dependencies (stdlib only; Python 3.8+). Run: python3 topology.py
"""

import itertools
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data", "labels.json")
BAR = "=" * 78
NOISE_FLOOR = 0.25


# --------------------------------------------------------------------------- #
# 1. The circle is the hole: a mean that exists on a line but not on a ring
# --------------------------------------------------------------------------- #
def circle_section():
    print(BAR + "\n1. THE HOLE  --  you can average on a line, but not on a ring\n" + BAR)
    print("  Aggregation = a continuous, anonymous rule that returns the common value")
    print("  when everyone agrees (unanimity). On a CONTRACTIBLE space it is easy:\n")
    print("    interval [0,1]:  mean(x,y) = (x+y)/2   continuous, anonymous,")
    print("                     and mean(x,x)=x. No obstruction.\n")
    print("  On a CIRCLE (preferences as directions -- the generic case) the same")
    print("  demand cannot be met. Take the only natural candidate, the midpoint of")
    print("  the shorter arc, fix one input at 0 deg, and sweep the other:\n")

    def circular_mean(x, y):
        d = ((y - x + 180) % 360) - 180          # signed shortest gap
        return (x + d / 2) % 360

    prev, jump_at, jump_sz = None, None, 0.0
    print("        y:    170     178     180     182     190")
    row = []
    for y in (170, 178, 180, 182, 190):
        row.append(circular_mean(0, y))
    print("    mean(0,y):" + "  ".join(f"{m:6.1f}" for m in row))
    for y in range(0, 361):
        m = circular_mean(0, y)
        if prev is not None:
            step = abs(((m - prev + 180) % 360) - 180)
            if step > jump_sz:
                jump_sz, jump_at = step, y
        prev = m
    print(f"\n  The 'average' jumps by ~{jump_sz:.0f} deg at y={jump_at} deg (the antipode):")
    print("  a discontinuity. And it is not a flaw of this candidate -- Chichilnisky")
    print("  proved EVERY continuous anonymous unanimous rule on the circle fails. The")
    print("  obstruction is a winding number forced to be a half-integer; the circle's")
    print("  hole (pi_1 = Z) is what your rule keeps falling into. Contractible space ->")
    print("  aggregation exists; a hole -> it cannot.")


# --------------------------------------------------------------------------- #
# 2. A reward is a potential; a cycle is its curl (discrete Hodge / HodgeRank)
# --------------------------------------------------------------------------- #
def circulation(margins):
    """margins: dict (i,j)->preference of i over j (antisymmetric implied).
    Returns the circulation around the 3-cycle 0->1->2->0. A reward function
    r with r[i]-r[j] == margin[(i,j)] exists IFF this is 0 for every cycle
    (the field is a gradient -- curl-free)."""
    return margins[(0, 1)] + margins[(1, 2)] + margins[(2, 0)]


def best_reward(margins):
    """Least-squares scalar reward (the HodgeRank 'gradient' component), gauge-
    fixed to r[0]=0. For a 3-cycle the closed form of the consistent part is the
    pairwise margins minus their common circulation/3."""
    L = circulation(margins) / 3.0
    g = {(0, 1): margins[(0, 1)] - L,
         (1, 2): margins[(1, 2)] - L,
         (2, 0): margins[(2, 0)] - L}        # curl-free residual
    r = {0: 0.0}
    r[1] = r[0] - g[(0, 1)]
    r[2] = r[1] - g[(1, 2)]
    return r, L


def hodge_section():
    print("\n" + BAR + "\n2. THE REWARD IS A POTENTIAL  --  a cycle is curl no ranking can hold\n" + BAR)
    print("  An RLHF reward model is a scalar field r over options; training asks for")
    print("  r[better] - r[worse] = margin. That is solvable IFF the margin field is a")
    print("  gradient -- IFF every loop's circulation is zero (curl-free; H^1 = 0).\n")
    cases = {
        "transitive (scarf>plastic>ribbon)": {(0, 1): 1, (1, 2): 1, (2, 0): -2},
        "Condorcet cycle (the value fork) ": {(0, 1): 1, (1, 2): 1, (2, 0): 1},
    }
    names = {0: "scarf", 1: "plastic", 2: "ribbon"}
    for label, m in cases.items():
        r, L = best_reward(m)
        total = sum(abs(v) for v in m.values())
        consistent = 1 - abs(circulation(m)) / total if total else 1.0
        c = circulation(m)
        cstr = "0" if c == 0 else f"{c:+d}"
        print(f"  {label}")
        print(f"     circulation around the loop = {cstr}    "
              f"(0 = a reward exists; !=0 = a hole)")
        if abs(L) < 1e-9:
            ranking = sorted(r, key=r.get, reverse=True)
            print(f"     -> reward fits: r = {{{', '.join(f'{names[k]}:{r[k]:+.1f}' for k in r)}}}")
            print(f"        a consistent ranking exists: {' > '.join(names[k] for k in ranking)}")
        else:
            print(f"     -> NO reward fits. Best least-squares reward is the flat tie "
                  f"r = {{{', '.join(f'{names[k]}:{r[k]:+.1f}' for k in r)}}}:")
            print(f"        the model can express NONE of the preference -- it is "
                  f"{(1-consistent)*100:.0f}% pure circulation.")
        print()
    print("  So a value fork is not a hard ranking problem; it is a field with curl.")
    print("  No potential (no reward, no 'ground truth' scalar) exists. To ship one")
    print("  anyway the model must CUT the loop somewhere -- and the cut is arbitrary,")
    print("  a topological defect. That cut is the external field of essay 2 and the")
    print("  casting vote of essay 1 -- the Arrovian dictator, now a tear in the space.")


# --------------------------------------------------------------------------- #
# 3. The actual topology of the disagreement (honest Betti numbers)
# --------------------------------------------------------------------------- #
def gf2_rank(rows):
    pivots, rank = {}, 0
    for r in rows:
        r = set(r)
        while r:
            p = min(r)
            if p in pivots:
                r ^= pivots[p]
            else:
                pivots[p] = r
                rank += 1
                break
    return rank


def betti(vertices, edges, triangles):
    """b0, b1 of a 2-complex over GF(2).

    b0 counts components; b1 counts independent loops not filled by triangles.
    (b0, b1) = (1, 0) rules out these two obstructions, but is not by itself a
    general proof of contractibility.
    """
    vidx = {v: i for i, v in enumerate(vertices)}
    eidx = {e: i for i, e in enumerate(edges)}
    d1 = [[vidx[e[0]], vidx[e[1]]] for e in edges]
    r1 = gf2_rank(d1)
    b0 = len(vertices) - r1
    d2 = [[eidx[tuple(sorted((t[0], t[1])))],
           eidx[tuple(sorted((t[1], t[2])))],
           eidx[tuple(sorted((t[0], t[2])))]] for t in triangles]
    r2 = gf2_rank(d2)
    b1 = (len(edges) - r1) - r2
    return b0, b1


def agreement_complex(ds, q, noise_floor=NOISE_FLOOR):
    """Thresholded flag complex of the 'same camp' graph.

    An edge joins two annotators when their co-deviation from the item mean is
    positive and at least ``noise_floor`` times the strongest positive coupling
    for this question. Annotators with no retained edge are returned separately
    as unaligned; counting them as one-person camps makes near-consensus data
    look spuriously disconnected.

    This is an exploratory camp diagnostic. It is not Chichilnisky's preference
    space and its Betti numbers do not, by themselves, establish the theorem's
    hypotheses on these data.
    """
    anns = ds["annotators"]
    v = {a: [it["labels"][q][a] for it in ds["items"]] for a in anns}
    ni = len(ds["items"])
    mu = [sum(v[a][k] for a in anns) / len(anns) for k in range(ni)]
    couplings = {}
    for a, b in itertools.combinations(anns, 2):
        couplings[(a, b)] = sum(
            (v[a][k] - mu[k]) * (v[b][k] - mu[k]) for k in range(ni)
        )
    strongest = max((j for j in couplings.values() if j > 0), default=0.0)
    threshold = noise_floor * strongest
    edges = [edge for edge, j in couplings.items()
             if strongest > 0 and j >= threshold - 1e-12]
    aligned = {a for edge in edges for a in edge}
    vertices = [a for a in anns if a in aligned]
    unaligned = [a for a in anns if a not in aligned]
    eset = set(edges)
    tris = [c for c in itertools.combinations(vertices, 3)
            if all(tuple(sorted((c[i], c[j]))) in eset for i, j in [(0, 1), (1, 2), (0, 2)])]
    return vertices, edges, tris, unaligned, threshold


def components_of(vertices, edges):
    """Connected components of an undirected graph, in stable display order."""
    neighbours = {v: set() for v in vertices}
    for a, b in edges:
        neighbours[a].add(b)
        neighbours[b].add(a)
    unseen = set(vertices)
    components = []
    while unseen:
        start = min(unseen)
        stack, component = [start], []
        unseen.remove(start)
        while stack:
            node = stack.pop()
            component.append(node)
            for nxt in sorted(neighbours[node], reverse=True):
                if nxt in unseen:
                    unseen.remove(nxt)
                    stack.append(nxt)
        components.append(sorted(component))
    return sorted(components, key=lambda c: (c[0], len(c)))


def betti_section(ds):
    print("\n" + BAR + "\n3. THE SHAPE OF THE DISAGREEMENT  --  Betti numbers of the real data\n" + BAR)
    print("  Build a thresholded graph of 'who shares a camp': retain positive")
    print(f"  co-deviation at >= {NOISE_FLOOR:.0%} of the strongest coupling, then form its flag")
    print("  complex. Annotators with no retained tie are UNALIGNED, not one-person")
    print("  camps. b0 counts camp components; b1 counts unfilled loops. This is an")
    print("  exploratory diagnostic, not a reconstruction of Chichilnisky's preference")
    print("  space or, by itself, a proof that a ground truth exists.\n")
    cohorts = {name: set(members) for name, members in ds["cohorts"].items()}
    for q in ("synthetic", "explicit"):
        V, E, T, unaligned, threshold = agreement_complex(ds, q)
        b0, b1 = betti(V, E, T)
        components = components_of(V, E)
        if not components:
            verdict = "no above-noise camp structure detected"
        elif b1 > 0:
            verdict = "an unfilled loop is present in the retained camp complex"
        elif b0 > 1:
            verdict = f"{b0} structured camps are disconnected"
        else:
            verdict = "one structured camp; no multi-camp split detected"
        print(f"  {q:9s}  (b0, b1) = ({b0}, {b1})   {verdict}")
        if components:
            print("             camps: " + " + ".join("{" + ", ".join(c) + "}" for c in components))
        if unaligned:
            print(f"             unaligned (no retained tie): {', '.join(unaligned)}")
        if len(components) == 2:
            matched = []
            for component in components:
                matches = [name for name, members in cohorts.items()
                           if set(component).issubset(members)]
                matched.append(matches[0] if len(matches) == 1 else None)
            if None not in matched and len(set(matched)) == 2:
                print("             ^ the two components recover the cores of the two named cohorts;")
                print("               unaligned annotators are not forced into either camp.")
        elif q == "synthetic" and len(components) == 1:
            print("             ^ only one small co-deviation pocket survives the floor; the")
            print("               near-unanimous vote contains no structured opposing camps.")
        print(f"             retained-coupling floor: {threshold:.6f}")
    print()
    print("  The noise floor is load-bearing and heuristic. Without it, near-zero")
    print("  residual ties fragment a near-consensus question into fake one-person")
    print("  'worldviews'. A production use should report threshold sensitivity rather")
    print("  than treating this one illustrative setting as universal.")
    print()
    # A constructed example of the other obstruction: a loop with no center.
    ring_V = ["c1", "c2", "c3", "c4"]
    ring_E = [("c1", "c2"), ("c2", "c3"), ("c3", "c4"), ("c1", "c4")]
    b0, b1 = betti(ring_V, ring_E, [])
    print(f"  (illustrative) four annotators who agree only around a ring "
          f"c1-c2-c3-c4-c1,")
    print(f"  no one agreeing across the diagonal: (b0, b1) = ({b0}, {b1}). A hole with")
    print(f"  no center -- everyone locally agrees, yet there is no global consensus to")
    print(f"  contract to. Here b1=1 records the loop explicitly; connecting this proxy")
    print(f"  complex to a formal social-choice domain requires additional assumptions.")


# --------------------------------------------------------------------------- #
# 4. The unification
# --------------------------------------------------------------------------- #
def unification():
    print("\n" + BAR + "\nONE DEFECT, THREE NAMES  --  the triptych closes\n" + BAR)
    rows = [
        ("essay 1  (social choice)", "no neutral rule for >=3 options", "Arrow's impossibility"),
        ("essay 2  (statistical mechanics)", "competing constraints, no ground state", "frustration / a spin glass"),
        ("essay 3  (topology)", "preference space is not contractible", "disconnection or a hole"),
    ]
    for a, b, c in rows:
        print(f"  {a:34s} {b:42s} {c}")
    print()
    print("  Baryshnikov (1993) proved essays 1 and 3 are literally the same theorem:")
    print("  Arrow's dictator is the topological obstruction, counted instead of seen.")
    print("  A Condorcet cycle (essay 1) is a frustrated loop (essay 2) is a generator")
    print("  of H^1 (essay 3) is nonzero curl with no reward potential. One hole.")
    print("  'Ground truth has no ground' = 'the preference space has no contractible")
    print("  center to call the ground.' Where it does (a fact), collapse freely. Where")
    print("  it doesn't (a value fork), there is no point to collapse to -- only the")
    print("  distribution, and a named human who decides where to cut.")


def main():
    with open(DATA) as f:
        ds = json.load(f)
    print(BAR + "\nTHE HOLE UNDER THE IMPOSSIBILITY"
          "\ntopological social choice (Chichilnisky 1980), run on data/labels.json\n" + BAR)
    circle_section()
    hodge_section()
    betti_section(ds)
    unification()


if __name__ == "__main__":
    main()
