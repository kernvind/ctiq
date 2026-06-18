import os
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

from ctiq_db.models import Base, TRIALS_SCHEMA

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _load_local_dotenv() -> None:
    """Load this package's .env so a DATABASE_URL kept there is picked up.

    Alembic only reads real (exported) environment variables; without this it silently
    falls back to the alembic.ini placeholder when DATABASE_URL lives only in .env.
    Uses setdefault, so an exported env var or `make migrate-* DATABASE_URL=...` always
    wins — .env is a fallback, never an override.
    """
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        return
    for raw in env_path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)


_load_local_dotenv()


def include_name(name, type_, parent_names):
    """Restrict autogenerate to the trial domain.

    With a schema-qualified metadata we must enable ``include_schemas`` so Alembic
    reflects the ``trials`` schema. Without this filter, autogenerate would also scan
    Supabase-managed schemas (auth, storage, public, …) and could propose dropping
    tables this package does not own. We only ever manage ``trials`` here.
    """
    if type_ == "schema":
        return name == TRIALS_SCHEMA
    return True

# DATABASE_URL from environment overrides the alembic.ini placeholder.
# Normalize the scheme to the psycopg (v3) driver: this project installs
# psycopg[binary], not psycopg2, but a bare "postgresql://" URL makes
# SQLAlchemy default to the psycopg2 dialect. Sharing one DATABASE_URL with
# Prisma (which requires the bare scheme) means we rewrite it here instead of
# forcing callers to remember the +psycopg suffix.
database_url = os.environ.get("DATABASE_URL")
if database_url:
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace(
            "postgresql://", "postgresql+psycopg://", 1
        )
    elif database_url.startswith("postgres://"):
        database_url = database_url.replace(
            "postgres://", "postgresql+psycopg://", 1
        )
    config.set_main_option("sqlalchemy.url", database_url)


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_schemas=True,
        include_name=include_name,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_schemas=True,
            include_name=include_name,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
