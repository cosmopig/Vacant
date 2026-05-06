"""Alembic env — imports SQLModel metadata for autogenerate.

Online mode runs SQL via a sync wrapper since Alembic's runtime is sync.
For autogenerate to work, downstream operators import this module and
invoke `alembic revision --autogenerate`.
"""

from __future__ import annotations

import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# Make `src/` importable so we can pull SQLModel.metadata for autogenerate.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sqlmodel import SQLModel

import vacant.registry.models  # noqa: F401  (registers tables on metadata)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = SQLModel.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    section = config.get_section(config.config_ini_section, {})
    # Strip the async driver for Alembic's sync runtime.
    if section.get("sqlalchemy.url", "").startswith("sqlite+aiosqlite"):
        section["sqlalchemy.url"] = section["sqlalchemy.url"].replace("sqlite+aiosqlite", "sqlite")
    connectable = engine_from_config(section, prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
