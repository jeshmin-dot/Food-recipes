import random
import re
from io import BytesIO

import pymysql
from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)
from fpdf import FPDF
from fpdf.enums import XPos, YPos

from app.database import get_or_create_category
from app.db import Row, execute, get_db, query_all, query_one
from app.decorators import login_required
from app.services import (
    RECIPE_SELECT,
    all_recipes,
    delete_uploaded_image,
    get_recipe,
    resolve_recipe_image,
    validate_recipe_form,
)

recipes_bp = Blueprint("recipes", __name__)


_LONG_WORD_RE = re.compile(r"\S{40,}")


def _break_long_words(text, chunk=40):
    """FPDF's word-wrap only knows how to break a line at a space. If a
    recipe field ever contains one long unbroken run of characters (a
    pasted URL, or just text typed/pasted with no spaces) that is wider
    than the page, multi_cell() cannot find anywhere to break it and
    raises "Not enough horizontal space to render a single character"
    instead of wrapping. Insert a breathing space every `chunk`
    characters inside any such run so there is always somewhere to wrap,
    without touching normal, already-spaced text."""

    def _splitter(match):
        word = match.group(0)
        return " ".join(word[i : i + chunk] for i in range(0, len(word), chunk))

    return _LONG_WORD_RE.sub(_splitter, text)


def _pdf_text(value):
    """FPDF's built-in Helvetica font can only render Windows-1252
    characters. Recipe text typed on a phone or copy-pasted from a word
    processor or recipe website often contains "smart" quotes, en/em
    dashes, or bullet characters outside that range, which raises an
    encoding error and crashes the whole request. Normalise the common
    ones to plain ASCII first, then drop anything else that still can't
    be represented, and break up any long unbroken run of characters, so
    PDF generation can never 500 regardless of what a recipe contains."""
    if not value:
        return ""
    replacements = {
        "‘": "'", "’": "'",
        "“": '"', "”": '"',
        "–": "-", "—": "-",
        "…": "...", " ": " ",
        "•": "-",
    }
    for bad, good in replacements.items():
        value = value.replace(bad, good)
    value = _break_long_words(value)
    return value.encode("latin-1", "ignore").decode("latin-1")


def _write_line(pdf, height, text):
    """FPDF's multi_cell(0, ...) auto-extends the cell to the page's
    right margin, then - by default - leaves the cursor sitting at that
    right edge instead of resetting it to the left margin on a new line.
    The next multi_cell() call then has zero horizontal room left and
    crashes with "Not enough horizontal space to render a single
    character". Forcing new_x/new_y here makes every line behave like
    normal paragraph flow instead."""
    pdf.multi_cell(0, height, _pdf_text(text), new_x=XPos.LMARGIN, new_y=YPos.NEXT)


@recipes_bp.route("/recipes")
def recipes():
    # Every filter below is built as a SQL WHERE clause with the value passed
    # as a parameter, rather than fetching every row and filtering in Python.
    query = request.args.get("q", "").strip().lower()
    cuisine = request.args.get("cuisine", "").strip()
    difficulty = request.args.get("difficulty", "").strip()
    ingredient = request.args.get("ingredient", "").strip().lower()
    time_bucket = request.args.get("time", "").strip()
    calorie_bucket = request.args.get("calories", "").strip()
    sort = request.args.get("sort", "newest").strip()

    clauses = []
    params = []

    if query:
        like = f"%{query}%"
        clauses.append("(LOWER(r.title) LIKE %s OR LOWER(c.name) LIKE %s OR LOWER(r.ingredients) LIKE %s)")
        params += [like, like, like]
    if cuisine:
        clauses.append("c.name = %s")
        params.append(cuisine)
    if difficulty:
        clauses.append("r.difficulty = %s")
        params.append(difficulty)
    if ingredient:
        clauses.append("LOWER(r.ingredients) LIKE %s")
        params.append(f"%{ingredient}%")

    if time_bucket == "under20":
        clauses.append("r.minutes < 20")
    elif time_bucket == "20to40":
        clauses.append("r.minutes BETWEEN 20 AND 40")
    elif time_bucket == "over40":
        clauses.append("r.minutes > 40")

    if calorie_bucket == "under300":
        clauses.append("r.calories IS NOT NULL AND r.calories < 300")
    elif calorie_bucket == "300to600":
        clauses.append("r.calories IS NOT NULL AND r.calories BETWEEN 300 AND 600")
    elif calorie_bucket == "over600":
        clauses.append("r.calories IS NOT NULL AND r.calories > 600")

    sql = RECIPE_SELECT
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)

    if sort == "quickest":
        sql += " ORDER BY r.minutes ASC"
    elif sort == "az":
        sql += " ORDER BY r.title ASC"
    else:
        sql += " ORDER BY r.created_at DESC"

    recipe_list = query_all(sql, params)

    cuisine_rows = query_all(
        "SELECT DISTINCT c.name FROM categories c JOIN recipes r ON r.category_id = c.id ORDER BY c.name"
    )
    all_cuisines = [row["name"] for row in cuisine_rows]
    all_difficulties = ["Easy", "Medium", "Project"]

    favorite_ids = set()
    if session.get("user_id"):
        rows = query_all("SELECT recipe_id FROM favorites WHERE user_id = %s", (session["user_id"],))
        favorite_ids = {row["recipe_id"] for row in rows}

    return render_template(
        "recipes.html",
        recipes=recipe_list,
        query=query,
        cuisine=cuisine,
        difficulty=difficulty,
        ingredient=ingredient,
        time_bucket=time_bucket,
        calorie_bucket=calorie_bucket,
        sort=sort,
        all_cuisines=all_cuisines,
        all_difficulties=all_difficulties,
        favorite_ids=favorite_ids,
    )


@recipes_bp.route("/recipes/random")
def random_recipe():
    recipe_list = all_recipes()
    if not recipe_list:
        flash("No recipes available yet.", "error")
        return redirect(url_for("recipes.recipes"))
    choice = random.choice(recipe_list)
    return redirect(url_for("recipes.recipe_detail", recipe_id=choice.id))


@recipes_bp.route("/recipes/<int:recipe_id>")
def recipe_detail(recipe_id):
    recipe = get_recipe(recipe_id)
    if recipe is None:
        abort(404, description="That recipe could not be found.")

    is_favorited = False
    if session.get("user_id"):
        is_favorited = query_one(
            "SELECT id FROM favorites WHERE user_id = %s AND recipe_id = %s",
            (session["user_id"], recipe.id),
        ) is not None

    reviews = query_all(
        """
        SELECT rv.id, rv.rating, rv.comment, rv.created_at, u.name AS user_name
        FROM reviews rv
        JOIN users u ON u.id = rv.user_id
        WHERE rv.recipe_id = %s
        ORDER BY rv.created_at DESC
        """,
        (recipe.id,),
    )
    for review in reviews:
        review["user"] = Row(name=review["user_name"])
    # The detail template shows the review count via recipe.reviews|length.
    recipe["reviews"] = reviews

    related = query_all(
        RECIPE_SELECT + " WHERE r.category_id = %s AND r.id <> %s LIMIT 3",
        (recipe.category_id, recipe.id),
    )
    return render_template(
        "recipe_detail.html", recipe=recipe, is_favorited=is_favorited, reviews=reviews, related=related
    )


@recipes_bp.route("/recipes/<int:recipe_id>/favorite", methods=["POST"])
@login_required
def toggle_favorite(recipe_id):
    recipe = get_recipe(recipe_id)
    if recipe is None:
        flash("That recipe no longer exists.", "error")
        return redirect(url_for("recipes.recipes"))

    existing = query_one(
        "SELECT id FROM favorites WHERE user_id = %s AND recipe_id = %s",
        (session["user_id"], recipe_id),
    )
    try:
        if existing:
            execute("DELETE FROM favorites WHERE id = %s", (existing.id,))
            flash("Removed from favorites.", "success")
        else:
            execute(
                "INSERT INTO favorites (user_id, recipe_id) VALUES (%s, %s)",
                (session["user_id"], recipe_id),
            )
            flash("Added to favorites.", "success")
    except pymysql.MySQLError:
        get_db().rollback()
        flash("We could not update your favorites. Please try again.", "error")

    return redirect(url_for("recipes.recipe_detail", recipe_id=recipe_id))


@recipes_bp.route("/recipes/<int:recipe_id>/review", methods=["POST"])
@login_required
def add_review(recipe_id):
    recipe = get_recipe(recipe_id)
    if recipe is None:
        flash("That recipe no longer exists.", "error")
        return redirect(url_for("recipes.recipes"))

    try:
        rating = int(request.form.get("rating", ""))
    except ValueError:
        rating = None

    if rating is None or rating < 1 or rating > 5:
        flash("Please choose a rating between 1 and 5.", "error")
        return redirect(url_for("recipes.recipe_detail", recipe_id=recipe_id))

    comment = request.form.get("comment", "").strip() or None

    try:
        # One review per user per recipe: update the existing one (so ratings
        # can't be stuffed by resubmitting the form) instead of inserting.
        existing = query_one(
            "SELECT id FROM reviews WHERE user_id = %s AND recipe_id = %s",
            (session["user_id"], recipe_id),
        )
        if existing:
            execute(
                "UPDATE reviews SET rating = %s, comment = %s WHERE id = %s",
                (rating, comment, existing.id),
            )
            flash("Your review was updated.", "success")
        else:
            execute(
                "INSERT INTO reviews (user_id, recipe_id, rating, comment) VALUES (%s, %s, %s, %s)",
                (session["user_id"], recipe_id, rating, comment),
            )
            flash("Thanks for your review!", "success")
    except pymysql.MySQLError:
        get_db().rollback()
        flash("We could not save your review. Please try again.", "error")

    return redirect(url_for("recipes.recipe_detail", recipe_id=recipe_id))


@recipes_bp.route("/dashboard", methods=["GET", "POST"])
@login_required
def dashboard():
    if request.method == "POST":
        image_url = resolve_recipe_image(request.form, request.files)
        minutes, servings, calories, error = validate_recipe_form(request.form, require_image=not image_url)

        if error:
            flash(error, "error")
            return redirect(url_for("recipes.dashboard"))

        try:
            category_id = get_or_create_category(request.form["cuisine"].strip())
            execute(
                """
                INSERT INTO recipes
                    (title, description, category_id, difficulty, minutes, servings,
                     image_url, ingredients, steps, nutrition, calories, owner_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    request.form["title"],
                    request.form["description"],
                    category_id,
                    request.form["difficulty"],
                    minutes,
                    servings,
                    image_url,
                    request.form["ingredients"],
                    request.form["steps"],
                    request.form.get("nutrition", "").strip() or None,
                    calories,
                    session["user_id"],
                ),
            )
        except pymysql.MySQLError:
            get_db().rollback()
            flash("We could not save that recipe. Please try again.", "error")
            return redirect(url_for("recipes.dashboard"))

        flash("Recipe added to the garden.", "success")
        return redirect(url_for("recipes.dashboard"))

    user_recipe_count = query_one(
        "SELECT COUNT(*) AS total FROM recipes WHERE owner_id = %s", (session["user_id"],)
    )["total"]
    user_favorite_count = query_one(
        "SELECT COUNT(*) AS total FROM favorites WHERE user_id = %s", (session["user_id"],)
    )["total"]
    user_review_count = query_one(
        "SELECT COUNT(*) AS total FROM reviews WHERE user_id = %s", (session["user_id"],)
    )["total"]
    return render_template(
        "dashboard.html",
        recipes=all_recipes(),
        user_recipe_count=user_recipe_count,
        user_favorite_count=user_favorite_count,
        user_review_count=user_review_count,
    )


@recipes_bp.route("/recipes/<int:recipe_id>/edit", methods=["GET", "POST"])
@login_required
def edit_recipe(recipe_id):
    recipe = get_recipe(recipe_id)
    if recipe is None:
        flash("That recipe no longer exists.", "error")
        return redirect(url_for("recipes.dashboard"))
    if recipe.owner_id != session["user_id"] and session.get("user_role") != "admin":
        abort(403, description="You can only edit recipes you added.")

    if request.method == "POST":
        new_image = resolve_recipe_image(request.form, request.files)
        minutes, servings, calories, error = validate_recipe_form(request.form, require_image=False)

        if error:
            flash(error, "error")
            return redirect(url_for("recipes.edit_recipe", recipe_id=recipe_id))

        old_image_url = recipe.image_url
        image_url = new_image or old_image_url
        try:
            category_id = get_or_create_category(request.form["cuisine"].strip())
            execute(
                """
                UPDATE recipes SET
                    title = %s, description = %s, category_id = %s, difficulty = %s,
                    minutes = %s, servings = %s, image_url = %s, ingredients = %s,
                    steps = %s, nutrition = %s, calories = %s
                WHERE id = %s
                """,
                (
                    request.form["title"],
                    request.form["description"],
                    category_id,
                    request.form["difficulty"],
                    minutes,
                    servings,
                    image_url,
                    request.form["ingredients"],
                    request.form["steps"],
                    request.form.get("nutrition", "").strip() or None,
                    calories,
                    recipe_id,
                ),
            )
        except pymysql.MySQLError:
            get_db().rollback()
            flash("We could not update that recipe. Please try again.", "error")
            return redirect(url_for("recipes.edit_recipe", recipe_id=recipe_id))

        if new_image and new_image != old_image_url:
            delete_uploaded_image(old_image_url)

        flash("Recipe updated.", "success")
        return redirect(url_for("recipes.dashboard"))

    return render_template("edit_recipe.html", recipe=recipe)


@recipes_bp.route("/recipes/<int:recipe_id>/delete", methods=["POST"])
@login_required
def delete_recipe(recipe_id):
    recipe = get_recipe(recipe_id)
    if recipe is None:
        flash("That recipe no longer exists.", "error")
        return redirect(url_for("recipes.dashboard"))
    if recipe.owner_id != session["user_id"] and session.get("user_role") != "admin":
        abort(403, description="You can only delete recipes you added.")

    image_url = recipe.image_url
    try:
        # Remove the rows that reference this recipe first, then the recipe.
        execute("DELETE FROM favorites WHERE recipe_id = %s", (recipe_id,))
        execute("DELETE FROM reviews WHERE recipe_id = %s", (recipe_id,))
        execute("DELETE FROM meal_plan_entries WHERE recipe_id = %s", (recipe_id,))
        execute("DELETE FROM recipes WHERE id = %s", (recipe_id,))
    except pymysql.MySQLError:
        get_db().rollback()
        flash("We could not delete that recipe. Please try again.", "error")
        return redirect(url_for("recipes.dashboard"))

    delete_uploaded_image(image_url)

    flash("Recipe deleted.", "success")
    return redirect(url_for("recipes.dashboard"))


@recipes_bp.route("/recipes/<int:recipe_id>/download")
@login_required
def download_recipe_pdf(recipe_id):
    recipe = get_recipe(recipe_id)
    if recipe is None:
        abort(404, description="That recipe could not be found.")

    try:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 20)
        _write_line(pdf, 10, recipe.title)

        pdf.set_font("Helvetica", "", 11)
        _write_line(
            pdf,
            6,
            f"{recipe.cuisine} - {recipe.difficulty} - {recipe.minutes} min - Serves {recipe.servings}",
        )
        pdf.ln(4)
        _write_line(pdf, 6, recipe.description)

        pdf.ln(4)
        pdf.set_font("Helvetica", "B", 13)
        _write_line(pdf, 8, "Ingredients")
        pdf.set_font("Helvetica", "", 11)
        for line in recipe.ingredients.split("\n"):
            line = line.strip()
            if line:
                _write_line(pdf, 6, f"- {line}")

        pdf.ln(4)
        pdf.set_font("Helvetica", "B", 13)
        _write_line(pdf, 8, "Steps")
        pdf.set_font("Helvetica", "", 11)
        steps = [s.strip() for s in recipe.steps.split("\n") if s.strip()]
        for i, step in enumerate(steps, start=1):
            _write_line(pdf, 6, f"{i}. {step}")

        if recipe.nutrition:
            pdf.ln(4)
            pdf.set_font("Helvetica", "B", 13)
            _write_line(pdf, 8, "Nutrition")
            pdf.set_font("Helvetica", "", 11)
            _write_line(pdf, 6, recipe.nutrition)

        buffer = BytesIO(pdf.output())
        buffer.seek(0)
    except Exception:
        current_app.logger.exception("Failed to generate PDF for recipe %s", recipe_id)
        flash("We could not generate that PDF. Please try again.", "error")
        return redirect(url_for("recipes.recipe_detail", recipe_id=recipe_id))

    safe_name = "".join(c for c in recipe.title if c.isalnum() or c in (" ", "-", "_")).strip() or "recipe"
    return send_file(
        buffer,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"{safe_name}.pdf",
    )