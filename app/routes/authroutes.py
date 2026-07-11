from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from sqlalchemy.exc import IntegrityError

from app.controllers.authcontroller import create_user, verify_user
from app.decorators import rate_limit
from app.models import db

auth_bp = Blueprint("auth", __name__)

MIN_PASSWORD_LENGTH = 6


@auth_bp.route("/login", methods=["GET", "POST"])
@rate_limit(max_attempts=8, window_seconds=300)
def login():
    if request.method == "POST":
        user = verify_user(request.form["email"], request.form["password"])
        if user:
            session["user_id"] = user.id
            session["user_name"] = user.name
            session["user_role"] = user.role
            flash("Welcome back to the kitchen.", "success")
            return redirect(url_for("recipes.dashboard"))
        flash("That email and password did not match.", "error")
    return render_template("login.html")


@auth_bp.route("/register", methods=["GET", "POST"])
@rate_limit(max_attempts=8, window_seconds=300)
def register():
    if request.method == "POST":
        password = request.form.get("password", "")
        if len(password) < MIN_PASSWORD_LENGTH:
            # The form also enforces minlength=6 client-side, but that's
            # trivially bypassed (disabled JS, a raw POST, curl, etc.), so
            # the real check has to live here too.
            flash(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.", "error")
            return render_template("register.html")
        try:
            create_user(request.form["name"], request.form["email"], password)
            flash("Account created. You can log in now.", "success")
            return redirect(url_for("auth.login"))
        except IntegrityError:
            db.session.rollback()
            flash("That email is already registered.", "error")
        except ValueError as exc:
            db.session.rollback()
            flash(str(exc), "error")
    return render_template("register.html")


@auth_bp.route("/logout")
def logout():
    session.clear()
    flash("You have been signed out.", "success")
    return redirect(url_for("main.home"))


@auth_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        flash("Demo reset link prepared. In a live site this would send email.", "success")
    return render_template("forgot_password.html")