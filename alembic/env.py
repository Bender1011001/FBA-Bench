"""Alembic environment script for FBA-Bench migrations.

Configures Alembic to use the application's SQLAlchemy metadata and DATABASE_URL
from environment variables.
"""

import os
from logging.config import fileConfig

from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool

from alembic import context

import sys
from pathlib import Path

# Add 'src' to path so we can import fba_bench_api
sys.path.append(str(Path(__file__).parent.parent / "src"))

# Load environment variables
load_dotenv()

# Import application's SQLAlchemy metadata
from fba_bench_api.models.base import Base
# Import all models to register tables with metadata
from fba_bench_api.models import agent, contact_message, experiment, simulation, user

target_metadata = Base.metadata

# Alembic Config object
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set the SQLAlchemy URL from environment
database_url = os.getenv("DATABASE_URL", "sqlite:///./fba_bench.db")
config.set_main_option("sqlalchemy.url", database_url)

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
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
    """Run migrations in 'online' mode."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
