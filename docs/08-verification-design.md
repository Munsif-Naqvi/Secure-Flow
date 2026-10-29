# Verification design (FYP-2)

**Status: design only. Nothing in this document is built in FYP-1, except layer 2.**
It records what we agreed about how SecureFlow will later decide whether an open route is really a problem.

## Why this is needed
The midterm engine flags every route that has no login check and is not on the public allowlist. Many such routes are public on purpose (a product list, an info page). A list of paths does not scale to apps with hundreds of routes, so we look at what a route *does*, not what it is called.

Two ideas guide the design:
- **Reachable is not the same as vulnerable.** A route that anyone can open is only a problem if it gives out something private or lets someone change data.
- **Confirmed means impact was proven.** A finding is *Confirmed* only when a live attack demonstrably had impact: private data came back, or existing data changed. Being reachable without login is not enough.

## The five layers

1. **Labels.** Every result gets an honest label.
   - *Confirmed*: a live test proved impact.
   - *Open route, is this intended?*: the route can be reached without login, but no test showed harm. The developer is asked, not accused.
   - In FYP-1 every result is *Unconfirmed*.

2. **Static identity check (built now, in FYP-1).** Reading the code, the engine sets aside routes that clearly ignore who the caller is and return fixed, harmless content ("public content", see `docs/03-detection-rules.md`). It also raises the severity of routes whose names suggest sensitive actions, or whose neighbours are protected. These rules are careful: when unsure, the route is still flagged.

3. **Differential test in the sandbox.** The sandbox calls each route three times: as an anonymous visitor, as an ordinary test user (User A), and as an admin test user. The responses are compared (logic below).

4. **Check what the response contains.** The sandbox looks at the content, not only the status code:
   - known private values planted in or read from the database copy (for example User B's email address);
   - sensitive field names (for example `password`, `token`, `ssn`);
   - for routes that change data: whether existing rows owned by a user were changed or deleted.

5. **Developer decisions.** The developer can answer "yes, this route is meant to be public". The answer is saved per project against the finding's `finding_match_key`, so the route is not asked about again. Bulk options (for example "every route in this Blueprint is public") keep the review list short.

## Layer 3 logic in two steps

**Step 1: is the anonymous visitor turned away?**
If the anonymous call gets 401, 403, or a redirect to the login page, the route is protected. Done.

**Step 2: the anonymous visitor got a normal 200. Compare the responses by identity.**
- **The responses differ between identities** (anonymous, User A, admin). Then the route uses the caller's identity, so login matters for it. If the anonymous visitor still got content, login is not enforced. That is **confirmed**.
- **The responses are identical for everyone.** Then the route ignores identity. The responses alone cannot say whether the route is public on purpose or is an open privileged route (an unprotected admin page also shows the same data to everyone). The verdict comes from **layer 4** (does the content include private values or sensitive fields, did data change) and from **privilege signals** (admin-style path or role names, use of admin tables, protected neighbouring routes).

Layer 3 *sorts* routes. It does not decide the identical case on its own.

## The ownership-check rule is separate
"User A can read User B's record" (missing ownership check, also called IDOR) is a separate detection rule, not one of the five layers. It shares the same sandbox, test accounts and database copy. Static detection of it comes in the later FYP-1 work; live confirmation comes in FYP-2.

## Limits
- The tool cannot read the developer's intent. It can only gather evidence.
- A route that is public by mistake but only exposes harmless-looking fields can be missed.
- The static rules (layer 2) are heuristics: rules of thumb, not proofs. They are written to miss as little as possible, at the price of some false alarms.
