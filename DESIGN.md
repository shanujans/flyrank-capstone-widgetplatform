# DESIGN.md — Embeddable Widget & Lead-Capture Platform

Phase 1 deliverable (Section 8 of the capstone brief): problem, data model,
API surface, layer sketch, and one explicit non-goal.

## 1. Problem

Let a customer configure a widget (signup form / CTA / popover) through an
authenticated admin API, then embed it on **any** website with one
`<script>` tag. The widget must render, capture visitor submissions across
origins the platform doesn't control, and survive the abuse and unreliability
that come with a public internet-facing endpoint — without ever losing a
valid submission and without ever leaking one tenant's data to another.

Three actors, three trust levels:
- **Widget owner** (authenticated) — manages widgets, views submissions.
- **Customer website** (any origin, unauthenticated) — loads the script and
  config; this is a *read-only* public surface.
- **Website visitor** (any origin, unauthenticated, untrusted) — submits
  form data; this is the surface that must assume hostile input.

## 2. Data model

```
Tenant
  id (PK)
  email (unique)
  hashed_password
  created_at

Widget
  id (PK, random hex — not sequential, so ids aren't enumerable)
  tenant_id (FK -> Tenant.id, indexed)
  type            # signup_form | cta | popover
  title
  description
  button_text
  fields          # JSON: [{name, label, type, required}, ...]
  display_options # JSON: {position, delay_seconds, ...}
  created_at, updated_at

Submission
  id (PK)
  widget_id (FK -> Widget.id, indexed)
  tenant_id (FK -> Tenant.id, indexed — denormalized on purpose, see below)
  data            # JSON: the visitor's validated field values
  ip_address
  country, city, geo_provider   # nullable — enrichment is best-effort
  notified        # bool — did the confirmation side effect succeed?
  created_at (indexed — dashboard queries filter/sort on this)
```

**Why `tenant_id` is denormalized onto `Submission`:** every tenant-isolation
check and every dashboard query filters on `tenant_id` directly, with no
join through `Widget` required. This means isolation is enforced even if a
`widget_id` were somehow guessed — the row still won't appear under the
wrong tenant's dashboard, and a stale/deleted widget can't strand orphaned
submissions the isolation logic forgot to filter.

**Why widget ids are random hex, not auto-increment ints:** the widget id
appears in a public `<script src="...?id=...">` tag on someone else's
website — it's not a secret, but it shouldn't be trivially enumerable
(`?id=1`, `?id=2`, ...) either.

## 3. The three request paths (API surface)

```
Widget owner (Bearer JWT)
  POST   /auth/register            create a tenant
  POST   /auth/login               get a token
  POST   /widgets                  create a widget
  GET    /widgets                  list own widgets
  GET    /widgets/{id}             read own widget       -> 404 if not owned
  PATCH  /widgets/{id}             update own widget      -> 404 if not owned
  DELETE /widgets/{id}             delete own widget       -> 404 if not owned
  GET    /widgets/{id}/embed       the <script> snippet
  GET    /dashboard/overview       counts across all own widgets
  GET    /dashboard/widgets/{id}/submissions
  GET    /dashboard/widgets/{id}/stats

Customer website (public, cached, CORS: *)
  GET    /widget/{version}/widget.js         long cache, immutable
  GET    /public/widgets/{id}/config         short cache

Website visitor (public, CORS: *, hardened)
  POST   /public/widgets/{id}/submissions
```

A tenant's own widget/submission endpoints return **404, not 403**, when the
resource belongs to someone else — this is deliberate: it means tenant A
can't even distinguish "doesn't exist" from "not yours," so there's no way
to enumerate tenant B's widget ids by probing for a 403-vs-404 signal.

## 4. Layers

```
HTTP layer      FastAPI routers (auth / widgets / public / dashboard)
                 -> boundary validation (Pydantic schemas), status codes, CORS
Logic layer      rate limiting, spam check, geo enrichment + fallback chain,
                 notification side effect, tenant-ownership checks
Data layer       SQLAlchemy models + session, SQLite (swappable to Postgres
                 via DATABASE_URL with no code change)
```

Kept deliberately thin (3 layers, not 5) — the brief's own guidance (Section
7) is to prove the pattern, not build a framework. Each router file owns one
request path; `app/rate_limit.py`, `app/geo.py`, and `app/notify.py` are the
three "hardening" modules the submission path composes together.

## 5. The hardened submission path, in order

```
POST /public/widgets/{id}/submissions
  1. widget exists?                       no  -> 404
  2. body size under 50KB?                no  -> 413                (pre-parse, cheap)
  3. JSON well-formed + schema-valid?     no  -> 422                (Pydantic)
  4. rate limit: per-IP, then per-widget  no  -> 429 + Retry-After
  5. honeypot field filled?               yes -> fake 201, nothing stored
  6. required fields present?             no  -> 422 with field names
  7. geo enrich: provider A -> provider B -> none (never blocks)
  8. store submission
  9. confirmation side effect (try/except — failure never un-succeeds the row)
  -> 201 with the stored (possibly geo-enriched) submission
```

Steps 2–6 are cheap and ordered before anything touches the database or the
network, so a flood of garbage requests is rejected as early as possible.

## 6. Non-goal (explicit)

**Multi-instance / distributed rate limiting is out of scope.** The rate
limiter is a single-process, in-memory sliding window. It resets on restart
and doesn't share counters across multiple uvicorn workers or machines. For
this capstone's scope — a local, single-worker deployment — that's the right
trade-off; a real production deployment behind a load balancer would back
this with Redis (`INCR` + `EXPIRE`) instead. The interface
(`limiter.allow(key, limit, window)`) is intentionally small so that swap
wouldn't touch any call site. This is documented again in README.md under
"Limitations."
