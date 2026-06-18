"""Dump the FastAPI OpenAPI schema to stdout.

No server is started and no model/DB is loaded — the SentenceTransformer model and
the asyncpg pool are created in the `lifespan` startup hook, not at import, so building
`app.openapi()` only needs the route definitions.

Consumed by `make gen-api-types`, which pipes this into openapi-typescript to regenerate
api-core's typed inference client (apps/api-core/src/libs/clinical-search/src/api-types.ts).

Run from the inference-service dir:  PYTHONPATH=. python scripts/dump_openapi.py
"""

import json

from src.app.main import app

if __name__ == "__main__":
    print(json.dumps(app.openapi(), indent=2))
