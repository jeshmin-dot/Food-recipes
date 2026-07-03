import secrets
from datetime import datetime

from flask import Flask, abort, flash, redirect, render_template, request, session, url_for
from sqlalchemy.exc import SQLAlchemyError

import config
from app.controllers.database import initialize_database
from app.database import get_or_create_category
from app.models import Category, Favorite, Recipe, Review, User, db
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
            "is_admin": session.get("user_role") == "admin",
        }

    @app.before_request
    def protect_forms():
        if request.method == "POST":
            sent = request.form.get("csrf_token", "")
            stored = session.get("csrf_token", "")
            if not sent or not stored or not secrets.compare_digest(sent, stored):
                abort(400, description="Invalid form token.")

    def require_admin():
        if session.get("user_role") != "admin":
            abort(404, description="That page could not be found.")

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

    @app.route("/")
    def home():
        recipes = all_recipes()
        featured = recipes[0] if recipes else None
        cuisines = sorted({recipe.cuisine for recipe in recipes})
        avg_minutes = round(sum(r.minutes for r in recipes) / len(recipes)) if recipes else 0
        return render_template(
            "home.html",
            recipes=recipes,
            featured=featured,
            recipe_count=len(recipes),
            cuisine_count=len(cuisines),
            avg_minutes=avg_minutes,
            all_cuisines=cuisines,
        )

    @app.route("/recipes")
    def recipes():
        recipe_list = all_recipes()
        query = request.args.get("q", "").strip().lower()
        cuisine = request.args.get("cuisine", "").strip()
        difficulty = request.args.get("difficulty", "").strip()
        time_bucket = request.args.get("time", "").strip()
        sort = request.args.get("sort", "newest").strip()

        if query:
            recipe_list = [
                recipe
                for recipe in recipe_list
                if query in recipe.title.lower()
                or query in recipe.cuisine.lower()
                or query in recipe.ingredients.lower()
            ]
        if cuisine:
            recipe_list = [recipe for recipe in recipe_list if recipe.cuisine == cuisine]
        if difficulty:
            recipe_list = [recipe for recipe in recipe_list if recipe.difficulty == difficulty]
        if time_bucket:
            recipe_list = [recipe for recipe in recipe_list if time_matches(recipe, time_bucket)]

        if sort == "quickest":
            recipe_list = sorted(recipe_list, key=lambda r: r.minutes)
        elif sort == "az":
            recipe_list = sorted(recipe_list, key=lambda r: r.title.lower())

        all_cuisines = sorted({recipe.cuisine for recipe in all_recipes()})
        all_difficulties = ["Easy", "Medium", "Project"]

        return render_template(
            "recipes.html",
            recipes=recipe_list,
            query=query,
            cuisine=cuisine,
            difficulty=difficulty,
            time_bucket=time_bucket,
            sort=sort,
            all_cuisines=all_cuisines,
            all_difficulties=all_difficulties,
        )

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
        return render_template(
            "recipe_detail.html", recipe=recipe, is_favorited=is_favorited, reviews=reviews
        )

    @app.route("/recipes/<int:recipe_id>/favorite", methods=["POST"])
    def toggle_favorite(recipe_id):
        if not session.get("user_id"):
            flash("Log in to save favorites.", "error")
            return redirect(url_for("auth.login"))

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
    def favorites():
        if not session.get("user_id"):
            flash("Log in to see your favorites.", "error")
            return redirect(url_for("auth.login"))
        favorite_rows = Favorite.query.filter_by(user_id=session["user_id"]).all()
        favorite_recipes = [row.recipe for row in favorite_rows]
        return render_template("favorites.html", recipes=favorite_recipes)

    @app.route("/recipes/<int:recipe_id>/review", methods=["POST"])
    def add_review(recipe_id):
        if not session.get("user_id"):
            flash("Log in to leave a review.", "error")
            return redirect(url_for("auth.login"))

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
                category = get_or_create_category(request.form["cuisine"].strip())
                recipe = Recipe(
                    title=request.form["title"],
                    description=request.form["description"],
                    category_id=category.id,
                    difficulty=request.form["difficulty"],
                    minutes=minutes,
                    servings=servings,
                    image_url=request.form["image_url"],
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
        if recipe.owner_id != session["user_id"] and session.get("user_role") != "admin":
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
                category = get_or_create_category(request.form["cuisine"].strip())
                recipe.title = request.form["title"]
                recipe.description = request.form["description"]
                recipe.category_id = category.id
                recipe.difficulty = request.form["difficulty"]
                recipe.minutes = minutes
                recipe.servings = servings
                recipe.image_url = request.form["image_url"]
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
    def delete_recipe(recipe_id):
        if not session.get("user_id"):
            flash("Log in to manage recipes.", "error")
            return redirect(url_for("auth.login"))

        recipe = get_recipe(recipe_id)
        if recipe is None:
            flash("That recipe no longer exists.", "error")
            return redirect(url_for("dashboard"))
        if recipe.owner_id != session["user_id"] and session.get("user_role") != "admin":
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

    @app.route("/admin")
    def admin_dashboard():
        require_admin()
        return render_template(
            "admin/dashboard.html",
            user_count=User.query.count(),
            recipe_count=Recipe.query.count(),
            category_count=Category.query.count(),
            review_count=Review.query.count(),
        )

    @app.route("/admin/users")
    def admin_users():
        require_admin()
        return render_template("admin/users.html", users=User.query.order_by(User.name).all())

    @app.route("/admin/users/<int:user_id>/delete", methods=["POST"])
    def admin_delete_user(user_id):
        require_admin()
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
    def admin_recipes():
        require_admin()
        return render_template("admin/recipes.html", recipes=all_recipes())

    @app.route("/admin/recipes/<int:recipe_id>/delete", methods=["POST"])
    def admin_delete_recipe(recipe_id):
        require_admin()
        recipe = get_recipe(recipe_id)
        if recipe:
            db.session.delete(recipe)
            db.session.commit()
            flash("Recipe removed.", "success")
        return redirect(url_for("admin_recipes"))

    @app.route("/admin/reviews")
    def admin_reviews():
        require_admin()
        return render_template("admin/reviews.html", reviews=Review.query.order_by(Review.created_at.desc()).all())

    @app.route("/admin/reviews/<int:review_id>/delete", methods=["POST"])
    def admin_delete_review(review_id):
        require_admin()
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

    @app.errorhandler(404)
    def handle_not_found(_error):
        return render_template(
            "error.html",
            error_title="Page not found",
            error_message="We couldn't find the page you were looking for.",
        ), 404

    return app
