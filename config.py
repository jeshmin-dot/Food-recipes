import os

from dotenv import load_dotenv
from sqlalchemy.engine import URL

load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

APP_NAME = "Recipe Garden"
SECRET_KEY = os.environ.get("SECRET_KEY", "recipe-garden-dev-key")

DEBUG = os.environ.get("FLASK_DEBUG", "0") == "1"

# --- Database -----------------------------------------------------------
# MySQL is the persistence layer for this project (per the assignment's
# required tech stack). Connection details come from individual env vars
# so nothing sensitive needs to be committed, matching the existing
# .env-based SECRET_KEY setup.
#
# Built via sqlalchemy.engine.URL.create() rather than a plain f-string so
# special characters in the password (@, :, /, etc.) are percent-encoded
# correctly instead of corrupting the connection string.
#
# DATABASE_URL can be set directly to override everything below - the
# test suite uses this to point at a throwaway SQLite file instead, so
# `pytest` can run anywhere without a MySQL server installed (see
# tests/test_app.py and REPORT.md's "Testing" section for that trade-off).
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = os.environ.get("DB_PORT", "3306")
DB_NAME = os.environ.get("DB_NAME", "recipe_garden")
DB_USER = os.environ.get("DB_USER", "root")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "")

DATABASE_URL = os.environ.get("DATABASE_URL") or URL.create(
    "mysql+pymysql",
    username=DB_USER,
    password=DB_PASSWORD,
    host=DB_HOST,
    port=int(DB_PORT),
    database=DB_NAME,
).render_as_string(hide_password=False)

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = not DEBUG