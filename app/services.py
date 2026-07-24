"""Small helpers shared by more than one blueprint.

Data access is raw parameterised SQL through app/db.py. RECIPE_SELECT is the
shared SELECT used everywhere a recipe is read: it joins the category so each
row carries its cuisine name, and a sub-query attaches the average star
rating, so the templates can keep using recipe.cuisine and
recipe.average_rating without an ORM.
"""

import os

from flask import current_app, url_for

from app.constants import REQUIRED_RECIPE_FIELDS
from app.db import query_all, query_one
from app.utils import save_uploaded_image

RECIPE_SELECT = """
SELECT r.id, r.title, r.description, r.difficulty, r.minutes, r.servings,
       r.image_url, r.ingredients, r.steps, r.nutrition, r.calories,
       r.category_id, r.owner_id, r.created_at,
       c.name AS cuisine,
       (SELECT ROUND(AVG(rv.rating), 1)
          FROM reviews rv
         WHERE rv.recipe_id = r.id) AS average_rating
FROM recipes r
JOIN categories c ON c.id = r.category_id
"""


def all_recipes():
    return query_all(RECIPE_SELECT + " ORDER BY r.created_at DESC")


def get_recipe(recipe_id):
    return query_one(RECIPE_SELECT + " WHERE r.id = %s", (recipe_id,))


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

    if missing or minutes is None or servings is None or minutes <= 0 or servings <= 0 or calories_invalid:
        return None, None, None, "Please fill in every field with valid values before saving."
    return minutes, servings, calories, None


def delete_uploaded_image(image_url):
    """Remove a previously-uploaded recipe image from disk once the database
    no longer points at it (call this AFTER the delete/commit that removed
    the reference, so the count below reflects the new state). Skips anything
    that isn't one of our own uploads and swallows filesystem errors so a
    missing/locked file never blocks a save or delete.
    """
    if not image_url or "/static/uploads/" not in image_url:
        return  # external URL, not one of our uploads - nothing to clean up

    still_used = query_one(
        "SELECT COUNT(*) AS total FROM recipes WHERE image_url = %s", (image_url,)
    )
    if still_used and still_used["total"] > 0:
        return  # another recipe still points at this exact file

    filename = image_url.rsplit("/", 1)[-1]
    upload_folder = os.path.join(current_app.static_folder, "uploads")
    path = os.path.join(upload_folder, filename)
    try:
        if os.path.isfile(path):
            os.remove(path)
    except OSError:
        pass