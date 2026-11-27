"""Criação do engine em SQLite."""

from pathlib import Path
from typing import Any

from sqlalchemy import Engine, create_engine, event, make_url
from sqlalchemy.pool import StaticPool


def make_engine(url: str) -> Engine:
    parsed = make_url(url)
    kwargs: dict[str, Any] = {}
    if parsed.get_backend_name() == "sqlite":
        if parsed.database in (None, "", ":memory:"):
            # Banco em memória: uma única conexão compartilhada
            kwargs["poolclass"] = StaticPool
            kwargs["connect_args"] = {"check_same_thread": False}
        else:
            Path(parsed.database).parent.mkdir(parents=True, exist_ok=True)

    engine = create_engine(parsed, **kwargs)

    if parsed.get_backend_name() == "sqlite":

        @event.listens_for(engine, "connect")
        def _on_connect(dbapi_connection: Any, _record: Any) -> None:
            # O pysqlite não abre transação antes de DDL: um DROP seria confirmado mesmo que o
            # INSERT seguinte falhasse.
            # Desligamos o controle dele e emitimos BEGIN nós mesmos.
            dbapi_connection.isolation_level = None
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        @event.listens_for(engine, "begin")
        def _on_begin(conn: Any) -> None:
            conn.exec_driver_sql("BEGIN")

    return engine
