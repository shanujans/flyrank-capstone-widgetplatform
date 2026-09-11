# BUILDLOG.md

Per the brief's ground rules: "AI-assisted building is encouraged — and
owned. Use AI tools freely, but keep BUILDLOG.md honest... 'The AI wrote it'
is not an answer." This log is written straight, without inflating the
human's involvement or hiding the AI's.

---

## Session 1 — initial build (Claude, in claude.ai)

**What AI did:** Wrote the entire first version of this repo — every file
under `app/`, the test suite, the widget bundle, the customer-site test
page, the seed script, and all the docs (`DESIGN.md`, `README.md`,
`EVIDENCE.md`, this file). Also ran the app and the test suite directly (in
a sandboxed container), fixed real bugs it hit along the way, and captured
live curl output as evidence rather than describing what it expected to
happen.

**Where AI got things wrong the first time, and had to fix them:**
- `pydantic.EmailStr` failed at import time until `email-validator` was
  installed explicitly — `pydantic[email]` isn't pulled in by
  `pip install pydantic` alone. Fixed by adding the dependency and pinning
  it in `requirements.txt`.
- The honeypot "fake success" response in `app/routers/public.py`
  originally referenced `datetime.utcnow()` without importing `timezone`
  after a later refactor — a real `NameError` caught by the test suite
  (`test_probe6_honeypot_filled_is_silently_dropped` failed), not by
  guessing. Fixed by adding the missing import.
- First pass used `passlib[bcrypt]` for password hashing; recent `bcrypt`
  releases (>=4.1) don't work with passlib's bcrypt backend as of this
  writing (a known upstream compatibility gap). Switched to calling
  `bcrypt` directly in `app/security.py` instead of debugging passlib's
  wrapper — simpler and one fewer dependency.
- Initial draft used `@app.on_event("startup")` and
  `class Config: from_attributes = True`, both of which are deprecated in
  the installed FastAPI/Pydantic versions. Rewritten to use a `lifespan`
  context manager and `ConfigDict(...)` respectively, once the deprecation
  warnings surfaced in the test run.

**What was deliberately simplified (see DESIGN.md §6 and README
"Limitations" for the reasoning, not just the decision):**
- Rate limiting is in-memory and single-process — explicitly out of scope
  for this capstone to make distributed (Redis-backed).
- Auth is minimal (email + bcrypt + JWT, no refresh/reset flow) — tenant
  isolation is what's graded, not auth sophistication.
- Geo enrichment defaults to a mocked, deterministic mode rather than
  hitting real providers on every request/test run, per the brief's own
  instruction ("mock the geo providers when you prove the fallback").

**What a human (you) should still do, and why "the AI wrote it" won't cut
it in review:**
- Read `DESIGN.md` §5 (the hardened submission path) and be able to walk
  through it step-by-step from memory — an evaluator will pick 2-3 lines
  from `app/routers/public.py` and ask you to explain them.
- Actually run the cross-origin demo yourself (README "Seeing the widget
  actually render cross-origin") rather than trusting the curl transcript
  — a real browser round trip (with devtools open on the Network tab) will
  teach you more about CORS preflight than reading about it will.
- If you extend this (stretch goals, a real frontend, deploying it
  somewhere), that work is yours — log it below in the same honest format:
  what you asked an AI tool for, what it got wrong, what you changed and
  why.

---

## Template for your own entries as you continue building

```
## Session N — <date> — <what you were working on>

**What AI helped with:**
-

**Where it was wrong, or you disagreed and changed it:**
-

**What you wrote or debugged yourself:**
-
```
