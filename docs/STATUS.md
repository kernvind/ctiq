# ctiq — Project Status

Living source of truth for what's built, what's in flight, and how to deploy it.
Maintained in the repo (versioned) because the product-engineering skill's backlog is a
read-only cache that doesn't persist across sessions.

**Last updated:** 2026-06-24

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

---

## In flight / next

1. **Change-event capture (ROADMAP NOW #2)** — diff-on-upsert into a new
   `trial_change_events` model so the compounding "change intelligence" moat starts
   accumulating. Cheap, time-sensitive (history is destroyed on every re-ingest today),
   independent of the search path.
2. **Structured eligibility extraction (ROADMAP NEXT #3)** — the flagship IP: split
   eligibility prose into `trial_eligibility_criteria` + per-item embeddings. Largest lift.
3. **Compare selection UX polish**, **scheduled agent monitoring** (move landscape
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

## Test status (all green as of 2026-06-24)

| Suite | Result |
|---|---|
| api-core (Jest, unit) | 75 passed |
| api-core integration (`session.int-spec`, Testcontainers) | 5 passed |
| api-core auth e2e (full app + Postgres) | all checks passed |
| web-dashboard (Vitest) | 100 passed |
| inference-service (pytest, unit) | 74 passed (+9 slice-3 planner/service) |
| inference-service integration (pgvector, Docker) | 10 passed (+4 slice-3 filters) |

---

## Deploy notes

- **Pending Prisma migrations** to run on the next deploy (in order):
  `20260622000000_user_remove_username`, `20260622010000_saved_trials`,
  `20260622020000_landscapes`.
- **inference-service needs `OPENAI_API_KEY`** in its prod env to activate the LLM
  planner; without it the service cleanly falls back to the rule-based planner. The
  `openai` dependency is declared in `pyproject.toml`.
- **Deploy services as a set** when a GraphQL/HTTP contract changed together (e.g. the
  raw-age fields touched inference + api-core + web; `me`/saved-trials/landscapes added
  schema). Nullable/additive fields mean no hard ordering, but the feature only lights up
  once all involved services are out.
