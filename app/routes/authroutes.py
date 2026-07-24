import re
import string

import pymysql
from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from app.controllers.authcontroller import create_user, verify_user
from app.db import get_db
from app.decorators import rate_limit

auth_bp = Blueprint("auth", __name__)

MIN_PASSWORD_LENGTH = 8

# Deliberately simple (not a full RFC 5322 parser): just enough to reject
# obvious typos and junk like "not-an-email" or "bob@" without also
# rejecting real addresses with pluses, dots or subdomains.
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _password_error(password):
    """Returns an error message if the password is too weak, or None if
    it's fine. Enforced here (not just via the form's minlength/pattern
    attributes) since client-side checks are trivially bypassed with
    disabled JS, a raw POST, or curl."""
    if len(password) < MIN_PASSWORD_LENGTH:
        return f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
    if not any(char in string.punctuation for char in password):
        return "Password must include at least one special character (e.g. ! @ # $ %)."
    return None


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
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        if not EMAIL_PATTERN.match(email):
            flash("Please enter a valid email address.", "error")
            return render_template("register.html")

        password_error = _password_error(password)
        if password_error:
            flash(password_error, "error")
            return render_template("register.html")
        try:
            create_user(request.form["name"], email, password)
            flash("Account created. You can log in now.", "success")
            return redirect(url_for("auth.login"))
        except pymysql.err.IntegrityError:
            get_db().rollback()
            flash("That email is already registered.", "error")
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