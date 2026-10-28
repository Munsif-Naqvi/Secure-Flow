"""Step 6 check: score.py compares the findings with each app's ground_truth.json.

fixtures/mini_corpus is a practice corpus. The comment above each route says
how it should be counted, so the expected table below can be checked by eye.
"""

import subprocess
import sys
from pathlib import Path

from test_main import FIXTURES

SCORE = Path(__file__).parent.parent / "score.py"


def run_score(folder):
    """Run `python engine/score.py <folder>` and return (exit code, stdout, stderr)."""
    completed = subprocess.run([sys.executable, str(SCORE), str(folder)], capture_output=True, text=True)
    return completed.returncode, completed.stdout, completed.stderr


CODE, TABLE, _ = run_score(FIXTURES / "mini_corpus")


def test_summary_table_counts_each_app_and_the_total():
    assert CODE == 0
    assert TABLE.splitlines()[:5] == [
        "| App | Real problems | Found | Missed | False alarms | Not checked yet |",
        "|---|---|---|---|---|---|",
        "| app_01_notes | 1 | 1 | 0 | 0 | 0 |",
        "| app_02_shop | 2 | 1 | 1 | 3 | 1 |",
        "| **Total** | **3** | **2** | **1** | **3** | **1** |",
    ]


def test_details_name_every_miss_and_false_alarm():
    assert "All real problems found, no false alarms." in TABLE  # app_01_notes
    assert "- Missed: `GET /admin/users`" in TABLE              # trusted @admin_check
    assert "- False alarm: `GET /pricing (app.py:19)`, public by design" in TABLE
    assert "- False alarm: `GET /status (app.py:25)`, not listed in ground truth" in TABLE


def test_same_path_is_told_apart_by_http_method():
    # The ground truth lists only DELETE /item/<id>, so the PUT finding is a false alarm.
    assert "- False alarm: `PUT /item/<int:item_id> (app.py:37)`, not listed in ground truth" in TABLE
    assert "DELETE /item" not in TABLE


def test_problem_types_the_engine_does_not_check_are_listed_apart():
    # app_02_shop lists a missing role check; the midterm engine only checks login.
    assert "- Not checked yet: `GET /admin/users, missing_role_check`" in TABLE
    assert "Missed: `GET /admin/users`" in TABLE  # the missing_login entry is still missed


def test_folder_without_ground_truth_is_an_error(tmp_path):
    code, out, err = run_score(tmp_path)
    assert code == 1
    assert out == ""
    assert "No app with a ground_truth.json" in err
