# ─── Upload PyArrow Tables to GCS as Parquet ─────────────────────────────────
 
from __future__ import annotations
 
import logging
from datetime import date, datetime, timezone
from typing import  Optional
 
import pyarrow as pa
import pyarrow.parquet as pq
from src.tasks.load.studies_to_parquet import _embeddings_to_arrow_tables, _studies_to_arrow_tables
 
logger = logging.getLogger(__name__)

def _write_tables_to_gcs(
    tables: dict[str, pa.Table],
    bucket_name: str,
    prefix: str,
    ingestion_date: date,
    chunk_idx: int,
    batch_id: str,
    compression: str = "snappy",
) -> dict[str, str]:
    """
    Write each `pa.Table` to GCS as a single Parquet object under a
    Hive-style date-partitioned path.
 
    Returns: {table_name: gs:// URI}. Empty tables are skipped (no empty
    Parquet files are written).
 
    Compression options: 'snappy' (BQ default, fastest), 'zstd' (smaller),
    'gzip' (compatibility). Stick with snappy unless storage cost dominates.
    """
 
 
    written: dict[str, str] = {}
    for table_name, table in tables.items():
        if table.num_rows == 0:
            logger.debug("Skipping empty table %s (no rows in batch)", table_name)
            continue
        blob_path = (
            f"{prefix.rstrip('/')}/{table_name}/"
            f"ingestion_date={ingestion_date.isoformat()}/"
            f"batch_{batch_id}/chunk_{chunk_idx:04d}.parquet"
        )
        uri = f"gs://{bucket_name}/{blob_path}"
        written[table_name] = uri
        
        pq.write_table(
            table,
            uri,
            compression=compression,         # Standard efficient compression
            use_dictionary=True,
            write_statistics=True,
            row_group_size=50_000,
        )
        logger.info("Wrote %d rows -> %s", table.num_rows, uri)
 
    return written

def upload_studies_batch(
    transformed_studies: list[Optional[dict]],
    bucket_name: str,
    chunk_idx: int,
    batch_id: str,
    ingestion_date: date,
    prefix: str = "clinical_trials/staging",
    compression: str = "snappy",
) -> dict[str, str]:
    """
    One-call helper: takes a batch of `transform_study()` outputs and
    writes all seven tables to GCS as Parquet.
 
    Returns: {table_name: gs:// URI}.
 
    Recommended batch size: 5,000 - 50,000 studies per call. The 'trial'
    rows are wide; the child tables (locations, mesh_terms) can be 10-50x
    that count. Larger batches = fewer, bigger Parquet files = faster
    BQ loads. Too large = OOM in the worker.
    """
    ingested_at = datetime.now(timezone.utc)
 
    tables = _studies_to_arrow_tables(
        transformed_studies, ingestion_date, ingested_at
    )
    return _write_tables_to_gcs(
        tables,
        bucket_name=bucket_name,
        prefix=prefix,
        ingestion_date=ingestion_date,
        chunk_idx=chunk_idx,
        compression=compression,
        batch_id=batch_id,
    )
    
def upload_embeddings_batch(
    embeddings: list[dict],
    bucket_name: str,
    chunk_idx: int,
    batch_id: str,
    ingestion_date: date,
    prefix: str = "clinical_trials/staging",
    compression: str = "snappy",
) -> dict[str, str]:
    """
    One-call helper: takes a batch of `transform_study()` outputs and
    writes all seven tables to GCS as Parquet.
 
    Returns: {table_name: gs:// URI}.
 
    Recommended batch size: 5,000 - 50,000 studies per call. The 'trial'
    rows are wide; the child tables (locations, mesh_terms) can be 10-50x
    that count. Larger batches = fewer, bigger Parquet files = faster
    BQ loads. Too large = OOM in the worker.
    """
 
    tables = _embeddings_to_arrow_tables(
        embeddings,
    )
    return _write_tables_to_gcs(
        tables,
        bucket_name=bucket_name,
        prefix=prefix,
        ingestion_date=ingestion_date,
        chunk_idx=chunk_idx,
        compression=compression,
        batch_id=batch_id,
    )