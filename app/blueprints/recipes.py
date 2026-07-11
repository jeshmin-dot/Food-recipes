import random

from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for
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