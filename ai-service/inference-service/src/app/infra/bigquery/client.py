from google.cloud import bigquery


class BigQueryClient:
    def __init__(self, client: bigquery.Client):
        self._client = client

    async def query(
        self,
        query: str,
        params: list[bigquery.ScalarQueryParameter | bigquery.ArrayQueryParameter] | None = None,
    ) -> list[dict]:

        job_config = None

        if params:
            job_config = bigquery.QueryJobConfig(
                query_parameters=params
            )

        query_job = self._client.query(
            query=query,
            job_config=job_config,
        )

        rows = query_job.result()

        return [dict(row.items()) for row in rows]