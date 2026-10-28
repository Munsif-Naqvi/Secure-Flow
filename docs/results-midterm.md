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

## Results
| App | Real problems | Found | Missed | False alarms | Not checked yet |
|---|---|---|---|---|---|
| app_01_ecommerce | 2 | 0 | 2 | 1 | 0 |
| app_02_admin_cms | 0 | 0 | 0 | 0 | 1 |
| app_03_idor | 0 | 0 | 0 | 0 | 1 |
| app_04_blog | 1 | 1 | 0 | 0 | 0 |
| app_05_safe_control | 0 | 0 | 0 | 1 | 0 |
| **Total** | **3** | **1** | **2** | **2** | **2** |

## Details

### app_01_ecommerce
- Missed: `GET,POST /checkout`
- Missed: `GET /orders`
- False alarm: `GET /products (app.py:112)`, public by design

### app_02_admin_cms
All real problems found, no false alarms.
- Not checked yet: `GET /admin/dashboard, missing_role_check`

### app_03_idor
All real problems found, no false alarms.
- Not checked yet: `GET /user/profile, missing_ownership_check`

### app_04_blog
All real problems found, no false alarms.

### app_05_safe_control
- False alarm: `GET /public/info (app.py:85)`, public by design

## What the results show
**Found 1 of 3 missing-login problems, with 2 false alarms.**

- **The two misses in app 1 come from the inline-check rule** (`docs/03-detection-rules.md`, part 2d). The rule counts any read of a user key in `session` as a login check. `/checkout` reads `session.get('user_id', 1)` to pick a default user, and `/orders` uses `if 'user_id' in session:` to choose which orders to show. Neither one stops a visitor who is not logged in, but both look like a check to the rule. A stricter rule would count a session check only when it leads to a redirect, an `abort(401/403)` or an error return. This needs a change to the rules document, so it has not been made yet.
- **The two false alarms are public pages that are not on the public allowlist**: `/products` (app 1) and `/public/info` (app 5). This is the expected behaviour of the allowlist. Adding these paths to the allowlist only to improve this score would be tuning the engine to the test.
- **App 2 and app 3** have problems of other kinds (a missing role check, and an IDOR). Their routes are login-protected, so the engine rightly does not flag them as missing login.
- **App 4** is scored perfectly, and **app 5** (the fully protected app) has one false alarm.

## Corpus coverage
`docs/07-test-corpus.md` lists what the five apps should cover between them. These are covered: public pages, `@login_required` (a custom decorator named `login_required`), unprotected state-changing and read-only routes, an inline session check.
These are not covered yet: a Blueprint with `url_prefix`, a `before_request` login check, `add_url_rule`, a token or `Authorization` header check, an f-string SQL query (stretch), and a file with a syntax error. The tiny app in `engine/tests/fixtures/tiny_app/` tests all of these, but it was written alongside the engine, so it does not measure the engine fairly.
