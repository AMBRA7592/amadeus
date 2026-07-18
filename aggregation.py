#!/usr/bin/env python3
"""
aggregation.py -- the theorem under the thesis.

"Ground Truth Has No Ground" argues, in prose, that majority vote is "a
specific, contestable rule" -- not a neutral readout of fact. Social choice
theory, the mathematics of turning many judgements into one, proved exactly
this (and its precise converse) decades ago. This script runs three of those
results against the very dataset in data/labels.json, so the claim stops being
rhetoric and becomes arithmetic you can re-run.

  ARROW (1951)    For >= 3 options there is NO aggregation rule that is at once
                  unanimous, independent of irrelevant alternatives, and
                  non-dictatorial. Neutrality is impossible; you only choose
                  which axiom to break.                      -> the ribbon.

  MAY (1952)      For exactly 2 options, simple majority IS the unique rule
                  that is anonymous, neutral, and positively responsive.
                  Majority vote is provably right -- but only here, and only
                  while one side actually outnumbers the other.
                                                             -> the binary cells.

  CONDORCET (1785) Majority tracks a truth only if (a) a truth exists, (b)
                  voters are independent, and (c) each beats chance. Break
                  independence -- a shared cohort norm -- and adding annotators
                  stops finding truth and starts amplifying the dominant norm
                  with rising, false confidence.             -> "get more labels".

This proof/illustration is intentionally pinned to data/labels.json: its printed
narrative names the demo's cohorts, ribbon, and 4-4 forks. For arbitrary
annotations use disagreement.py, soft_labels.py, and resolution.py with --data.

No third-party dependencies (stdlib only; Python 3.8+). Run: python3 aggregation.py
"""

import json
import math
import os
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data", "labels.json")
BAR = "=" * 78


# --------------------------------------------------------------------------- #
# tiny stdlib-only stats (math.comb is 3.10+, so we roll our own to keep 3.8+)
# --------------------------------------------------------------------------- #
def comb(n, k):
    if k < 0 or k > n:
        return 0
    return math.factorial(n) // (math.factorial(k) * math.factorial(n - k))


def majority_correct(n, p):
    """P(a majority of n independent voters is correct), each correct w.p. p.
    n is forced odd so 'majority' never ties. This is the Condorcet Jury
    Theorem's engine: for p > 1/2 it climbs to 1 as n grows."""
    need = n // 2 + 1
    return sum(comb(n, k) * p**k * (1 - p)**(n - k) for k in range(need, n + 1))


def effective_n(n, rho):
    """Effective sample size of n voters with intraclass correlation rho.
    Correlated voters carry less independent information; this is the standard
    design-effect correction. As n -> inf it saturates at 1/rho: a shared norm
    caps how much the crowd can ever know, no matter how many you hire."""
    return n / (1 + (n - 1) * rho)


def nearest_odd(x):
    k = max(1, int(round(x)))
    return k if k % 2 == 1 else k - 1 if k > 1 else 1


# --------------------------------------------------------------------------- #
def load():
    with open(DATA) as f:
        ds = json.load(f)
    return ds["items"], ds["cohorts"], ds["questions"]


def cell_counts(votes):
    return Counter(votes.values())


def plurality(counts):
    top = max(counts.values())
    winners = sorted(str(l) for l, c in counts.items() if c == top)
    return winners[0], top, len(winners) > 1, winners


# --------------------------------------------------------------------------- #
# 0. Regime map: which theorem even applies to each cell?
# --------------------------------------------------------------------------- #
def regime_map(items, cohorts, questions):
    print(BAR + "\n0. WHICH THEOREM APPLIES  --  May's world vs Arrow's world\n" + BAR)
    print("  A cell is in MAY's world if the question is binary (2 options): there,")
    print("  majority vote is the *uniquely* fair rule -- collapse it with a clear")
    print("  conscience. It is in ARROW's world if there are >=3 live options: there,")
    print("  no aggregation rule is neutral, and 'the' majority label is an artifact")
    print("  of the rule you happened to pick.\n")
    may = arrow = 0
    for it in items:
        for q, votes in it["labels"].items():
            counts = cell_counts(votes)
            live = sum(1 for c in counts.values() if c)
            qtype = questions[q]["type"]
            world = "MAY  (binary)" if qtype == "binary" else "ARROW (multi)"
            if qtype == "binary":
                may += 1
            else:
                arrow += 1
            maj, top, tie, _ = plurality(counts)
            share = top / sum(counts.values())
            note = ""
            if tie:
                note = "  <- exact tie: May's rule is SILENT here (see 2)"
            elif qtype != "binary" and share < 0.5:
                note = "  <- plurality < 50%: the 'winner' is a minority (see 1)"
            print(f"  {it['id']} / {q:9s}  {world:14s}  live_options={live}  "
                  f"plurality={maj!r}@{share*100:.0f}%{note}")
    print(f"\n  {may} cells in May's world (binary), {arrow} in Arrow's world (multi-option).")


# --------------------------------------------------------------------------- #
# 1. ARROW, on the ribbon: same ballots, the "fact" depends on the rule
# --------------------------------------------------------------------------- #
def arrow_on_ribbon(items):
    print("\n" + BAR + "\n1. ARROW'S WORLD  --  the ribbon: a fact that changes with the rule\n" + BAR)
    target = next((it for it in items if it["id"] == "img1"), items[0])
    counts = cell_counts(target["labels"]["ribbon"])
    n = sum(counts.values())
    maj, top, tie, _ = plurality(counts)
    ordered = counts.most_common()
    print(f"  {target['id']} / ribbon   ballots (n={n}): "
          f"{ {k: v for k, v in ordered} }")
    print(f"\n  PLURALITY ('majority vote') says ground truth = {maj!r} "
          f"at {top}/{n} = {top/n*100:.1f}%.")
    print(f"  But {n - top}/{n} = {(n-top)/n*100:.1f}% of annotators said something else.")
    print(f"  The single word shipped as 'ground truth' is the modal *minority* opinion.\n")

    print("  Now keep the same ballots and change only the aggregation rule:\n")
    print(f"  - PLURALITY              -> {maj!r}  (one rule, one winner)")
    print(f"  - RANDOM DICTATOR        -> a lottery (this rule is anonymous, Pareto,")
    print(f"                              and strategyproof -- impeccable credentials):")
    for lab, c in ordered:
        print(f"        P(ground truth = {str(lab)!r}) = {c}/{n} = {c/n:.3f}")
    print(f"    Under this equally-defensible rule, {maj!r} is the answer only "
          f"{top/n*100:.0f}% of the time.")
    print("\n  Nobody changed their mind. The 'ground truth' moved because the RULE")
    print("  moved. That is Arrow's impossibility you can hold in your hand: with")
    print("  >=3 options there is no neutral way to pick one, so 'the label' is")
    print("  always partly a property of the aggregator, never purely of the data.")


# --------------------------------------------------------------------------- #
# 2. MAY, and where it runs out: the 4-4 fork resolved by alphabetical order
# --------------------------------------------------------------------------- #
def may_and_the_castingvote(items, cohorts, questions):
    print("\n" + BAR + "\n2. MAY'S WORLD, AND WHERE IT RUNS OUT  --  the tie-break is a casting vote\n" + BAR)
    print("  May's theorem blesses majority vote for binary choices -- but its")
    print("  'positive responsiveness' axiom only bites when one side has MORE votes.")
    print("  At an exact tie the theorem is silent, and whatever breaks the silence")
    print("  is doing un-axiomatized, unelected work. Watch it happen on real cells.\n")

    forks = []
    for it in items:
        for q, votes in it["labels"].items():
            if questions[q]["type"] != "binary":
                continue
            counts = cell_counts(votes)
            _, top, tie, winners = plurality(counts)
            if tie:
                A = Counter(votes[m] for m in cohorts["A"] if m in votes)
                B = Counter(votes[m] for m in cohorts["B"] if m in votes)
                forks.append((it["id"], q, counts, A, B, winners))

    names = {q: questions[q].get("labels", {}) for q in questions}
    a_wins = 0
    for item_id, q, counts, A, B, winners in forks:
        lab = names[q]
        shipped_key = winners[0]                 # exactly what disagreement.py's sorted()[0] picks
        shipped = lab.get(shipped_key, shipped_key)
        # Re-label the SAME ballots so the other option sorts first; nothing human changes.
        flipped_key = sorted(winners, reverse=True)[0]
        flipped = lab.get(flipped_key, flipped_key)
        a_maj = max(A, key=A.get)
        a_label = lab.get(str(a_maj), str(a_maj))
        if shipped_key == str(a_maj):
            a_wins += 1
        print(f"  {item_id} / {q}:  {dict(counts)}  -> 4-4 TIE, a value fork.")
        print(f"      cohort A leans {a_label!r}, cohort B leans the other reading.")
        print(f"      sorted()[0] ships .......... {shipped!r}   (because {shipped_key!r} sorts first)")
        print(f"      rename the keys and re-run .. {flipped!r}   (same ballots, opposite 'truth')")
        print()
    if forks:
        print(f"  The casting vote was cast by STRING ORDER. And notice the pattern:")
        print(f"  cohort A's reading won {a_wins}/{len(forks)} forks -- not on the merits, but because")
        print(f"  its label sorts first. A pipeline that 'has no policy on safety' has,")
        print(f"  in fact, adopted one: whatever alphabetises lowest. That is the silent")
        print(f"  governance decision the essay names, caught in the act.")


# --------------------------------------------------------------------------- #
# 3. CONDORCET: when more annotators help, and when they make it worse
# --------------------------------------------------------------------------- #
def condorcet(p=0.6, rho=0.3):
    print("\n" + BAR + "\n3. CONDORCET'S WORLD  --  does adding annotators find truth, or bury it?\n" + BAR)
    print(f"  Suppose each annotator is right with probability p={p} on a question that")
    print(f"  HAS a right answer. The Condorcet Jury Theorem says majority vote then")
    print(f"  converges to truth as you add voters. This is the case the words 'ground")
    print(f"  truth' were built for:\n")
    print(f"      annotators (independent)   P(majority correct)")
    for n in (1, 3, 9, 27, 81):
        print(f"        n={n:<4d}                   {majority_correct(n, p):.4f}")
    print(f"\n  -> add labelers, get truer. Majority vote EARNS its authority here.\n")

    print(f"  Now break independence. Let the annotators share a cohort norm, modeled")
    print(f"  as intraclass correlation rho={rho} (the San-Francisco-vs-Tokyo effect:")
    print(f"  people in the same normative frame err together). Correlated voters carry")
    print(f"  less independent information, so the effective crowd size saturates:\n")
    print(f"      annotators (corr. rho={rho})   effective n   P(majority correct)")
    cap = 1 / rho
    for n in (1, 3, 9, 27, 81):
        ne = effective_n(n, rho)
        acc = majority_correct(nearest_odd(ne), p)
        print(f"        n={n:<4d}                   {ne:5.2f}        {acc:.4f}")
    print(f"\n  -> no matter how many you hire, the crowd behaves like ~{cap:.1f} independent")
    print(f"     voters. Scaling buys you almost nothing once a shared norm is present.\n")

    print(f"  And the sting: if that shared norm points AWAY from the minority's reading,")
    print(f"  the same crowd is, in effect, right with probability p<1/2 -- so the jury")
    print(f"  theorem runs in reverse and majority vote converges to the WRONG answer,")
    print(f"  with mounting confidence:\n")
    q = 1 - p  # the dominant norm pushes the popular-but-wrong way
    print(f"      annotators (biased, p={q})    P(majority correct)")
    for n in (1, 3, 9, 27, 81):
        print(f"        n={n:<4d}                   {majority_correct(n, q):.4f}")
    print(f"\n  -> 'get more labels', the reflex for hard cases, here manufactures")
    print(f"     consensus: it makes the dominant norm look MORE certain, not more true.")


# --------------------------------------------------------------------------- #
def main():
    items, cohorts, questions = load()
    print(BAR)
    print("THE THEOREM UNDER THE THESIS")
    print("social choice theory, run against data/labels.json")
    print(BAR)
    regime_map(items, cohorts, questions)
    arrow_on_ribbon(items)
    may_and_the_castingvote(items, cohorts, questions)
    condorcet()
    print("\n" + BAR + "\nTAKEAWAY\n" + BAR)
    print("  The essay says majority vote is 'a specific, contestable rule.' The math")
    print("  says more: for >=3 options NO rule is neutral (Arrow), for 2 options")
    print("  majority is the ONLY fair one but goes silent at a tie (May), and adding")
    print("  annotators finds truth only when a truth exists and voters are independent")
    print("  (Condorcet). So the honest deliverable is not just the distribution -- it")
    print("  is the distribution PLUS the name of the rule you used to collapse it,")
    print("  because in Arrow's world the rule is part of the answer.")


if __name__ == "__main__":
    main()
