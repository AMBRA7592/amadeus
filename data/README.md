# Bring your own annotations

The three operational tools accept this repository's JSON input format:

```bash
python3 disagreement.py --data my_labels.json --out out/
python3 soft_labels.py --data my_labels.json --out out/
python3 govern.py list --out out/
# optional: python3 govern.py decide --item ID --question Q --owner OWNER --decision LABEL --rationale WHY --out out/
python3 resolution.py --data my_labels.json --out out/
```

Use the same `--data` and `--out` values for the three data-processing commands.
The stages run in order: `soft_labels.py` consumes `out/triage.json`, `govern.py`
reads or updates `out/governance.jsonl`, and `resolution.py` consumes the triage,
soft-label, and governance artifacts already in `out/`. The data-processing tools
create the output directory when needed.

The machine-readable contract is
[`schema/labels.schema.json`](../schema/labels.schema.json). The tools also run
standard-library cross-field checks that JSON Schema cannot conveniently
express, such as ensuring every vote refers to a declared annotator.

## The format

```json
{
  "_about": "A minimal two-item example.",
  "questions": {
    "sentiment": {
      "type": "binary",
      "labels": {"0": "negative", "1": "positive"},
      "note": "The judgement requested from each annotator."
    }
  },
  "annotators": ["ann-a", "ann-b"],
  "cohorts": {"all": ["ann-a", "ann-b"]},
  "items": [
    {
      "id": "case-1",
      "desc": "First item shown to the annotators.",
      "labels": {"sentiment": {"ann-a": 1, "ann-b": 0}},
      "reasons": {
        "sentiment": {"ann-b": "The wording reads negatively to me."}
      }
    },
    {
      "id": "case-2",
      "desc": "Second item shown to the annotators.",
      "labels": {"sentiment": {"ann-a": 0, "ann-b": 0}}
    }
  ]
}
```

The fields are:

- `_about` is optional free-text provenance for the dataset.
- `questions` declares every judgement axis. Each question has a `type`, a
  label definition, and an optional `note`.
- `annotators` is the unique global list of annotator identifiers.
- `cohorts` groups annotators by normative context. Every member must occur in
  `annotators`.
- `items` is a non-empty array. Every item has a unique `id`, optional `desc`,
  and one non-empty vote map for every declared question.
- `labels[question]` maps annotator identifier to that annotator's stored value.
  Partial annotation is allowed, but every named annotator must be declared.
- `reasons` is optional. It maps question, then annotator, to a free-text reason.

## Binary versus categorical questions

A binary question uses integer votes `0` and `1`. Its `labels` declaration maps
their JSON string forms to display names:

```json
"explicit": {
  "type": "binary",
  "labels": {"0": "safe", "1": "explicit / flag"}
}
```

A categorical question stores the label string itself, and the declaration is
the complete allowed list:

```json
"ribbon": {
  "type": "categorical",
  "labels": ["none", "scarf", "plastic", "ribbon", "unknown"]
}
```

The tools reject binary values other than integer `0`/`1`, categorical values
outside the declared list, unknown questions, and unknown annotators.

## From a Label Studio JSON export

The following recipe assumes one Label Studio task per item, one completed
annotation per annotator, and choice controls whose `from_name` equals the
question name. A typical result used by the recipe looks like this:

```json
{
  "id": "case-1",
  "data": {"text": "First item"},
  "annotations": [{
    "completed_by": {"id": "ann-a"},
    "result": [{
      "from_name": "sentiment",
      "value": {"choices": ["positive"]}
    }]
  }]
}
```

Save the export as `label-studio-export.json`, adjust `QUESTIONS` and
`BINARY_CHOICES`, and run this standard-library script:

```python
import json
from pathlib import Path

QUESTIONS = {
    "sentiment": {
        "type": "binary",
        "labels": {"0": "negative", "1": "positive"},
    }
}
BINARY_CHOICES = {"sentiment": {"negative": 0, "positive": 1}}


def annotator_id(annotation):
    value = annotation["completed_by"]
    if isinstance(value, dict):
        value = value.get("id") or value.get("email") or value.get("username")
    if value is None:
        raise ValueError("annotation has no completed_by identifier")
    return str(value)


tasks = json.loads(Path("label-studio-export.json").read_text(encoding="utf-8"))
annotators = set()
items = []
for task in tasks:
    labels = {question: {} for question in QUESTIONS}
    for annotation in task.get("annotations", []):
        annotator = annotator_id(annotation)
        annotators.add(annotator)
        for result in annotation.get("result", []):
            question = result.get("from_name")
            if question not in QUESTIONS:
                continue
            choices = result.get("value", {}).get("choices", [])
            if len(choices) != 1:
                raise ValueError("expected one choice for {!r}".format(question))
            choice = choices[0]
            if QUESTIONS[question]["type"] == "binary":
                choice = BINARY_CHOICES[question][choice]
            labels[question][annotator] = choice
    empty = [question for question, votes in labels.items() if not votes]
    if empty:
        raise ValueError("task {!r} has no votes for {}".format(task["id"], empty))
    items.append({
        "id": str(task["id"]),
        "desc": str(task.get("data", {}).get("text", "")),
        "labels": labels,
    })

annotators = sorted(annotators)
dataset = {
    "_about": "Converted from Label Studio.",
    "questions": QUESTIONS,
    "annotators": annotators,
    "cohorts": {"all": annotators},
    "items": items,
}
Path("labels.json").write_text(
    json.dumps(dataset, indent=2) + "\n", encoding="utf-8"
)
```

Label Studio projects vary. If your controls use `labels`, `textarea`, or
multiple-choice values instead of `choices`, adapt the small extraction block;
the output contract remains the same.

## From a wide CSV

For a table with one row per item, name vote columns
`QUESTION__ANNOTATOR`. For example:

```csv
item_id,desc,sentiment__ann-a,sentiment__ann-b
case-1,First item,1,0
case-2,Second item,0,0
```

Save it as `labels-wide.csv`, adjust `QUESTIONS`, and run:

```python
import csv
import json
from pathlib import Path

QUESTIONS = {
    "sentiment": {
        "type": "binary",
        "labels": {"0": "negative", "1": "positive"},
    }
}

with Path("labels-wide.csv").open(newline="", encoding="utf-8") as handle:
    reader = csv.DictReader(handle)
    vote_columns = []
    annotators = set()
    for column in reader.fieldnames or []:
        if "__" not in column:
            continue
        question, annotator = column.split("__", 1)
        if question not in QUESTIONS:
            raise ValueError("unknown question column {!r}".format(question))
        vote_columns.append((column, question, annotator))
        annotators.add(annotator)

    items = []
    for row in reader:
        labels = {question: {} for question in QUESTIONS}
        for column, question, annotator in vote_columns:
            raw = row.get(column, "").strip()
            if not raw:
                continue
            value = int(raw) if QUESTIONS[question]["type"] == "binary" else raw
            labels[question][annotator] = value
        empty = [question for question, votes in labels.items() if not votes]
        if empty:
            raise ValueError("row {!r} has no votes for {}".format(row["item_id"], empty))
        items.append({
            "id": row["item_id"],
            "desc": row.get("desc", ""),
            "labels": labels,
        })

annotators = sorted(annotators)
dataset = {
    "_about": "Converted from a wide CSV.",
    "questions": QUESTIONS,
    "annotators": annotators,
    "cohorts": {"all": annotators},
    "items": items,
}
Path("labels.json").write_text(
    json.dumps(dataset, indent=2) + "\n", encoding="utf-8"
)
```

## Validate and run

The first tool performs the runtime checks without any dependency:

```bash
python3 disagreement.py --data labels.json --out out/
```

For full JSON Schema validation, install `jsonschema` in your own environment
and run:

```bash
python3 -c 'import json; from jsonschema import Draft202012Validator; s=json.load(open("schema/labels.schema.json")); Draft202012Validator.check_schema(s); Draft202012Validator(s).validate(json.load(open("labels.json"))); print("labels.json valid")'
```

Then complete the pipeline with the same paths:

```bash
python3 soft_labels.py --data labels.json --out out/
python3 govern.py list --out out/
python3 resolution.py --data labels.json --out out/
```

If `govern.py list` shows a pending value fork, a named owner can record the
decision before the resolution step. For example, the bundled demo contains
the pending `img2 / explicit` fork:

```bash
python3 govern.py decide \
  --item img2 \
  --question explicit \
  --owner "Safety policy owner" \
  --decision safe \
  --rationale "Apply the documented editorial-context policy." \
  --out out/
```

For your data, use an item, question, and decision shown by your own queue.

The command atomically updates `out/governance.jsonl`, refuses placeholder
owners or blank decisions/rationales, and will not overwrite an existing
decision. Re-running `soft_labels.py` preserves the owner, decision, rationale,
and `decided_at` timestamp. Run `resolution.py` afterward to emit the resulting
`decided:<label>` disposition with `named_owner` authority.

## Cohorts are optional in meaning, but load-bearing in the format

The `cohorts` field is required because value-fork detection asks whether
coherent groups reach different conclusions. If you have no meaningful
normative cohorts, put every annotator in one group as the examples do:

```json
"cohorts": {"all": ["ann-a", "ann-b"]}
```

With one cohort, the tools still compute distributions, entropy, likely errors,
and review routing, but they cannot claim cohort divergence. Do not invent
cohorts merely to make value-fork detection fire.
