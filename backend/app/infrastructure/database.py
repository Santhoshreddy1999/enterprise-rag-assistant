from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, Engine, create_engine, event, inspect, text
from sqlalchemy.engine import Dialect
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.types import TypeDecorator, TypeEngine


class Base(DeclarativeBase):
    pass


class EmbeddingType(TypeDecorator[list[float]]):
    """Use pgvector in PostgreSQL and JSON arrays in portable test databases."""

    impl = JSON
    cache_ok = True

    def __init__(self, dimensions: int) -> None:
        super().__init__()
        self.dimensions = dimensions

    def load_dialect_impl(self, dialect: Dialect) -> TypeEngine[Any]:
        if dialect.name == "postgresql":
            return dialect.type_descriptor(Vector(self.dimensions))
        return dialect.type_descriptor(JSON())

    def process_bind_param(self, value: list[float] | None, dialect: Dialect) -> list[float] | None:
        return value

    def process_result_value(self, value: Any, dialect: Dialect) -> list[float] | None:
        if value is None:
            return None
        return [float(item) for item in value]


def _sqlite_foreign_keys(dbapi_connection: Any, _connection_record: Any) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


class Database:
    def __init__(self, url: str) -> None:
        options: dict[str, Any] = {"pool_pre_ping": True}
        if url.startswith("sqlite"):
            options["connect_args"] = {"check_same_thread": False}
            options["pool_pre_ping"] = False
            if ":memory:" in url or url.rstrip("/") in {"sqlite:", "sqlite+pysqlite:"}:
                options["poolclass"] = StaticPool

        self.engine: Engine = create_engine(url, **options)
        if self.engine.dialect.name == "sqlite":
            event.listen(self.engine, "connect", _sqlite_foreign_keys)
        self.session_factory = sessionmaker(
            bind=self.engine,
            class_=Session,
            autoflush=False,
            expire_on_commit=False,
        )

    def sessions(self) -> Iterator[Session]:
        with self.session_factory() as session:
            yield session

    def create_schema(self) -> None:
        # Importing registers all mapped tables on Base.metadata.
        from app.infrastructure import models  # noqa: F401

        if self.engine.dialect.name == "postgresql":
            with self.engine.begin() as connection:
                connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        Base.metadata.create_all(self.engine)

    def is_ready(self) -> bool:
        try:
            with self.engine.connect() as connection:
                connection.execute(text("SELECT 1"))
                if not inspect(connection).has_table("users"):
                    return False
                if self.engine.dialect.name == "postgresql":
                    vector_enabled = connection.scalar(
                        text("SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector')")
                    )
                    if not vector_enabled:
                        return False
            return True
        except Exception:
            return False

    def dispose(self) -> None:
        self.engine.dispose()
