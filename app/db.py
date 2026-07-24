"""Raw MySQL access using PyMySQL, in place of an ORM.

A single database connection is opened per request and stored on Flask's
`g` object, then closed automatically when the request finishes. Every
query in the application is parameterised - the values are always passed
to the driver separately from the SQL string (the %s placeholders) - so
user input is never concatenated into a statement and SQL injection is not
possible.
"""

import pymysql
from flask import g

import config


def get_db():
    """Return the connection for the current request, opening one if needed."""
    if "db" not in g:
        g.db = pymysql.connect(
            host=config.DB_HOST,
            port=int(config.DB_PORT),
            user=config.DB_USER,
            password=config.DB_PASSWORD,
            database=config.DB_NAME,
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=False,
        )
    return g.db


def close_db(exc=None):
    """Close the request's connection (registered as a teardown handler)."""
    db = g.pop("db", None)
    if db is not None:
        db.close()


class Row(dict):
    """A database row that supports both row['title'] and row.title access,
    so view code and templates can keep using the familiar attribute style."""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def __setattr__(self, name, value):
        self[name] = value


def query_all(sql, params=None):
    """Run a SELECT and return every matching row as a list of Row objects."""
    with get_db().cursor() as cursor:
        cursor.execute(sql, params or ())
        return [Row(row) for row in cursor.fetchall()]


def query_one(sql, params=None):
    """Run a SELECT and return the first row (or None)."""
    with get_db().cursor() as cursor:
        cursor.execute(sql, params or ())
        row = cursor.fetchone()
        return Row(row) if row is not None else None


def execute(sql, params=None):
    """Run an INSERT/UPDATE/DELETE, commit, and return the new row id."""
    conn = get_db()
    with conn.cursor() as cursor:
        cursor.execute(sql, params or ())
        new_id = cursor.lastrowid
    conn.commit()
    return new_id