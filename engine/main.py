"""SecureFlow engine: command-line entry point.

Usage:
    python engine/main.py <project_folder>

Prints the scan result as JSON on standard output, in the format of
docs/04-findings.schema.json.

Midterm step 1 ("hello world through the whole chain"): the engine does not
analyse anything yet. It picks the first Python file in the folder and reports
one fake finding on line 1, so we can check that the VS Code extension can run
the engine, read its JSON and underline the right line.
"""

import json
import os
import sys
from datetime import datetime, timezone

# Folders that never contain the developer's own app code.
SKIPPED_FOLDERS = {".git", ".venv", "venv", "env", "__pycache__", "node_modules", ".secureflow"}


def now_iso():
    """Current time as an ISO 8601 string, for started_at / finished_at."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def find_python_files(project_path):
    """Return the relative paths (forward slashes) of all .py files, sorted."""
    found = []
    for folder, subfolders, files in os.walk(project_path):
        # Editing the list in place tells os.walk not to go into these folders.
        subfolders[:] = [name for name in subfolders if name not in SKIPPED_FOLDERS]
        for name in files:
            if name.endswith(".py"):
                full_path = os.path.join(folder, name)
                relative = os.path.relpath(full_path, project_path)
                found.append(relative.replace(os.sep, "/"))
    return sorted(found)


def fake_finding(file_path):
    """One made-up finding, only used to test the engine-to-extension chain."""
    return {
        "finding_match_key": "fake:" + file_path + ":1",
        "problem_class": "access_control",
        "problem_type": "missing_login",
        "severity": "Medium",
        "finding_status": "unconfirmed",
        "url_path": "/fake",
        "file_path": file_path,
        "line_number": 1,
        "explanation": "Test finding: SecureFlow is connected. This is not a real problem.",
    }


def scan(project_path):
    """Build the scan result as a Python dict (turned into JSON by main)."""
    started_at = now_iso()
    python_files = find_python_files(project_path)

    findings = []
    if python_files:
        findings.append(fake_finding(python_files[0]))

    return {
        "schema_version": "1.0",
        "scan": {
            "project_path": project_path,
            "scan_mode": "code_only",
            "scan_status": "completed",
            "started_at": started_at,
            "finished_at": now_iso(),
            "files_scanned": len(python_files),
            "files_skipped": [],
        },
        "routes": [],
        "findings": findings,
        "summary": {
            "suspects_found": len(findings),
            "problems_confirmed": 0,  # Only a live test can confirm (FYP-2).
        },
    }


def main(argv):
    if len(argv) != 2:
        print("Usage: python engine/main.py <project_folder>", file=sys.stderr)
        return 2

    project_path = os.path.abspath(argv[1])
    if not os.path.isdir(project_path):
        print("Not a folder: " + project_path, file=sys.stderr)
        return 2

    result = scan(project_path)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
