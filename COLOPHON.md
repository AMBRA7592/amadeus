# Colophon

**Author:** Amadeus Brandes  
**Repository:** https://github.com/releasecontrol/groundless-truth  
**Production period:** April–July 2026

## Authorship and method

The thesis and the editorial responsibility for this project are human-directed.
AI assisted with research, drafting, implementation, and auditing. Every
executable claim was independently re-derived, tested, and guarded by continuous
integration.

## What "verified" means here

The repository keeps two kinds of evidence visibly apart:

- **Tier 1 — CI-pinned.** The runnable demonstrations accompanying the four
  foundational treatments, and every quoted headline number in the essays and
  tools, are recomputed by `test_claims.py` on every push and pull request
  against Python 3.8 and 3.12. If the prose disagrees with what the code
  computes, CI fails. For these, *verified* means mechanically re-derived on
  committed or synthetic data — not asserted.
- **Tier 2 — manifest-reproducible.** The external-data results (the ChaosNLI
  reproducibility report and the bounded Measuring Hate Speech pilot) are
  produced from pinned dataset revisions and published as aggregate reports and
  manifests — counts, checksums, and results, never source rows or identifiers.
  For these, *verified* means reproducible by re-download against a recorded
  checksum, not regenerated inside CI.

The four foundational treatments—the aggregation theorem, spin-glass mapping,
topological obstruction, and information-geometry centres—are mathematical.
Under their stated assumptions, they identify conditions in which these failure
modes are unavoidable. Whether they are frequent in any given dataset is a
separate empirical question.

## Tools

AI tools were used collectively for research, drafting, implementation, and
independent auditing; individual tools are not enumerated. Editorial
responsibility for the thesis, the claims, and their disposition rests with the
author.

## Citation and license

Repository citation metadata is maintained in [`CITATION.cff`](CITATION.cff).
The code and operational content are released under the MIT license (`LICENSE`);
the six essays are released under CC BY 4.0 (`LICENSE-CC-BY-4.0.txt`). See
[`LICENSING.md`](LICENSING.md).
