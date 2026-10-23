# SecureFlow: guide for Claude Code

## What this project is
SecureFlow is a final year project (SZABIST Karachi, two students: Syed Munsif and Maheen Arshad, advisor Muhammad Ahsan). It is a VS Code extension plus a Python engine that finds security problems in **Python Flask** apps. It targets two problem classes: **Broken Access Control** and **Unsafe Input Handling**. Full background: `docs/01-project-brief.md`. Full requirements: `docs/reference/SecureFlow_SRS.pdf`.

The long-term idea: the engine reads the code (static analysis), then a Docker sandbox attacks a disposable copy of the app to prove each suspect. A problem is called *confirmed* only when a live test proved it.

## Where we are now: FYP-1, midterm slice
**Build only this, nothing more** (details and acceptance checks in `docs/02-midterm-scope.md`):
1. A Python engine run from the command line: `python engine/main.py <project_folder>` prints findings as JSON.
2. The engine finds Flask routes, detects their login protections, and flags routes with **no login check** (rules in `docs/03-detection-rules.md`).
3. The VS Code extension runs the engine on the open folder and shows the flagged routes (underlines, results list, status bar).
4. Every result is labelled **Unconfirmed**. There is no Docker in this phase.

**Do not build yet** unless the user says the phase has changed: Docker or any sandbox, live tests, fix suggestions, report export, scan history UI, SQLite storage, first-run setup, test setup screen, AI features, other frameworks, other databases. If a request needs one of these, say so and ask first.

## Repository layout
```
secureflow/
  CLAUDE.md
  docs/               project documents (read these first)
  engine/             Python engine (static analysis)
    main.py           command-line entry point
    secureflow/       package: routes.py, protections.py, rules.py, output.py
    tests/            pytest tests
  extension/          VS Code extension (TypeScript, esbuild)
  corpus/             test Flask apps with ground truth (made by Maheen)
```
If the real layout differs (for example the extension was generated at the repo root), adapt and tell the user once. Do not reorganise without asking.

## Technical decisions (already made)
- Extension: TypeScript, bundled with esbuild. It runs the engine as a child process and reads its JSON from standard output.
- Engine: Python 3.10+, standard library only for the midterm (use `ast`). Add a dependency only if truly needed, and ask first. Tests with `pytest`.
- The contract between engine and extension is `docs/04-findings.schema.json`. Validate engine output against it in tests. Do not change the contract without telling the user.
- Static analysis never executes the scanned project's code.
- Never send code or results to any online service.

## Rules for how to work with this user
- The user is a student who is learning. After each change, explain in two or three plain sentences what the code does and why. Avoid jargon, or explain it.
- Work in **small steps**. One step at a time, run it, show the result, then continue. Do not generate the whole project in one go.
- Write a small test for every detection rule using the files in `corpus/` or a tiny sample app in `engine/tests/fixtures/`.
- Prefer **correct over clever**. A rule that finds fewer problems with few false alarms is better than one that finds many with many false alarms.
- Keep the code simple and commented where the logic is not obvious. The user must be able to explain every rule to a panel.
- Before editing many files, or before adding a dependency, ask.
- Do not invent features or requirement text. If something is unclear, check `docs/` first, then ask.

## Words that must be used consistently
- **Suspect**: a place in the code that looks like a problem and has not been tested.
- **Unconfirmed**: a suspect from a code-only scan. This is the only status the midterm engine produces.
- **Confirmed**: proven by a live test (FYP-2 only).
- **Finding**: a suspect with its status and explanation.

## Commands
- Run the engine: `python engine/main.py corpus/app_01_*/` (or any Flask folder)
- Engine tests: `cd engine && python -m pytest`
- Extension: open `extension/` in VS Code and press F5 to launch the Extension Development Host. Build with `npm run compile` (check `package.json` for the exact scripts).
- Package: `npx vsce package`

## Definition of done for the midterm
See the checklist at the end of `docs/02-midterm-scope.md`.
