# Midterm results: SecureFlow on the test corpus

First run on 2026-10-28, updated on 2026-10-29 after the public content rule, with `python engine/score.py corpus/`, on Maheen's five apps (`corpus/README.md`).
Every finding is **Unconfirmed**: it comes from reading the code only.

## How to read the table
- **Real problems**: routes in `should_flag` with a problem the midterm engine looks for (a missing login check).
- **Found** (true positive): a real problem the engine flagged.
- **Missed** (false negative): a real problem the engine did not flag.
- **False alarm** (false positive): a flagged route that is not a real problem.
- **Known limitation**: a flagged route that is not a real problem but that the code-only scan is *expected* to flag, because of a documented limit (a public page that reads the database, `docs/03-detection-rules.md` part 4). Listed under `known_limitations` in the ground truth, reported on its own line, not counted as a false alarm.
- **Precision** = found / (found + false alarms): how many flags were right. **Recall** = found / (found + missed): how many real problems were flagged.
- **Not checked yet**: real problems of a kind the midterm engine does not look for (role checks, ownership checks). They are planned for later and are not counted as missed.

A finding matches a ground truth entry when the `url_path` is equal and, if the entry lists `http_methods`, the route shares one of them.

## Results (current engine)
With the public content rule (`docs/03-detection-rules.md`, part 6). Two database routes were added to the corpus for this work: `GET /catalog` in app 1 (public by design, a known limitation) and `GET /users` in app 4 (a real missing-login problem).

| App | Real problems | Found | Missed | False alarms | Not checked yet |
|---|---|---|---|---|---|
| app_01_ecommerce | 2 | 2 | 0 | 0 | 0 |
| app_02_admin_cms | 0 | 0 | 0 | 0 | 1 |
| app_03_idor | 0 | 0 | 0 | 0 | 1 |
| app_04_blog | 2 | 2 | 0 | 0 | 0 |
| app_05_safe_control | 0 | 0 | 0 | 0 | 0 |
| **Total** | **4** | **4** | **0** | **0** | **2** |

Known limitations (flagged as expected, not counted as false alarms): 1
Precision: 1.00 (4/4), recall: 1.00 (4/4)

- The two old false alarms, `GET /products` (app 1) and `GET /public/info` (app 5), are gone. Both only return a fixed text, so they are now public content and appear in `routes` with `public_content:static_response`.
- No real problem was lost: all 4 missing-login routes are still flagged, including the new `/users`.
- Stage 3 (severity signals, part 7) changes no counts, only severities. In the corpus, `GET /users` (app 4) is High because of the privileged word `users`; no corpus group has enough protected routes for the neighbour signal.
- `GET /catalog` is still flagged, as expected: it reads the database, and the code-only scan cannot tell that the `products` table belongs to no user. FYP-2 will resolve it by looking at the response (`docs/08-verification-design.md`).

## Before and after: the public content rule

| Engine and corpus | Found | Missed | False alarms | Known limitations | Precision | Recall |
|---|---|---|---|---|---|---|
| Step 6 engine, original corpus | 3 | 0 | 2 | (none listed) | 0.60 (3/5) | 1.00 (3/3) |
| Step 6 engine, corpus with the 2 new routes | 4 | 0 | 2 | 1 | 0.67 (4/6) | 1.00 (4/4) |
| With the public content rule, same corpus | 4 | 0 | 0 | 1 | 1.00 (4/4) | 1.00 (4/4) |

A caution: the corpus is small (5 apps), and the rule was written knowing which two routes were false alarms. The rule is based on a general reason (the handler uses nothing about the visitor and returns a fixed text), not on these routes' names, and 21 negative cases in `engine/tests/fixtures/content_app/` check that it stays strict. It should still be checked on new apps.

## Results with the Step 6 engine
Inline session rule 2d tightened in Step 6 (see "Before and after: the inline session rule" below). Original corpus, before the public content rule.

| App | Real problems | Found | Missed | False alarms | Not checked yet |
|---|---|---|---|---|---|
| app_01_ecommerce | 2 | 2 | 0 | 1 | 0 |
| app_02_admin_cms | 0 | 0 | 0 | 0 | 1 |
| app_03_idor | 0 | 0 | 0 | 0 | 1 |
| app_04_blog | 1 | 1 | 0 | 0 | 0 |
| app_05_safe_control | 0 | 0 | 0 | 1 | 0 |
| **Total** | **3** | **3** | **0** | **2** | **2** |

### Details (Step 6 engine)

#### app_01_ecommerce
- False alarm: `GET /products (app.py:112)`, public by design

#### app_02_admin_cms
No missing-login problems to find, and no false alarms.
- Not checked yet: `GET /admin/dashboard, missing_role_check`

#### app_03_idor
No missing-login problems to find, and no false alarms.
- Not checked yet: `GET /user/profile, missing_ownership_check`

#### app_04_blog
All real problems found, no false alarms.

#### app_05_safe_control
- False alarm: `GET /public/info (app.py:85)`, public by design

## What the Step 6 results showed
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
