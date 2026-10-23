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

## Status bar
`SecureFlow: <N> unprotected routes` (or `SecureFlow: no problems found`). Clicking it opens the results.

## Out of scope for the midterm
Cancel button, Docker messages, test setup screen, fix preview, report export, history, hover card.
