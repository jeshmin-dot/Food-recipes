import pymysql
from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from app.db import execute, get_db, query_all, query_one
from app.decorators import login_required
from app.services import RECIPE_SELECT

account_bp = Blueprint("account", __name__)

MIN_PASSWORD_LENGTH = 6


def _favorite_recipes(user_id):
    return query_all(
        RECIPE_SELECT + " JOIN favorites f ON f.recipe_id = r.id WHERE f.user_id = %s ORDER BY f.created_at DESC",
        (user_id,),
    )


@account_bp.route("/favorites")
@login_required
def favorites():
    recipes = _favorite_recipes(session["user_id"])
    favorite_ids = {row.id for row in recipes}
    return render_template("favorites.html", recipes=recipes, favorite_ids=favorite_ids)


@account_bp.route("/profile")
@login_required
def profile():
    user = query_one("SELECT * FROM users WHERE id = %s", (session["user_id"],))
    uploaded_recipes = query_all(
        RECIPE_SELECT + " WHERE r.owner_id = %s ORDER BY r.created_at DESC", (session["user_id"],)
    )
    favorite_recipes = _favorite_recipes(session["user_id"])
    review_count = query_one(
        "SELECT COUNT(*) AS total FROM reviews WHERE user_id = %s", (session["user_id"],)
    )["total"]
    return render_template(
        "profile.html",
        profile_user=user,
        uploaded_recipes=uploaded_recipes,
        favorite_recipes=favorite_recipes,
        review_count=review_count,
    )


@account_bp.route("/account", methods=["GET", "POST"])
@login_required
def account_settings():
    user = query_one("SELECT * FROM users WHERE id = %s", (session["user_id"],))

    if request.method == "POST":
        form_type = request.form.get("form_type")

        if form_type == "profile":
            new_name = request.form.get("name", "").strip()
            new_email = request.form.get("email", "").strip().lower()
            if not new_name or not new_email:
                flash("Name and email cannot be empty.", "error")
                return redirect(url_for("account.account_settings"))
            try:
                execute(
                    "UPDATE users SET name = %s, email = %s WHERE id = %s",
                    (new_name, new_email, session["user_id"]),
                )
                session["user_name"] = new_name
                flash("Profile updated.", "success")
            except pymysql.MySQLError:
                get_db().rollback()
                flash("Could not update profile - that email may already be in use.", "error")
            return redirect(url_for("account.account_settings"))

        if form_type == "password":
            from werkzeug.security import check_password_hash, generate_password_hash

            current_password = request.form.get("current_password", "")
            new_password = request.form.get("new_password", "")
            if not check_password_hash(user["password_hash"], current_password):
                flash("Current password is incorrect.", "error")
                return redirect(url_for("account.account_settings"))
            if len(new_password) < MIN_PASSWORD_LENGTH:
                flash(f"New password must be at least {MIN_PASSWORD_LENGTH} characters.", "error")
                return redirect(url_for("account.account_settings"))
            execute(
                "UPDATE users SET password_hash = %s WHERE id = %s",
                (generate_password_hash(new_password), session["user_id"]),
            )
            flash("Password changed successfully.", "success")
            return redirect(url_for("account.account_settings"))

    return render_template("account.html", profile_user=user)