# The missing ownership check rule (IDOR): how it works

This document explains the `missing_ownership_check` rule from start to finish: why it exists, what it looks for, how the engine decides, and where it can be wrong. It is written so it still makes sense weeks later without the chat history.

Short version: many pages show "a record", such as a note, an order or a profile, and the visitor picks which one through a number in the address, for example `/user/profile?id=2`. If the code opens that record without checking that it belongs to the visitor, a logged-in user can read or change someone else's data just by changing the number. This rule finds those routes.

The exact rule is in `docs/03-detection-rules.md`, part 10. The code is `engine/secureflow/ownership_check.py`. This document explains both.

---

## 1. Why this rule was needed

SecureFlow already had two access-control rules:

| Rule | The question it asks | Example check in Flask |
|---|---|---|
| Missing login (part 3) | Who are you? | `@login_required` |
| Missing role check (part 9) | Are you an admin? | `if session.get("role") != "admin": abort(403)` |
| **Missing ownership check (part 10, new)** | **Is this record yours?** | `if note["user_id"] != session["user_id"]: abort(403)` |

The third question is different from the other two. Alice is logged in, and she is an ordinary user on an ordinary page, so the login and role rules are both happy. But if she asks for Bob's note, the app should still say no. When it doesn't, the problem is called **IDOR**, short for "Insecure Direct Object Reference". The visitor refers directly to an object (a record) by its id, and the app trusts that reference without checking it.

This is exactly Maheen's corpus app `app_03_idor`:

```python
@app.route('/user/profile')
@login_required
def user_profile():
    requested_id = request.args.get('id')          # the visitor chooses the id
    if not requested_id:
        requested_id = session['user_id']          # only a default
    db = get_db()
    user = db.execute('SELECT * FROM users WHERE id = ?', (requested_id,)).fetchone()
    ...  # shows email, credit card and address
```

Alice logs in and opens `/user/profile?id=2`. She sees Bob's email, credit card and address. Before this rule, the scorer listed this route as "not checked yet", because the engine had no rule for it. Now it is found.

It is also in the requirements. SRS **CODE-5** says "The system shall flag admin-style routes without a role check **and routes that take a record ID without an ownership check**". The role half was done in part 9; this rule is the second half. It is also the third Broken Access Control problem in the project brief ("one user reaching another user's data"). The midterm scope phrases it as "Missing ownership check (IDOR), using the database tables the route reads", and section 4 explains that part.

---

## 2. The rule in one sentence

A route is flagged as `missing_ownership_check` when it **has a login check**, it **reads or changes a table whose rows belong to users**, **a value the visitor chooses** goes into that query, and SecureFlow **finds no ownership check**.

All four must be true. Each part is explained below.

---

## 3. Part one: the route has a login check

Function: `is_login_protected(route)`, **reused** from the role rule (`role_check.py`).

As in the role rule, only routes with a real protection in `protections_found` are looked at. Two kinds of route are skipped:
- **Routes with no protection at all.** The missing-login rule already flags them, and "anyone can open it" is the bigger problem. So one route never gets both a `missing_login` and a `missing_ownership_check` finding.
- **Routes that are only "public on purpose"** (`public_content:...`, `developer_marked:...`). These labels are not protections.

---

## 4. Part two: the table belongs to users

This is the "using the database tables the route reads" part of the scope.

Not every table is private. A `products` table is the same for everyone, so opening product number 7 is fine. A `notes` table, where each note belongs to someone, is private. So the rule first finds out **which tables belong to users**.

### a. Finding the tables

Function: `user_owned_tables(files, project_path)`.

Flask apps that use plain SQL nearly always create their tables with a `CREATE TABLE` statement. The engine looks for that text in two places:
- inside **strings in any Python file** of the project, as in `cursor.execute("CREATE TABLE IF NOT EXISTS notes (...)")` (this is how Maheen's apps do it);
- inside **`.sql` files** in the project, for example `schema.sql` (this is how the official Flask tutorial does it). Function: `sql_files(project_path)`.

The code is only read, never run, and no database is opened.

For each `CREATE TABLE name ( ... )` the engine takes the table name and the text between the brackets (function `create_tables`). The brackets can nest, as in `price DECIMAL(10, 2)` or `REFERENCES users(id)`, so the engine counts opening and closing brackets to find the right end. Then it splits the column list on the commas that are not inside brackets (function `split_columns`).

### b. Deciding "this table belongs to users"

Function: `owner_reason(table_name, columns_text)`. A table belongs to users when **one** of these is true:

1. **It is the users table itself**: its name is `user`, `users`, `account` or `accounts` (the list `USER_TABLE_NAMES` in `constants.py`). Each row is one person's data.
2. **It has an owner column**: a column named `user_id`, `owner_id`, `author_id`, `account_id`, `customer_id` or `created_by` (the list `OWNER_COLUMNS`). That column says which user owns each row.
3. **A column points to the users table**: `owner INTEGER REFERENCES users(id)`, or a separate line `FOREIGN KEY (writer) REFERENCES users(id)`. This catches owner columns with unusual names.

Examples:

```sql
CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT)          -- belongs to users (rule 1)
CREATE TABLE notes (id INTEGER, user_id INTEGER, body TEXT)      -- belongs to users (rule 2)
CREATE TABLE invoices (id INTEGER, owner INTEGER REFERENCES users(id))  -- belongs to users (rule 3)
CREATE TABLE products (id INTEGER, name TEXT, price DECIMAL(10, 2))     -- shared, not private
```

The reason is kept, because it goes into the explanation (section 7).

This is the same idea as "private values" in `docs/08-verification-design.md`, layer 4: values from the users table and from tables with a user or owner column are private, and values from shared tables are not. The code-only rule and the later live test use the same definition.

**A table with no `CREATE TABLE` in the project is not looked at.** If the engine cannot see how a table is built, it cannot tell who owns its rows. Guessing from the table name would cause false alarms, and CLAUDE.md prefers fewer, correct findings.

---

## 5. Part three: the visitor chooses the value

Functions: `visitor_source`, `visitor_place`, `keyed_read`, `sort_variables`.

The rule looks at every database query in the handler: a call to `.execute(...)` or `.executemany(...)`.

### a. Which queries count

- Only queries that start with `SELECT` (read), `UPDATE` or `DELETE` (change). An `INSERT` adds a *new* row, so it cannot open someone else's.
- The table names are taken from the SQL text after `FROM`, `JOIN` and `UPDATE` (function `query_tables`). At least one must be a table that belongs to users (section 4).
- If the SQL text is kept in a variable first (`sql = "SELECT ..."`, then `db.execute(sql, ...)`), the engine follows the variable inside the same handler (function `sql_text`).

### b. Values the visitor chooses

A value is **visitor-chosen** when it comes from:

| Where | Example | Named in the explanation as |
|---|---|---|
| A URL variable | `@app.route("/notes/<int:note_id>")` | `note_id in the URL path` |
| The query string | `request.args.get("id")` | `id from the query string` |
| A form | `request.form["id"]` | `id from the form` |
| Either of those | `request.values.get("id")` | `id from the request` |
| A JSON body | `request.get_json()["id"]`, `request.json["id"]` | `id from the JSON body` |

The engine checks the query's parameters, for example `(note_id,)`, and also the SQL text itself, so an f-string like `f"SELECT * FROM orders WHERE id = {order_id}"` counts too.

### c. Following variables

Real code rarely puts `request.args.get("id")` straight into the query. It stores it first:

```python
note_id = request.args.get("id")
db.execute("SELECT * FROM notes WHERE id = ?", (note_id,))
```

Function `sort_variables` looks at every `name = ...` in the handler and remembers which names hold a visitor value. It repeats a few times, so a chain like `raw = request.args["id"]` then `note_id = int(raw)` is followed too.

**One visitor assignment is enough.** In app 3 the id is first taken from the visitor, and only replaced by the session id when the visitor gave none:

```python
requested_id = request.args.get('id')
if not requested_id:
    requested_id = session['user_id']
```

The visitor can still type `?id=2`, so `requested_id` counts as visitor-chosen.

If several visitor values go into one query (for example a new title *and* the id of the post to rename), the explanation names the one whose name contains `id`, because that is the one that picks the record.

---

## 6. Part four: no ownership check is found

If **any** of these three is found, the route is not flagged.

### a. The query itself is tied to the logged-in user

Function: `is_session_user(node, session_names)`.

The safest way to write such a query is to ask the database for "this id, **and** owned by me":

```python
db.execute("SELECT * FROM notes WHERE id = ? AND user_id = ?", (note_id, session["user_id"]))
```

Now Alice can only ever get her own notes. So if any value in the query is **the logged-in user's identity**, the query is safe. The identity is any of:
- `session["user_id"]` or `session.get("user_id")` (any session key containing `user`, `uid`, `login`, `auth` or `token`, the same list as the login rule);
- `current_user.id`, or any other `current_user` attribute **except** `is_authenticated`, `is_active` and `is_anonymous`. Those only say *whether* someone is logged in, not *who* (the list `LOGIN_STATE_ATTRIBUTES`);
- `g.user` (or any `g` attribute containing `user`);
- `get_jwt_identity()`;
- a variable set **only** from one of these, for example `customer = current_user.id`.

A query like `SELECT * FROM users WHERE id = ?` with `(session["user_id"],)` is also safe for the same reason: the visitor chooses nothing, the page always shows "me".

### b. An `if` that compares the record with the logged-in user and turns the visitor away

Functions: `has_ownership_if`, `compares_with_session_user`.

Many apps first load the record, then check its owner. This is Maheen's safe route in `app_05_safe_control`:

```python
note = db.execute('SELECT * FROM private_notes WHERE id = ?', (note_id,)).fetchone()
if note['user_id'] != session['user_id']:
    abort(403)
```

The engine looks for an `if` that does **two** things:
1. its test **compares** the logged-in user (as in a) with something else, using `==`, `!=`, `is` or `is not`;
2. one of its branches **turns the visitor away** (function `turns_visitor_away`, shared with the login and role rules): a `redirect(...)`, an `abort(...)`, a `raise`, or an error answer such as `return "Not your note", 403`.

The "something else" must **not be a fixed value**. This matters:

```python
if session.get("user_id") is None:     # compares with None, a fixed value
    return redirect(url_for("login"))  # this is a LOGIN check, not an ownership check
```

This only checks that someone is logged in. It says nothing about whose record it is, so it does not count. The test app has exactly this case (`/notes/raw`) and it is flagged.

Same idea as before: a check only counts if it can stop the visitor. Reading the owner without sending anyone away protects nothing.

### c. An owner-style decorator

Function: `has_owner_decorator(route)`.

A decorator **below** `@app.route` whose name contains `owner`, for example `@owner_required`, is trusted as an ownership check (the list `OWNER_DECORATOR_WORDS`). This is the same "trust the name" choice as the role rule makes with `@admin_only`.

---

## 7. The finding

Function: `make_finding(route, query)`.

- `problem_class`: `access_control`, `problem_type`: `missing_ownership_check`
- `severity`: always **High**. It is another user's private data, or a change to it.
- `finding_status`: `unconfirmed`, like every code-only result.
- `finding_match_key`: the same formula as the other rules, with `missing_ownership_check` in it.
- `explanation`, for app 3:

  > This route (GET /user/profile) checks that the visitor is logged in, but it reads a record from the users table using a value the visitor chooses (id from the query string). Each row of that table is one user's data, and SecureFlow found no check that the record belongs to the visitor. A logged-in user may be able to see another user's data by changing that value. This was found by reading the code and has not been tested live.

  The middle sentence says *why* the table is private, so the developer can check the reasoning:
  - users table: "Each row of that table is one user's data"
  - owner column: "In that table the user_id column says which user owns each row"
  - a column pointing to users: "In that table the owner column points to the users table, so each row belongs to a user"

  For `UPDATE` and `DELETE` the words change to "changes a record in" and "change or delete another user's data".

One route gets at most one ownership finding, for its first unchecked query. A route can get both a role-check finding and an ownership finding, because those are two different problems.

The output format (`docs/04-findings.schema.json`) did not change: `missing_ownership_check` was already one of the allowed problem types.

---

## 8. Where this fits in one scan

In `scan()` in `engine/main.py`:

1. find files, routes, protections (as before);
2. public content labels, then developer marks (as before);
3. `missing_login_findings(routes)`: the missing-login rule;
4. `missing_role_findings(routes, files)`: the role-check rule;
5. **`missing_ownership_findings(routes, files, project_path)`**: this rule, new. It needs `project_path` to find `.sql` files;
6. sort all findings by file and line.

Other changes that came with it:
- **Scorer** (`engine/score.py`): now also scores `missing_ownership_check` entries. Every problem type in the corpus is now checked, so the "Not checked yet" column is 0.
- **Practice corpus** (`engine/tests/fixtures/mini_corpus`): it used an ownership entry as its example of "a type the engine does not check yet". That example is now `sql_injection`, so the scorer's "not checked yet" feature is still tested.
- **Extension** (`extension/src/resultsView.ts`): a new group "Missing ownership checks", card title "Logged in, but no check that the record belongs to the visitor". The status bar already counts every finding as a suspect.
- **"Mark as public"** is not offered on these findings: a mark only answers the login question.

---

## 9. Honest limits (say these to the panel)

1. **Only plain SQL is read.** Queries written with an ORM (a library that turns Python classes into tables), such as SQLAlchemy's `Note.query.get(note_id)` or `db.session.get(Note, note_id)`, are not looked at yet. Such IDORs are missed. This is the natural next step.
2. **Tables created outside the project's code are unknown.** If the tables come from migrations run elsewhere or from an existing database file, there is no `CREATE TABLE` to read, so those routes are not flagged.
3. **An ownership check in a helper function is not seen.** For example `check_owner(note)` on the first line, or `if not current_user.owns(note): abort(403)` (a call, not a comparison). The route is then flagged even though it is safe ("when unsure, flag").
4. **It trusts names.** An `@owner_required` that checks nothing hides the problem. The owner column list is also names only: an owner column called `made_by` with no `REFERENCES` is not recognised.
5. **The users table is always treated as private.** A page meant to show other people's public profiles (`/user/<name>` on a social site) is flagged; the developer decides.
6. **It cannot prove impact.** Like every result now, it is Unconfirmed. In FYP-2 the sandbox confirms it by logging in as User A and asking for a record that belongs to User B (SRS **VERIFY5**).

---

## 10. Results on the corpus

| | Before the rule | After the rule |
|---|---|---|
| Real problems checked | 6 | 7 |
| Found | 6 | 7 |
| False alarms | 0 | 0 |
| Not checked yet | 1 (the IDOR in app 3) | 0 |
| Precision / recall | 1.00 / 1.00 | 1.00 / 1.00 |

- `app_03` `/user/profile` (visitor-chosen id, users table, no check): **found**.
- `app_05` `/notes/view` (same shape, but checks `note['user_id'] != session['user_id']` and aborts): **correctly not flagged**.
- No other corpus route got the new finding. The other logged-in routes either read no user table with a visitor value (`/profile`, `/user/dashboard`, `/admin/dashboard`) or only insert a row (`/post/create`). Open routes such as `/post/delete/<int:post_id>` stay `missing_login` only.

Caution: the rule was written knowing these two apps, so it is also tested on 18 routes in `engine/tests/fixtures/idor_app/`, built to cover each case above.

---

## 11. Files involved

| File | What it does |
|---|---|
| `engine/secureflow/ownership_check.py` | The whole rule (new) |
| `engine/secureflow/constants.py` | `USER_TABLE_NAMES`, `OWNER_COLUMNS`, `VISITOR_SOURCES`, `LOGIN_STATE_ATTRIBUTES`, `OWNER_DECORATOR_WORDS` |
| `engine/secureflow/role_check.py` | Reused: `is_login_protected` |
| `engine/secureflow/protections.py` | Reused: `turns_visitor_away`, `walk_list`, `SESSION_USER_WORDS` |
| `engine/main.py` | Calls the rule after the role rule |
| `engine/score.py` | Scores `missing_ownership_check` |
| `engine/tests/fixtures/idor_app/app.py` | One route per case, with the expected result in a comment above each (new) |
| `engine/tests/fixtures/idor_app/schema.sql` | A table that exists only in a `.sql` file (new) |
| `engine/tests/test_ownership_check.py` | The rule's tests (7, new) |
| `engine/tests/test_corpus.py`, `test_score.py` | Corpus check includes the new type; "not checked yet" example moved |
| `extension/src/resultsView.ts` | The "Missing ownership checks" group |
| `docs/03-detection-rules.md` | Part 10: the exact rule |

---

## 12. What the tests prove (`test_ownership_check.py` on `idor_app`)

- **Flagged, exactly these eight:**
  - an id from the query string (`/notes/view`);
  - an id as a URL variable (`/notes/<int:note_id>`);
  - a `DELETE` by any id (`/notes/<int:note_id>/delete`);
  - the session id used only as a default (`/profile`, the same shape as app 3);
  - an id inside an f-string query on a table with `customer_id` (`/orders/<order_id>`);
  - a table found only in `schema.sql`, owner column via `REFERENCES users(id)` (`/invoices/view`);
  - an id from the JSON body, table owned through a `FOREIGN KEY` line (`/api/posts/rename`);
  - a session compared with `None` only, which is a login check (`/notes/raw`).
- **Not flagged, ownership checks recognised:** `if note["user_id"] != session["user_id"]: abort(403)`, the same with `current_user.id` and `return ..., 403`, a query with `AND user_id = ?` and the session id, the same through a variable, and `@owner_required`.
- **Not flagged, no other user's record can be opened:** a shared `products` table, a table with no `CREATE TABLE` anywhere, an `INSERT`, and an id taken only from the session (`/me`).
- An open route with a visitor id gets **one** finding (`missing_login`), not two.
- The explanation text and fields are exact, the `DELETE` wording is used for a delete, the id (not the new title) is named for the rename, and the output validates against the schema.
- On the corpus: app 3 gives exactly `/user/profile` as `missing_ownership_check`, and app 5 gives no findings.

---

## 13. Questions a panel might ask

**"Why not flag every route that takes an id?"**
Most ids point to shared things, such as a product, a blog post to read, or a category. Flagging them all would bury the real problems in false alarms. Only records from tables that belong to users need an ownership check, and the `CREATE TABLE` text tells us which tables those are.

**"How do you know a table belongs to users without running the app?"**
From the way the table is built: it is the users table, it has a column such as `user_id`, or a column points to the users table. All of this is written in the `CREATE TABLE` text, which the engine reads like any other text. No database is opened and no code is run.

**"Why skip tables you can't see?"**
Without the table definition we would be guessing from the table's name. A wrong guess is a false alarm, and the project prefers fewer, correct findings. It is written down as a limit.

**"Why does `if session.get('user_id') is None` not count?"**
It only checks that *someone* is logged in. It never looks at whose record it is. An ownership check must compare the record's owner with the logged-in user.

**"Why is it always High?"**
The attacker only needs an ordinary account, and changing one number is enough to read or change another user's private data, such as Bob's credit card in app 3.

**"Is it proven?"**
No. It is a suspect (Unconfirmed). FYP-2 proves it by logging in as test User A and asking for a record that belongs to test User B (SRS VERIFY5).

---

## Words used here

- **IDOR (Insecure Direct Object Reference)**: the visitor names a record directly (by its id), and the app opens it without checking that the visitor may see it.
- **Record (row)**: one entry in a database table, such as one note or one user.
- **Ownership check**: code that makes sure the record belongs to the logged-in user before showing or changing it.
- **Owner column**: a column such as `user_id` that says which user a row belongs to.
- **`CREATE TABLE`**: the SQL statement that builds a table and lists its columns.
- **`REFERENCES` / `FOREIGN KEY`**: SQL words that say "this column points to a row in another table".
- **URL variable**: a part of the route path in angle brackets, such as `<int:note_id>`, that Flask passes to the handler.
- **Query string**: the part of an address after `?`, such as `?id=2`, read with `request.args`.
- **ORM**: a library (such as SQLAlchemy) that lets code use Python classes instead of writing SQL.
- **Turn the visitor away**: redirect, abort, raise, or answer with 401/403, so the page is not shown.
