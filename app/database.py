from collections.abc import Generator

from sqlalchemy import inspect, text
from sqlmodel import Session, SQLModel, create_engine

from app.config import get_settings


settings = get_settings()

connect_args = {}
if settings.database_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(settings.database_url, connect_args=connect_args)


def init_db() -> None:
    SQLModel.metadata.create_all(engine)
    ensure_schema_compatibility()


def ensure_schema_compatibility() -> None:
    if not settings.database_url.startswith("sqlite"):
        return

    inspector = inspect(engine)
    if "signals" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("signals")}
    
    if "is_favorite" in columns and "deleted_at" in columns:
        return

    with engine.begin() as connection:
        if "is_favorite" not in columns:
            connection.execute(
                text("ALTER TABLE signals ADD COLUMN is_favorite BOOLEAN NOT NULL DEFAULT 0")
            )
        if "deleted_at" not in columns:
            connection.execute(
                text("ALTER TABLE signals ADD COLUMN deleted_at DATETIME")
            )


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
