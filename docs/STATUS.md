# ctiq — Project Status

Living source of truth for what's built, what's in flight, and how to deploy it.
Maintained in the repo (versioned) because the product-engineering skill's backlog is a
read-only cache that doesn't persist across sessions.

**Last updated:** 2026-06-30

---

## Snapshot

A clinical-trial intelligence platform on public ClinicalTrials.gov data. Live on a
Hetzner VM (Docker Compose). Two surfaces:

- **Public free tier** (no account): semantic trial search, trial detail, side-by-side
  compare.
- **Authed tier** (the product): role-aware dashboard, saved trials, saved landscapes +
  monitoring, eligibility matching, and **portfolio screening** (site-payer wedge). New
  features go here; the public surface is the acquisition funnel.

Personas: **Patient** (free funnel + future AI assistant), **Clinician** (Pro tier),
**Analyst/Competitor** (Intelligence tier — the revenue engine), **Admin** (internal).

**Go-to-market direction (2026-06-30):** the first paying customer is the **trial site /
network**, not the individual clinician — enrollment is revenue, and the coordinator who screens
patients is the user. This flips the clinician product from "patient → all of CT.gov" to "**my
open trials → is this patient eligible?**" The eligibility matcher + explainability is the trust
layer every version of that needs; the site wedge points it at a payer. See ROADMAP "Site-payer wedge".

---

## Shipped

### Auth
- **Login by email** — `username` removed from the User model and every auth flow
  (schema, Zod, GraphQL inputs, api-core, web forms, JWT). JWT carries `email` + `role`.
  Migration: `20260622000000_user_remove_username`.
- **`me` query + role-aware UI** — first guarded GraphQL query (`@UseGuards(GqlAuthGuard)`
  + `@CurrentUser()` decorator), re-reads the user from the DB. `User` type + `Role` enum
  in `@repo/graphql-types`. Web: `getCurrentUser` (RSC-safe), `roleLabel`, `UserBadge` in
  the dashboard header.

### Public free tier (Tier 1 clinical features)
- **Recruitment-status fix** — open-enrolling trials shown by default; non-actionable
  (completed/terminated/…) collapsed behind a toggle. `lib/trial-status.ts`.
- **Study-rigor badges** — "Randomized · Double-blind · Parallel" on trial detail.
  `lib/trial-rigor.ts`.
- **Side-by-side compare** — URL-driven `/compare?ids=…`, attribute-row grid; selection
  via checkboxes + a sticky "Compare (N)" bar in the results list. `lib/compare-ids.ts`.
- **Age fidelity** — `min_age_raw`/`max_age_raw` threaded end-to-end (ctiq-db → inference
  → api-core GraphQL → web) so age shows CT.gov's exact string ("1 Month – 18 Years")
  instead of a parsed float; `formatAgeYears` is the fallback.

### Authed tier
- **Saved trials / watchlist** — first authed-write feature. `SavedTrial` user-domain
  table (keyed by NCT id, no cross-ORM FK), `saveTrial`/`unsaveTrial`/`savedTrials`,
  `SaveTrialButton` on the dashboard detail page, `/dashboard/saved`. Migration:
  `20260622010000_saved_trials`.
- **Role-aware dashboard** — replaces the blank `/dashboard`. Greeting from `me`, an
  "Ask CTIQ" bar (→ search; the future LLM/agent entry point), live saved-trials count,
  role-specific cards, an activity-feed scaffold (the future agent surface).
- **Saved landscapes + on-view monitoring** (Analyst CI core, v1) — `Landscape`
  user-domain table holding a structured `spec` (JSON) + a `lastSeenNctIds` snapshot.
  `createLandscape`/`deleteLandscape`/`markLandscapeSeen`/`landscapes`. Landscape detail
  page re-runs the saved query, flags **New since last check**, and marks seen on view.
  Analyst dashboard surfaces real landscapes. Migration: `20260622020000_landscapes`.

### Observability — inference-service (2026-11-05)
- **JSON logs on stdout** (`core/set_logger.py`): replaces the text format + in-container rotating
  files. `severity`/`message` keys match api-core's pino output. Per-request `request_id`
  (ContextVar, `X-Request-ID` in/out) on every line. uvicorn's access log is disabled (it prints
  `?q=<search text>`); `ObservabilityMiddleware` logs method/route/status/duration without the
  query string.
- **Prometheus metrics** (`infra/observability/`, `/metrics`): HTTP rate/latency/errors by route
  template, embedding + vector-search latency, empty-result searches, planner cache hit/miss and
  LLM-vs-rule-based routing, LLM latency/outcome/**token usage**, LLM→rule-based fallbacks.
- **PHI hygiene:** removed raw query text from INFO/DEBUG log messages (now `query_len`, counts).
- **Collection stack** (opt-in `--profile monitoring`): Prometheus + Loki + Alloy + Grafana with a
  provisioned dashboard — see `infra/hetzner/README.md`. Not yet deployed.
- **Not yet:** api-core `/metrics` + forwarding its request id to inference (cross-service trace),
  ETL logging (still its own text `set_logger.py`), alert rules.

### LLM NL→query agent (OpenAI) — slices 1–2
- **What it is:** an LLM-based query planner behind the existing `QueryPlannerProtocol`
  port. `inference-service/.../planning/llm_planner.py` uses the **OpenAI Responses API**
  (`responses.parse`, model `gpt-5-mini`) with strict structured outputs (`CompiledQuery`:
  intent, semantic_query, phases, statuses, sponsor, conditions).
- **Live wiring (slice 2):** `build_query_planner(settings)` uses the LLM planner **only
  when `OPENAI_API_KEY` is set**, with the **rule-based planner as fallback** on any error
  (`FallbackQueryPlanner`); refusals degrade to a safe DESCRIPTIVE plan. The planner path
  is now async; the rule-based planner is wrapped via `SyncPlannerAdapter`.
- **Applied today (slice 3 ✅):** all extracted filters now shape the search. `QueryPlan`
  carries `status_filter`/`sponsor_filter`/`condition_filter`/`semantic_query`; the LLM
  planner populates them (statuses validated against the CT.gov enum set, conditions
  trimmed/deduped). The repository applies them as **hard pre-filters** before the KNN:
  status = exact `IN`, phase = array overlap, **sponsor + condition = fuzzy `ILIKE`**
  (case-insensitive substring — "Pfizer" matches "Pfizer Inc.", "melanoma" matches
  "Malignant Melanoma"; true fixes are sponsor entity-resolution + MeSH expansion,
  deferred). Filters apply on **any intent**, so `COMPETITIVE_INTEL` queries now actually
  filter (the intent still only selects which fields to search). The service embeds the
  filter-stripped `semantic_query` (falling back to the raw query when it's empty), so
  "phase 3 Pfizer" no longer pollutes the vector match — the slice-3 quick win, done.
- **Planner efficiency (fast-path + cache) ✅** — the LLM call is skipped for queries with no
  structured-filter signal (`needs_llm`: no phase/status/sponsor hint → rule-based, since a plain
  condition query has nothing to extract or strip), and an LRU (`CachingQueryPlanner`,
  `query_plan_cache_size`) memoizes plans by normalized query so repeated/popular searches never
  re-hit the LLM. Keeps the highest-volume surface off the LLM. Composition:
  `cache(fast-path(LLM + rule-based fallback))`. (Stale docstrings that claimed the filters
  weren't wired were also corrected.)

### Structured eligibility (Asset 1 — flagship IP) — Stage A shipped
- **Per-criterion extraction** — the `eligibility_criteria` blob is split + classified into
  `trial_eligibility_criteria` rows (`criterion_type`, `category` [13-way taxonomy], verbatim
  `text`, `confidence`, `is_actionable`, `source_bullet_index`, `display_order`,
  version-salted `source_hash`), with a nullable Stage-B `predicate` JSONB for the enumerable
  categories. LLM structured outputs (`responses.parse`, `gpt-5-mini`). Migration `0005`.
- **Two extraction modes** — inline (ThreadPool concurrency) and **OpenAI Batch API**
  (~50% cheaper, async submit/poll via a persisted `eligibility_batch_jobs` table,
  migration `0006`). `nct_id` rides `custom_id`; never routed through the LLM.
- **Per-item embeddings** — each actionable item embedded as `eligibility_inclusion` /
  `eligibility_exclusion` (`chunk_id = display_order` links the vector to its row); planner
  routes `Intent.PATIENT → (eligibility_inclusion, summary)` (inclusion only — cosine is
  sign-blind). Curated BQ tables auto-create from the parquet schema.

### Eligibility matching (Clinician tier — ROADMAP step 6 + 6b) ✅
- **Stateless patient↔trial matcher** — a never-persisted patient profile is evaluated
  in-request against the structured criteria (PHI gate honored). Pure logic, no LLM,
  labeled "decision support, not medical advice," **clinician-only** (`@Roles(CLINICIAN)`).
- **Two endpoints:** patient-first `POST /api/v1/match/trials` (rank recruiting candidates
  for a condition+profile — backs `/dashboard/match`) and per-trial
  `POST /api/v1/match/trials/{nct_id}` (full criterion-by-criterion verdicts — the "Why?"
  drill-in). Per-criterion verdict (pass/fail/uncertain/not-evaluated) → trial signal
  (likely-eligible / possible / likely-excluded).
- **Washout / temporal matching (6b)** ✅ — `prior_therapy` predicates now carry
  `washout_days` ("within 3 weeks" → 21, extracted by the LLM); the patient profile carries a
  `washouts` days-since map; the evaluator resolves windowed criteria directly — enough time
  elapsed → PASS, still inside the window → FAIL, `required` inverted. A matched-but-untimed
  therapy now returns an **honest UNCERTAIN** instead of the old conservative FAIL. Threaded
  through every layer (extraction predicate + prompt, inference schema/evaluator, GraphQL
  `WashoutInput` + zod, web "days since last treatment" form). `_EXTRACTOR_VERSION` → `3-washout`.
- **Match UX refinements** — ranked list now splits trials the matcher *couldn't assess*
  (no structured eligibility, or prose-only) into a distinct "Not enough data to assess" group
  instead of disguising them as "Possible"; the matched profile is snapshotted so drill-in
  verdicts can't drift from the bucket label; submit/drill-in loading states decoupled.
- **Explanation depth (sharpen #2)** — each trial shows **match completeness** ("machine-checked
  8 of 12 criteria") derived from the verdict counts, and **likely-excluded trials surface the
  failing criterion inline** ("Blocked: ECOG 2 vs required [0,1]") via a new
  `MatchedTrial.blockers` (the FAIL verdicts `rank_matches` already computes, reusing
  `CriterionVerdict`) — the "why" on the ranked list without a per-trial drill-in.
- **Wired:** inference (evaluator + repository + services + router) → api-core (service +
  resolver, zod) → web (actions + `MatchView`, role-gated nav desktop + mobile).
- **Known gaps:** time-window evaluation needs the physician to supply days-since (no patient
  timing → UNCERTAIN); surgery/prior-trial events still bucket under `prior_therapy` (taxonomy
  split deferred); days-since is integer-only (no date input yet).

### Portfolio screening (site-payer wedge v1 — no PHI) ✅
- **The pivot in product form:** instead of searching all of CT.gov, a site keeps an **open-trial
  portfolio** and screens a patient against *only* those trials — the "which of MY trials does this
  patient fit?" flow the trial-site payer actually wants. One patient at a time, at the point of
  care; the profile is evaluated in-request and **never persisted** (no PHI, no patient panels/EHR).
- **Storage:** new `PortfolioTrial` Prisma model (user-scoped, `userId + nctId` unique, by-ID
  reference — no cross-ORM FK), a sibling of `SavedTrial`. Migration `20260629000000_portfolio_trials`.
- **Scoped matching:** new `POST /api/v1/match/portfolio {profile, nct_ids}` in inference — **no
  vector search** (candidate set is explicit); reuses `get_trials_meta` (new) + `get_criteria_bulk`
  + `rank_matches`, so blockers/completeness come for free. Portfolio trials with no extracted
  criteria surface as `has_criteria=False` → "criteria not available" (no extraction-on-add in v1).
- **Wired:** inference endpoint → api-core (`portfolio` CRUD module + `screenPortfolio` resolver,
  CLINICIAN-gated, reads the user's NCT ids and forwards) → web (portfolio manager + screening view
  reusing `MatchView` via a `mode` prop, lifted state so "Screen patient" enables live once a trial
  is added, CLINICIAN-only `/dashboard/screen` route + nav link).
- **Known gaps / fast-follows:** portfolio trials need extracted eligibility to produce verdicts
  (the backfill unblocks this too); no **extraction-on-add**, no aggregate **enrollment funnel**
  (screened/eligible/enrolled counters — the ROI dashboard, PHI-free), no population/EHR screening
  (the PHI tier), no org-scoped portfolios (user-scoped for now — no org model yet).

---

## In flight / next

1. **Eligibility re-embed + washout backfill (finish Stage A rollout)** — run migrations
   `0005`/`0006`, set ETL `OPENAI_API_KEY`, then a full re-extract + re-embed. The
   `_EXTRACTOR_VERSION` → `3-washout` bump invalidates all eligibility `source_hash`es, so this
   also backfills `washout_days` predicates; stale single-chunk `eligibility` vectors are
   dropped and the two new field types populate (replace-by-nct_id only swaps a trial's vectors
   when it's re-embedded). **The gating item** — until this runs, *both* the matcher and portfolio
   screening have few predicates to act on (most trials show "criteria not available").
2. **Site-payer wedge fast-follows** (the chosen GTM direction — see ROADMAP):
   (a) **extraction-on-add** — extract eligibility for a portfolio trial the moment it's added, so
   a site's whole portfolio is screenable without waiting on the global backfill;
   (b) **aggregate enrollment funnel** — per-portfolio-trial screened/eligible/enrolled counters
   (anonymous tallies, still PHI-free) — the ROI dashboard that justifies the site paying;
   (c) later tier: **population/panel + EHR screening** (crosses into PHI — needs a BAA) and
   **org/network-scoped** portfolios (needs an org model).
3. **Washout follow-ups (ROADMAP 6b tail)** — split surgery/prior-trial events out of the
   `prior_therapy` category (their own taxonomy + evaluator dispatch), and add date-based
   timing input (compute days-since) alongside today's integer days-since.
4. **Change-event capture (ROADMAP NOW #2)** — diff-on-upsert into a new
   `trial_change_events` model so the compounding "change intelligence" moat starts
   accumulating. Cheap, time-sensitive (history is destroyed on every re-ingest today),
   independent of the search path.
5. **Compare selection UX polish**, **scheduled agent monitoring** (move landscape
   monitoring from on-view to a cron + activity-feed digest — needs a scheduler),
   **BigQuery analytics** (trend/aggregate CI — no live read path yet), and the
   **AI tier** (summaries, eligibility help, chat — registered users).

---

## Architecture facts (the non-obvious constraints)

- **Two ORMs, split by domain:** `@repo/db` (Prisma) owns user/auth in the `app` schema;
  `ctiq-db` (SQLAlchemy) owns clinical-trial tables in the `trials` schema. Disjoint;
  cross-domain links are **by NCT-id reference, never a cross-ORM FK**.
- **The LLM does structured extraction, never generation** — two uses only: the query
  *planner* (search, `OPENAI_API_KEY`-gated + rule-based fallback) and *eligibility extraction*
  (ETL, `responses.parse` → typed predicates). **No RAG / no generated answers**, and the
  **matcher is pure deterministic logic (no LLM)**. Embeddings remain **local**
  (`sentence-transformers`, `nomic-ai/nomic-embed-text-v1.5`).
- **Codegen pipeline:** api-core is GraphQL code-first → `schema.gql` (`schema:generate`);
  the web sdk's `.graphql` operation docs are **generated** from `schema.gql`
  (`generate-operations.ts`), then graphql-codegen builds the typed sdk. Don't hand-author
  operation docs.
- **api-core ↔ inference HTTP types** (`libs/clinical-search/api-types.ts`) are generated
  from inference's OpenAPI via `make gen-api-types`.

---

## Test status (all green as of 2026-06-30)

| Suite | Result |
|---|---|
| api-core (Jest, unit) | 91 passed (+ portfolio service 3 / screening resolver 1) |
| api-core integration (`session.int-spec`, Testcontainers) | 5 passed |
| api-core auth e2e (full app + Postgres) | all checks passed (+ 3 clinician-gating checks) |
| web-dashboard (Vitest) | 135 passed (+ screenPortfolio action, screening nav link) |
| inference-service (pytest, unit) | 122 passed (+ portfolio router 2 / screen-portfolio service 2, planner fast-path/cache 6) |
| inference-service integration (pgvector, Docker) | 15 passed (+ eligibility repository 5) |
| ETL `ctiq_etl` (pytest, unit) | 35 passed (`make test-etl`) |

---

## Deploy notes

- **Pending Prisma migrations** to run on the next deploy (in order):
  `20260622000000_user_remove_username`, `20260622010000_saved_trials`,
  `20260622020000_landscapes`, `20260629000000_portfolio_trials` (open-trial portfolio).
  (The dev/pooler DB is already migrated — `prisma migrate status` clean as of 2026-06-30.)
- **New api-core env:** `FAST_API_MATCH_PORTFOLIO_PATH` (default `/match/portfolio`) — the
  inference route for portfolio screening. Code defaults it, so absence won't break startup.
- **Pending Alembic (`ctiq-db`, `trials` schema) migrations:** `0005` (trial eligibility
  criteria) and `0006` (eligibility batch jobs). Run before the eligibility ETL/matcher path.
- **inference-service needs `OPENAI_API_KEY`** in its prod env to activate the LLM
  planner; without it the service cleanly falls back to the rule-based planner. The
  `openai` dependency is declared in `pyproject.toml`.
- **ETL needs `OPENAI_API_KEY`** to run eligibility extraction (auto-skips without it).
  After deploy, run the **re-embed backfill** to drop stale `eligibility` chunks and
  populate `eligibility_inclusion`/`eligibility_exclusion`.
- **api-core ↔ inference match path:** the eligibility-match endpoints are reached via the
  existing internal-token HTTP client; deploy inference + api-core + web as a set (new
  GraphQL `matchTrials`/`matchTrial` contract).
- **Deploy services as a set** when a GraphQL/HTTP contract changed together (e.g. the
  raw-age fields touched inference + api-core + web; `me`/saved-trials/landscapes added
  schema). Nullable/additive fields mean no hard ordering, but the feature only lights up
  once all involved services are out.
