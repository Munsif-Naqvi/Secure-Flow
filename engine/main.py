"""SecureFlow engine: command-line entry point.

Usage:
    python engine/main.py <project_folder>

Prints the scan result as JSON on standard output, in the format of
docs/04-findings.schema.json.

Midterm step 4: the engine finds the Flask routes (secureflow/routes.py),
detects each route's login protections (secureflow/protections.py) and lists
them under "routes". Then the missing-login rule (secureflow/rules.py) turns
every unprotected, non-public route into an Unconfirmed finding.
"""

import json
import os
import sys
from datetime import datetime, timezone

from secureflow.protections import add_protections
from secureflow.routes import collect_files, find_routes, parse_files
from secureflow.rules import missing_login_findings

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


def scan(project_path):
    """Build the scan result as a Python dict (turned into JSON by main)."""
    started_at = now_iso()
    python_files = find_python_files(project_path)
    trees, files_skipped = parse_files(project_path, python_files)
    files = collect_files(trees)
    routes = find_routes(files)
    add_protections(routes, files)

    findings = missing_login_findings(routes)

    return {
        "schema_version": "1.0",
        "scan": {
            "project_path": project_path,
            "scan_mode": "code_only",
            "scan_status": "completed",
            "started_at": started_at,
            "finished_at": now_iso(),
            "files_scanned": len(trees),
            "files_skipped": files_skipped,
        },
        "routes": [route.to_dict() for route in routes],
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
