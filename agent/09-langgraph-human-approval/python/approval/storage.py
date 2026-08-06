"""SQLite-backed graph lifecycle for cross-process resume."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph.state import CompiledStateGraph

from approval.graph import build_graph


@contextmanager
def open_sqlite_graph(database: Path) -> Iterator[CompiledStateGraph]:
    """Open a compiled graph whose checkpoints survive process restarts."""
    database.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database, check_same_thread=False)
    try:
        checkpointer = SqliteSaver(connection)
        checkpointer.setup()
        yield build_graph(checkpointer)
    finally:
        connection.close()
