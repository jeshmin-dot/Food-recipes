from flask import Blueprint, flash, redirect, render_template, session, url_for

from app.db import Row, execute, query_all, query_one
from app.decorators import admin_required
from app.services import delete_uploaded_image, get_recipe

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def _count(table):
    return query_one(f"SELECT COUNT(*) AS total FROM {table}")["total"]


@admin_bp.route("")
@admin_required
def admin_dashboard():
    return render_template(
        "admin/dashboard.html",
        user_count=_count("users"),
        recipe_count=_count("recipes"),
        category_count=_count("categories"),
        review_count=_count("reviews"),
    )


@admin_bp.route("/users")
@admin_required
def admin_users():
    users = query_all("SELECT * FROM users ORDER BY name")
    return render_template("admin/users.html", users=users)


@admin_bp.route("/users/<int:user_id>/delete", methods=["POST"])
@admin_required
def admin_delete_user(user_id):
    if user_id == session.get("user_id"):
        flash("You can't delete your own account from here.", "error")
        return redirect(url_for("admin.admin_users"))
    user = query_one("SELECT id FROM users WHERE id = %s", (user_id,))
    if user:
        # Keep the user's recipes but detach them, then remove the rows that
        # reference the user, then the user themselves.
        execute("UPDATE recipes SET owner_id = NULL WHERE owner_id = %s", (user_id,))
        execute("DELETE FROM favorites WHERE user_id = %s", (user_id,))
        execute("DELETE FROM reviews WHERE user_id = %s", (user_id,))
        execute("DELETE FROM meal_plan_entries WHERE user_id = %s", (user_id,))
        execute("DELETE FROM users WHERE id = %s", (user_id,))
        flash("User removed.", "success")
    return redirect(url_for("admin.admin_users"))


@admin_bp.route("/recipes")
@admin_required
def admin_recipes():
    recipes = query_all(
        """
        SELECT r.id, r.title, r.difficulty, r.minutes, r.servings, r.image_url,
               r.owner_id, c.name AS cuisine, u.name AS owner_name
        FROM recipes r
        JOIN categories c ON c.id = r.category_id
        LEFT JOIN users u ON u.id = r.owner_id
        ORDER BY r.created_at DESC
        """
    )
    for recipe in recipes:
        recipe["owner"] = Row(name=recipe["owner_name"]) if recipe.get("owner_name") else None
    return render_template("admin/recipes.html", recipes=recipes)


@admin_bp.route("/recipes/<int:recipe_id>/delete", methods=["POST"])
@admin_required
def admin_delete_recipe(recipe_id):
    recipe = get_recipe(recipe_id)
    if recipe:
        image_url = recipe.image_url
        execute("DELETE FROM favorites WHERE recipe_id = %s", (recipe_id,))
        execute("DELETE FROM reviews WHERE recipe_id = %s", (recipe_id,))
        execute("DELETE FROM meal_plan_entries WHERE recipe_id = %s", (recipe_id,))
        execute("DELETE FROM recipes WHERE id = %s", (recipe_id,))
        delete_uploaded_image(image_url)
        flash("Recipe removed.", "success")
    return redirect(url_for("admin.admin_recipes"))


@admin_bp.route("/reviews")
@admin_required
def admin_reviews():
    reviews = query_all(
        """
        SELECT rv.id, rv.rating, rv.comment, rv.created_at,
               u.name AS user_name, rc.title AS recipe_title
        FROM reviews rv
        JOIN users u ON u.id = rv.user_id
        JOIN recipes rc ON rc.id = rv.recipe_id
        ORDER BY rv.created_at DESC
        """
    )
    for review in reviews:
        review["user"] = Row(name=review["user_name"])
        review["recipe"] = Row(title=review["recipe_title"])
    return render_template("admin/reviews.html", reviews=reviews)


@admin_bp.route("/reviews/<int:review_id>/delete", methods=["POST"])
@admin_required
def admin_delete_review(review_id):
    review = query_one("SELECT id FROM reviews WHERE id = %s", (review_id,))
    if review:
        execute("DELETE FROM reviews WHERE id = %s", (review_id,))
        flash("Review removed.", "success")
    return redirect(url_for("admin.admin_reviews"))