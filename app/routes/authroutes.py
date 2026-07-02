from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from sqlite3 import IntegrityError

from app.controllers.authcontroller import create_user, verify_user

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = verify_user(request.form["email"], request.form["password"])
        if user:
            session["user_id"] = user["id"]
            session["user_name"] = user["name"]
            flash("Welcome back to the kitchen.", "success")
            return redirect(url_for("dashboard"))
        flash("That email and password did not match.", "error")
    return render_template("login.html")


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        try:
            create_user(request.form["name"], request.form["email"], request.form["password"])
            flash("Account created. You can log in now.", "success")
            return redirect(url_for("auth.login"))
        except IntegrityError:
            flash("That email is already registered.", "error")
    return render_template("register.html")


@auth_bp.route("/logout")
def logout():
    session.clear()
    flash("You have been signed out.", "success")
    return redirect(url_for("home"))
