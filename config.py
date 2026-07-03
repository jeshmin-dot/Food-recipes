import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

APP_NAME = "Recipe Garden"
SECRET_KEY = os.environ.get("SECRET_KEY", "recipe-garden-dev-key")

DATABASE_PATH = os.environ.get(
    "DATABASE_PATH",
    os.path.join(BASE_DIR, "instance", "recipe_garden.db")
)

DEBUG = os.environ.get("FLASK_DEBUG", "0") == "1"