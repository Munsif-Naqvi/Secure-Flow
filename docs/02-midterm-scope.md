# Midterm scope (about 8 days)

## Deliverable
The extension scans a Flask project and flags routes that look unprotected. All results are "Unconfirmed". Delivered with the SRS, ERD, Figma design and plan.

## Steps and acceptance checks
Do the steps in order. Each is small. Do not start the next until the current one passes.

1. **Hello world through the whole chain.**
   Extension command "SecureFlow: Scan Project" runs `python engine/main.py <open folder>`; the engine prints one fake finding as JSON; the extension underlines the right line.
   *Check:* press F5, run the command on any folder, see an underline.
2. **Route finder.** Use `ast` to find every Flask route: `@app.route`, `@bp.route` on Blueprints (with `url_prefix`), `app.add_url_rule`. Record url path, HTTP methods (default GET), file, line.
   *Check:* on `engine/tests/fixtures/tiny_app/`, all routes are listed correctly. pytest passes.
3. **Protection detector.** For each route find login or role protections: decorators, `before_request` hooks, and simple inline checks. Rules in `docs/03-detection-rules.md`.
   *Check:* the tiny app's protected routes show a protection, the unprotected ones show none.
4. **Missing-login rule.** Flag routes with no protection, except the public allowlist. Build findings in the format of `docs/04-findings.schema.json`.
   *Check:* output validates against the schema. The tiny app yields exactly the expected findings.
5. **Extension display.** Amber underline on the route line, results list (view in the side panel or a simple webview) with click-to-code, status bar summary such as "SecureFlow: 3 unprotected routes", "Unconfirmed" label, plain-language explanation. Layout follows the Figma screens (`docs/figma/`).
   *Check:* demo on the tiny app works end to end.
6. **Run on the corpus** (Maheen's 5 apps, `docs/07-test-corpus.md`). Compare findings with each `ground_truth.json`. Record how many real problems were found and how many false alarms.
   *Check:* a results table exists in `docs/results-midterm.md`.
7. **Package.** `npx vsce package` produces a `.vsix`. Install it in a normal VS Code window and run it once.

## Stretch (only if everything above is done)
String-built SQL queries (`cursor.execute(f"...{user_input}...")` or concatenation). Flag as `sql_injection`, Unconfirmed.

## Cut-line
If time runs short, stop after step 5 and step 6 with whatever apps are ready. Drop steps 7 and the stretch first.

## Midterm demo script
1. Open a sample app in VS Code. 2. Run SecureFlow: Scan Project. 3. Show underlines and the results list. 4. Click a finding, open the explanation. 5. Show the results table: SecureFlow versus the ground truth (and Bandit if available).

## Definition of done (midterm)
- [ ] Engine runs from the command line and its output validates against the schema
- [ ] Routes are found for decorators, blueprints and add_url_rule
- [ ] Protections detected as in `docs/03-detection-rules.md`
- [ ] Missing-login findings produced; public routes are not flagged
- [ ] Extension shows underlines, results list, status bar, explanation
- [ ] All results say Unconfirmed
- [ ] pytest tests exist for route finding, protection detection and the rule
- [ ] Results on the corpus recorded
- [ ] `.vsix` builds and installs
