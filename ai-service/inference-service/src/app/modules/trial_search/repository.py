import logging
from typing import Optional, Sequence

from src.app.infra.postgres.client import PostgresClient
from src.app.modules.trial_search.planning.schemas import Field
from src.app.modules.trial_search.schemas import TrialSearchResultRow
from src.app.core.config import Settings

logger = logging.getLogger(__name__)


class TrialSearchRepository:
    """Read-side repository for the trial search use case."""

    def __init__(self, pg: PostgresClient, settings: Settings):
        self.pg = pg
        self.settings = settings

    async def vector_search(
        self,
        embedding: list[float],
        fields: Sequence[Field],
        top_k: int,
        phase_filter: Optional[tuple[str, ...]] = None,
        statuses: Optional[tuple[str, ...]] = None,
    ) -> list[TrialSearchResultRow]:
        if not embedding:
            raise ValueError("vector_search requires a non-empty embedding")
        if not fields:
            raise ValueError("vector_search requires at least one field type")

        oversample_k = self.settings.vector_search_oversample_factor * top_k

        # Build param list dynamically so optional filters get correct $n positions.
        params: list = []

        def p(value) -> str:
            params.append(value)
            return f"${len(params)}"

        embedding_ref   = p(embedding)
        oversample_ref  = p(oversample_k)
        field_types_ref = p([str(f) for f in fields])
        limit_ref       = p(top_k)

        pre_filters = ["1=1"]
        if statuses:
            pre_filters.append(f"overall_status = ANY({p(list(statuses))})")
        if phase_filter:
            pre_filters.append(f"phases && {p(list(phase_filter))}")

        pre_filter_sql = " AND ".join(pre_filters)

        query = f"""
        WITH candidates AS (
            SELECT nct_id
            FROM clinical_trials
            WHERE {pre_filter_sql}
        ),
        matched AS (
            SELECT
                e.nct_id,
                e.field_type,
                e.chunk_text,
                e.embedding <=> {embedding_ref}  AS distance
            FROM trial_embeddings e
            WHERE e.field_type = ANY({field_types_ref})
              AND e.nct_id IN (SELECT nct_id FROM candidates)
            ORDER BY distance
            LIMIT {oversample_ref}
        ),
        per_trial_matches AS (
            SELECT
                nct_id,
                MIN(distance) AS best_distance,
                jsonb_agg(
                    jsonb_build_object(
                        'field_type', field_type,
                        'chunk_text', chunk_text,
                        'distance',   distance
                    )
                    ORDER BY distance
                ) AS all_chunks
            FROM matched
            GROUP BY nct_id
        ),
        location_aggs AS (
            SELECT
                nct_id,
                COUNT(*)                                        AS total_sites,
                COUNT(*) FILTER (WHERE status = 'RECRUITING')  AS recruiting_sites,
                jsonb_agg(
                    jsonb_build_object(
                        'facility', facility,
                        'city',     city,
                        'state',    state,
                        'country',  country,
                        'status',   status
                    )
                    ORDER BY CASE WHEN status = 'RECRUITING' THEN 0 ELSE 1 END, facility
                ) FILTER (WHERE rn <= 5) AS sample_facilities
            FROM (
                SELECT *,
                    ROW_NUMBER() OVER (
                        PARTITION BY nct_id
                        ORDER BY CASE WHEN status = 'RECRUITING' THEN 0 ELSE 1 END, facility
                    ) AS rn
                FROM trial_locations
                WHERE nct_id IN (SELECT nct_id FROM per_trial_matches)
            ) ranked
            GROUP BY nct_id
        )
        SELECT
            m.nct_id,
            t.brief_title,
            t.brief_summary,
            t.overall_status,
            t.phases,
            t.conditions,
            t.lead_sponsor_name,
            t.lead_sponsor_class,
            t.min_age_years,
            t.max_age_years,
            t.sex,
            t.healthy_volunteers,
            m.best_distance,
            m.all_chunks,
            COALESCE(loc.total_sites, 0)              AS total_sites,
            COALESCE(loc.recruiting_sites, 0)         AS recruiting_sites,
            COALESCE(loc.sample_facilities, '[]'::jsonb) AS sample_facilities
        FROM per_trial_matches m
        JOIN clinical_trials t USING (nct_id)
        LEFT JOIN location_aggs loc USING (nct_id)
        ORDER BY m.best_distance
        LIMIT {limit_ref}
        """

        rows = await self.pg.fetch(query, *params)
        logger.info("vector_search returned %d rows (top_k=%d)", len(rows), top_k)

        results = []
        for row in rows:
            d = dict(row)
            all_chunks = d.pop("all_chunks") or []
            d["best_chunk"] = all_chunks[0]
            d["top_chunks"] = all_chunks[:3]
            results.append(TrialSearchResultRow.model_validate(d))

        return results
