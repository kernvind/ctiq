# ctiq — IP Roadmap

How the three defensible assets get built on top of the **current** schema
(`py-packages/ctiq-db`), ETL (`pipelines/ctiq_etl`), and planner
(`ai-service/inference-service`). Companion to `STATUS.md` (what's shipped) — this file
is the forward plan organized around *what makes the product defensible*, not just the
next ticket.

**Last updated:** 2026-06-24

---

## The thesis

The data is public (ClinicalTrials.gov, 590k+ trials, free API) and semantic search over
it is commodity. Neither is a moat. The core IP is the **derived, structured,
longitudinal intelligence layer** that turns snapshot data into something *matchable*,
*time-aware*, and *normalized*. Three assets, ranked by defensibility:

1. **Structured eligibility** — the deepest moat. Turn unstructured inclusion/exclusion
   prose into machine-matchable criteria. Expensive, needs clinical validation, serves
   all three personas.
2. **Change intelligence** — the *compounding* moat. A history of what changed and when.
   Can't be backfilled; value is a function of how long you've been collecting. **Urgent:
   the ETL currently overwrites in place and destroys prior state on every re-ingest.**
3. **Normalized entity graph** — the curation moat. Resolved sponsors + MeSH
   therapeutic-area rollups. Lower ceiling, high confidence, makes analytics trustworthy.

The OpenAI planner is valuable *product* but **not** the IP — it's the lens; the assets
above are what it points at.

---

## Current-state facts this roadmap builds on

Grounded in the repo as of 2026-06-23:

- **`QueryPlan` now carries `status_filter`, `sponsor_filter`, `condition_filter`,
  `semantic_query`** in addition to `intent`/`fields`/`phase_filter`/`top_k`
  (`planning/schemas.py`). As of slice 3 (2026-06-24) the LLM planner populates them from
  `CompiledQuery` and the repository SQL applies them as pre-filters. *(Done — kept here
  as the now-true baseline the rest of the roadmap builds on.)*
- **`Intent.COMPETITIVE_INTEL`** maps to the same fields as DESCRIPTIVE, but is no longer
  a no-op: the structured filters (sponsor/phase/status/condition) now apply regardless of
  intent, so competitive-intel queries actually filter.
- **Eligibility is embedded as one chunk** per trial (`field_type="eligibility"`); the
  ETL flags this as a v0 limitation that hurts matching.
- **The ETL upsert overwrites in place** (`_trial_upsert`: `on_conflict_do_update`,
  newer `ingested_at` wins; child tables DELETE+INSERT). No diff is captured — prior
  state is gone after each run.
- **MeSH terms are ingested** (`trial_mesh_terms`, including `is_ancestor` rows) but
  nothing in the planner routes by them.
- **No analytics read path** on the live system. `load/bq.py` writes to BigQuery in ETL,
  but nothing reads it at query time.

---

## Roadmap

### NOW (this sprint) — lay the substrate, stop the bleeding

**1. Slice 3 — apply the structured filters (Asset 1 substrate). ✅ DONE (2026-06-24).**
The precision foundation everything else leans on. The LLM already extracted the filters;
they now act.
- `QueryPlan` extended with `status_filter`, `sponsor_filter`, `condition_filter`,
  `semantic_query`.
- Threaded `CompiledQuery` → `QueryPlan` → repository SQL as pre-filters: `overall_status`
  exact `IN`, `phases` array-overlap, `lead_sponsor_name` + `conditions` **fuzzy `ILIKE`**
  (case-insensitive substring, LIKE-wildcards escaped). Fuzzy chosen deliberately: exact
  match silently drops trials due to CT.gov string variance — the precise fixes are
  sponsor entity-resolution (Asset 3) and MeSH expansion (step 5), both still ahead.
- `COMPETITIVE_INTEL` "uses them" by virtue of filters applying on **any** intent (intent
  only selects search fields); no per-intent gating needed.
- Quick win shipped: service embeds the filter-stripped `semantic_query` (raw-query
  fallback when empty), so "phase 3 Pfizer" stops polluting the vector match.
- Covered by +9 planner/service unit tests and +4 pgvector integration tests.
- *No new model. No PHI.*

**2. Start capturing change events (Asset 2 — do this now, it's cheap and time-sensitive).**
Every day without this is history permanently lost.
- **New model `trial_change_events`** (`nct_id`, `field`, `old_value`, `new_value`,
  `change_type` [`added`/`removed`/`modified`/`status_change`], `changed_at`,
  `ingestion_date`). Alembic migration.
- In `upsert_trials`, before overwriting, diff the incoming row against the existing one
  for a watchlist of high-signal fields first: `overall_status`, `phases`,
  `enrollment_count`, `primary_completion_date`, `lead_sponsor_name`. Write events in the
  same transaction as the upsert.
- No UI required yet — the point is to *accumulate* the asset. Surfacing comes Next.
- *New model. No PHI. Buildable today, independent of Slice 3 — can run in parallel.*

### NEXT — build the flagship, surface the moat

**3. Structured eligibility extraction (Asset 1 — the flagship IP).**
Turn the `eligibility_criteria` free-text blob into machine-matchable, per-criterion rows.
This is the dependency under the high-value physician features (pre-screening + match
explanation, step 6) — diagnosis, stage, biomarker, prior-therapy, and ECOG all live
*only* in this blob today.

- **New model `trial_eligibility_criteria`**: `nct_id`, `criterion_type`
  [`inclusion`/`exclusion`], `text` (verbatim atomic assertion), `category` (taxonomy
  below), `subtype` (free text — names the `other` bucket and adds detail elsewhere),
  `predicate` JSONB (nullable, normalized — Stage B), `confidence` float, `is_actionable`
  bool (false = boilerplate like "other criteria apply"), `source_bullet_index` int (which
  source bullet this assertion came from — bullets are compound, see refinement #1),
  `source_hash` (skip re-extract when the blob is unchanged), `display_order`. Alembic
  migration, lives in `trials` schema, keyed on `nct_id` (no cross-ORM FK).

- **Category taxonomy** (the make-or-break design call — what makes criteria matchable).
  ~11 categories that recur across CT.gov eligibility prose; the user's targets map onto it:
  | Category | Captures | User's target |
  |---|---|---|
  | `diagnosis` | disease requirement ("histologically confirmed NSCLC") | **diagnosis** |
  | `disease_stage` | stage / severity ("Stage IV", "metastatic", "newly diagnosed") | **stage** |
  | `biomarker` | molecular/genetic markers ("EGFR exon 19 del", "PD-L1 ≥50%", "HER2+") | **biomarkers / EGFR** |
  | `prior_therapy` | treatment history ("prior EGFR TKI", "treatment-naïve", "≤2 prior lines") | **prior treatments** |
  | `performance_status` | ECOG / Karnofsky | **ECOG** |
  | `demographic` | age, sex (maps to existing structured cols) | age |
  | `lab_value` | hematologic/hepatic/renal thresholds ("ANC ≥1500") | — |
  | `disease_assessment` | measurable/evaluable disease ("measurable per RECIST v1.1") | — |
  | `comorbidity` | concurrent conditions ("no symptomatic brain mets") | — |
  | `concomitant_med` | meds required/prohibited | — |
  | `reproductive` | pregnancy / contraception | — |
  | `consent_logistics` | informed consent, compliance, geography | — |
  | `other` | fallback (never force a fit) | — |

- **Two-stage build — don't conflate them.** The user's instinct ("store as structured
  fields") is Stage B; the achievable flagship v1 is Stage A. Be explicit about the split:
  - **Stage A — split + classify (the realistic v1, huge value alone).** LLM splits the
    blob into individual items, tags each with `criterion_type` + `category` + verbatim
    `text` + `confidence`. `predicate` stays null. Enables category-scoped semantic
    matching ("trials whose *biomarker inclusion* mentions EGFR") and the explanation UI.
  - **Stage B — normalize `predicate`, category-by-category, highest-structure first.**
    Only the enumerable categories get a predicate; leave prose-y ones as text+category.
    Predicate shapes (the biomarker one is deliberately rich — see refinement #2):
    - `biomarker`: `{marker, op?, value?, unit?, qualifier?: "sensitizing"|"activating", relation: required|excluded, unknown_status?: eligible|excluded, assay?}`
      — e.g. PD-L1 inclusion `{"marker":"PD-L1","op":">=","value":1,"unit":"%TC","relation":"required","assay":"VENTANA SP263"}`;
      EGFR exclusion `{"marker":["EGFR","ALK","ROS1"],"qualifier":"sensitizing","relation":"excluded","unknown_status":"excluded"}`
    - `performance_status`: `{scale:"ECOG", min:0, max:1}`
    - `disease_stage`: `{stage:["IV"], modifiers:["recurrent","metastatic"]}`
    - `prior_therapy`: `{therapy_class:"checkpoint inhibitor", relation:"prohibited"|"required"|"max_lines", value?:2}`
    - `demographic`: `{min:18, unit:"years"}` (reconcile with existing `min_age_years`)
    - `lab_value`: `{analyte:"ANC", op:">=", value:1500, unit:"/uL"}`

- **Extraction approach.** ETL transform step, LLM with structured outputs (same
  `responses.parse` + Pydantic pattern the query planner already uses; reuse `gpt-5-mini`).
  Per-trial call on non-empty `eligibility_criteria`. **Cost/latency control:** gate on
  `source_hash` so re-ingest only re-extracts changed blobs; skip trials with no
  eligibility text; batch the backfill. This is the "new LLM ETL dependency at backfill
  scale" — at 590k trials it's a real one-time cost, hence the caching.

- **Validated against real prose** ([NCT06561386](https://clinicaltrials.gov/study/NCT06561386),
  Phase 3 NSCLC) — the taxonomy held; four refinements came out of the dry run:
  1. **Bullets are compound — the unit is the atomic assertion, not the bullet.** One
     inclusion bullet = diagnosis + stage + prior_therapy (three rows). The prompt must
     split *within* a bullet; `source_bullet_index` traces each row back.
  2. **Biomarker predicate must carry threshold + qualifier + assay + unknown-status
     handling** — and unknown-status flips per trial (one trial excludes unknown EGFR,
     another keeps unknown BRAF eligible). A flat `required/excluded` enum loses the nuance
     that decides the match. Hence the rich shape above.
  3. **`disease_assessment` was a missing category** ("measurable disease per RECIST" is
     ubiquitous); rare edges like "life expectancy ≥3 months" go to `other` + `subtype`.
  4. **Boilerplate must be dropped** ("Other protocol-defined criteria apply") — the
     `is_actionable` flag + low `confidence` handle it on trial #1.

- **Re-embed per-item** — add `field_type="eligibility_item"` so the one-chunk limitation
  is fixed; route `Intent.PATIENT` to the item-level field. Materially better matching.

- **Validation gate.** Predicates feeding a "likely match" verdict need clinical
  spot-checking before they're trusted. `confidence` + an honest **"uncertain"** bucket
  (low-confidence or unparsed criteria) is what keeps step 6 from being confidently wrong.

- *New model + new embedding field_type + new LLM ETL dependency. The real moat — Stage A
  is the flagship deliverable; Stage B is incremental depth, not a prerequisite to ship.*

- **Progress (2026-06-24):**
  - ✅ Model `trial_eligibility_criteria` + migration `0005`; exported from `ctiq_db`.
  - ✅ Extractor (`pipelines/ctiq_etl/.../transform/eligibility_extract.py`): Pydantic
    `ExtractedCriterion`/`ExtractedEligibility`, `EligibilityExtractor` (OpenAI
    `responses.parse`), `extract_trials` enrichment with `source_hash` re-extract gating.
  - ✅ **Load path wired** end-to-end mirroring embeddings: parquet `ELIGIBILITY_SCHEMA` →
    GCS (`upload_eligibility_batch`) → BQ (`ELIGIBILITY_TABLE_CONFIG`, replace-by-nct_id) →
    Postgres (`upsert_eligibility_criteria`); flow gains a per-trial extraction loop +
    `--skip-eligibility` (auto-skips with no OpenAI key).
  - ✅ **Per-item embeddings done.** Dropped the single averaged `eligibility` chunk; now
    embed each Stage A item with `field_type` `eligibility_inclusion` / `eligibility_exclusion`
    (boilerplate not embedded; `chunk_id = display_order` links the vector back to its
    `trial_eligibility_criteria` row for explanation). Items are embedded from the extractor
    output and merged into the trial's existing embeddings batch, so replace-by-nct_id stays
    correct. Planner routes `Intent.PATIENT → (eligibility_inclusion, summary)` — **inclusion
    only**, since cosine similarity is sign-blind and matching exclusions would falsely surface
    disqualifying trials. Exclusion vectors are stored for the future Stage B "excluded?" path.
  - ✅ **Curated BQ tables now auto-create.** `bq.ensure_curated_table` derives the BQ
    schema from the parquet schema (`SUBDIR_SCHEMAS`, one source of truth) and runs
    `create_table(exists_ok=True)` (clustered by nct_id) at the top of every load —
    non-destructive to existing tables. The eligibility table needs no manual DDL.
  - ⏳ **Remaining for Stage A:** run migration `0005`, set ETL `OPENAI_API_KEY`,
    `poetry install` (new `openai` dep), then a **full re-embed backfill** — required to
    drop stale `eligibility` chunks and populate the two new field types (replace-by-nct_id
    only swaps a trial's vectors when it's re-embedded).

**4. Surface change intelligence in landscapes (Asset 2 — turn data into a feature).**
- Upgrade landscape monitoring from `lastSeenNctIds` (membership only) to **field-level
  changes** — "Sponsor X moved NCT… Recruiting → Terminated," "enrollment cut 400→120."
- Feed the dashboard activity-feed scaffold that already exists.
- *Reads `trial_change_events` from step 2. No new model. Analyst-facing.*

**5. MeSH therapeutic-area rollups in search (Asset 3 — quick win, data already there).**
- Wire `trial_mesh_terms` (walk `is_ancestor` chain) into the planner: condition-family
  expansion ("uterine cancer" also surfaces "Endometrial Neoplasms") and rollup grouping.
- *No new model — data is ingested, just unrouted. Planner extension.*

### LATER — depth and scale (each carries a named dependency)

**6. Guided eligibility matching (Asset 1 — the payoff).**
Structured fields (`min_age_years`, `sex`, `healthy_volunteers`, `std_ages`) + parsed
criteria from step 3 → a guided yes/no funnel and per-trial "you likely match / likely
don't" signal.
- **Dependency / gate:** if it stores any patient health profile, that's **new PHI** —
  ctiq stores none today. Compliance review *before* building. A stateless,
  nothing-persisted version sidesteps this and is the safer first cut.

**7. Sponsor entity resolution (Asset 3 — CI backbone).**
- **New model(s) `sponsors` + `sponsor_aliases`** — resolve `lead_sponsor_name` variants
  and link `collaborators` to canonical entities.
- Unlocks trustworthy "everything Sponsor X is doing" across name spellings.
- *New model + entity-resolution work. No PHI.*

**8. Scheduled monitoring + digests (Asset 2 — automation).**
Move landscape monitoring from on-view to a cron job + activity-feed/email digest.
- **Dependency:** needs a scheduler (none in the stack today).

**9. Sponsor / phase landscape analytics (Asset 3 — the analyst's dream view).**
Trial counts by sponsor/phase/therapeutic-area over time.
- **Dependency:** an aggregate read path. At 590k+ trials this is the
  Postgres-materialized-rollups vs. BigQuery decision — an **architecture addition**, not
  a feature ticket. Decide deliberately; don't let it jump the queue.

**10. Drug entity resolution (Asset 3 — the *molecule* CI backbone).**
The drug analog of sponsor resolution (step 7). `trial_interventions.other_names` already
holds code-name / brand / generic aliases ("MK-3475" = pembrolizumab = Keytruda) — the raw
material is ingested, just unresolved.
- **New model(s) `drugs` + `drug_aliases`** — resolve `trial_interventions.name` +
  `other_names` to a canonical molecule; optionally tag modality from `type`
  (DRUG/BIOLOGICAL/…) and MeSH intervention terms.
- Unlocks "every trial testing molecule X across all spellings," combination-therapy
  detection (via `arm_group_labels`), and drug-repurposing signals (same molecule, many
  conditions). Pairs with sponsor resolution to answer "who is developing what, at what
  phase" — the core Competitor/Intelligence-tier query.
- *New model + entity-resolution work. No PHI. Highest-leverage of the unrouted tables.*

**11. Endpoint-trend analytics (Asset 3 — regulatory-strategy signal).**
`trial_outcomes` (primary/secondary `measure`, `time_frame`) is ingested and embedded but
**unrouted**. Normalize endpoints and aggregate them.
- **Enabling piece:** an endpoint normalization map (`measure` → canonical, e.g. "Overall
  Survival" / "OS" / "overall survival rate" → `OS`). Small lookup/enrichment, not a heavy
  model — start with the top oncology endpoints (OS, PFS, ORR, DOR, DFS).
- Unlocks: primary-endpoint mix by therapeutic area (OS vs surrogate ORR/PFS), expected
  data-readout timing from `time_frame`, and a "hard vs surrogate endpoint" quality read
  for clinicians.
- **Dependency:** shares the aggregate read-path decision with step 9 (rollups vs.
  BigQuery) — sequence the two together once that architecture call is made.

---

## New DB models this roadmap introduces

The user's call to "add more models as we develop" — here's the running list, in build order:

| Model | Asset | When | Notes |
|---|---|---|---|
| `trial_change_events` | Change intelligence | NOW | Diff-on-upsert; start accumulating immediately |
| `trial_eligibility_criteria` | Structured eligibility | NEXT | + new `eligibility_item` embedding field_type; Stage A (split+classify) then Stage B (predicate) |
| `sponsors` / `sponsor_aliases` | Entity graph | LATER | Canonical sponsor + alias map |
| `drugs` / `drug_aliases` | Entity graph | LATER | Canonical molecule from `interventions.other_names` |
| endpoint normalization map | Entity graph | LATER | `outcomes.measure` → canonical (OS/PFS/ORR/…); lookup, not a heavy model |
| (materialized rollups *or* BigQuery read path) | Entity graph | LATER | Architecture decision, not a model |

All new models follow the existing convention: live in the `trials` schema, child tables
key on `nct_id` (cross-domain links by NCT-id reference, never a cross-ORM FK).

---

## Sequencing rationale

- **Slice 3 + change-capture run first and in parallel** — one finishes paid-for work
  and is the precision substrate; the other is cheap and time-sensitive (data is being
  destroyed now). Neither blocks the other.
- **Structured eligibility is the flagship but deliberately second** — it's the deepest
  moat, but it's also the largest lift and the one most worth letting a paying persona
  pull out of you rather than building fully up front.
- **Each LATER item names its blocker** (PHI review, scheduler, analytics read path) so
  none gets mis-estimated as a normal feature.
