"""Step 1 check: the engine runs from the command line and prints valid JSON."""

import json
import subprocess
import sys
from pathlib import Path

ENGINE_MAIN = Path(__file__).parent.parent / "main.py"
FIXTURES = Path(__file__).parent / "fixtures"


def run_engine(folder):
    """Run `python engine/main.py <folder>` and return the parsed JSON output."""
    completed = subprocess.run(
        [sys.executable, str(ENGINE_MAIN), str(folder)],
        capture_output=True, text=True, check=True,
    )
    return json.loads(completed.stdout)


def test_output_has_the_top_level_parts_of_the_schema():
    result = run_engine(FIXTURES / "hello_app")
    assert result["schema_version"] == "1.0"
    assert set(result) == {"schema_version", "scan", "routes", "findings", "summary"}


def test_fake_finding_points_at_the_python_file_and_is_unconfirmed():
    result = run_engine(FIXTURES / "hello_app")
    assert len(result["findings"]) == 1
    finding = result["findings"][0]
    assert finding["file_path"] == "app.py"
    assert finding["line_number"] == 1
    assert finding["finding_status"] == "unconfirmed"
    assert result["summary"] == {"suspects_found": 1, "problems_confirmed": 0}


def test_folder_without_python_files_gives_no_findings(tmp_path):
    result = run_engine(tmp_path)
    assert result["findings"] == []
