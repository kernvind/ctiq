# ctiq — Project Status

Living source of truth for what's built, what's in flight, and how to deploy it.
Maintained in the repo (versioned) because the product-engineering skill's backlog is a
read-only cache that doesn't persist across sessions.

**Last updated:** 2026-06-28

---

## Snapshot

A clinical-trial intelligence platform on public ClinicalTrials.gov data. Live on a
Hetzner VM (Docker Compose). Two surfaces:

- **Public free tier** (no account): semantic trial search, trial detail, side-by-side
  compare.
- **Authed tier** (the product): role-aware dashboard, saved trials, saved landscapes +
  monitoring. New features go here; the public surface is the acquisition funnel.

Personas: **Patient** (free funnel + future AI assistant), **Clinician** (Pro tier),
**Analyst/Competitor** (Intelligence tier — the revenue engine), **Admin** (internal).

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

### Eligibility matching (Clinician tier — ROADMAP step 6 v1) ✅
- **Stateless patient↔trial matcher** — a never-persisted patient profile is evaluated
  in-request against the structured criteria (PHI gate honored). Pure logic, no LLM,
  labeled "decision support, not medical advice," **clinician-only** (`@Roles(CLINICIAN)`).
- **Two endpoints:** patient-first `POST /api/v1/match/trials` (rank recruiting candidates
  for a condition+profile — backs `/dashboard/match`) and per-trial
  `POST /api/v1/match/trials/{nct_id}` (full criterion-by-criterion verdicts — the "Why?"
  drill-in). Per-criterion verdict (pass/fail/uncertain/not-evaluated) → trial signal
  (likely-eligible / possible / likely-excluded).
- **Wired:** inference (evaluator + repository + services + router) → api-core (service +
  resolver, zod) → web (actions + `MatchView`, role-gated nav desktop + mobile).
- **Known gaps:** no temporal/washout evaluation yet (windowed criteria → UNCERTAIN by
  design); fixed a false-PASS where prior-therapy absence from an incomplete list was read
  as a confident negative. Next slice: **washout/temporal matching** (ROADMAP 6b).

---

## In flight / next

1. **Eligibility re-embed backfill (finish Stage A rollout)** — run migrations `0005`/`0006`,
   set ETL `OPENAI_API_KEY`, then a full re-embed so stale single-chunk `eligibility`
   vectors are dropped and the two new field types populate (replace-by-nct_id only swaps a
   trial's vectors when it's re-embedded).
2. **Washout / temporal matching (ROADMAP 6b)** — the next eligibility slice: `washout_days`
   predicate + a patient timing field + window-aware evaluator, so "within N weeks" criteria
   stop defaulting to UNCERTAIN. Plus split surgery/prior-trial events out of `prior_therapy`.
3. **Change-event capture (ROADMAP NOW #2)** — diff-on-upsert into a new
   `trial_change_events` model so the compounding "change intelligence" moat starts
   accumulating. Cheap, time-sensitive (history is destroyed on every re-ingest today),
   independent of the search path.
4. **Compare selection UX polish**, **scheduled agent monitoring** (move landscape
   monitoring from on-view to a cron + activity-feed digest — needs a scheduler),
   **BigQuery analytics** (trend/aggregate CI — no live read path yet), and the
   **AI tier** (summaries, eligibility help, chat — registered users).

---

## Architecture facts (the non-obvious constraints)

- **Two ORMs, split by domain:** `@repo/db` (Prisma) owns user/auth in the `app` schema;
  `ctiq-db` (SQLAlchemy) owns clinical-trial tables in the `trials` schema. Disjoint;
  cross-domain links are **by NCT-id reference, never a cross-ORM FK**.
- **The LLM is only in the query *planner*** — gated on `OPENAI_API_KEY`, always
  fallback-protected. No RAG / no generated answers. Embeddings remain **local**
  (`sentence-transformers`, `nomic-ai/nomic-embed-text-v1.5`).
- **Codegen pipeline:** api-core is GraphQL code-first → `schema.gql` (`schema:generate`);
  the web sdk's `.graphql` operation docs are **generated** from `schema.gql`
  (`generate-operations.ts`), then graphql-codegen builds the typed sdk. Don't hand-author
  operation docs.
- **api-core ↔ inference HTTP types** (`libs/clinical-search/api-types.ts`) are generated
  from inference's OpenAPI via `make gen-api-types`.

---

## Test status (all green as of 2026-06-28)

| Suite | Result |
|---|---|
| api-core (Jest, unit) | 85 passed (+ eligibility-match service 7 / resolver 3) |
| api-core integration (`session.int-spec`, Testcontainers) | 5 passed |
| api-core auth e2e (full app + Postgres) | all checks passed (+ 3 clinician-gating checks) |
| web-dashboard (Vitest) | 123 passed (+ nav-links, match-logic, un-orphaned auth-actions) |
| inference-service (pytest, unit) | 104 passed (+ evaluator 24, match router 6) |
| inference-service integration (pgvector, Docker) | 15 passed (+ eligibility repository 5) |
| ETL `ctiq_etl` (pytest, unit) | 32 passed (suite bootstrapped this cycle; `make test-etl`) |

---

## Deploy notes

- **Pending Prisma migrations** to run on the next deploy (in order):
  `20260622000000_user_remove_username`, `20260622010000_saved_trials`,
  `20260622020000_landscapes`.
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
