from __future__ import annotations
import sys
from pathlib import Path
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context

# Usamos DATABASE_URL desde tu app
from app.core.config import settings
from app.models.base import Base

target_metadata = Base.metadata

BASE_DIR = Path(__file__).resolve().parent.parent  # .../backend
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# Config Alembic
config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)



def run_migrations_offline():
    url = settings.sqlalchemy_database_uri
    context.configure(
        url=url,
        target_metadata=target_metadata,   # sin autogenerate por ahora
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = settings.sqlalchemy_database_uri
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        future=True,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,  # si luego defines modelos, podrás activar autogenerate
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
