# SecureFlow: project brief

## The problem
Students and small teams build Flask web apps without security training. Code-only scanners such as Bandit report long lists of possible problems and many are false alarms. Developers ignore the list or waste time checking each item.

## The idea
SecureFlow gives a short, trustworthy list. It runs inside VS Code. It reads the Flask code to find *suspects*. Later (FYP-2), a Docker sandbox attacks a safe copy of the app to *prove* each suspect. A problem is reported as **confirmed** only when the attack worked. The developer sees the proof and can apply a ready-made fix and re-run the test.

## The two problem classes
1. **Broken Access Control**: missing login check, missing role (admin) check, one user reaching another user's data.
2. **Unsafe Input Handling**: SQL injection, command injection, path traversal, template injection.

## Users
One user type: the developer. SecureFlow has no accounts or login of its own. It runs locally. The "test accounts" in the docs belong to the app being tested.

## Architecture
- **VS Code extension (TypeScript)**: commands, panels, underlines. Runs the engine as a command-line program and reads JSON.
- **Engine (Python)**: finds routes and protections, applies rules, produces findings. Later: controls the Docker test box and runs live tests.
- **Test box (Docker, FYP-2)**: disposable container with a copy of the app and its database. No internet while running. Removed after the scan.
- **SecureFlow database (SQLite, local file in `.secureflow/`)**: scans, routes, findings, evidence, fixes. Schema in `docs/05-database.sql` (not used in the midterm slice).

## Phases
- **FYP-1 (semester 1)**: code scan, routes and protections, rules, VS Code UI, explanations, rule-based fix suggestions, report export, scan history, benchmark with Bandit baseline.
- **FYP-2 (semester 2)**: complete Docker setup, database copy, test setup, live verification, proof view, fix re-test, full error screens, full benchmark, user testing.
- **Midterm slice (now)**: see `docs/02-midterm-scope.md`.

## Future goals (not in FYP-1 or FYP-2 scope yet)
- **Publish the extension** on the VS Code Marketplace, and on Open VSX for Cursor and VSCodium. Until then it is shared as a `.vsix` file. Before publishing: create a publisher account (its ID must match `"publisher"` in `extension/package.json`), add a LICENSE file and a 128×128 PNG icon, then run `npx vsce publish` (`npx ovsx publish` for Open VSX).

## Principles
- Never report a problem as confirmed without a live test. **Confirmed** (FYP-2 only) means an attack demonstrably had impact: private data came back, or existing data changed. A route that is merely reachable without login is not a confirmed problem. In FYP-1 every result is Unconfirmed.
- **Reachable is not the same as vulnerable.** A route that anyone can open may be public on purpose. It is a suspect to ask the developer about, not a proven problem. See `docs/08-verification-design.md`.
- **When unsure, flag.** A response that is the same for every user does not prove a route is public: an unprotected admin page also shows the same data to everyone. So the static rules stay conservative.
- Never change the developer's real files or database unasked.
- Plain language in every message the developer sees.
- Fewer, more accurate findings beat more, noisier ones.

## Reference files
`docs/reference/SecureFlow_SRS.pdf` (requirements), `docs/reference/SecureFlow_ERD.png` (database), the Figma screens (export key screens into `docs/figma/`).
