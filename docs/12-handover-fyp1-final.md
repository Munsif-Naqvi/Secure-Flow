# Starter pack: unsafe input rules and exposed secrets (FYP-1 final)

**For:** Maheen. **From:** Munsif, written with Claude Code. **Date:** 25 November 2026.

Up to the midterm, Munsif built the engine and the extension. For the FYP-1 final, the work is split:

| Who | Builds |
| --- | --- |
| **Maheen** | The **unsafe input rules** using taint tracking (SQL injection, command injection, path traversal, template injection; SRS CODE-6), and the new **exposed secrets** rules (secrets written in the code, a `.env` file that git does not ignore). |
| **Munsif** | The **database side** (details to be agreed between us). |

This guide tells you what already exists, what we agreed on, and how to build your part the same way the first part was built. Read sections 1 to 4 before writing any code. The ready-to-paste Claude Code prompts are in `docs/13-claude-code-prompts.md`.

---

## 1. The ten rules we always follow

These come from `CLAUDE.md` and from what went wrong or right during the midterm work. Claude Code reads `CLAUDE.md` on its own, but you should know them too, because the panel will ask *you*.

1. **Never run the scanned project's code.** The engine only reads files. It parses Python with the standard `ast` module and looks at the tree.
2. **Standard library only.** No new Python packages without asking each other first. Tests use `pytest`.
3. **Never send code or results online.** Everything stays on the developer's computer.
4. **Correct over clever.** A rule that finds fewer problems with few false alarms beats one that finds many with many false alarms. If a data flow is not clear from the code, do not flag it, and write it down as a known limit instead.
5. **Every result is Unconfirmed.** Only a live test (FYP-2) can confirm. Use the words in `CLAUDE.md` ("suspect", "Unconfirmed", "finding") exactly.
6. **Small steps.** One rule, or one part of a rule, at a time: write it, run it, show the result, then continue. Never let Claude Code generate a whole feature in one go.
7. **A test for every rule,** using a tiny sample app in `engine/tests/fixtures/`. Write a comment above each example route saying what the engine should report, so a person can check by eye.
8. **The schema is the contract.** `docs/04-findings.schema.json` is what the extension expects. Changing it means telling each other first (the secrets rules need one change; see section 6).
9. **Write the rule down.** Each rule gets its section in `docs/03-detection-rules.md`, an entry under "Decisions made along the way" in `CLAUDE.md`, and a plain walkthrough doc like `docs/11-missing-ownership-check.md`.
10. **Every rule must be explainable to the panel** in two or three plain sentences. If you cannot explain it, it is too clever.

---

## 2. How the engine works today (the map)

`python engine/main.py <folder>` runs `scan()` in `engine/main.py`. In order:

```
find_python_files      list .py files (skips venv, node_modules, .git, ...)
parse_files            ast.parse each file; syntax errors -> files_skipped
collect_files          pass 1: per file, which names are Flask apps / Blueprints, imports, functions, classes
find_routes            pass 2: every route (decorators, Blueprints, add_url_rule, MethodView classes)
add_protections        login decorators, before_request hooks, inline checks -> protections_found
add_public_content     fixed harmless pages are labelled so they are not flagged
add_developer_marks    "# secureflow: public" comments and .secureflow/route_decisions.json
missing_login_findings      rules part 3
missing_role_findings       rules part 9
missing_ownership_findings  rules part 10
sort, then print JSON (routes, findings, summary)
```

Your new rules plug in **after** the existing three, as new `findings += ...` lines. Each rule lives in its own file in `engine/secureflow/`, like `role_check.py` and `ownership_check.py`. Read `ownership_check.py` first: it is the closest to what you will build, because it already looks inside handler bodies for `.execute(...)` calls and for values that come from the visitor (`request.args`, URL variables).

What a `Route` gives you (from `engine/secureflow/routes.py`):

| Field | Meaning |
| --- | --- |
| `url_path`, `http_methods`, `file_path`, `line_number` | Where the route is |
| `handler` | The `ast` node of the function Flask calls (for a MethodView class: the `get`/`post`/... method) |
| `view_class` | The MethodView class, or `None` |
| `owner` | The Flask app or Blueprint |
| `protections_found` | Login protections found (empty = no login check) |

Helpers you will reuse: `last_name()` and `static_text()` in `routes.py`, `walk_list()` in `protections.py`, `match_key()` in `rules.py`. Do not copy them; import them.

---

## 3. Decisions already made that affect your part

| Decision | What it means for you |
| --- | --- |
| The schema already has the four types | `problem_class: "unsafe_input"`, `problem_type`: `sql_injection`, `command_injection`, `path_traversal`, `template_injection`. No schema change is needed for taint tracking. |
| `finding_match_key` is not unique | Two findings on the same path in the same file share a key. Do not use it as an ID. |
| Scoring matches path, method, then type | `engine/score.py` only scores types in `CHECKED_PROBLEM_TYPES`. Add each new type there when its rule is done, or it will show as "not checked". |
| Database-backed pages stay flagged | Do not loosen a rule to make the score look better. Put honest misses in `known_limitations` in `ground_truth.json`. |
| Class-based routes | `@blp.route` on a `MethodView` class gives one route per method, so a taint rule reads `route.handler` (the method) and works without special code. |
| The engine is copied into the `.vsix` | Any new engine file in `engine/secureflow/` is picked up automatically by `extension/copy-engine.js`. Check this once when you package. |

**Trap in the extension.** The results list only shows problem types listed in `PROBLEM_TYPES` in `extension/src/resultsView.ts`. A new type that is not there is silently left out of the list (the underlines still show). Add one line per new type, with a plain group name and title.

---

## 4. Lessons from the first part (what we learned the hard way)

1. **Test on real code you did not write.** We scanned a public Flask course repository. SecureFlow flagged all 100 routes it found. The real reason was not false alarms: the engine had *missed* about 1,000 routes written as `@blp.route` on a class, and only saw the beginner apps that really had no login. Always ask two separate questions: *what did it miss?* and *what did it wrongly flag?* Check a sample of results by hand.
2. **Scan one project folder, not a whole repository.** A course repository holds many copies of the same code, which repeats findings.
3. **Severity must be explainable.** A panel will ask "why is this one High and that one Medium?" Write the reason into the explanation text. For example, today a POST route is High because it can change data, but its explanation does not say so; that is worth fixing.
4. **"Reading a value" is not "checking it".** Early on, `session.get("user_id", 1)` was counted as a login check, and it stops nobody. The same trap exists for you: `name = request.args.get("name").strip()` does **not** clean the value. Only list real cleaning steps as sanitizers (section 5.4).
5. **Line numbers in fixtures go stale.** Adding one comment line shifts every route below it. Write the fixture first, then print the engine's line numbers, then write the expected values in the test.
6. **Keep the corpus honest.** Mark anything Claude adds to the corpus with a comment in the app and a note in `corpus/README.md`, as we did before.

---

## 5. Taint tracking: the proposed design

"Taint tracking" means following a value from the place a visitor controls (a **source**) to a place where it can do harm (a **sink**). If nothing on the way cleans it (a **sanitizer**), the sink is a suspect. This is SRS CODE-6 and section 4.5.2, step 4.

This design is a starting point we agreed on, not a finished spec. Confirm each piece in a small step, and move the final version into `docs/03-detection-rules.md` as each rule lands.

### 5.1 Scope: start small

- **Inside one handler only** (the function Flask calls for a route). Values passed into a helper function in another place are not followed at first. That is a known limit; following calls into helpers can come later as a stretch.
- **Every route counts,** with or without a login check. Logging in does not make SQL injection safe.
- One finding **per sink line**, at the sink's line, with the route's `url_path`.

### 5.2 Sources (where visitor data comes in)

| Source | Example |
| --- | --- |
| Query string | `request.args["q"]`, `request.args.get("q")` |
| Form | `request.form[...]`, `request.form.get(...)`, `request.values...` |
| JSON body | `request.json[...]`, `request.get_json()` and anything read from it |
| Files | `request.files["f"].filename` |
| Headers and cookies | `request.headers.get(...)`, `request.cookies.get(...)` |
| URL variables | handler parameters named in the path, e.g. `name` in `/store/<name>` |

### 5.3 How taint spreads

A name becomes tainted when it is assigned a value that contains a tainted part:

- plain assignment: `q = request.args.get("q")`
- joining text: `"... " + q`, f-strings `f"... {q}"`, `"%s" % q`, `"{}".format(q)`
- simple wrappers that keep the text: `str(q)`, `q.strip()`, `q.lower()`
- reading from a tainted dict or list: `data["name"]` when `data = request.get_json()`

Go through the handler's statements top to bottom. Keep it simple: no loops over branches, no guessing about what a function returns, except the wrappers listed above.

### 5.4 Sanitizers (what cleans a value)

| For | Counts as cleaning |
| --- | --- |
| Any sink | `int(...)`, `float(...)` (the value can only be a number) |
| SQL | Passing the value as a **parameter**: `cursor.execute("... WHERE id = ?", (q,))`. Only the first argument (the SQL text) is checked. |
| Shell | `shlex.quote(...)`; a list of arguments **without** `shell=True` |
| File paths | `werkzeug.utils.secure_filename(...)`, `os.path.basename(...)`, `flask.safe_join` / `werkzeug.security.safe_join` |
| Templates | Passing the value as a variable to `render_template(...)` / `render_template_string(fixed_text, name=q)` |

Anything not in this table does not clean the value. When you add one, write down why it is safe.

### 5.5 Sinks (the four rules)

| Rule | `problem_type` | Flag when a tainted value reaches | Suggested severity |
| --- | --- | --- | --- |
| SQL built by joining text | `sql_injection` | the **first** argument of `.execute(...)`, `.executemany(...)`, `.executescript(...)`, or `text(...)` (SQLAlchemy) | High |
| Shell commands | `command_injection` | `os.system(...)`, `os.popen(...)`, `subprocess.run/call/check_output/Popen(...)` with `shell=True` or a single string | High |
| File paths | `path_traversal` | `open(...)`, `send_file(...)`, `os.remove(...)`, `os.path.join(...)` whose result is opened | High |
| Templates from text | `template_injection` | `render_template_string(...)` first argument, `jinja2.Template(...)` | High |

Every finding uses `problem_class: "unsafe_input"`, `finding_status: "unconfirmed"`, and an explanation in this shape:

> This route (`<METHODS> <url_path>`) builds an SQL query from `<value>`, which the visitor controls (`<source>`), and SecureFlow found nothing that cleans it on the way. An attacker may be able to change the query. This was found by reading the code and has not been tested live.

### 5.6 Order to build in

1. `sql_injection`. The mini corpus (`engine/tests/fixtures/mini_corpus/app_02_shop`) already has one ground-truth entry for it, and `ownership_check.py` already finds `.execute(...)` calls.
2. The shared taint helper (sources plus spreading), pulled out of step 1 once it works, so the other three rules reuse it.
3. `command_injection`, `path_traversal`, `template_injection`, one at a time.
4. Add each type to `CHECKED_PROBLEM_TYPES` in `engine/score.py` and to `PROBLEM_TYPES` in the extension.
5. Add corpus cases (Maheen's corpus) with `should_flag` and `should_not_flag` for each type, including safe versions (a parameterized query, a list-form `subprocess.run`).

### 5.7 Honest limits to state

- Values that pass through helper functions, class attributes or other files are not followed.
- ORM queries (`Model.query.filter(...)`) are not looked at; only raw SQL text.
- A sanitizer we do not know about will cause a false alarm; one we wrongly trust will cause a miss.

---

## 6. Exposed secrets: the agreed new rules

This was **not in the SRS (version 1.0)**. We agreed to add it. Add a line to the SRS change log when the rules are done.

It does not fit "Broken Access Control" or "Unsafe Input Handling", so it needs a **schema change**, which is the first step of this work:

- Add `exposed_secret` to the `problem_class` enum.
- Add `hardcoded_secret` and `env_file_not_ignored` to the `problem_type` enum.
- These findings are about a file, not a route, so they use `url_path: ""` (the schema already allows an empty string). Check that the extension shows such a card sensibly (no empty "route" text).
- Bump nothing else. Tell Munsif before merging, because the contract changes.

### 6.1 `hardcoded_secret`

Flag a secret written directly into the Python code:

- `app.secret_key = "..."`, `app.config["SECRET_KEY"] = "..."`, `app.config.update(SECRET_KEY="...")`
- a variable or config key whose name contains `SECRET`, `PASSWORD`, `TOKEN`, `API_KEY` or `PRIVATE_KEY`, assigned a plain string
- strings that look like well-known key formats (for example AWS keys starting with `AKIA`, Stripe live keys starting with `sk_live_`, GitHub tokens starting with `ghp_`)

Do **not** flag: empty strings, values read from the environment (`os.environ[...]`, `os.getenv(...)`), and obvious placeholders (`"changeme"`, `"your-key-here"`, `"xxx"`). Keep the placeholder list in `engine/secureflow/constants.py`. Decide together whether `os.getenv("SECRET_KEY", "dev")` (a fixed fallback) is flagged; we suggest yes, at Medium, because the fallback is used when the variable is missing.

**Never put the secret itself in the output.** The explanation names the variable and line only, for example "`SECRET_KEY` is set to a fixed string in the code". The JSON may be shared or saved later.

### 6.2 `env_file_not_ignored`

Flag a `.env` file (also `.env.local`, `.env.production`, ...) in the project when the project's `.gitignore` has no line that matches it. Read the `.gitignore` as text and match with `fnmatch`. Lines starting with `!` (undo an ignore) make the answer unclear: then flag, and say so in the explanation. Never read or print the values inside the `.env` file.

Severity: High if the `.env` file contains a line that looks like `NAME=value` with a secret-style name, otherwise Medium.

---

## 7. How to work, day to day

1. **Branch per step** from the latest `main`, for example `maheen/sql-injection`. Open a pull request into `main` when a step is done, and ask Munsif to look at it.
2. **Before each push**, run:
   - `cd engine && python -m pytest` (all tests pass)
   - `python engine/score.py corpus/` (compare with the last result; explain any change)
3. **After each rule**, update `docs/03-detection-rules.md`, add a decision entry in `CLAUDE.md`, and write the walkthrough doc (copy the section layout of `docs/11-missing-ownership-check.md`: why, the rule in one sentence, its parts, the finding, honest limits, results, files, tests, panel questions).
4. **Test outside the corpus** on at least one public Flask project, one folder at a time, and check a sample of results by hand.
5. **Ask before** adding a dependency, editing many files at once, or changing the schema.

### Done for the FYP-1 final (your part)

- [ ] `sql_injection`, `command_injection`, `path_traversal`, `template_injection` rules, each with a fixture app and tests (flagged and safe cases)
- [ ] Shared taint helper with its own tests (sources, spreading, sanitizers)
- [ ] Schema change for `exposed_secret`, agreed with Munsif
- [ ] `hardcoded_secret` and `env_file_not_ignored` rules with tests, never printing secret values
- [ ] New types added to `score.py` and to the extension's results view
- [ ] Corpus cases with ground truth for every new type, and the score table updated in the results doc
- [ ] Rules documented in `docs/03-detection-rules.md`, walkthrough docs written, `CLAUDE.md` decisions updated
- [ ] SRS change log line for the exposed secrets rules
