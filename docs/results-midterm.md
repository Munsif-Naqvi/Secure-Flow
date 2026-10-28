# Midterm results: SecureFlow on the test corpus

**Status: not run yet.** The five corpus apps (`docs/07-test-corpus.md`) are not in `corpus/` yet. When they are, run the scorer and paste its output below.

## How the results are made
```
python engine/score.py corpus/ > scratch.md
```
`engine/score.py` scans every app folder in `corpus/` that has a `ground_truth.json`, then compares the findings with it:

- **Found** (true positive): a `should_flag` entry that the engine flagged.
- **Missed**: a `should_flag` entry that the engine did not flag.
- **False alarm** (false positive): a finding that matches no `should_flag` entry. The details say whether the route was listed as public by design or not listed at all.

A finding matches an entry when the `url_path` is equal and, if the entry lists `http_methods`, the route shares at least one of them. All findings are Unconfirmed: they come from reading the code only.

## Results
_To be filled in from the scorer output._
