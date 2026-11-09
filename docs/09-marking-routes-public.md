# Marking a route as public: how it works

This document explains the "marked public" feature from start to finish: why it exists, what the developer does, what the engine does, what the VS Code extension does, and why each safety rule is there. It is written so it still makes sense weeks later without the chat history.

Short version: the developer can say "this route is meant to be open to everyone", either by a comment above the route or in a small settings file. The engine then stops flagging that route, but still lists it so the decision stays visible. The extension can write the comment for the developer with one click.

The exact rule is in `docs/03-detection-rules.md`, part 8. This document explains it.

---

## 1. Why this feature exists

SecureFlow flags every route that has no login check (the missing-login rule). Many such routes are fine: a product list, a price page, a news page. They are public **on purpose**.

The engine already removes some of these by itself:
- the **public allowlist**: well-known paths like `/`, `/login`, `/about`;
- the **public content rule**: routes that only return fixed text and touch nothing else (no database, no request data).

But some public pages read the database, for example a product catalogue. The engine cannot tell from code alone whether a table is private (orders of a user) or shared (products for everyone). So it keeps flagging them. That is correct ("when unsure, flag"), but it is noisy for the developer.

The only person who really knows the intent is the developer. So we let the developer answer the question "is this route meant to be public?" once, and the engine remembers the answer.

Important: a mark is the developer's **claim**. The engine does not check it. That is why the marked route is still listed with a label (section 6), and why some cases ignore the mark (section 7).

---

## 2. What the developer writes

There are two ways. Both do the same thing.

### Way 1: a comment above the route

```python
# secureflow: public
@app.route("/catalog")
def catalog():
    return jsonify(db.execute("SELECT name FROM products").fetchall())
```

Rules for the comment:
- The text is `secureflow: public`. Upper or lower case does not matter, and extra spaces are allowed (`#SecureFlow :  Public` works).
- No other words on that line. `# secureflow: public route` does **not** count, and a misspelling like `# securflow: public` does **not** count.
- It must be **directly above** the route's decorators. "Directly" means: going up from the first `@` line, there are only comment lines until we reach it. A blank line or a line of code in between breaks the link.
- If the function has several decorators, the comment goes above the **topmost** one:

```python
# secureflow: public        <- correct place
@app.route("/prices")
@app.route("/prices/today")
def prices(): ...
```

  One comment here marks **both** routes, because they belong to the same function.
- For a route made with `app.add_url_rule(...)`, the comment goes directly above that line.

### Way 2: the decisions file

A file in the scanned project: `.secureflow/route_decisions.json`

```json
{ "public_routes": ["/news", "/shop/*"] }
```

Rules for the file:
- Each entry is a path, written the way Flask writes it, and must start with `/`.
- A part written as `*` matches **exactly one** part of the path. Parts are the pieces between `/`.
- A slash at the end is ignored. Upper and lower case **do** matter (Flask also treats `/News` and `/news` as different pages).

| Pattern | Route path | Match? | Why |
|---|---|---|---|
| `/news` | `/news/` | yes | the trailing slash is ignored |
| `/shop/*` | `/shop/<int:item_id>` | yes | `*` matches the one part `<int:item_id>` |
| `/shop/*` | `/shop/<int:item_id>/reviews` | no | the path has one part more than the pattern |
| `/news` | `/News/archive` | no | different case, and a different number of parts |

When to use which: the comment sits next to the code, so anyone reading the route sees the decision. The file is handy for many routes at once (for example a whole `/public/*` area) without touching the code.

---

## 3. Where this fits in one scan

When you run `python engine/main.py <folder>`, the function `scan()` in `engine/main.py` does these steps, in this order:

1. **Find the Python files** and read each one into a syntax tree (`ast`). The code is never run.
2. **Find the routes** (`routes.py`): every `@app.route`, `@bp.get`, `add_url_rule`, and so on.
3. **Find the protections** (`protections.py`): `@login_required`, `before_request` hooks, inline checks. Each route gets a list called `protections_found`.
4. **Public content** (`public_content.py`): unprotected routes that only return fixed text get the label `public_content:static_response`.
5. **Developer marks** (`developer_marks.py`), the new step: unprotected routes the developer marked get the label `developer_marked:comment` or `developer_marked:decisions_file`.
6. **The rules** (`rules.py`, `role_check.py`): turn routes into findings.

The trick that makes it work: the missing-login rule only flags a route whose `protections_found` list is **empty**. Steps 4 and 5 put a label into that list, so the rule skips those routes. No change to the rule itself was needed.

---

## 4. How the engine finds the comment

The code is in `engine/secureflow/developer_marks.py`. The main function is `add_developer_marks(routes, project_path)`.

### Step A: only look at routes that need a decision

`needs_decision(route)` says yes only when all three are true:
- the route has **no** protection yet (otherwise there is nothing to decide);
- the route has **no** login decorator sitting above its route decorator (see section 7, rule 1);
- the route is **not** on the public allowlist (it would not be flagged anyway).

### Step B: find the line the comment must be above

`first_line_of_route(route)` answers "where does this route start?".
- For a decorator route, it takes the line numbers of all decorators on the function and returns the smallest one: the topmost decorator.
- For an `add_url_rule` route, it returns the line of that call.

### Step C: walk upwards and look for the comment

`has_mark_comment(route, lines)` starts on the line just above the route and walks **up**, one line at a time, while the line is a comment (starts with `#`). If one of those comment lines is the mark, the answer is yes. As soon as it meets a line that is not a comment (a blank line or code), it stops.

Example (line numbers on the left):

```
10  # ------------------------------
11  # Product list, shared by everyone
12  # secureflow: public
13  @app.route("/catalog")
14  def catalog(): ...
```

The route starts at line 13. The walk checks line 12: a comment, and it is the mark, so the answer is yes. (If the mark were on line 10 it would still count, because lines 11 and 12 are comments too.)

A case that does not count:

```
20  # secureflow: public
21
22  @app.route("/stock")
```

The walk checks line 21: blank, not a comment. It stops. No mark.

The check of the text itself is a small pattern (a "regular expression"): `#`, then `secureflow`, then `:`, then `public`, with optional spaces, any case, and nothing else on the line. That is why a typo is not accepted: being strict means the engine never guesses what the developer meant.

---

## 5. How the engine reads the decisions file

`read_decisions_file(project_path)`:
1. If `.secureflow/route_decisions.json` does not exist, that is normal: there are simply no patterns.
2. It reads the file as JSON. If the JSON is broken, the whole file is ignored and a line is added to `files_skipped` in the output, with the reason. The scan continues.
3. It checks the shape: there must be a list `public_routes`, and every entry must be text starting with `/`. If even one entry is wrong, the **whole** file is ignored (and reported). This way a typo never applies "half" of the developer's decisions.

`path_matches(pattern, url_path)` splits both at `/`, requires the same number of parts, and compares part by part: equal, or `*` in the pattern.

The comment is checked first. If a route has both a comment and a matching file entry, it gets the comment label.

---

## 6. What a marked route looks like in the output

The route is **not** in `findings`. It **is** still in `routes`, with its label:

```json
{
  "url_path": "/catalog",
  "http_methods": ["GET"],
  "file_path": "app.py",
  "line_number": 13,
  "protections_found": ["developer_marked:comment"]
}
```

Why keep it in the list: so the decision can always be seen and reviewed. Nothing is hidden silently. The label also says **who** decided: the developer (`developer_marked`), not the engine (`public_content`).

The output format (`docs/04-findings.schema.json`) did not change. `protections_found` was already a list of text labels.

---

## 7. The safety rules, and why each exists

**Rule 1: a misplaced login decorator beats the mark.**
```python
# secureflow: public
@login_required          # above the route decorator, so Flask ignores it
@app.route("/wishlist")
def wishlist(): ...
```
The `@login_required` shows the developer wanted a login check. The mark says the opposite. When the code contradicts itself, the engine keeps the route flagged, and the explanation tells the developer to move the decorator below `@app.route`. (Flask applies decorators from the bottom up and saves the view at `@app.route`, so anything above it is ignored.)

**Rule 2: a marked route is not a "protected neighbour".**
Another rule (part 7 of the detection rules) raises a flagged route to High when most routes in its group are protected. A marked route has a label in `protections_found`, so without care it would look "protected" and wrongly push its neighbours to High. Marked routes are therefore left out of that count, exactly like public content routes. In the code this is `is_open_on_purpose()` in `rules.py`, using the list `PUBLIC_LABELS` in `constants.py`.

**Rule 3: a broken decisions file is ignored as a whole and reported.** See section 5.

**Rule 4: a mark only answers the missing-login question.** It does not hide any other kind of finding (for example the role check rule only looks at routes that have a real login check, and a mark is not one).

**Rule 5: no marks in the corpus.** Adding marks to Maheen's test apps would hide real problems and make the scores look better than the engine really is.

---

## 8. The extension: the lightbulb and the button

The extension never decides what is public. It only **writes the comment** for the developer, so there are no typos. The engine then judges the comment exactly like a hand-typed one.

### Three VS Code ideas you need

- **Diagnostic**: VS Code's name for an underline with a message (what a spell checker or a linter makes). After a scan, `showFindings()` in `extension.ts` creates one diagnostic per finding and tags it with `source = 'SecureFlow'`.
- **Code action provider**: a class you give to VS Code that answers "do you have a fix for the problem under the cursor?". If it returns actions, VS Code shows the lightbulb. If it returns nothing, there is no lightbulb.
- **Command**: a named action that can be run from anywhere (a menu, a button, another piece of code). Ours is called `secureflow.markPublic`.

### How the lightbulb appears

1. In `activate()` (`extension.ts`) we register our provider for Python files:
   `vscode.languages.registerCodeActionsProvider({ language: 'python', scheme: 'file' }, new MarkPublicActions(...))`
   This means: "VS Code, when the cursor is on a problem in a .py file, ask `MarkPublicActions`."
2. The extension keeps the last scan's findings in a variable, `lastScan`.
3. When the cursor sits on an underline, VS Code calls `provideCodeActions()` (`markPublic.ts`) and passes it the diagnostics under the cursor. For each one, our code:
   - skips it if its source is not `SecureFlow`;
   - finds the finding in `lastScan` with the same file and line;
   - skips it if `canMark(finding)` says no: only missing-login findings can be marked, and not when a login decorator sits above the route decorator (the mark would do nothing, see section 7, rule 1);
   - otherwise returns one action, "SecureFlow: Mark this route as public", which carries the command `secureflow.markPublic` and the finding.
4. VS Code shows the lightbulb (also reachable with **Ctrl+.**).

### The button in the results panel

The results panel is a small web page inside VS Code (`resultsView.ts`). Each selected finding shows a "Mark as public" button, again only when `canMark()` says yes. Clicking it sends a message to the extension, which runs the **same** command. So both paths end in one function.

### What happens after the click: `markPublic()` in `markPublic.ts`

1. **Safety check.** If the file has unsaved changes, or was saved after the scan started, it stops with: "app.py changed since the scan. Save it and scan again before marking a route." Reason: the finding's line number comes from the scan; if the file changed, that line may now be a different route.
2. **Find where the comment goes.** `markInsertLine()` in `markComment.ts` starts at the finding's line and walks **up** over every decorator above it, so the comment lands above the topmost one (the same place the engine looks, section 4). It understands decorators written over several lines, like
   ```python
   @app.route("/a",
              methods=["GET"])
   ```
   by checking that the brackets open on the `@` line and close again before the route line. It never climbs into the function above.
3. **Insert the comment** with the same indentation as the line below it, as one edit. That is why one **Ctrl+Z** removes it.
4. **Save the file.** The engine reads files from disk, not from the editor, so it must be saved.
5. **Scan again.** The engine sees the comment, labels the route `developer_marked:comment`, and the underline disappears.
6. A short message reminds the developer: "A wrong mark hides a real problem: delete the comment to undo it."

### Why one route at a time, and no "mark all"

Marking many routes at once from a list of checkboxes makes it easy to mark a real problem without reading its code. A wrong mark hides a real bug. Deciding one route at a time, while looking at its code, is slower but safer, and easier to defend.

This is the only place where the extension writes into the developer's files, and only when the developer clicks.

---

## 9. The whole journey in one picture

```
Developer clicks "Mark this route as public"
        |
        v
markPublic(): file unchanged since the scan?  -- no -->  warning, nothing written
        | yes
        v
markInsertLine(): walk up past the decorators
        |
        v
insert "# secureflow: public", save the file
        |
        v
scan again: python engine/main.py <folder>
        |
        v
engine: developer_marks.py finds the comment above the route
        |
        v
route gets "developer_marked:comment" in protections_found
        |
        v
missing-login rule skips it (its list is not empty)
        |
        v
no finding -> no underline, status bar count goes down by one
```

---

## 10. Files involved

| File | What it does |
|---|---|
| `engine/secureflow/developer_marks.py` | Finds the comment and reads the decisions file; adds the labels |
| `engine/secureflow/constants.py` | The two label texts and `PUBLIC_LABELS` |
| `engine/secureflow/rules.py` | `is_open_on_purpose()`: marked routes are not counted as protected neighbours |
| `engine/main.py` | Calls `add_developer_marks()` after the public content step; adds a broken file to `files_skipped` |
| `engine/tests/fixtures/marks_app/` | Test app with one route per case, plus a decisions file |
| `engine/tests/test_developer_marks.py` | Engine tests (8) |
| `extension/src/markComment.ts` | Where the comment goes (pure text logic, no VS Code) |
| `extension/src/markPublic.ts` | The lightbulb provider and the `markPublic()` action |
| `extension/src/extension.ts` | Registers the provider and the command; keeps `lastScan` |
| `extension/src/resultsView.ts` | The "Mark as public" button |
| `extension/src/test/markComment.test.ts` | Tests for where the comment goes (7) |
| `extension/src/test/extension.test.ts` | Marks `GET /status` in tiny_app, checks the underlines drop from 9 to 8, puts the file back |

---

## 11. What the tests prove

Engine (`test_developer_marks.py`, on `marks_app`):
- Marked by comment, by comment above `add_url_rule`, by the file, by the file with a trailing slash, and by a `*` pattern: none of these are flagged, and each keeps its label.
- One comment above two route decorators marks both.
- Exactly these stay flagged: a blank line between comment and route, a comment between the decorator and `def`, a misplaced `@login_required`, a path one part longer than the pattern, and a path with different case.
- A broken JSON file and a file with one bad entry are both ignored and reported, and the route stays flagged.
- A marked route is not counted as a protected neighbour.

Extension: where the comment goes for one decorator, a stack, a multi-line decorator, an `add_url_rule` call (with indentation), and that it never climbs into the function above.

The corpus scores did not change, because no corpus app carries a mark.

---

## 12. Questions a panel might ask

**"Can't a developer just mark everything public and hide all problems?"**
Yes, the same way they could delete the scanner. The mark is their own claim. SecureFlow makes it visible (the route stays in the list with a `developer_marked` label), refuses it when the code contradicts it (misplaced decorator), and only lets the extension mark one route at a time. In FYP-2, live testing gives a second opinion.

**"Why not just let the engine decide?"**
The engine cannot see intent. A product list and a list of other users' orders can look the same in code. When unsure the engine flags, and the mark lets the human answer the question the code cannot.

**"Why is the comment so strict about spelling?"**
A loose match could treat an unrelated comment as a mark and hide a real problem. Strict means no guessing, and the extension writes it for you anyway.

**"Why both a comment and a file?"**
The comment keeps the decision next to the code. The file covers groups of routes (`/public/*`) without editing code.

---

## Words used here

- **Route**: a URL the Flask app answers, with the function that answers it.
- **Decorator**: a line starting with `@` above a function, such as `@app.route("/x")` or `@login_required`.
- **Flagged / finding**: the engine reports the route as a possible problem.
- **Label**: a short text in `protections_found` saying why a route is not flagged.
- **Allowlist**: the fixed list of paths that are always public (`/`, `/login`, ...).
- **Syntax tree (`ast`)**: Python's way of turning code into a structure we can read without running it.
- **Regular expression**: a small pattern for matching text.
- **Diagnostic**: an underline with a message in VS Code.
- **Code action**: a fix offered by the lightbulb.
