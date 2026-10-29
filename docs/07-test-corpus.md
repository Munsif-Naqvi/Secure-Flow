# Test corpus (Maheen)

Five small Flask apps that contain known problems, used to test and measure SecureFlow.

## Folder layout
```
corpus/
  app_01_<short_name>/
    app.py (and other files)
    ground_truth.json
  app_02_.../
```

## ground_truth.json
Lists every route that **is** unprotected and should be flagged, and the routes that are public by design and should not be.
```json
{
  "app": "app_01_notes",
  "should_flag": [
    { "url_path": "/notes/<id>/delete", "http_methods": ["POST"], "problem_type": "missing_login" }
  ],
  "should_not_flag": [
    { "url_path": "/", "reason": "public home page" },
    { "url_path": "/login", "reason": "login page" }
  ],
  "known_limitations": [
    { "url_path": "/catalog", "http_methods": ["GET"], "problem_type": "missing_login", "note": "public by design, reads the database; still flagged until live verification (FYP-2)" }
  ]
}
```
`known_limitations` (optional) lists routes that are not real problems but that the code-only scan is *expected* to flag, because of a documented limit of the rules. Tests require them to be flagged, and the scorer reports them on their own line instead of counting them as false alarms.

## What each app should contain (cover all of these across the five apps)
- Public pages (home, login, register) that must not be flagged.
- Routes protected with `@login_required` (Flask-Login) and with a custom decorator.
- Routes unprotected and state-changing (delete, update).
- Routes unprotected and read-only (list users, view data).
- A Blueprint with a `url_prefix`, one with a `before_request` login check, one without.
- A route using `add_url_rule`.
- An inline check (`if "user_id" not in session: return redirect(...)`).
- A token-protected API route (JWT or an `Authorization` header check).
- One app with a SQL query built with an f-string (for the stretch rule).
- One app with a deliberate syntax error in an unused file (the engine should skip it, not crash).
Apps may be small (50–150 lines). They may be adapted from public "deliberately vulnerable Flask" examples; note the source in a README.

## Scoring
For each app, compare the engine's `findings` with `should_flag`/`should_not_flag` by `url_path`:
- true positive: flagged and in `should_flag`
- false positive: flagged but in `should_not_flag` or not listed
- known limitation: flagged and in `known_limitations` (reported apart, not a false positive)
- missed: in `should_flag` but not flagged
Report per app and in total, in `docs/results-midterm.md`. A small script `engine/score.py` should do this.

## Delivery
Two apps by day 3, the other three by day 6, so the engine can be tested early.
