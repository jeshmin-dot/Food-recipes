import os
import random
import secrets
from datetime import datetime
from functools import wraps

from flask import Flask, abort, flash, redirect, render_template, request, session, url_for
from sqlalchemy import or_
from sqlalchemy.exc import SQLAlchemyError

import config
from app.controllers.database import initialize_database
from app.database import get_or_create_category
from app.models import Category, Favorite, MealPlanEntry, Recipe, Review, User, db
from app.routes.authroutes import auth_bp
from app.utils import save_uploaded_image

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
MEALS = ["Breakfast", "Lunch", "Dinner"]
REQUIRED_RECIPE_FIELDS = ["title", "description", "cuisine", "difficulty", "minutes", "servings", "ingredients", "steps"]


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = config.SECRET_KEY
    app.config["DEBUG"] = config.DEBUG
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{config.DATABASE_PATH}"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SESSION_COOKIE_HTTPONLY"] = config.SESSION_COOKIE_HTTPONLY
    app.config["SESSION_COOKIE_SAMESITE"] = config.SESSION_COOKIE_SAMESITE
    app.config["SESSION_COOKIE_SECURE"] = config.SESSION_COOKIE_SECURE

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
            "is_admin": session.get("user_role") == "admin",
        }

    @app.before_request
    def protect_forms():
        if request.method == "POST":
            sent = request.form.get("csrf_token", "")
            stored = session.get("csrf_token", "")
            if not sent or not stored or not secrets.compare_digest(sent, stored):
                abort(400, description="Invalid form token.")

    def login_required(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not session.get("user_id"):
                flash("Please log in to continue.", "error")
                return redirect(url_for("auth.login"))
            return view(*args, **kwargs)
        return wrapped

    def admin_required(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if session.get("user_role") != "admin":
                abort(403, description="You don't have permission to view this page.")
            return view(*args, **kwargs)
        return wrapped

    def all_recipes():
        return Recipe.query.order_by(Recipe.created_at.desc()).all()

    def get_recipe(recipe_id):
        return Recipe.query.get(recipe_id)

    def time_matches(recipe, time_bucket):
        if time_bucket == "under20":
            return recipe.minutes < 20
        if time_bucket == "20to40":
            return 20 <= recipe.minutes <= 40
        if time_bucket == "over40":
            return recipe.minutes > 40
        return True

    def resolve_recipe_image(form, files):
        upload_folder = os.path.join(app.static_folder, "uploads")
        uploaded_name = save_uploaded_image(files.get("image_file"), upload_folder)
        if uploaded_name:
            return url_for("static", filename=f"uploads/{uploaded_name}")
        url_value = form.get("image_url", "").strip()
        return url_value or None

    def validate_recipe_form(form, require_image):
        """Shared validation for both the add and edit recipe forms.

        Returns (minutes, servings, error_message). error_message is None
        when everything's valid; minutes/servings are None if invalid.
        """
        missing = [field for field in REQUIRED_RECIPE_FIELDS if not form.get(field, "").strip()]
        try:
            minutes = int(form.get("minutes", ""))
            servings = int(form.get("servings", ""))
        except ValueError:
            minutes = servings = None

        if require_image and not form.get("image_url", "").strip():
            missing.append("image")

        if missing or minutes is None:
            return None, None, "Please fill in every field with valid values before saving."
        return minutes, servings, None

    @app.route("/")
    def home():
        recipes = all_recipes()
        featured = recipes[0] if recipes else None
        cuisines = sorted({recipe.cuisine for recipe in recipes})
        avg_minutes = round(sum(r.minutes for r in recipes) / len(recipes)) if recipes else 0
        favorite_ids = set()
        if session.get("user_id"):
            favorite_ids = {f.recipe_id for f in Favorite.query.filter_by(user_id=session["user_id"]).all()}
        return render_template(
            "home.html",
            recipes=recipes,
            featured=featured,
            recipe_count=len(recipes),
            cuisine_count=len(cuisines),
            avg_minutes=avg_minutes,
            all_cuisines=cuisines,
            favorite_ids=favorite_ids,
        )

    @app.route("/recipes")
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

    @app.route("/recipes/random")
    def random_recipe():
        recipes = all_recipes()
        if not recipes:
            flash("No recipes available yet.", "error")
            return redirect(url_for("recipes"))
        choice = random.choice(recipes)
        return redirect(url_for("recipe_detail", recipe_id=choice.id))

    @app.route("/recipes/<int:recipe_id>")
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

    @app.route("/recipes/<int:recipe_id>/favorite", methods=["POST"])
    @login_required
    def toggle_favorite(recipe_id):
        recipe = get_recipe(recipe_id)
        if recipe is None:
            flash("That recipe no longer exists.", "error")
            return redirect(url_for("recipes"))

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

        return redirect(url_for("recipe_detail", recipe_id=recipe_id))

    @app.route("/favorites")
    @login_required
    def favorites():
        favorite_rows = Favorite.query.filter_by(user_id=session["user_id"]).all()
        favorite_recipes = [row.recipe for row in favorite_rows]
        favorite_ids = {row.recipe_id for row in favorite_rows}
        return render_template("favorites.html", recipes=favorite_recipes, favorite_ids=favorite_ids)

    @app.route("/profile")
    @login_required
    def profile():
        user = User.query.get(session["user_id"])
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

    @app.route("/account", methods=["GET", "POST"])
    @login_required
    def account_settings():
        user = User.query.get(session["user_id"])

        if request.method == "POST":
            form_type = request.form.get("form_type")

            if form_type == "profile":
                new_name = request.form.get("name", "").strip()
                new_email = request.form.get("email", "").strip()
                if not new_name or not new_email:
                    flash("Name and email cannot be empty.", "error")
                    return redirect(url_for("account_settings"))
                try:
                    user.name = new_name
                    user.email = new_email
                    db.session.commit()
                    session["user_name"] = user.name
                    flash("Profile updated.", "success")
                except (SQLAlchemyError, ValueError):
                    db.session.rollback()
                    flash("Could not update profile - that email may already be in use.", "error")
                return redirect(url_for("account_settings"))

            if form_type == "password":
                from werkzeug.security import check_password_hash, generate_password_hash

                current_password = request.form.get("current_password", "")
                new_password = request.form.get("new_password", "")
                if not check_password_hash(user.password_hash, current_password):
                    flash("Current password is incorrect.", "error")
                    return redirect(url_for("account_settings"))
                if len(new_password) < 6:
                    flash("New password must be at least 6 characters.", "error")
                    return redirect(url_for("account_settings"))
                user.password_hash = generate_password_hash(new_password)
                db.session.commit()
                flash("Password changed successfully.", "success")
                return redirect(url_for("account_settings"))

        return render_template("account.html", profile_user=user)

    @app.route("/recipes/<int:recipe_id>/review", methods=["POST"])
    @login_required
    def add_review(recipe_id):
        recipe = get_recipe(recipe_id)
        if recipe is None:
            flash("That recipe no longer exists.", "error")
            return redirect(url_for("recipes"))

        try:
            rating = int(request.form.get("rating", ""))
        except ValueError:
            rating = None

        if rating is None or rating < 1 or rating > 5:
            flash("Please choose a rating between 1 and 5.", "error")
            return redirect(url_for("recipe_detail", recipe_id=recipe_id))

        try:
            review = Review(
                user_id=session["user_id"],
                recipe_id=recipe_id,
                rating=rating,
                comment=request.form.get("comment", "").strip() or None,
            )
            db.session.add(review)
            db.session.commit()
        except SQLAlchemyError:
            db.session.rollback()
            flash("We could not save your review. Please try again.", "error")
            return redirect(url_for("recipe_detail", recipe_id=recipe_id))

        flash("Thanks for your review!", "success")
        return redirect(url_for("recipe_detail", recipe_id=recipe_id))

    @app.route("/meal-planner", methods=["GET", "POST"])
    @login_required
    def meal_planner():
        if request.method == "POST":
            try:
                for day in DAYS:
                    for meal in MEALS:
                        field_name = f"{day}_{meal}"
                        recipe_id = request.form.get(field_name, "").strip()

                        existing = MealPlanEntry.query.filter_by(
                            user_id=session["user_id"], day_of_week=day, meal_type=meal
                        ).first()

                        if not recipe_id:
                            if existing:
                                db.session.delete(existing)
                            continue

                        if existing:
                            existing.recipe_id = int(recipe_id)
                        else:
                            db.session.add(
                                MealPlanEntry(
                                    user_id=session["user_id"],
                                    recipe_id=int(recipe_id),
                                    day_of_week=day,
                                    meal_type=meal,
                                )
                            )
                db.session.commit()
                flash("Meal plan saved.", "success")
            except SQLAlchemyError:
                db.session.rollback()
                flash("We could not save your meal plan. Please try again.", "error")
            return redirect(url_for("meal_planner"))

        entries = MealPlanEntry.query.filter_by(user_id=session["user_id"]).all()
        plan = {(e.day_of_week, e.meal_type): e.recipe for e in entries}
        return render_template(
            "meal_planner.html",
            days=DAYS,
            meals=MEALS,
            plan=plan,
            all_recipes=all_recipes(),
        )

    @app.route("/meal-planner/shopping-list")
    @login_required
    def shopping_list():
        entries = MealPlanEntry.query.filter_by(user_id=session["user_id"]).all()
        ingredient_lines = []
        for entry in entries:
            for line in entry.recipe.ingredients.split("\n"):
                line = line.strip()
                if line:
                    ingredient_lines.append(line)

        counts = {}
        for line in ingredient_lines:
            key = line.lower()
            counts[key] = counts.get(key, (line, 0))
            counts[key] = (counts[key][0], counts[key][1] + 1)

        combined = sorted(counts.values(), key=lambda pair: pair[0].lower())
        return render_template("shopping_list.html", ingredients=combined, has_plan=bool(entries))

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
    @login_required
    def dashboard():
        if request.method == "POST":
            image_url = resolve_recipe_image(request.form, request.files)
            minutes, servings, error = validate_recipe_form(request.form, require_image=not image_url)

            if error:
                flash(error, "error")
                return redirect(url_for("dashboard"))

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
                return redirect(url_for("dashboard"))

            flash("Recipe added to the garden.", "success")
            return redirect(url_for("dashboard"))

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

    @app.route("/recipes/<int:recipe_id>/edit", methods=["GET", "POST"])
    @login_required
    def edit_recipe(recipe_id):
        recipe = get_recipe(recipe_id)
        if recipe is None:
            flash("That recipe no longer exists.", "error")
            return redirect(url_for("dashboard"))
        if recipe.owner_id != session["user_id"] and session.get("user_role") != "admin":
            abort(403, description="You can only edit recipes you added.")

        if request.method == "POST":
            new_image = resolve_recipe_image(request.form, request.files)
            minutes, servings, error = validate_recipe_form(request.form, require_image=False)

            if error:
                flash(error, "error")
                return redirect(url_for("edit_recipe", recipe_id=recipe_id))

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
                return redirect(url_for("edit_recipe", recipe_id=recipe_id))

            flash("Recipe updated.", "success")
            return redirect(url_for("dashboard"))

        return render_template("edit_recipe.html", recipe=recipe)

    @app.route("/recipes/<int:recipe_id>/delete", methods=["POST"])
    @login_required
    def delete_recipe(recipe_id):
        recipe = get_recipe(recipe_id)
        if recipe is None:
            flash("That recipe no longer exists.", "error")
            return redirect(url_for("dashboard"))
        if recipe.owner_id != session["user_id"] and session.get("user_role") != "admin":
            abort(403, description="You can only delete recipes you added.")

        try:
            db.session.delete(recipe)
            db.session.commit()
        except SQLAlchemyError:
            db.session.rollback()
            flash("We could not delete that recipe. Please try again.", "error")
            return redirect(url_for("dashboard"))

        flash("Recipe deleted.", "success")
        return redirect(url_for("dashboard"))

    @app.route("/admin")
    @admin_required
    def admin_dashboard():
        return render_template(
            "admin/dashboard.html",
            user_count=User.query.count(),
            recipe_count=Recipe.query.count(),
            category_count=Category.query.count(),
            review_count=Review.query.count(),
        )

    @app.route("/admin/users")
    @admin_required
    def admin_users():
        return render_template("admin/users.html", users=User.query.order_by(User.name).all())

    @app.route("/admin/users/<int:user_id>/delete", methods=["POST"])
    @admin_required
    def admin_delete_user(user_id):
        if user_id == session.get("user_id"):
            flash("You can't delete your own account from here.", "error")
            return redirect(url_for("admin_users"))
        user = User.query.get(user_id)
        if user:
            Recipe.query.filter_by(owner_id=user_id).update({"owner_id": None})
            db.session.delete(user)
            db.session.commit()
            flash("User removed.", "success")
        return redirect(url_for("admin_users"))

    @app.route("/admin/recipes")
    @admin_required
    def admin_recipes():
        return render_template("admin/recipes.html", recipes=all_recipes())

    @app.route("/admin/recipes/<int:recipe_id>/delete", methods=["POST"])
    @admin_required
    def admin_delete_recipe(recipe_id):
        recipe = get_recipe(recipe_id)
        if recipe:
            db.session.delete(recipe)
            db.session.commit()
            flash("Recipe removed.", "success")
        return redirect(url_for("admin_recipes"))

    @app.route("/admin/reviews")
    @admin_required
    def admin_reviews():
        return render_template("admin/reviews.html", reviews=Review.query.order_by(Review.created_at.desc()).all())

    @app.route("/admin/reviews/<int:review_id>/delete", methods=["POST"])
    @admin_required
    def admin_delete_review(review_id):
        review = Review.query.get(review_id)
        if review:
            db.session.delete(review)
            db.session.commit()
            flash("Review removed.", "success")
        return redirect(url_for("admin_reviews"))

    @app.route("/forgot-password", methods=["GET", "POST"])
    def forgot_password():
        if request.method == "POST":
            flash("Demo reset link prepared. In a live site this would send email.", "success")
        return render_template("forgot_password.html")

    @app.errorhandler(403)
    def handle_forbidden(_error):
        return render_template(
            "error.html",
            error_title="Access denied",
            error_message="You don't have permission to view this page.",
        ), 403

    @app.errorhandler(404)
    def handle_not_found(_error):
        return render_template(
            "error.html",
            error_title="Page not found",
            error_message="We couldn't find the page you were looking for.",
        ), 404

    @app.errorhandler(500)
    def handle_server_error(_error):
        db.session.rollback()
        return render_template(
            "error.html",
            error_title="Something went wrong",
            error_message="An unexpected error occurred. Please try again.",
        ), 500

    return app
