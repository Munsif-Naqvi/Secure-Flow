# The missing role check rule: how it works

This document explains the `missing_role_check` rule from start to finish: why it exists, what it looks for, how the engine decides, and where it can be wrong. It is written so it still makes sense weeks later without the chat history.

Short version: some pages are meant for admins only. Such a page needs two checks: "is the visitor logged in?" and "is the visitor an admin?". If the code has the first check but not the second, any logged-in user can open the admin page. This rule finds those routes.

The exact rule is in `docs/03-detection-rules.md`, part 9. The code is `engine/secureflow/role_check.py`. This document explains both.

---

## 1. Why this rule was needed

Until now SecureFlow had one access-control rule: **missing login**. It flags routes that anyone can open without logging in.

But logging in only proves **who** you are. It does not prove you are **allowed** to do something. Two different questions:

| Question | Name | Example check in Flask |
|---|---|---|
| Who are you? | authentication (login) | `@login_required` |
| Are you allowed to do this? | authorisation (role, permission) | `if session.get("role") != "admin": abort(403)` |

An admin page needs both. A very common mistake is to add `@login_required` and forget the role check. The page then *looks* protected (you must log in), so the missing-login rule says nothing, but every ordinary user can open it.

This is exactly Maheen's corpus app `app_02_admin_cms`:

```python
@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    # @login_required verifies the user is logged in, but there is NO role check!
    secrets = db.execute('SELECT * FROM system_secrets').fetchall()
    ...
```

Any logged-in user (for example `john_doe`, a normal user) can read the payment gateway key. Before this rule, the scorer listed this route as "not checked yet", because the engine had no rule for it. Now it is found.

It is also in the requirements: SRS **CODE-5** says "The system shall flag admin-style routes without a role check". And it is one of the three Broken Access Control problems in the project brief (missing login check, missing role check, one user reaching another user's data).

---

## 2. The rule in one sentence

A route is flagged as `missing_role_check` when it **has a login check**, its **name says it is for admins**, and SecureFlow **finds no role check** for it.

All three must be true. Each part is explained below.

---

## 3. Part one: the route has a login check

Function: `is_login_protected(route)`.

The protection detector (`protections.py`) has already filled each route's `protections_found` list, for example `["login_required"]`. This rule only looks at routes where that list holds a **real** protection.

Two kinds of route are skipped:
- **Routes with no protection at all.** These are already flagged by the missing-login rule. Flagging them twice ("no login" and "no role") would be noise, and the bigger problem is the missing login. So one route never gets both findings.
- **Routes that are only "public on purpose"**: the labels `public_content:static_response`, `developer_marked:comment` and `developer_marked:decisions_file` are not protections. They live in `PUBLIC_LABELS` in `constants.py`.

---

## 4. Part two: the route is "admin-style"

Function: `is_admin_style(route)`.

The engine cannot read the developer's mind, so it uses names. A route is admin-style when one of these contains (any case) `admin`, `superuser` or `moderator`:
- the **path**, for example `/admin/dashboard`;
- the **handler function name**, for example `def admin_panel()` on the path `/panel`;
- the **variable name of its Blueprint**, for example `admin_bp = Blueprint(...)`, even when the paths themselves do not say admin.

The word list is `ADMIN_ROUTE_WORDS` in `constants.py`.

Why only names: it is simple, every panel member can check it by eye, and it gives few false alarms. A logged-in page called `/dashboard` is normal and is not looked at. (The price: an admin page with an innocent name is missed. See section 8.)

---

## 5. Part three: no role check is found

Function: `has_role_check(route, role_hooks)`. It returns yes if **any** of these three is found.

### a. A role decorator

Function: `role_decorator(route)`.

Like the login rule, only decorators **below** `@app.route` count, because Flask ignores the ones above it. A decorator counts as a role check when:
- its name is one of the well-known ones: `admin_required`, `roles_required`, `role_required`, `permission_required`; or
- it is a home-made decorator whose name contains `role`, `admin`, `superuser`, `staff`, `permission` or `privilege` (the list `ROLE_WORDS`), for example `@admin_only`.

For a MethodView class, the `decorators = [...]` list is checked the same way.

```python
@app.route("/admin/reports")
@login_required
@admin_only                 # role check: not flagged
def admin_reports(): ...
```

### b. A role check inside the handler

Function: `role_check_in(function)`.

It looks for an `if` that does **two** things:
1. its test **mentions a role** (function `tests_role`): a name such as `role`, an attribute such as `current_user.is_admin` or `current_user.has_role`, or a text such as `"admin"`;
2. one of its branches **turns the visitor away** (function `turns_visitor_away`, shared with the login rule): a `redirect(...)`, an `abort(...)`, a `raise`, or an error answer such as `return "Forbidden", 403`.

All of these count:

```python
if session.get("role") != "admin":
    abort(403)

if not current_user.is_admin:
    return "Forbidden", 403

if not current_user.has_role("admin"):
    return redirect(url_for("index"))
```

This one does **not** count:

```python
role = session.get("role")          # only reads the role
return "stats for " + str(role)     # nobody is ever turned away
```

Reading the role stops no one, so it is not a check. This is the same idea as the session rule decided in Step 6 for login checks: a check must be able to send the visitor away.

### c. A role check in a `before_request` hook

Function: `find_role_hooks(files)`.

A Blueprint (or the app) can have a function that runs before every one of its routes:

```python
@staff_bp.before_request
def staff_must_be_admin():
    if session.get("role") != "admin":
        abort(403)
```

If such a hook contains a role check (the same test as in b), every route of that Blueprint is covered. A hook on the app itself covers every route.

Note the difference with `engine/tests/fixtures/tiny_app/admin.py`: its admin Blueprint hook only checks `current_user.is_authenticated`. That is a **login** check, not a role check, so its two admin routes are flagged.

---

## 6. The finding

Function: `make_finding(route)`.

- `problem_class`: `access_control`, `problem_type`: `missing_role_check`
- `severity`: always **High**. An admin page open to every logged-in user is serious.
- `finding_status`: `unconfirmed`, like every code-only result.
- `finding_match_key`: the same formula as the login rule, with `missing_role_check` in it.
- `explanation`:

  > This route (GET /admin/dashboard) checks that the visitor is logged in, but SecureFlow found no admin or role check. Its name suggests it is meant for admins, so any logged-in user may be able to use it. This was found by reading the code and has not been tested live.

  If a role decorator sits **above** `@app.route` (so Flask ignores it), one sentence is added after the first one, for example: "A @admin_only sits above the route decorator, so Flask ignores it; move it below."

The output format (`docs/04-findings.schema.json`) did not change: `missing_role_check` was already one of the allowed problem types.

---

## 7. Where this fits in one scan

In `scan()` in `engine/main.py`:

1. find files, routes, protections (as before);
2. public content labels, then developer marks (as before);
3. `missing_login_findings(routes)`: the missing-login rule;
4. **`missing_role_findings(routes, files)`**: this rule, new;
5. sort all findings by file and line, so the list follows the code no matter which rule found each one.

Other changes that came with it:
- **Scorer** (`engine/score.py`): now scores `missing_role_check` entries too, and matches a finding to a ground-truth entry by **problem type** as well as path. So a missing-login finding can never be counted as finding a role-check problem by accident.
- **Extension**: the results view groups findings into "Missing login checks" and "Missing role checks", each card has a matching title, and the status bar says "N suspects" instead of "N unprotected routes" (a role-check route is protected by login, so "unprotected" would be wrong).
- **"Mark as public"** is not offered on role-check findings: a mark only answers the login question.

---

## 8. Honest limits (say these to the panel)

1. **It trusts names.** A decorator called `@admin_check` that checks nothing counts as a role check, so the problem is hidden. Likewise `@admin_login_required` that only checks login. The practice corpus in `engine/tests/fixtures/mini_corpus/app_02_shop` has exactly this case and the scorer reports it as **missed**, on purpose.
2. **An admin page with an innocent name is not looked at**, for example `/settings/system` used only by admins.
3. **A role check inside another function** that the handler calls (for example `check_admin()` on the first line) is not seen. The route is then flagged even though it is safe. This follows the project principle "when unsure, flag".
4. **It cannot prove impact.** Like every result now, it is Unconfirmed. In FYP-2 the sandbox confirms it by calling the route as an ordinary test user (SRS VERIFY: "send the request as a normal user to an admin route").

---

## 9. Results on the corpus

| | Before the rule | After the rule |
|---|---|---|
| Real problems checked | 5 | 6 |
| Found | 5 | 6 |
| False alarms | 0 | 0 |
| Not checked yet | 2 | 1 (the IDOR in app 3) |
| Precision / recall | 1.00 / 1.00 | 1.00 / 1.00 |

- `app_02` `/admin/dashboard` (login only): **found**.
- `app_05` `/admin/dashboard` (checks `session.get('role') != 'admin'` and aborts): **correctly not flagged**.

Caution: the rule was written knowing these two apps, so it is also tested on 13 routes in `engine/tests/fixtures/role_app/`, built to cover each case above.

---

## 10. Files involved

| File | What it does |
|---|---|
| `engine/secureflow/role_check.py` | The whole rule |
| `engine/secureflow/constants.py` | `ADMIN_ROUTE_WORDS` and `ROLE_WORDS` |
| `engine/secureflow/protections.py` | Reused: `protection_label`, `turns_visitor_away`, `walk_list` |
| `engine/main.py` | Calls the rule after the missing-login rule; sorts the findings |
| `engine/score.py` | Scores `missing_role_check`; matches by problem type |
| `engine/tests/fixtures/role_app/app.py` | One route per case, with the expected result in a comment above each |
| `engine/tests/test_role_check.py` | The rule's tests (7) |
| `extension/src/resultsView.ts`, `extension.ts` | Grouping by problem type, card titles, "N suspects" |

---

## 11. What the tests prove (`test_role_check.py` on `role_app`)

- Flagged, exactly these five: an admin path with login only, `admin` only in the handler name, the role only read, `@admin_only` above the route decorator, and `admin` only in the Blueprint's variable name.
- Not flagged: `abort(403)`, `return ..., 403`, a redirect, a home-made `@admin_only`, `@roles_required("admin")`, and a Blueprint `before_request` role hook.
- An open admin route gets **one** finding (`missing_login`), not two.
- A logged-in page without an admin name (`/dashboard`) is not flagged.
- The explanation text and fields are exact, findings stay in code order, and the output validates against the schema.
- `tiny_app`'s admin Blueprint (hook checks login only) gives exactly its two admin routes.

---

## 12. Questions a panel might ask

**"Why not flag every logged-in route without a role check?"**
Most logged-in pages are for every user (your profile, your orders). Flagging them all would bury real problems in false alarms. Only pages whose name says "admin" are expected to have a role check.

**"Why trust a decorator just because it is called admin-something?"**
Reading inside every home-made decorator is much harder and would still be guessing. Trusting the name is simple and explainable; the cost (a fake `@admin_check`) is written down as a limit and shows up in our own test corpus as a miss.

**"Why is it always High?"**
An admin page usually changes settings or shows everyone's data, and the attacker only needs an ordinary account, which most apps let anyone create.

**"Is it proven?"**
No. It is a suspect (Unconfirmed). FYP-2 proves it by logging in as a normal test user and opening the page.

---

## Words used here

- **Authentication**: proving who you are (logging in).
- **Authorisation**: deciding what you are allowed to do (roles, permissions).
- **Role**: a group a user belongs to, such as `admin` or `user`, usually stored in the users table or the session.
- **Decorator**: a line starting with `@` above a function.
- **Blueprint**: a group of Flask routes, often with a shared path prefix and shared hooks.
- **`before_request` hook**: a function Flask runs before every route of its app or Blueprint.
- **Turn the visitor away**: redirect, abort, raise, or answer with 401/403, so the page is not shown.
