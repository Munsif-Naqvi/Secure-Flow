# Starter pack: FYP-1 final

This guide explains what SecureFlow does so far and what you will build next. Words in *italics* are explained in section 10 at the end.

## 1. What SecureFlow is

SecureFlow reads the code of a Flask app and points out places that look unsafe. It does this without running the app. Each place it finds is a *suspect*, and every suspect is marked *Unconfirmed*, because nobody has tested it yet. Testing suspects in a safe copy of the app (Docker) comes in FYP-2.

There are two parts:
- **The engine** (`engine/`), written in Python. You run `python engine/main.py <folder>` and it prints the results as JSON.
- **The VS Code extension** (`extension/`). It runs the engine, underlines the suspects in the code and lists them in a panel.

## 2. What is already built

The engine already finds three kinds of access problems:

| Problem | Plain meaning |
| --- | --- |
| `missing_login` | Anyone can open this page without logging in. |
| `missing_role_check` | You must log in, but any user can open an admin page. |
| `missing_ownership_check` | A logged-in user can open someone else's record by changing an ID in the URL. |

Each rule has a short write-up in `docs/` (for example `docs/11-missing-ownership-check.md`). Read one of them to see the style we use.

## 3. How a scan works

1. The engine lists all Python files in the folder.
2. It turns each file into a tree of code parts (an *AST*), so it can look at the code without running it.
3. It finds every route (each URL the app answers) and the function that handles it.
4. It checks each route for login checks.
5. Each rule looks at the routes and adds its suspects to the list, which is printed as JSON.

Your rules are added at step 5, next to the existing ones. The main file is `engine/main.py`, and each rule has its own file in `engine/secureflow/`.

## 4. Rules we always follow

- **Never run the scanned app's code.** Only read it.
- **No new Python libraries** unless we both agree first.
- **Fewer, correct results beat many wrong ones.** If you are not sure something is a problem, do not flag it. Write it down as a limit instead.
- **Small steps.** Build one rule, test it, check the result, then move on.
- **Every rule gets a test,** using a tiny sample app in `engine/tests/fixtures/`.
- **You must be able to explain every rule** to the panel in two or three simple sentences.

## 5. Your first job: unsafe input (taint tracking)

The idea is simple. Follow a value the visitor typed and see where it ends up.

- It **starts** at a *source*, for example `request.args.get("name")` (a value from the URL).
- If it **reaches** a risky place (a *sink*), such as an SQL query,
- and **nothing cleans it** on the way (a *sanitizer*),
- then that line is a suspect.

Example:

```python
name = request.args.get("name")                           # source: the visitor controls this
sql = "SELECT * FROM users WHERE name = '" + name + "'"   # the value is joined into SQL text
cursor.execute(sql)                                       # sink: flag this line
```

The safe version passes the value separately, so the database never treats it as SQL:

```python
cursor.execute("SELECT * FROM users WHERE name = ?", (name,))   # safe: do not flag
```

You build four rules, one at a time, in this order:

| Rule | Unsafe (flag it) | Safe (do not flag) |
| --- | --- | --- |
| `sql_injection` | Visitor value joined into SQL text, then `.execute(...)` | Value passed separately with `?`, or turned into a number with `int(...)` |
| `command_injection` | Visitor value in `os.system(...)`, or in `subprocess.run(..., shell=True)` | `subprocess.run([...])` with a list and no `shell=True` |
| `path_traversal` | Visitor value used as a file name in `open(...)` or `send_file(...)` | Cleaned with `secure_filename(...)` first |
| `template_injection` | Visitor value used as the template in `render_template_string(...)` | Value passed in as a variable: `render_template("page.html", name=name)` |

Where visitor values come from: `request.args`, `request.form`, `request.get_json()`, `request.files`, `request.headers`, `request.cookies`, and the variables in the URL itself (like `<name>` in `/store/<name>`).

To keep it simple at first, only follow a value **inside one route function**. Values passed into other functions can come later.

Start with `sql_injection`. Then move the shared part (finding sources and following values) into one file, `engine/secureflow/taint.py`, so the other three rules can reuse it. `engine/secureflow/ownership_check.py` already finds `.execute(...)` calls and visitor values, so read it first.

## 6. Your second job: exposed secrets

This is a new idea we agreed on. It is not in the SRS yet, so add a line to the SRS change log when it is done.

### 6.1 Secrets written in the code (`hardcoded_secret`)

```python
app.secret_key = "my-real-key-123"         # flag: a fixed secret in the code
API_KEY = "AKIA..."                        # flag
API_KEY = os.environ["API_KEY"]            # do not flag: read from the environment
SECRET_KEY = "changeme"                    # do not flag: an obvious placeholder
```

Never show the secret itself in the results. Say only which name and line it is on.

### 6.2 A `.env` file that git does not ignore (`env_file_not_ignored`)

A `.env` file usually holds passwords and keys. If `.gitignore` does not list it, it can end up on GitHub. Flag the `.env` file when no line in `.gitignore` matches it. Never print what is inside the `.env` file.

### Before you start these two rules

The results format (`docs/04-findings.schema.json`) does not have these types yet. Adding them is the first step, and Munsif must agree, because the extension depends on that format.

## 7. How to work on each step

1. Make a new branch from the latest `main`.
2. Write the tiny sample app first, with a comment above each route saying what should happen.
3. Write the rule and its test.
4. Run the tests: `cd engine && python -m pytest`.
5. Run the score: `python engine/score.py corpus/`. If the numbers change, find out why.
6. Write the rule down in `docs/03-detection-rules.md`.
7. Open a pull request and ask Munsif to look at it.

The prompts in `docs/13-claude-code-prompts.md` walk you through these steps with Claude Code.

## 8. Easy mistakes to avoid

- **Check results by hand.** When we tested on a real project, SecureFlow flagged every route. The real cause was that it had missed most of the routes. Always ask two questions: what did it miss, and what did it wrongly flag?
- **Scan one app folder at a time,** not a whole repository with many copies of the same code.
- **Not everything cleans a value.** `name.strip()` or `name.lower()` still lets the attack through. Only real cleaning steps count.
- **Line numbers move.** Adding one line to a sample app shifts every line below it. Run the engine first, then copy the line numbers into the test.
- **New types need two small additions:** add each one to `CHECKED_PROBLEM_TYPES` in `engine/score.py`, and to `PROBLEM_TYPES` in `extension/src/resultsView.ts`. Without the second one, the extension does not show them in its results list.

## 9. Done when

- [ ] The four unsafe input rules work, each with a sample app and tests (unsafe and safe cases)
- [ ] The shared `taint.py` has its own tests
- [ ] The results format has the two secrets types (agreed with Munsif)
- [ ] The two secrets rules work, and no secret value ever appears in the results
- [ ] New types show in `score.py` and in the extension
- [ ] The corpus has examples for every new type
- [ ] Every rule is written down in `docs/03-detection-rules.md`

## 10. Words used in this guide

| Word | Meaning |
| --- | --- |
| *Suspect* | A place in the code that looks unsafe but has not been tested. |
| *Unconfirmed* | The label every suspect gets for now. Only a live test (FYP-2) can confirm one. |
| *AST* | A tree of the code's parts, made by Python's `ast` module. It lets us read code without running it. |
| *Taint tracking* | Following a value from where the visitor typed it to where it is used. |
| *Source* | Where a visitor value comes in, such as `request.args`. |
| *Sink* | A risky place for a visitor value, such as an SQL query or a shell command. |
| *Sanitizer* | Something that makes the value safe, such as `int(...)` or `secure_filename(...)`. |
| *Fixture* | A tiny sample app in `engine/tests/fixtures/`, used only by the tests. |
| *Corpus* | The bigger test apps in `corpus/`, each with a list of correct answers (`ground_truth.json`). |
