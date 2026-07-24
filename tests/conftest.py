"""Test configuration: run the suite against a throwaway SQLite database.

The application talks to MySQL through PyMySQL in development and production
(see app/db.py and config.py). For the tests we do not want to depend on a
running MySQL server, so this file redirects every pymysql.connect() call to
an in-memory SQLite database while the tests run. Production code is left
completely untouched - app/db.py still calls pymysql.connect() exactly as it
does against MySQL; only the destination changes here.

A small translation layer rewrites the few MySQL-specific pieces of SQL
(the AUTO_INCREMENT/UNIQUE KEY table syntax and the %s placeholders) into
their SQLite equivalents, and re-raises SQLite errors as the matching
PyMySQL error classes so the application's existing except blocks behave
exactly as they would against MySQL.
"""

import re
import sqlite3
import sys
from pathlib import Path

import pymysql
import pytest

# Make the project importable when pytest is run from the tests/ folder.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


# The one SQLite connection shared by every "connection" the app opens
# during a single test. app/db.py opens a fresh connection per request, but
# they must all see the same in-memory database, so they are all backed by
# this single shared handle. It is replaced with an empty one before each
# test by the autouse fixture below.
_state = {"conn": None}


def _fresh_sqlite():
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = OFF")
    _state["conn"] = conn
    return conn


def _translate(sql):
    """Rewrite the handful of MySQL-only constructs the app uses so the
    same SQL runs unchanged on SQLite."""
    sql = sql.replace("%s", "?")
    sql = re.sub(
        r"INT\s+AUTO_INCREMENT\s+PRIMARY\s+KEY",
        "INTEGER PRIMARY KEY AUTOINCREMENT",
        sql,
        flags=re.IGNORECASE,
    )
    sql = re.sub(r"\bAUTO_INCREMENT\b", "", sql, flags=re.IGNORECASE)
    sql = re.sub(r"UNIQUE\s+KEY\s+\w+\s+\(", "UNIQUE (", sql, flags=re.IGNORECASE)
    sql = re.sub(
        r"ON\s+DUPLICATE\s+KEY\s+UPDATE\s+recipe_id\s*=\s*VALUES\(recipe_id\)",
        "ON CONFLICT(user_id, day_of_week, meal_type) "
        "DO UPDATE SET recipe_id = excluded.recipe_id",
        sql,
        flags=re.IGNORECASE,
    )
    return sql


class _ShimCursor:
    def __init__(self, sqlite_conn):
        self._cur = sqlite_conn.cursor()
        self.lastrowid = None
        self.rowcount = -1

    def execute(self, sql, params=None):
        try:
            self._cur.execute(_translate(sql), tuple(params or ()))
        except sqlite3.IntegrityError as exc:
            raise pymysql.err.IntegrityError(str(exc))
        except sqlite3.Error as exc:
            raise pymysql.err.OperationalError(str(exc))
        self.lastrowid = self._cur.lastrowid
        self.rowcount = self._cur.rowcount
        return self.rowcount

    def executemany(self, sql, seq_of_params):
        rows = [tuple(p) for p in seq_of_params]
        try:
            self._cur.executemany(_translate(sql), rows)
        except sqlite3.IntegrityError as exc:
            raise pymysql.err.IntegrityError(str(exc))
        except sqlite3.Error as exc:
            raise pymysql.err.OperationalError(str(exc))
        self.lastrowid = self._cur.lastrowid
        self.rowcount = self._cur.rowcount
        return self.rowcount

    def fetchone(self):
        row = self._cur.fetchone()
        return dict(row) if row is not None else None

    def fetchall(self):
        return [dict(row) for row in self._cur.fetchall()]

    def close(self):
        self._cur.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self._cur.close()


class _ShimConnection:
    """Stands in for a pymysql connection, backed by the shared SQLite handle.

    close() is deliberately a no-op: the app closes its connection at the end
    of every request, but the tests need the same in-memory database to stay
    alive across all of a test's requests. The database is thrown away and
    recreated between tests by the autouse fixture instead.
    """

    def cursor(self, *args, **kwargs):
        return _ShimCursor(_state["conn"])

    def commit(self):
        _state["conn"].commit()

    def rollback(self):
        _state["conn"].rollback()

    def close(self):
        pass


def _fake_connect(*args, **kwargs):
    if _state["conn"] is None:
        _fresh_sqlite()
    return _ShimConnection()


# Point the whole application at SQLite for the duration of the test session.
pymysql.connect = _fake_connect


@pytest.fixture(autouse=True)
def _fresh_database():
    """Give every test a brand-new, empty database."""
    old = _state.get("conn")
    if old is not None:
        old.close()
    _fresh_sqlite()
    yield
