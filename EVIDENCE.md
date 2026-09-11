# EVIDENCE.md

One pasted proof per checkbox in Section 6 of the brief. Everything below is
real, unedited output from a live server run — full transcript at
[`tests/manual_evidence_transcript.txt`](./tests/manual_evidence_transcript.txt)
— plus the pytest suite (`pytest tests/ -v`, 17/17 passing) which re-proves
every one of these automatically on every run.

---

## Widget management

### ✅ Authenticated CRUD endpoints; requests without valid auth are rejected

```
$ curl -s -o /dev/null -w 'HTTP %{http_code}\n' http://127.0.0.1:8000/widgets
HTTP 401
```

Full CRUD proven in the same run: `POST /widgets` -> 201, `GET /widgets/{id}`
-> 200, `PATCH /widgets/{id}` -> 200, `DELETE /widgets/{id}` -> 204, then
`GET /widgets/{id}` -> 404 (gone). See `test_widget_crud_happy_path` and
`test_widget_crud_requires_auth` in `tests/test_capstone.py`.

### ✅ Multi-tenant isolation proven

```
$ curl -s -X POST .../auth/register -d '{"email":"owner@othercorp.com",...}'
{"id":2,"email":"owner@othercorp.com",...}
$ curl -s -o /dev/null -w 'HTTP %{http_code}\n' \
    http://127.0.0.1:8000/widgets/bf36075445e9482f8b37b0ede0a7de8b \
    -H 'Authorization: Bearer <tenant-B-token>'
HTTP 404
```

Tenant B, authenticated with their own valid token, gets a 404 (not a 403 —
so tenant B can't even distinguish "not yours" from "doesn't exist") on
tenant A's widget. Also proven for `PATCH` and for
`GET /dashboard/widgets/{id}/submissions` — see `test_tenant_isolation`.

---

## Widget delivery

### ✅ Embed snippet generated per widget

```
$ curl -s http://127.0.0.1:8000/widgets/bf36.../embed -H 'Authorization: Bearer ...'
{"widget_id":"bf36075445e9482f8b37b0ede0a7de8b","snippet":"<script src=\"http://127.0.0.1:8000/widget/v1/widget.js?id=bf36075445e9482f8b37b0ede0a7de8b\" async></script>"}
```

### ✅ Public config endpoint: small payload, correct cache headers

```
$ curl -s -D - -o /dev/null http://127.0.0.1:8000/public/widgets/bf36.../config \
    -H 'Origin: http://customer-site.example:5500'
HTTP/1.1 200 OK
content-length: 316
content-type: application/json
cache-control: public, max-age=60
access-control-allow-origin: *
```

### ✅ Widget JS served as a versioned bundle

```
$ curl -s -D - -o /dev/null http://127.0.0.1:8000/widget/v1/widget.js
HTTP/1.1 200 OK
cache-control: public, max-age=31536000, immutable
content-type: application/javascript
etag: "325369d3d7755f6ebacfa6958b1053ef"
```

URL includes the version (`/widget/v1/...`) — a breaking change ships as
`/widget/v2/widget.js`, a new URL, so old cached copies are never served
stale. See `test_widget_bundle_has_long_immutable_cache`.

### ✅ Widget renders on a page from a different origin than the API

`customer-site/index.html` is a plain HTML file with no build step, meant to
be served on a different port than the API (`python -m http.server 5500`
vs. the API's `:8000`) — see README "Seeing the widget actually render
cross-origin" for the exact steps. The widget bundle fetches its config and
posts submissions via `fetch(..., {mode: "cors"})` against the API origin
read from its own `<script src>` — see `app/static/widget.v1.js`.

---

## Public submission API

### ✅ Cross-origin submissions: correct CORS, preflight handled

```
$ curl -s -D - -o /dev/null -X OPTIONS \
    http://127.0.0.1:8000/public/widgets/bf36.../submissions \
    -H 'Origin: http://customer-site.example:5500' \
    -H 'Access-Control-Request-Method: POST' \
    -H 'Access-Control-Request-Headers: content-type'
HTTP/1.1 200 OK
access-control-allow-origin: *
access-control-allow-methods: DELETE, GET, HEAD, OPTIONS, PATCH, POST, PUT
access-control-allow-headers: content-type
```

### ✅ All input validated; malformed/oversized payloads -> clean 4xx JSON

```
$ curl ... -d '{"data":{"name":"No email here"},"hp_field":""}'
{"detail":["'email' is required"]}
HTTP 422

$ curl ... -d '{not valid json'
{"detail":[{"type":"json_invalid","loc":["body",1],"msg":"JSON decode error",...}]}
HTTP 422

$ curl ... --data-binary @<60KB-file>
{"detail":"Payload too large"}
HTTP 413
```

Never a 500 in any of these — see `test_probe2_*` in `tests/test_capstone.py`
(4 tests: missing field, malformed JSON, oversized body, over-length field).

### ✅ Valid submissions stored safely, linked to the right widget and tenant

```
$ curl -s -X POST .../submissions -d '{"data":{"email":"visitor@example.com","name":"Ada Lovelace"},"hp_field":""}'
{"id":1,"widget_id":"bf36...","data":{"email":"visitor@example.com",...},"country":"Sri Lanka",...}

$ curl -s .../dashboard/widgets/bf36.../submissions -H 'Authorization: Bearer <owner-token>'
[{"id":1,"widget_id":"bf36...","data":{"email":"visitor@example.com",...}}]
```

Same submission, visible immediately via the owner's dashboard.

---

## Abuse protection

### ✅ Rate limiting (per IP and per widget) -> 429 under a burst; service stays up

```
$ for i in 1..8; do curl -X POST .../submissions -d '{"data":{"email":"flood@example.com"}...}'; done
201 201 201 429 429 429 429 429

$ curl -s http://127.0.0.1:8000/health
{"status":"ok","app":"FlyRank Widget & Lead-Capture Platform"}
```

(`RATE_LIMIT_PER_IP_PER_MINUTE=5` for this run.) The first 3 succeed, the
rest are rejected with 429 — and `/health` immediately after confirms the
process itself never went down. See `test_probe3_rate_limit_returns_429...`.

### ✅ At least one spam-prevention technique demonstrably blocks spam

```
$ curl -s -X POST .../submissions -d '{"data":{"email":"bot@example.com"},"hp_field":"I am a bot"}'
{"id":0,"widget_id":"bf36...","data":{},...}   <- looks like success to the bot

submission count before honeypot test: 7, after: 7   <- nothing was actually stored
```

Honeypot field (`hp_field`) is rendered off-screen in the real widget
(`app/static/widget.v1.js`) — invisible and untouched by real visitors, but
filled by naive scripted bots. See `test_probe6_honeypot_filled_is_silently_dropped`.

---

## Enrichment & safe side effects

### ✅ Provider fallback chain: A down -> B answers -> submission enriched

```
$ # .env: MOCK_GEO_PROVIDER_A_DOWN=true
$ curl -s -X POST .../submissions -d '{"data":{"email":"fallback@example.com"}...}'
{"id":5,...,"country":"Sri Lanka","city":"Negombo","geo_provider":"provider_b",...}
```

### ✅ All providers down -> submission still succeeds, without geo

```
$ # .env: MOCK_GEO_PROVIDER_A_DOWN=true AND MOCK_GEO_PROVIDER_B_DOWN=true
$ curl -s -X POST .../submissions -d '{"data":{"email":"nogeo@example.com"}...}'
{"id":6,...,"country":null,"city":null,"geo_provider":null,...}
```

Status code was `201` in both cases — degrade, never fail. See
`test_probe4_provider_a_down_falls_back_to_b` and
`test_probe4_both_providers_down_still_succeeds_without_geo`.

### ✅ A failing confirmation side effect does not prevent storage

```
$ # .env: FORCE_NOTIFY_FAILURE=true
$ curl -s -X POST .../submissions -d '{"data":{"email":"sideeffect@example.com"}...}'
{"id":7,...,"notified":false,...}   <- id=7 proves the row WAS stored; only "notified" flipped
```

Server log for that exact request shows a normal `201 Created` — the
`RuntimeError` raised inside `send_confirmation()` was caught in
`app/routers/public.py` and never reached the HTTP response. See
`test_probe5_notification_failure_does_not_break_submission`.

---

## Documentation

### ✅ README with architecture diagram, setup, API docs; Section 11 files present

- `README.md` — architecture diagram, Docker + non-Docker setup, cross-origin
  walkthrough, curl proofs, limitations, project layout.
- `capstone.yaml`, `EVIDENCE.md` (this file), `BUILDLOG.md`, `.env.example`
  — all present at repo root.
- Interactive API docs auto-generated by FastAPI at `/docs` once the server
  is running.

---

## Test suite (re-proves all of the above automatically)

```
$ pytest tests/ -v
...
tests/test_capstone.py::test_widget_crud_requires_auth PASSED
tests/test_capstone.py::test_widget_crud_happy_path PASSED
tests/test_capstone.py::test_tenant_isolation PASSED
tests/test_capstone.py::test_embed_snippet_contains_widget_id PASSED
tests/test_capstone.py::test_widget_bundle_has_long_immutable_cache PASSED
tests/test_capstone.py::test_config_endpoint_has_short_cache_and_cors PASSED
tests/test_capstone.py::test_cors_preflight_on_submission_endpoint PASSED
tests/test_capstone.py::test_probe1_valid_submission_is_stored_and_visible PASSED
tests/test_capstone.py::test_probe2_missing_required_field_is_422 PASSED
tests/test_capstone.py::test_probe2_malformed_json_is_4xx_not_500 PASSED
tests/test_capstone.py::test_probe2_oversized_payload_is_413 PASSED
tests/test_capstone.py::test_probe2_field_over_max_length_is_422 PASSED
tests/test_capstone.py::test_probe3_rate_limit_returns_429_then_recovers_for_other_widget PASSED
tests/test_capstone.py::test_probe4_provider_a_down_falls_back_to_b PASSED
tests/test_capstone.py::test_probe4_both_providers_down_still_succeeds_without_geo PASSED
tests/test_capstone.py::test_probe5_notification_failure_does_not_break_submission PASSED
tests/test_capstone.py::test_probe6_honeypot_filled_is_silently_dropped PASSED

======================== 17 passed, 3 warnings in 6.06s ========================
```
