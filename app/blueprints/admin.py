from flask import Blueprint, flash, redirect, render_template, session, url_for

from app.decorators import admin_required
from app.models import Category, Recipe, Review, User, db
from app.services import all_recipes, delete_uploaded_image, get_recipe

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.route("")
@admin_required
def admin_dashboard():
    return render_template(
        "admin/dashboard.html",
        user_count=User.query.count(),
        recipe_count=Recipe.query.count(),
        category_count=Category.query.count(),
        review_count=Review.query.count(),
    )


@admin_bp.route("/users")
@admin_required
def admin_users():
    return render_template("admin/users.html", users=User.query.order_by(User.name).all())


@admin_bp.route("/users/<int:user_id>/delete", methods=["POST"])
@admin_required
def admin_delete_user(user_id):
    if user_id == session.get("user_id"):
        flash("You can't delete your own account from here.", "error")
        return redirect(url_for("admin.admin_users"))
    user = db.session.get(User, user_id)
    if user:
        Recipe.query.filter_by(owner_id=user_id).update({"owner_id": None})
        db.session.delete(user)
        db.session.commit()
        flash("User removed.", "success")
    return redirect(url_for("admin.admin_users"))


@admin_bp.route("/recipes")
@admin_required
def admin_recipes():
    return render_template("admin/recipes.html", recipes=all_recipes())


@admin_bp.route("/recipes/<int:recipe_id>/delete", methods=["POST"])
@admin_required
def admin_delete_recipe(recipe_id):
    recipe = get_recipe(recipe_id)
    if recipe:
        image_url = recipe.image_url
        db.session.delete(recipe)
        db.session.commit()
        delete_uploaded_image(image_url)
        flash("Recipe removed.", "success")
    return redirect(url_for("admin.admin_recipes"))


@admin_bp.route("/reviews")
@admin_required
def admin_reviews():
    return render_template("admin/reviews.html", reviews=Review.query.order_by(Review.created_at.desc()).all())


@admin_bp.route("/reviews/<int:review_id>/delete", methods=["POST"])
@admin_required
def admin_delete_review(review_id):
    review = db.session.get(Review, review_id)
    if review:
        db.session.delete(review)
        db.session.commit()
        flash("Review removed.", "success")
    return redirect(url_for("admin.admin_reviews"))