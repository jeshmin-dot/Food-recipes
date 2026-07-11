from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from sqlalchemy.exc import SQLAlchemyError

from app.decorators import login_required
from app.models import Favorite, Review, User, db

account_bp = Blueprint("account", __name__)

MIN_PASSWORD_LENGTH = 6


@account_bp.route("/favorites")
@login_required
def favorites():
    favorite_rows = Favorite.query.filter_by(user_id=session["user_id"]).all()
    favorite_recipes = [row.recipe for row in favorite_rows]
    favorite_ids = {row.recipe_id for row in favorite_rows}
    return render_template("favorites.html", recipes=favorite_recipes, favorite_ids=favorite_ids)


@account_bp.route("/profile")
@login_required
def profile():
    user = db.session.get(User, session["user_id"])
    favorite_rows = Favorite.query.filter_by(user_id=session["user_id"]).all()
    favorite_recipes = [row.recipe for row in favorite_rows]
    review_rows = Review.query.filter_by(user_id=session["user_id"]).all()
    return render_template(
        "profile.html",
        profile_user=user,
        uploaded_recipes=user.recipes,
        favorite_recipes=favorite_recipes,
        review_count=len(review_rows),
    )


@account_bp.route("/account", methods=["GET", "POST"])
@login_required
def account_settings():
    user = db.session.get(User, session["user_id"])

    if request.method == "POST":
        form_type = request.form.get("form_type")

        if form_type == "profile":
            new_name = request.form.get("name", "").strip()
            new_email = request.form.get("email", "").strip()
            if not new_name or not new_email:
                flash("Name and email cannot be empty.", "error")
                return redirect(url_for("account.account_settings"))
            try:
                user.name = new_name
                user.email = new_email
                db.session.commit()
                session["user_name"] = user.name
                flash("Profile updated.", "success")
            except (SQLAlchemyError, ValueError):
                db.session.rollback()
                flash("Could not update profile - that email may already be in use.", "error")
            return redirect(url_for("account.account_settings"))

        if form_type == "password":
            from werkzeug.security import check_password_hash, generate_password_hash

            current_password = request.form.get("current_password", "")
            new_password = request.form.get("new_password", "")
            if not check_password_hash(user.password_hash, current_password):
                flash("Current password is incorrect.", "error")
                return redirect(url_for("account.account_settings"))
            if len(new_password) < MIN_PASSWORD_LENGTH:
                flash(f"New password must be at least {MIN_PASSWORD_LENGTH} characters.", "error")
                return redirect(url_for("account.account_settings"))
            user.password_hash = generate_password_hash(new_password)
            db.session.commit()
            flash("Password changed successfully.", "success")
            return redirect(url_for("account.account_settings"))

    return render_template("account.html", profile_user=user)