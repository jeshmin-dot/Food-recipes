"""Small helpers shared by more than one blueprint.

Kept framework-thin on purpose: these are plain functions (not a service
class) since the app is small enough that a class-based service layer
would just be ceremony. If the route count keeps growing, splitting this
into per-domain service modules would be the next refactor.
"""

import os

from flask import current_app, url_for

from app.constants import REQUIRED_RECIPE_FIELDS
from app.models import Recipe, db
from app.utils import save_uploaded_image


def all_recipes():
    return Recipe.query.order_by(Recipe.created_at.desc()).all()


def get_recipe(recipe_id):
    return db.session.get(Recipe, recipe_id)


def resolve_recipe_image(form, files):
    upload_folder = os.path.join(current_app.static_folder, "uploads")
    uploaded_name = save_uploaded_image(files.get("image_file"), upload_folder)
    if uploaded_name:
        return url_for("static", filename=f"uploads/{uploaded_name}")
    url_value = form.get("image_url", "").strip()
    return url_value or None


def validate_recipe_form(form, require_image):
    """Shared validation for both the add and edit recipe forms.

    Returns (minutes, servings, calories, error_message). error_message is
    None when everything's valid; the other three are None if invalid.
    Calories is optional - an empty field is fine and stored as None, but
    a value that isn't a non-negative whole number is rejected rather than
    silently dropped, so a typo doesn't quietly save as "no data".
    """
    missing = [field for field in REQUIRED_RECIPE_FIELDS if not form.get(field, "").strip()]
    try:
        minutes = int(form.get("minutes", ""))
        servings = int(form.get("servings", ""))
    except ValueError:
        minutes = servings = None

    calories_raw = form.get("calories", "").strip()
    calories = None
    calories_invalid = False
    if calories_raw:
        try:
            calories = int(calories_raw)
            if calories < 0:
                calories_invalid = True
        except ValueError:
            calories_invalid = True

    if require_image and not form.get("image_url", "").strip():
        missing.append("image")

    if missing or minutes is None or calories_invalid:
        return None, None, None, "Please fill in every field with valid values before saving."
    return minutes, servings, calories, None


def delete_uploaded_image(image_url):
    """Remove a previously-uploaded recipe image from disk once the database
    no longer points at it (call this AFTER the commit/delete that removed
    the reference, so the count() below reflects the new state). Skips
    anything that isn't one of our own uploads (e.g. an external image_url)
    and swallows filesystem errors so a missing/locked file never blocks a
    save or delete.
    """
    if not image_url or "/static/uploads/" not in image_url:
        return  # external URL, not one of our uploads - nothing to clean up

    if Recipe.query.filter(Recipe.image_url == image_url).count() > 0:
        return  # another recipe still points at this exact file

    filename = image_url.rsplit("/", 1)[-1]
    upload_folder = os.path.join(current_app.static_folder, "uploads")
    path = os.path.join(upload_folder, filename)
    try:
        if os.path.isfile(path):
            os.remove(path)
    except OSError:
        pass