"""SecureFlow scorer: compare the engine's findings with each app's ground truth.

Usage:
    python engine/score.py <corpus_folder>

<corpus_folder> holds one sub-folder per test app (corpus/app_01_notes/, ...).
Each app has a ground_truth.json that lists the routes that should be flagged
and the routes that are public by design (format: docs/07-test-corpus.md).

The scorer scans every app with the engine and prints a Markdown results table,
ready to paste into docs/results-midterm.md.

How a finding is matched to a ground truth entry:
    The url_path must be equal. If the entry also lists http_methods, the
    finding's route must share at least one of them. This keeps PUT and DELETE
    on the same path apart when the ground truth lists them separately.

Counting (per app):
    found        should_flag entries that at least one finding matches
    missed       should_flag entries that no finding matches
    false alarm  findings that match no should_flag entry
    not checked  should_flag entries of a problem type the engine does not
                 look for yet (for example missing_role_check). They are
                 listed on their own, not counted as missed.
    known limitation
                 findings that match a known_limitations entry: routes that
                 are not real problems but that the code-only scan is expected
                 to flag (for example a public page that reads the database).
                 They are listed on their own, not counted as false alarms.

Below the table the scorer prints precision and recall for the whole corpus:
    precision = found / (found + false alarms)   how many flags were right
    recall    = found / (found + missed)         how many real problems were flagged
"""

import json
import os
import sys

from main import scan

# The problem types the midterm engine looks for. An entry without a
# problem_type is treated as missing_login, like the example in docs/07.
CHECKED_PROBLEM_TYPES = {"missing_login"}


def load_ground_truth(app_folder):
    with open(os.path.join(app_folder, "ground_truth.json"), encoding="utf-8") as handle:
        return json.load(handle)


def finding_methods(finding, routes):
    """The HTTP methods of the route a finding was made for.

    Findings do not carry their methods, so look up the route at the same
    file, line and url_path in the scan's "routes" list.
    """
    for route in routes:
        if (route["file_path"], route["line_number"], route["url_path"]) == (
            finding["file_path"], finding["line_number"], finding["url_path"]
        ):
            return route["http_methods"]
    return []


def matches(entry, finding, methods):
    """True when a ground truth entry describes the route of this finding."""
    if entry["url_path"] != finding["url_path"]:
        return False
    if "http_methods" not in entry:
        return True
    return bool(set(entry["http_methods"]) & set(methods))


def describe(item, methods=None):
    """A short label such as "POST /notes/<id>/delete" for the results tables."""
    methods = methods if methods is not None else item.get("http_methods", [])
    return (",".join(methods) + " " if methods else "") + item["url_path"]


def score_app(result, truth):
    """Compare one engine result with one ground truth. Returns a dict of counts and details."""
    all_should_flag = truth.get("should_flag", [])
    should_flag = [e for e in all_should_flag if e.get("problem_type", "missing_login") in CHECKED_PROBLEM_TYPES]
    not_checked = [e for e in all_should_flag if e not in should_flag]
    public_paths = {entry["url_path"] for entry in truth.get("should_not_flag", [])}
    known_limitations = truth.get("known_limitations", [])

    found_entries = set()   # indexes into should_flag that some finding matched
    false_alarms = []       # (label, reason)
    known_flagged = []      # (label, note) for findings that match a known_limitations entry
    known_matched = set()   # indexes into known_limitations that some finding matched
    for finding in result["findings"]:
        methods = finding_methods(finding, result["routes"])
        hits = [i for i, entry in enumerate(should_flag) if matches(entry, finding, methods)]
        if hits:
            found_entries.update(hits)
            continue
        label = describe(finding, methods) + " (" + finding["file_path"] + ":" + str(finding["line_number"]) + ")"
        known = [i for i, entry in enumerate(known_limitations) if matches(entry, finding, methods)]
        if known:
            known_matched.update(known)
            known_flagged.append((label, known_limitations[known[0]].get("note", "")))
            continue
        if finding["url_path"] in public_paths:
            reason = "public by design"
        else:
            reason = "not listed in ground truth"
        false_alarms.append((label, reason))

    missed = [describe(entry) for i, entry in enumerate(should_flag) if i not in found_entries]
    return {
        "app": truth.get("app", ""),
        "should_flag": len(should_flag),
        "found": len(found_entries),
        "missed": missed,
        "false_alarms": false_alarms,
        "not_checked": [describe(entry) + ", " + entry["problem_type"] for entry in not_checked],
        "known_limitations": known_flagged,
        # Expected to be flagged but were not. Not an error in the score, but worth seeing.
        "known_not_flagged": [describe(e) for i, e in enumerate(known_limitations) if i not in known_matched],
        "files_skipped": [skipped["file_path"] for skipped in result["scan"]["files_skipped"]],
    }


def app_folders(corpus_folder):
    """Every sub-folder that has a ground_truth.json, sorted by name."""
    folders = []
    for name in sorted(os.listdir(corpus_folder)):
        folder = os.path.join(corpus_folder, name)
        if os.path.isfile(os.path.join(folder, "ground_truth.json")):
            folders.append(folder)
    return folders


def score_corpus(corpus_folder):
    scores = []
    for folder in app_folders(corpus_folder):
        truth = load_ground_truth(folder)
        truth.setdefault("app", os.path.basename(folder))
        scores.append(score_app(scan(folder), truth))
    return scores


def results_table(scores):
    """The scores as Markdown: one summary table, then the details of each miss and false alarm."""
    lines = [
        "| App | Real problems | Found | Missed | False alarms | Not checked yet |",
        "|---|---|---|---|---|---|",
    ]
    totals = [0, 0, 0, 0, 0]
    for score in scores:
        row = [score["should_flag"], score["found"], len(score["missed"]), len(score["false_alarms"]), len(score["not_checked"])]
        totals = [a + b for a, b in zip(totals, row)]
        lines.append("| " + score["app"] + " | " + " | ".join(str(n) for n in row) + " |")
    lines.append("| **Total** | " + " | ".join("**" + str(n) + "**" for n in totals) + " |")

    found, missed, false_alarms = totals[1], totals[2], totals[3]
    known = sum(len(score["known_limitations"]) for score in scores)
    lines.append("")
    lines.append("Known limitations (flagged as expected, not counted as false alarms): " + str(known))
    lines.append("Precision: " + ratio(found, found + false_alarms) + ", recall: " + ratio(found, found + missed))

    lines.append("")
    lines.append("## Details")
    for score in scores:
        lines.append("")
        lines.append("### " + score["app"])
        if not score["missed"] and not score["false_alarms"]:
            if score["should_flag"]:
                lines.append("All real problems found, no false alarms.")
            else:
                lines.append("No missing-login problems to find, and no false alarms.")
        for label in score["not_checked"]:
            lines.append("- Not checked yet: `" + label + "`")
        for label in score["missed"]:
            lines.append("- Missed: `" + label + "`")
        for label, reason in score["false_alarms"]:
            lines.append("- False alarm: `" + label + "`, " + reason)
        for label, note in score["known_limitations"]:
            lines.append("- Known limitation: `" + label + "`, " + note)
        for label in score["known_not_flagged"]:
            lines.append("- Known limitation no longer flagged: `" + label + "`")
        if score["files_skipped"]:
            lines.append("- Files skipped (could not be read): " + ", ".join("`" + f + "`" for f in score["files_skipped"]))
    return "\n".join(lines)


def ratio(part, whole):
    """part / whole with two decimals, e.g. "0.67 (4/6)". "n/a" when whole is 0."""
    if whole == 0:
        return "n/a"
    return "{:.2f} ({}/{})".format(part / whole, part, whole)


def main(argv):
    if len(argv) != 2:
        print("Usage: python engine/score.py <corpus_folder>", file=sys.stderr)
        return 2
    corpus_folder = os.path.abspath(argv[1])
    if not os.path.isdir(corpus_folder):
        print("Not a folder: " + corpus_folder, file=sys.stderr)
        return 2

    scores = score_corpus(corpus_folder)
    if not scores:
        print("No app with a ground_truth.json found in " + corpus_folder, file=sys.stderr)
        return 1
    print(results_table(scores))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
