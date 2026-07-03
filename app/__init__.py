import secrets
import sqlite3
from datetime import datetime

from flask import Flask, abort, flash, redirect, render_template, request, session, url_for

import config
from app.controllers.database import initialize_database
from app.database import get_connection
from app.routes.authroutes import auth_bp


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = config.SECRET_KEY
    app.config["DEBUG"] = config.DEBUG

    initialize_database()
    app.register_blueprint(auth_bp)

    def get_csrf_token():
        token = session.get("csrf_token")
        if not token:
            token = secrets.token_urlsafe(32)
            session["csrf_token"] = token
        return token

    @app.context_processor
    def inject_layout_data():
        return {
            "app_name": config.APP_NAME,
            "year": datetime.now().year,
            "csrf_token": get_csrf_token,
            "current_user": session.get("user_name"),
        }

    @app.before_request
    def protect_forms():
        if request.method == "POST":
            sent = request.form.get("csrf_token", "")
            stored = session.get("csrf_token", "")
            if not sent or not stored or not secrets.compare_digest(sent, stored):
                abort(400, description="Invalid form token.")

    def all_recipes():
        try:
            with get_connection() as db:
                return db.execute("SELECT * FROM recipes ORDER BY created_at DESC").fetchall()
        except sqlite3.Error:
            return []

    def get_recipe(recipe_id):
        try:
            with get_connection() as db:
                return db.execute("SELECT * FROM recipes WHERE id = ?", (recipe_id,)).fetchone()
        except sqlite3.Error:
            return None

    @app.route("/")
    def home():
        recipes = all_recipes()
        featured = recipes[0] if recipes else None
        return render_template("home.html", recipes=recipes, featured=featured)

    @app.route("/recipes")
    def recipes():
        recipe_list = all_recipes()
        query = request.args.get("q", "").strip().lower()
        if query:
            recipe_list = [
                recipe
                for recipe in recipe_list
                if query in recipe["title"].lower()
                or query in recipe["cuisine"].lower()
                or query in recipe["ingredients"].lower()
            ]
        return render_template("recipes.html", recipes=recipe_list, query=query)

    @app.route("/cook-mode")
    def cook_mode():
        return render_template("cook_mode.html", recipes=all_recipes())

    @app.route("/pantry", methods=["GET", "POST"])
    def cookies():
        if request.method == "POST":
            response = redirect(url_for("cookies"))
            response.set_cookie("pantry_style", request.form.get("pantry_style", "quick"), max_age=60 * 60 * 24 * 90)
            response.set_cookie("serving_size", request.form.get("serving_size", "4"), max_age=60 * 60 * 24 * 90)
            flash("Pantry preferences saved.", "success")
            return response
        return render_template(
            "cookies.html",
            pantry_style=request.cookies.get("pantry_style", "quick"),
            serving_size=request.cookies.get("serving_size", "4"),
        )

    @app.route("/dashboard", methods=["GET", "POST"])
    def dashboard():
        if not session.get("user_id"):
            flash("Log in to add recipes.", "error")
            return redirect(url_for("auth.login"))
        if request.method == "POST":
            required = ["title", "description", "cuisine", "difficulty", "minutes",
                        "servings", "image_url", "ingredients", "steps"]
            missing = [field for field in required if not request.form.get(field, "").strip()]
            try:
                minutes = int(request.form.get("minutes", ""))
                servings = int(request.form.get("servings", ""))
            except ValueError:
                minutes = servings = None

            if missing or minutes is None:
                flash("Please fill in every field with valid values before saving.", "error")
                return redirect(url_for("dashboard"))

            try:
                with get_connection() as db:
                    db.execute(
                        """
                        INSERT INTO recipes
                        (title, description, cuisine, difficulty, minutes, servings, image_url, ingredients, steps, owner_id)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            request.form["title"],
                            request.form["description"],
                            request.form["cuisine"],
                            request.form["difficulty"],
                            minutes,
                            servings,
                            request.form["image_url"],
                            request.form["ingredients"],
                            request.form["steps"],
                            session["user_id"],
                        ),
                    )
            except sqlite3.Error:
                flash("We could not save that recipe. Please try again.", "error")
                return redirect(url_for("dashboard"))

            flash("Recipe added to the garden.", "success")
            return redirect(url_for("dashboard"))
        return render_template("dashboard.html", recipes=all_recipes())

    @app.route("/recipes/<int:recipe_id>/edit", methods=["GET", "POST"])
    def edit_recipe(recipe_id):
        if not session.get("user_id"):
            flash("Log in to manage recipes.", "error")
            return redirect(url_for("auth.login"))

        recipe = get_recipe(recipe_id)
        if recipe is None:
            flash("That recipe no longer exists.", "error")
            return redirect(url_for("dashboard"))
        if recipe["owner_id"] != session["user_id"]:
            flash("You can only edit recipes you added.", "error")
            return redirect(url_for("dashboard"))

        if request.method == "POST":
            required = ["title", "description", "cuisine", "difficulty", "minutes",
                        "servings", "image_url", "ingredients", "steps"]
            missing = [field for field in required if not request.form.get(field, "").strip()]
            try:
                minutes = int(request.form.get("minutes", ""))
                servings = int(request.form.get("servings", ""))
            except ValueError:
                minutes = servings = None

            if missing or minutes is None:
                flash("Please fill in every field with valid values before saving.", "error")
                return redirect(url_for("edit_recipe", recipe_id=recipe_id))

            try:
                with get_connection() as db:
                    db.execute(
                        """
                        UPDATE recipes
                        SET title = ?, description = ?, cuisine = ?, difficulty = ?,
                            minutes = ?, servings = ?, image_url = ?, ingredients = ?, steps = ?
                        WHERE id = ?
                        """,
                        (
                            request.form["title"],
                            request.form["description"],
                            request.form["cuisine"],
                            request.form["difficulty"],
                            minutes,
                            servings,
                            request.form["image_url"],
                            request.form["ingredients"],
                            request.form["steps"],
                            recipe_id,
                        ),
                    )
            except sqlite3.Error:
                flash("We could not update that recipe. Please try again.", "error")
                return redirect(url_for("edit_recipe", recipe_id=recipe_id))

            flash("Recipe updated.", "success")
            return redirect(url_for("dashboard"))

        return render_template("edit_recipe.html", recipe=recipe)

    @app.route("/recipes/<int:recipe_id>/delete", methods=["POST"])
    def delete_recipe(recipe_id):
        if not session.get("user_id"):
            flash("Log in to manage recipes.", "error")
            return redirect(url_for("auth.login"))

        recipe = get_recipe(recipe_id)
        if recipe is None:
            flash("That recipe no longer exists.", "error")
            return redirect(url_for("dashboard"))
        if recipe["owner_id"] != session["user_id"]:
            flash("You can only delete recipes you added.", "error")
            return redirect(url_for("dashboard"))

        try:
            with get_connection() as db:
                db.execute("DELETE FROM recipes WHERE id = ?", (recipe_id,))
        except sqlite3.Error:
            flash("We could not delete that recipe. Please try again.", "error")
            return redirect(url_for("dashboard"))

        flash("Recipe deleted.", "success")
        return redirect(url_for("dashboard"))

    @app.route("/forgot-password", methods=["GET", "POST"])
    def forgot_password():
        if request.method == "POST":
            flash("Demo reset link prepared. In a live site this would send email.", "success")
        return render_template("forgot_password.html")

    @app.errorhandler(404)
    def handle_not_found(_error):
        return render_template(
            "error.html",
            error_title="Page not found",
            error_message="We couldn't find the page you were looking for.",
        ), 404

    return app
