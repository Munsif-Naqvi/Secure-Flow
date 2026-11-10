# Extension behaviour for the midterm

Source of truth for layout: the Figma screens (export Main, 02-Scanning, 03-Results, 04-Finding-Detail into `docs/figma/`). Build only the parts below. Use VS Code's own look (theme colours, fonts).

## Commands (in `package.json`, `contributes.commands`)
- `SecureFlow: Scan Project`: runs a scan on the first workspace folder.
- `SecureFlow: Show Results`: reopens the last results.

## Scan flow
1. If no folder is open: show "Open a Flask project folder first."
2. Show a progress notification "Scanning <folder name>".
3. Run `python engine/main.py <folder>` as a child process. Try `python3` if `python` is not found. Read standard output as JSON and validate the basic shape (`schema_version`, `findings`, `summary`).
4. On engine error or invalid JSON: show a short message ("SecureFlow could not read the scan result. Your files were not changed.") and a button "Open log". Never crash the extension.
5. On success: create diagnostics, update the status bar and open the results view.

## Editor
- One diagnostic per finding at `file_path:line_number`. Severity: High = Error (red), Medium = Warning (amber). Source: `SecureFlow`. Message: the finding's `explanation`.
- Clear old diagnostics at the start of each scan.

## Results view (a simple webview or tree view in the side panel)
- Summary card: "<N> unprotected routes found", then a line "Unconfirmed: found by reading the code, not tested live".
- List of findings: severity, `url_path`, `file_path:line_number`, one-line title ("No login check found").
- Clicking a finding opens the file at that line.
- Selecting a finding shows its `explanation` and the note about unconfirmed results.
- If there are no findings: "No unprotected routes found. This does not prove the app is safe."

## Mark a route as public (added after the midterm extension)
Answers the missing-login question for a route that is public on purpose (rule: `docs/03-detection-rules.md`, part 8).
- The lightbulb on a SecureFlow underline offers "SecureFlow: Mark this route as public". The selected finding in the results view has a "Mark as public" button with the note "Only if this route is meant for everyone. A wrong mark hides a real problem."
- The action writes `# secureflow: public` directly above the route's topmost decorator (or above the `add_url_rule` call), with the same indentation, saves the file and scans again. The edit is one undo step.
- If the file has unsaved changes or changed since the scan, nothing is written: "<file> changed since the scan. Save it and scan again before marking a route."
- Not offered when a login decorator sits above the route decorator: the engine keeps such a route flagged, so the mark would do nothing.
- Only one route at a time, on purpose: there is no bulk "mark all" action, so each route is looked at before it is marked.

## Problem types
Findings are grouped by `problem_type` in the results view: "Missing login checks" (card title "No login check found") "Missing role checks" ("Logged in, but no admin or role check found") and "Missing ownership checks" ("Logged in, but no check that the record belongs to the visitor"). The summary card and status bar count all of them as suspects: "<N> suspects found", `SecureFlow: <N> suspects`.

## Status bar
`SecureFlow: <N> unprotected routes` (or `SecureFlow: no problems found`). Clicking it opens the results.

## Out of scope for the midterm
Cancel button, Docker messages, test setup screen, fix preview, report export, history, hover card. (The "Mark as public" action above is the only place the extension writes to the developer's files, and only when clicked.)
