# Claude Code prompts for the FYP-1 final (unsafe input and exposed secrets)

Paste these into Claude Code **one at a time**, in order. Wait for each step to finish, read what it changed, run the tests yourself, and only then paste the next one. If a result looks wrong, say so in your own words before moving on. Each prompt assumes Claude Code is open in the repository, where it reads `CLAUDE.md` by itself.

The design behind these prompts is in `docs/12-handover-fyp1-final.md`. If Claude Code suggests something that disagrees with that file, ask it why before accepting.

---

## Step 0: get oriented (no code changes)

```
Read CLAUDE.md, docs/12-handover-fyp1-final.md, docs/03-detection-rules.md and
engine/secureflow/ownership_check.py. Do not change any files. Then explain to me
in plain words: (1) how one scan runs from main.py to the JSON output, (2) how
ownership_check.py finds .execute(...) calls and visitor-chosen values, and
(3) which parts of that I can reuse for the sql_injection rule. Ask me anything
that is unclear in the handover doc.
```

## Step 1: the first taint rule, SQL injection, inside one handler

```
Start on a new branch from the latest main called maheen/sql-injection.
Build only the sql_injection rule from docs/12-handover-fyp1-final.md section 5,
in a new file engine/secureflow/sql_injection.py, and nothing else yet.
First write a tiny fixture app in engine/tests/fixtures/sqli_app with a comment
above each route saying what should happen: string joining, an f-string,
% formatting and .format() into cursor.execute (flagged); a parameterized query
with ? and a value converted with int() (not flagged); a URL variable as the
source; request.get_json() as the source. Show me the fixture before writing the rule.
```

```
Now write the rule and its tests in engine/tests/test_sql_injection.py, then plug
it into scan() in engine/main.py after the ownership rule. Run the whole test
suite and python engine/score.py corpus/, and show me both results. Explain the
rule to me in two or three plain sentences.
```

## Step 2: pull out the shared taint helper

```
The other three unsafe input rules need the same sources, spreading and
sanitizers as sql_injection. Move only that shared part into
engine/secureflow/taint.py, with its own tests in engine/tests/test_taint.py
(each source, each way taint spreads, each sanitizer, and .strip() NOT cleaning
a value). The sql_injection results must not change: show me the test run and
the score before and after.
```

## Step 3: command injection

```
On a new branch maheen/command-injection from main, add the command_injection
rule from docs/12-handover-fyp1-final.md section 5.5 using engine/secureflow/taint.py.
Fixture first (os.system, os.popen, subprocess.run with shell=True: flagged;
subprocess.run with a list and no shell=True, shlex.quote: not flagged), show it
to me, then the rule and tests. Run the tests and the score and show the results.
```

## Step 4: path traversal

```
Same as the last step, for path_traversal, on branch maheen/path-traversal.
Flagged: open(), send_file(), os.remove() with a visitor value, and os.path.join
with a visitor value that is then opened. Not flagged: secure_filename(),
os.path.basename(), safe_join(). Fixture first, then the rule and tests.
```

## Step 5: template injection

```
Same again for template_injection, on branch maheen/template-injection.
Flagged: render_template_string() or jinja2.Template() built from a visitor value.
Not flagged: render_template("page.html", name=value) and
render_template_string("fixed text {{ name }}", name=value).
Fixture first, then the rule and tests.
```

## Step 6: show the new types in scoring and in the extension

```
Add sql_injection, command_injection, path_traversal and template_injection to
CHECKED_PROBLEM_TYPES in engine/score.py and to PROBLEM_TYPES in
extension/src/resultsView.ts with plain group names and titles. Build the
extension (check package.json for the script) and tell me how to check the
results view by hand with F5 on the sqli_app fixture.
```

## Step 7: corpus cases

```
I will add unsafe input routes to the corpus apps myself. Read corpus/README.md
and the ground_truth.json format, then check my new entries: does every
should_flag and should_not_flag entry match a real route and line? Do not change
the apps. Run the score and show me the table.
```

## Step 8: the schema change for exposed secrets

```
On branch maheen/exposed-secrets, make only the schema change in
docs/12-handover-fyp1-final.md section 6: add problem_class exposed_secret and
problem_types hardcoded_secret and env_file_not_ignored to
docs/04-findings.schema.json. Check what the extension shows for a finding with
url_path "" and fix the card if it looks broken. Do not write the rules yet.
List every file you changed so I can tell Munsif about the contract change.
```

## Step 9: hardcoded secrets

```
Add the hardcoded_secret rule from section 6.1 in engine/secureflow/secrets.py.
Fixture first (app.secret_key = "...", app.config["SECRET_KEY"] = "...",
API_KEY = "...", an AKIA... value: flagged; os.environ, os.getenv, "",
"changeme": not flagged; os.getenv("SECRET_KEY", "dev"): ask me first).
The explanation and the JSON must never contain the secret value: add a test
that proves it. Then the rule and tests.
```

## Step 10: .env not ignored by git

```
Add the env_file_not_ignored rule from section 6.2. Fixture folders with:
a .env and no .gitignore (flagged), a .env with ".env" in .gitignore (not
flagged), a .env.production matched by ".env*" (not flagged), and a .gitignore
with a "!" line (flagged, and the explanation says why). Never read or print the
values inside .env except to decide High or Medium. Then the rule and tests.
```

## Step 11: write it all down

```
For each rule I added, update docs/03-detection-rules.md, add a decision entry
under "Decisions made along the way" in CLAUDE.md, and write a walkthrough doc
with the same sections as docs/11-missing-ownership-check.md. Then go through the
"Done for the FYP-1 final" checklist in docs/12-handover-fyp1-final.md and tell
me what is still open.
```

---

## Useful one-liners at any time

- "Explain the change you just made in two or three plain sentences, as if to the panel."
- "Is this flag a false alarm or a real suspect? Show me the code path from source to sink."
- "Scan only this folder and check five findings by hand with me: <folder>."
- "What did the engine miss in this folder? Look for sinks it did not report."
- "Before you edit more than two files, list them and wait for me."
