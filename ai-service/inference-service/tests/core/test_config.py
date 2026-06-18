from src.app.core.config import Settings


def test_asyncpg_url_strips_psycopg_driver_prefix():
    s = Settings(pg_database_url="postgresql+psycopg://u:p@host:5432/db")
    assert s.asyncpg_database_url == "postgresql://u:p@host:5432/db"


def test_asyncpg_url_strips_asyncpg_driver_prefix():
    s = Settings(pg_database_url="postgresql+asyncpg://u:p@host:5432/db")
    assert s.asyncpg_database_url == "postgresql://u:p@host:5432/db"


def test_asyncpg_url_leaves_a_plain_url_unchanged():
    s = Settings(pg_database_url="postgresql://u:p@host:5432/db")
    assert s.asyncpg_database_url == "postgresql://u:p@host:5432/db"
