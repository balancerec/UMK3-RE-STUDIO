"""Regression tests for SQLite connection lifetime on Windows.

The sqlite3.Connection context manager only handles transactions, not close().
These tests cover both explicit closure and persistence/rollback.
"""
import sqlite3
import tempfile

import pytest

from backend.storage import Store


def test_connection_closes_after_success_and_persists():
    with tempfile.TemporaryDirectory() as root:
        store = Store(root)
        with store.connection() as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS connection_test (value TEXT)")
            conn.execute("INSERT INTO connection_test(value) VALUES (?)", ("saved",))
        with pytest.raises(sqlite3.ProgrammingError, match="closed"):
            conn.execute("SELECT 1")

        reopened = Store(root)
        with reopened.connection() as reader:
            values = [row["value"] for row in reader.execute("SELECT value FROM connection_test")]
        assert values == ["saved"]
        with pytest.raises(sqlite3.ProgrammingError, match="closed"):
            reader.execute("SELECT 1")


def test_connection_closes_and_rolls_back_after_failure():
    with tempfile.TemporaryDirectory() as root:
        store = Store(root)
        with store.connection() as setup:
            setup.execute("CREATE TABLE rollback_test (value INTEGER)")
        with pytest.raises(RuntimeError, match="abort transaction"):
            with store.connection() as conn:
                conn.execute("INSERT INTO rollback_test(value) VALUES (1)")
                raise RuntimeError("abort transaction")
        with pytest.raises(sqlite3.ProgrammingError, match="closed"):
            conn.execute("SELECT 1")

        with store.connection() as reader:
            assert reader.execute("SELECT count(*) FROM rollback_test").fetchone()[0] == 0


def test_project_operations_release_database_for_temp_cleanup():
    # Exiting TemporaryDirectory deletes studio.sqlite3 on Windows only
    # when all handles have been closed.
    with tempfile.TemporaryDirectory() as root:
        first = Store(root)
        project = first.create("Deluxe")
        first.add_symbol(project["id"], "SnesPrgRom", 0x86A207, "CHARACTER_TABLE")
        second = Store(root)
        assert second.get(project["id"])["name"] == "Deluxe"
        assert len(second.symbols(project["id"])) == 1
