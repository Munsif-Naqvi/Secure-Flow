# Midterm results: SecureFlow on the test corpus

Run on 2026-10-28 with `python engine/score.py corpus/`, on Maheen's five apps (`corpus/README.md`).
Every finding is **Unconfirmed**: it comes from reading the code only.

## How to read the table
- **Real problems**: routes in `should_flag` with a problem the midterm engine looks for (a missing login check).
- **Found** (true positive): a real problem the engine flagged.
- **Missed** (false negative): a real problem the engine did not flag.
- **False alarm** (false positive): a flagged route that is not a real problem.
- **Not checked yet**: real problems of a kind the midterm engine does not look for (role checks, ownership checks). They are planned for later and are not counted as missed.

A finding matches a ground truth entry when the `url_path` is equal and, if the entry lists `http_methods`, the route shares one of them.

## Results (current engine)
Inline session rule 2d tightened in Step 6 (see "Before and after" below).

| App | Real problems | Found | Missed | False alarms | Not checked yet |
|---|---|---|---|---|---|
| app_01_ecommerce | 2 | 2 | 0 | 1 | 0 |
| app_02_admin_cms | 0 | 0 | 0 | 0 | 1 |
| app_03_idor | 0 | 0 | 0 | 0 | 1 |
| app_04_blog | 1 | 1 | 0 | 0 | 0 |
| app_05_safe_control | 0 | 0 | 0 | 1 | 0 |
| **Total** | **3** | **3** | **0** | **2** | **2** |

## Details

### app_01_ecommerce
- False alarm: `GET /products (app.py:112)`, public by design

### app_02_admin_cms
No missing-login problems to find, and no false alarms.
- Not checked yet: `GET /admin/dashboard, missing_role_check`

### app_03_idor
No missing-login problems to find, and no false alarms.
- Not checked yet: `GET /user/profile, missing_ownership_check`

### app_04_blog
All real problems found, no false alarms.

### app_05_safe_control
- False alarm: `GET /public/info (app.py:85)`, public by design

## What the results show
**Found all 3 missing-login problems, with 2 false alarms.**

- **The two false alarms are public pages that are not on the public allowlist**: `/products` (app 1) and `/public/info` (app 5). This is the expected behaviour of the allowlist. Adding these paths to the allowlist only to improve this score would be tuning the engine to the test.
- **App 2 and app 3** have problems of other kinds (a missing role check, and an IDOR). Their routes are login-protected, so the engine rightly does not flag them as missing login.
- **App 4** is scored perfectly, and **app 5** (the fully protected app) has one false alarm.

## Before and after: the inline session rule
The first run used rule 2d as first written, which counted *any* read of a user key in `session` as a login check:

| App | Real problems | Found | Missed | False alarms | Not checked yet |
|---|---|---|---|---|---|
| app_01_ecommerce | 2 | 0 | 2 | 1 | 0 |
| app_02_admin_cms | 0 | 0 | 0 | 0 | 1 |
| app_03_idor | 0 | 0 | 0 | 0 | 1 |
| app_04_blog | 1 | 1 | 0 | 0 | 0 |
| app_05_safe_control | 0 | 0 | 0 | 1 | 0 |
| **Total** | **3** | **1** | **2** | **2** | **2** |

Both misses were in app 1. `/checkout` reads `session.get('user_id', 1)` to pick a default user, and `/orders` uses `if 'user_id' in session:` to choose which orders to show. Neither one stops a visitor who is not logged in, but both looked like a check to the rule.

The rule now counts a session check only inside an `if` whose branch turns the visitor away (a redirect, `abort(...)`, `raise`, or a 401/403 answer). The new tests are in `engine/tests/fixtures/session_app/`. One tiny_app route changed with it: `/account/me` only reads `session["user"]`, so it is now flagged.

Changing a rule after seeing the score can tune the engine to the test. Here the change follows a general reason (reading a value does not stop anyone), not the names of the corpus routes, and it should be checked again on new apps.

## Corpus coverage
`docs/07-test-corpus.md` lists what the five apps should cover between them. These are covered: public pages, `@login_required` (a custom decorator named `login_required`), unprotected state-changing and read-only routes, an inline session check.
These are not covered yet: a Blueprint with `url_prefix`, a `before_request` login check, `add_url_rule`, a token or `Authorization` header check, an f-string SQL query (stretch), and a file with a syntax error. The tiny app in `engine/tests/fixtures/tiny_app/` tests all of these, but it was written alongside the engine, so it does not measure the engine fairly.
