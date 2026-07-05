import os

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

APP_NAME = "Recipe Garden"
SECRET_KEY = os.environ.get("SECRET_KEY", "recipe-garden-dev-key")

DATABASE_PATH = os.environ.get(
    "DATABASE_PATH", os.path.join(BASE_DIR, "instance", "recipe_garden.db")
)

DEBUG = os.environ.get("FLASK_DEBUG", "0") == "1"

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = not DEBUG
