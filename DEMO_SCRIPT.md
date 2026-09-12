# FL-09 Demo Video Script (3–5 Minutes)

**Target length:** 3:30–4:30  
**Format:** Live terminal + browser recording, no slides  
**Narration style:** Honest, technical, slightly accountable — "here's what it does, here's where it's weak"

---

## Scene 1: Repo Overview (0:00–0:30)

**Visual:** Terminal at repo root, `ls -la`

**Narration:**
> "This is the FlyRank capstone — an embeddable widget and lead-capture platform. Stack is Python, FastAPI, SQLite. The brief: let a customer configure a widget, hand them one `<script>` tag, and safely catch everything the public internet throws back. I'll show you the architecture, run the tests, prove the cross-origin widget render, and walk through one limitation on camera."

---

## Scene 2: Architecture Walkthrough (0:30–1:15)

**Visual:** `cat README_FL09.md` (architecture diagram section)

**Narration:**
> "Three actors. Widget owner authenticates with JWT, manages widgets via CRUD API — tenant-isolated, so owner B can't even see owner A's widgets. Customer website drops in one script tag — that hits the public config endpoint, cached 60 seconds, CORS wildcard. Website visitor submits the form — that's the hardened submission path: body size guard, JSON validation, rate limiting per IP and per widget, honeypot spam trap, geo enrichment with a two-provider fallback chain, then storage. A confirmation side effect runs after — if it fails, we log it but never block the 201. Owner pulls submissions and stats via the dashboard API."

---

## Scene 3: Test Suite — All Green (1:15–1:45)

**Visual:** `pytest tests/ -v` running

**Narration:**
> "17 tests, all passing. Every acceptance probe from the brief is automated: valid submission, four flavors of bad input, rate limit burst, geo fallback single and double failure, notification failure resilience, honeypot. Plus tenant isolation, widget CRUD, CORS preflight, cache headers. The test suite is the contract — if it passes, the capstone requirements are met."

---

## Scene 4: Cross-Origin Widget Demo (1:45–3:00)

**Visual:** Split screen — Terminal 1: API on :8000, Terminal 2: seed script output, Terminal 3: customer-site on :5500, Browser: http://127.0.0.1:5500/index.html with devtools Network tab open

**Narration (while doing it live):**
> "Start the API. Run the seed script — gives me a demo login and a widget ID. Copy that widget ID into the customer-site HTML. Serve customer-site on port 5500 — different origin than the API on 8000. Open in browser. There's the widget, rendered from the API's static bundle. Fill in an email, hit Submit. Watch the Network tab — there's the CORS preflight (OPTIONS), then the POST to /public/widgets/:id/submissions, 201 Created, response includes geo enrichment. Back in the owner's dashboard — there's the submission, linked to the right tenant. That's the whole loop working cross-origin, exactly like a real customer site."

---

## Scene 5: One Design Decision — In-Memory Rate Limiting (3:00–3:45)

**Visual:** `cat app/rate_limit.py` (show the sliding window dict)

**Narration:**
> "One design decision I want to call out: rate limiting is in-memory, single-process. It's a Python dict keyed by IP and widget ID, sliding window. The brief explicitly called this out as a non-goal — 'distributed rate limiting is out of scope.' I agreed. For a local capstone, this is fine. For a real deployment, you'd back it with Redis so multiple workers share state and limits survive restarts. I didn't reach for Redis because the brief said don't, and because the grade lives in the backend hardening — not the infra. But I'll be honest: if this went to prod tomorrow, this is the first thing I'd swap."

---

## Scene 6: One Limitation — Geo Mocking by Default (3:45–4:30)

**Visual:** `.env` file showing `MOCK_GEO=true`, then flip to `false` and show a real request

**Narration:**
> "One limitation: geo enrichment defaults to mocked. `MOCK_GEO=true` in `.env` means the fallback chain is deterministic for tests — provider A returns Sri Lanka/Colombo, provider B returns Sri Lanka/Negombo. That's great for grading, but it's not real geo. If you flip `MOCK_GEO=false`, it hits ip-api.com and ipapi.co — free tiers, 45 req/min and ~1,000/day. I ran it live once, it works, but you hit rate limits fast. The fallback chain logic is real — I proved both providers down still succeeds without geo — but the enrichment data itself is mocked by default. That's a deliberate trade-off: deterministic tests over real data in CI."

---

## Scene 7: AI Transparency Line (4:30–5:00)

**Visual:** `cat BUILDLOG.md` (first session summary)

**Narration:**
> "Framework note — transparency diligence. This project was built with AI assistance. The initial repo — every file under app/, tests/, scripts/, customer-site/, all the docs — was written by Claude in one session. But: I ran the tests, fixed the bugs it missed (missing imports, deprecation warnings, bcrypt compatibility), and I ran the cross-origin demo myself in a real browser. The AI wrote the first draft; I verified the behavior. That's the honest line."

---

## Scene 8: Wrap (5:00–5:15)

**Visual:** Repo root, GitHub URL

**Narration:**
> "Repo is at github.com/shanujans/flyrank-capstone-widgetplatform. README has the full setup, curl proofs, limitations, and the AI transparency breakdown. Thanks for watching."

---

## Recording Checklist

- [ ] Terminal font size readable (16pt+)
- [ ] Browser devtools Network tab visible
- [ ] No dead air — narrate while commands run
- [ ] Show the actual curl output, not just "it works"
- [ ] Pause on the limitation — don't rush past it
- [ ] End with the GitHub URL on screen for 3 seconds