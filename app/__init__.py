import secrets
from datetime import datetime

from flask import Flask, abort, flash, redirect, render_template, request, session, url_for
from sqlalchemy.exc import SQLAlchemyError

import config
from app.controllers.database import initialize_database
from app.models import Recipe, db
from app.routes.authroutes import auth_bp


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = config.SECRET_KEY
    app.config["DEBUG"] = config.DEBUG
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{config.DATABASE_PATH}"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)
    with app.app_context():
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
        return Recipe.query.order_by(Recipe.created_at.desc()).all()

    def get_recipe(recipe_id):
        return Recipe.query.get(recipe_id)

    @app.route("/")
    def home():
        recipes = all_recipes()
        featured = recipes[0] if recipes else None
        cuisines = {recipe.cuisine for recipe in recipes}
        avg_minutes = round(sum(r.minutes for r in recipes) / len(recipes)) if recipes else 0
        return render_template(
            "home.html",
            recipes=recipes,
            featured=featured,
            recipe_count=len(recipes),
            cuisine_count=len(cuisines),
            avg_minutes=avg_minutes,
        )

    @app.route("/recipes")
    def recipes():
        recipe_list = all_recipes()
        query = request.args.get("q", "").strip().lower()
        if query:
            recipe_list = [
                recipe
                for recipe in recipe_list
                if query in recipe.title.lower()
                or query in recipe.cuisine.lower()
                or query in recipe.ingredients.lower()
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
                recipe = Recipe(
                    title=request.form["title"],
                    description=request.form["description"],
                    cuisine=request.form["cuisine"],
                    difficulty=request.form["difficulty"],
                    minutes=minutes,
                    servings=servings,
                    image_url=request.form["image_url"],
                    ingredients=request.form["ingredients"],
                    steps=request.form["steps"],
                    owner_id=session["user_id"],
                )
                db.session.add(recipe)
                db.session.commit()
            except SQLAlchemyError:
                db.session.rollback()
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
        if recipe.owner_id != session["user_id"]:
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
                recipe.title = request.form["title"]
                recipe.description = request.form["description"]
                recipe.cuisine = request.form["cuisine"]
                recipe.difficulty = request.form["difficulty"]
                recipe.minutes = minutes
                recipe.servings = servings
                recipe.image_url = request.form["image_url"]
                recipe.ingredients = request.form["ingredients"]
                recipe.steps = request.form["steps"]
                db.session.commit()
            except SQLAlchemyError:
                db.session.rollback()
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
        if recipe.owner_id != session["user_id"]:
            flash("You can only delete recipes you added.", "error")
            return redirect(url_for("dashboard"))

        try:
            db.session.delete(recipe)
            db.session.commit()
        except SQLAlchemyError:
            db.session.rollback()
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
