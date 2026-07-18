#!/usr/bin/env python3
"""
soft_labels.py -- emit kept distributions in a form a trainer actually consumes.

Standard pipelines hand the trainer one column: the majority label. This emits
the full distribution as a soft label, a per-cell training weight derived from
the entropy of disagreement, and a routing flag that tells the training loop how
to treat the cell. The argument "preserve the disagreement" stops being a
recommendation and becomes a file format.

Three outputs:
  1. soft_labels.jsonl  -- one record per (item, question), trainer-ready
  2. soft_labels.csv    -- the same, flat, for eyeballing
  3. governance.jsonl   -- value forks routed to a NAMED human owner; a queue of
                           policy decisions that must be made before the affected
                           cells may enter the training pool.

Weighting (transparent on purpose):
  training_weight = 1 - normalized_entropy   (so unanimous cells -> 1.0,
  contested cells -> proportionally less). Two routings are *gated out* of the
  usable signal and carry weight 0:
    - value_fork   : not training data; a governance decision (see governance.jsonl)
    - human_review : held back this epoch (its would-be weight is kept as
                     `provisional_weight` so it can be admitted once reviewed).

Run AFTER disagreement.py (it consumes triage.json):
    python3 disagreement.py && python3 soft_labels.py
"""

import argparse
import csv
import json
import math
import os
from collections import Counter

from disagreement import PIPELINE_EPILOG, load_dataset

HERE = os.path.dirname(os.path.abspath(__file__))
TRIAGE = os.path.join(HERE, "triage.json")
DATA = os.path.join(HERE, "data", "labels.json")
OUT_JSONL = os.path.join(HERE, "soft_labels.jsonl")
OUT_CSV = os.path.join(HERE, "soft_labels.csv")
OUT_GOV = os.path.join(HERE, "governance.jsonl")

GATED = {"value_fork", "human_review"}   # routings that contribute 0 usable weight


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


def normalize_counts(distribution):
    """Vote counts -> probability vector. (Plain normalization, not a softmax:
    these are observed human frequencies, and exponentiating them would invent
    confidence the annotators never expressed.)"""
    total = sum(distribution.values())
    return {label: count / total for label, count in distribution.items()} if total else {}


def confidence(entropy_bits, support_size):
    """1 - normalized entropy. Unanimous cell -> 1.0; maximal disagreement -> 0.0."""
    if support_size <= 1:
        return 1.0
    max_entropy = math.log2(support_size)
    return round(1.0 - entropy_bits / max_entropy, 3) if max_entropy else 1.0


def routing_for(verdict):
    return {
        "CONFIDENT": "supervised",
        "CONTESTED:VALUE-FORK": "value_fork",      # not training data; governance
        "CONTESTED:NO-GROUND": "soft_label_only",  # train on distribution, never collapse
        "CONTESTED:VARIATION": "soft_label_only",
    }.get(verdict, "human_review")                 # REVIEW -> held back


def label_name(question, key, questions):
    """Map a stored label key to its human name (binary 0/1 -> words);
    categorical labels are already their own names."""
    labels = questions.get(question, {}).get("labels")
    if isinstance(labels, dict):
        return labels.get(str(key), str(key))
    return str(key)


def load_prior_governance(path):
    """Prior governance records, keyed by (item_id, question). A backlog must
    persist: a re-run must never erase a human's owner assignment or recorded
    decision. Without this, the demo would model the very state-loss the essay
    condemns."""
    prior = {}
    if os.path.exists(path):
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line:
                    r = json.loads(line)
                    prior[(r["item_id"], r["question"])] = r
    return prior


def main(argv=None):
    args = _parse_args(argv)
    data_path = args.data
    out_dir = os.path.abspath(args.out or os.getcwd())
    os.makedirs(out_dir, exist_ok=True)
    triage_path = os.path.join(out_dir, "triage.json")
    out_jsonl = os.path.join(out_dir, "soft_labels.jsonl")
    out_csv = os.path.join(out_dir, "soft_labels.csv")
    out_gov = os.path.join(out_dir, "governance.jsonl")

    if not os.path.exists(triage_path):
        raise SystemExit("triage.json not found -- run `python3 disagreement.py` first.")
    with open(triage_path) as f:
        triage = json.load(f)
    questions = load_dataset(data_path)["questions"]

    records, governance = [], []
    for c in triage["cells"]:
        q = c["question"]
        routing = routing_for(c["verdict"])
        support = sum(1 for v in c["distribution"].values() if v > 0)
        prov = confidence(c["entropy_bits"], support)        # would-be weight
        weight = 0.0 if routing in GATED else prov           # usable-now weight

        soft = {label_name(q, k, questions): round(p, 3)
                for k, p in normalize_counts({k: int(v) for k, v in c["distribution"].items()}).items()}
        maj = label_name(q, c["majority_vote"], questions)

        rec = {
            "item_id": c["item"], "question": q, "routing": routing,
            "soft_label": soft, "majority_label": maj,
            "entropy_bits": c["entropy_bits"], "training_weight": weight,
            "n_annotators": c["n"], "reasons_present": bool(c.get("reasons")),
            "manufactured_consensus": c.get("manufactured_consensus", False),
        }
        if routing == "human_review":
            rec["provisional_weight"] = prov                 # admit after a human looks
        records.append(rec)

        if routing == "value_fork":
            governance.append({
                "item_id": c["item"], "question": q,
                "cohort_majorities": {k: (label_name(q, v, questions) if v is not None else None)
                                      for k, v in c["cohort_majorities"].items()},
                "soft_label": soft, "reasons": c.get("reasons", {}),
                "decision_required_from": "<named human owner -- to be assigned>",
                "decision_recorded": None, "decision_rationale": None,
            })

    with open(out_jsonl, "w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")
    with open(out_csv, "w", newline="") as f:
        w = csv.writer(f)
        cols = ["item_id", "question", "routing", "majority_label", "entropy_bits",
                "training_weight", "n_annotators", "reasons_present",
                "manufactured_consensus", "soft_label"]
        w.writerow(cols)
        for r in records:
            w.writerow([r.get(c) if c != "soft_label" else json.dumps(r["soft_label"]) for c in cols])
    # Merge with any prior governance file so owners and decisions survive re-runs.
    prior = load_prior_governance(out_gov)
    current_keys = set()
    merged = []
    for g in governance:
        key = (g["item_id"], g["question"])
        current_keys.add(key)
        if key in prior:                                 # preserve the human's input;
            p = prior[key]                               # refresh only annotation-derived fields
            g["decision_required_from"] = p.get("decision_required_from", g["decision_required_from"])
            g["decision_recorded"] = p.get("decision_recorded")
            g["decision_rationale"] = p.get("decision_rationale")
            if "decided_at" in p: g["decided_at"] = p["decided_at"]
            if "decision_off_menu" in p: g["decision_off_menu"] = p["decision_off_menu"]
        g["status"] = "decided" if g["decision_recorded"] is not None else "pending"
        merged.append(g)
    for key, p in prior.items():                         # don't drop a decided record just
        if key not in current_keys and p.get("decision_recorded") is not None:  # because the cell
            p["status"] = "resolved_no_longer_fork"      # is no longer a fork -- keep the audit trail
            merged.append(p)
    governance = merged
    with open(out_gov, "w") as f:
        for g in governance:
            f.write(json.dumps(g) + "\n")

    rc = Counter(r["routing"] for r in records)
    weight_sum = sum(r["training_weight"] for r in records)
    bar = "=" * 78
    print(bar + "\nSOFT LABEL EXPORT  --  what a trainer should actually consume\n" + bar)
    print(f"  records emitted .............................. {len(records)}")
    print(f"  supervised (confidence-weighted; unanimous=1.0) {rc['supervised']}")
    print(f"  soft_label_only (distribution preserved) ..... {rc['soft_label_only']}")
    print(f"  human_review (held back; weight 0 this epoch)  {rc['human_review']}")
    print(f"  value_fork (routed to governance; weight 0) .. {rc['value_fork']}")
    print()
    print(f"  usable training weight ....................... {weight_sum:.2f} / {len(records)}")
    print(f"  weight withheld (entropy + held-back + forks)  {len(records) - weight_sum:.2f}")
    print(f"  manufactured-consensus records flagged ....... {sum(r['manufactured_consensus'] for r in records)}")
    print()
    print(f"  trainer-ready jsonl  -> {os.path.relpath(out_jsonl, out_dir)}")
    print(f"  inspection csv       -> {os.path.relpath(out_csv, out_dir)}")
    pending = [g for g in governance if g.get("status") == "pending"]
    decided = [g for g in governance if g.get("status") != "pending"]
    print(f"  governance queue     -> {os.path.relpath(out_gov, out_dir)}  "
          f"({len(pending)} pending, {len(decided)} decided -- merged with prior runs)")

    if pending:
        print("\n  UNRESOLVED governance decisions (do NOT train until decided):")
        for g in pending:
            print(f"    {g['item_id']} / {g['question']}: cohorts diverge -> {g['cohort_majorities']}")

    print("\n" + bar + "\n  HOW TO USE THIS DOWNSTREAM\n" + bar)
    print("  supervised      : majority_label as hard target, weighted by training_weight.")
    print("  soft_label_only : cross-entropy against soft_label, weighted by training_weight.")
    print("                    Do NOT collapse to one class.")
    print("  human_review    : excluded this epoch; route to a labeler with reasons attached,")
    print("                    then re-admit at provisional_weight.")
    print("  value_fork      : EXCLUDED. A named owner must record a decision in")
    print("                    governance.jsonl before these cells may train anything.")


if __name__ == "__main__":
    main()
