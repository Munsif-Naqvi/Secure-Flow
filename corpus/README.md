# Test corpus

Small Flask apps with known problems and a `ground_truth.json` each, used to test and score the engine.
Folder layout and what each app should contain: see `docs/07-test-corpus.md`. Score them with `python engine/score.py corpus/`.

## Source
The five apps were written by Maheen Arshad for this project, in
[Maheen-12/SecureFlow-Authentication-Sample-Apps](https://github.com/Maheen-12/SecureFlow-Authentication-Sample-Apps)
(commit `fa0972e`). Each `app.py` was copied unchanged; its folder was renamed to the `app_NN_<name>` layout.

**Later additions (by SecureFlow, not by Maheen).** Two database routes were added for the "reduce false missing-login flags" work. Each is marked with a comment in the app:
- `app_01_ecommerce`: `GET /catalog` and a `products` table. It is public by design but reads the database, so the code-only scan still flags it. It is listed under `known_limitations`.
- `app_04_blog`: `GET /users`, with no login check, lists every account from the users table. It is listed under `should_flag`.

| Folder | Original | What it tests |
|---|---|---|
| `app_01_ecommerce` | App 1 | Checkout and order history with no login check |
| `app_02_admin_cms` | App 2 | Admin page that checks login but not the role |
| `app_03_idor` | App 3 | Profile page that does not check the profile belongs to the user (IDOR) |
| `app_04_blog` | App 4 | Delete route with no login check |
| `app_05_safe_control` | App 5 | Fully protected app, to count false alarms |

## Ground truth
Each `ground_truth.json` was written from the `VULNERABLE ROUTE` and `SAFE ROUTE` comments in the app.
`/products` in app 1 is not marked either way; it is listed as public because it shows a product list. Maheen should confirm this.
`known_limitations` lists routes that are not real problems but that the code-only scan is expected to flag anyway (see `docs/03-detection-rules.md`, part 4). The scorer reports them on their own line, not as false alarms.
The role check (app 2) and ownership check (app 3) problems are not checked by the midterm engine, which only looks for missing login checks.
