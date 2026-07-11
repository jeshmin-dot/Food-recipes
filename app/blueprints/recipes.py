import random
import re
from io import BytesIO

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
from sqlalchemy import or_
from sqlalchemy.exc import SQLAlchemyError

from app.database import get_or_create_category
from app.decorators import login_required
from app.models import Category, Favorite, Recipe, Review, db
from app.services import (
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
        "…": "...", " ": " ",
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
    # Query-level filtering: every filter below is applied as a SQL WHERE
    # clause (via SQLAlchemy), rather than fetching every row and
    # filtering with Python list comprehensions.
    query = request.args.get("q", "").strip().lower()
    cuisine = request.args.get("cuisine", "").strip()
    difficulty = request.args.get("difficulty", "").strip()
    ingredient = request.args.get("ingredient", "").strip().lower()
    time_bucket = request.args.get("time", "").strip()
    sort = request.args.get("sort", "newest").strip()

    recipe_query = Recipe.query.join(Category)

    if query:
        pattern = f"%{query}%"
        recipe_query = recipe_query.filter(
            or_(
                Recipe.title.ilike(pattern),
                Category.name.ilike(pattern),
                Recipe.ingredients.ilike(pattern),
            )
        )
    if cuisine:
        recipe_query = recipe_query.filter(Category.name == cuisine)
    if difficulty:
        recipe_query = recipe_query.filter(Recipe.difficulty == difficulty)
    if ingredient:
        recipe_query = recipe_query.filter(Recipe.ingredients.ilike(f"%{ingredient}%"))
    if time_bucket == "under20":
        recipe_query = recipe_query.filter(Recipe.minutes < 20)
    elif time_bucket == "20to40":
        recipe_query = recipe_query.filter(Recipe.minutes.between(20, 40))
    elif time_bucket == "over40":
        recipe_query = recipe_query.filter(Recipe.minutes > 40)

    if sort == "quickest":
        recipe_query = recipe_query.order_by(Recipe.minutes.asc())
    elif sort == "az":
        recipe_query = recipe_query.order_by(Recipe.title.asc())
    else:
        recipe_query = recipe_query.order_by(Recipe.created_at.desc())

    recipe_list = recipe_query.all()

    all_cuisines = sorted({recipe.cuisine for recipe in all_recipes()})
    all_difficulties = ["Easy", "Medium", "Project"]

    favorite_ids = set()
    if session.get("user_id"):
        favorite_ids = {f.recipe_id for f in Favorite.query.filter_by(user_id=session["user_id"]).all()}

    return render_template(
        "recipes.html",
        recipes=recipe_list,
        query=query,
        cuisine=cuisine,
        difficulty=difficulty,
        ingredient=ingredient,
        time_bucket=time_bucket,
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
        is_favorited = Favorite.query.filter_by(
            user_id=session["user_id"], recipe_id=recipe.id
        ).first() is not None
    reviews = Review.query.filter_by(recipe_id=recipe.id).order_by(Review.created_at.desc()).all()
    related = (
        Recipe.query.filter(Recipe.category_id == recipe.category_id, Recipe.id != recipe.id)
        .limit(3)
        .all()
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

    existing = Favorite.query.filter_by(user_id=session["user_id"], recipe_id=recipe_id).first()
    try:
        if existing:
            db.session.delete(existing)
            flash("Removed from favorites.", "success")
        else:
            db.session.add(Favorite(user_id=session["user_id"], recipe_id=recipe_id))
            flash("Added to favorites.", "success")
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
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
        # One review per user per recipe: update the existing one (so
        # ratings can't be stuffed by resubmitting the form) instead of
        # always inserting a new row.
        existing = Review.query.filter_by(user_id=session["user_id"], recipe_id=recipe_id).first()
        if existing:
            existing.rating = rating
            existing.comment = comment
            flash("Your review was updated.", "success")
        else:
            db.session.add(
                Review(user_id=session["user_id"], recipe_id=recipe_id, rating=rating, comment=comment)
            )
            flash("Thanks for your review!", "success")
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        flash("We could not save your review. Please try again.", "error")

    return redirect(url_for("recipes.recipe_detail", recipe_id=recipe_id))


@recipes_bp.route("/dashboard", methods=["GET", "POST"])
@login_required
def dashboard():
    if request.method == "POST":
        image_url = resolve_recipe_image(request.form, request.files)
        minutes, servings, error = validate_recipe_form(request.form, require_image=not image_url)

        if error:
            flash(error, "error")
            return redirect(url_for("recipes.dashboard"))

        try:
            category = get_or_create_category(request.form["cuisine"].strip())
            recipe = Recipe(
                title=request.form["title"],
                description=request.form["description"],
                category_id=category.id,
                difficulty=request.form["difficulty"],
                minutes=minutes,
                servings=servings,
                image_url=image_url,
                ingredients=request.form["ingredients"],
                steps=request.form["steps"],
                nutrition=request.form.get("nutrition", "").strip() or None,
                owner_id=session["user_id"],
            )
            db.session.add(recipe)
            db.session.commit()
        except SQLAlchemyError:
            db.session.rollback()
            flash("We could not save that recipe. Please try again.", "error")
            return redirect(url_for("recipes.dashboard"))

        flash("Recipe added to the garden.", "success")
        return redirect(url_for("recipes.dashboard"))

    user_recipe_count = Recipe.query.filter_by(owner_id=session["user_id"]).count()
    user_favorite_count = Favorite.query.filter_by(user_id=session["user_id"]).count()
    user_review_count = Review.query.filter_by(user_id=session["user_id"]).count()
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
        minutes, servings, error = validate_recipe_form(request.form, require_image=False)

        if error:
            flash(error, "error")
            return redirect(url_for("recipes.edit_recipe", recipe_id=recipe_id))

        old_image_url = recipe.image_url
        try:
            category = get_or_create_category(request.form["cuisine"].strip())
            recipe.title = request.form["title"]
            recipe.description = request.form["description"]
            recipe.category_id = category.id
            recipe.difficulty = request.form["difficulty"]
            recipe.minutes = minutes
            recipe.servings = servings
            if new_image:
                recipe.image_url = new_image
            recipe.ingredients = request.form["ingredients"]
            recipe.steps = request.form["steps"]
            recipe.nutrition = request.form.get("nutrition", "").strip() or None
            db.session.commit()
        except SQLAlchemyError:
            db.session.rollback()
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
        db.session.delete(recipe)
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        flash("We could not delete that recipe. Please try again.", "error")
        return redirect(url_for("recipes.dashboard"))

    delete_uploaded_image(image_url)

    flash("Recipe deleted.", "success")
    return redirect(url_for("recipes.dashboard"))


@recipes_bp.route("/recipes/<int:recipe_id>/download")
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
        # Log the real exception to the terminal for debugging, but never
        # show the visitor a raw 500 - send them back with a message
        # instead, matching how every other write path in this app fails.
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