import logging
from typing import Optional, Sequence
from google.cloud import bigquery

from src.app.infra.bigquery.client import BigQueryClient
from src.app.modules.trial_search.planning.schemas import Field
from src.app.modules.trial_search.schemas import TrialSearchResultRow
from src.app.core.config import Settings

logger = logging.getLogger(__name__)

class TrialSearchRepository:
    """Read-side repository for the trial search use case."""

    def __init__(self, bq: BigQueryClient, settings: Settings):
        self.bq = bq
        self.settings = settings

    async def vector_search(
        self,
        embedding: list[float],
        fields: Sequence[Field],
        top_k: int,
        phase_filter: Optional[tuple[str, ...]] = None,
        statuses: Optional[tuple[str, ...]] = None
    ) -> list[TrialSearchResultRow]:
        """
        Run vector search over embedded trial chunks, applying structured
        filters BEFORE the vector search to prune the candidate set.
        """
        if not embedding:
            raise ValueError("vector_search requires a non-empty embedding")
        if not fields:
            raise ValueError("vector_search requires at least one field type")

        trials_table = self.settings.bq_full_table_id
        embeddings_table = self.settings.bq_embeddings_table_id
        locations_table = self.settings.bq_full_locations_table_id
        oversample_k = self.settings.vector_search_oversample_factor * top_k
        # Build the structured pre-filter dynamically.
        # Only include filters that are present.
        pre_filters = ["1=1"]  # base predicate; lets us safely AND below
        params: list[bigquery.ScalarQueryParameter | bigquery.ArrayQueryParameter] = [
            bigquery.ArrayQueryParameter("query_embedding", "FLOAT64", embedding),
            bigquery.ScalarQueryParameter("oversample_k", "INT64", oversample_k),  # oversample for dedup
            bigquery.ScalarQueryParameter("limit_k", "INT64", top_k),
            bigquery.ArrayQueryParameter(
                "field_types", "STRING",
                [str(f) for f in fields],
            ),
        ]

        if statuses:
            pre_filters.append("overall_status IN UNNEST(@statuses)")
            params.append(bigquery.ArrayQueryParameter("statuses", "STRING", list(statuses)))

        if phase_filter:
            pre_filters.append(
                "EXISTS (SELECT 1 FROM UNNEST(phases) p WHERE p IN UNNEST(@phase_filter))"
            )
            params.append(
                bigquery.ArrayQueryParameter("phase_filter", "STRING", list(phase_filter))
            )

        pre_filter_sql = " AND ".join(pre_filters)

        query = f"""
        WITH candidates AS (
          SELECT nct_id
          FROM `{trials_table}`
          WHERE {pre_filter_sql}
        ),
        matched AS (
          SELECT
            base.nct_id,
            base.field_type,
            base.chunk_text,
            distance
          FROM VECTOR_SEARCH(
            (
              SELECT *
              FROM `{embeddings_table}`
              WHERE field_type IN UNNEST(@field_types)
                AND nct_id IN (SELECT nct_id FROM candidates)
            ),
            'embedding',
            (SELECT @query_embedding AS embedding),
            top_k => @oversample_k,
            distance_type => 'COSINE'
          )
        ),
          -- Step 3: Per-trial aggregates from matched chunks.
          --         Pick best chunk + top 3 chunks; collapse to one row per trial.
          per_trial_matches AS (
            SELECT
              nct_id,
              MIN(distance) AS best_distance,
              ARRAY_AGG(
                STRUCT(field_type, chunk_text, distance)
                ORDER BY distance
                LIMIT 1
              )[OFFSET(0)] AS best_chunk,
              ARRAY_AGG(
                STRUCT(field_type, chunk_text, distance)
                ORDER BY distance
                LIMIT 3
              ) AS top_chunks
            FROM matched
            GROUP BY nct_id
          ),

          -- Step 4: Location aggregates for the matched trials only.
          --         Scoped subquery so we don't scan the whole locations table.
          location_aggs AS (
            SELECT
              nct_id,
              COUNT(*) AS total_sites,
              COUNTIF(status = 'RECRUITING') AS recruiting_sites,
            ARRAY_AGG(
            STRUCT(facility, city, state, country, status)
            ORDER BY
            CASE WHEN status = 'RECRUITING' THEN 0 ELSE 1 END,
            facility   -- deterministic tie-breaker, not semantic ranking
            LIMIT 5
            ) AS sample_facilities
            FROM `{locations_table}`
            WHERE nct_id IN (SELECT nct_id FROM per_trial_matches)
            GROUP BY nct_id
          )
-- Step 5: Hydrate with parent table fields + location aggregates.
        SELECT
          m.nct_id,
          t.brief_title,
          t.brief_summary,
          t.overall_status,
          t.phases,
          t.conditions,
          t.lead_sponsor_name,
          t.lead_sponsor_class,

          -- Structured eligibility
          t.min_age_years,
          t.max_age_years,
          t.sex,
          t.healthy_volunteers,

          -- Match context
          m.best_distance,
          m.best_chunk,
          m.top_chunks,

          -- Location aggregates (NULL-safe for trials with no locations)
          IFNULL(loc.total_sites, 0)        AS total_sites,
          IFNULL(loc.recruiting_sites, 0)   AS recruiting_sites,
          IFNULL(loc.sample_facilities, []) AS sample_facilities

        FROM per_trial_matches m
        JOIN `{trials_table}` t USING (nct_id)
        LEFT JOIN location_aggs loc USING (nct_id)
        ORDER BY m.best_distance
        LIMIT @limit_k
        """

        rows = await self.bq.query(query=query, params=params)
        logger.info("vector_search returned %d rows (top_k=%d)", len(rows), top_k)

        return [TrialSearchResultRow.model_validate(row)  for row in rows]