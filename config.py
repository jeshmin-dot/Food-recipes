import os

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

APP_NAME = "Recipe Garden"
SECRET_KEY = os.environ.get("SECRET_KEY", "recipe-garden-dev-key")

DEBUG = os.environ.get("FLASK_DEBUG", "0") == "1"

# --- Database -----------------------------------------------------------
# MySQL is the persistence layer for this project (per the assignment's
# required tech stack). The application connects with the PyMySQL driver
# and runs every query as raw, parameterised SQL (see app/db.py); there is
# no ORM. Connection details come from individual environment variables so
# nothing sensitive needs to be committed, matching the existing .env-based
# SECRET_KEY setup.
#
# The test suite does not use these values: it redirects the driver at an
# in-memory SQLite database instead (see tests/conftest.py), so `pytest`
# runs on any machine without a MySQL server.
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = os.environ.get("DB_PORT", "3306")
DB_NAME = os.environ.get("DB_NAME", "recipe_garden")
DB_USER = os.environ.get("DB_USER", "root")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "")

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = not DEBUG
