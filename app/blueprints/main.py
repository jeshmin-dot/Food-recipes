from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from app.db import query_all
from app.services import all_recipes

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def home():
    recipes = all_recipes()
    featured = recipes[0] if recipes else None
    cuisines = sorted({recipe.cuisine for recipe in recipes})
    avg_minutes = round(sum(r.minutes for r in recipes) / len(recipes)) if recipes else 0
    favorite_ids = set()
    if session.get("user_id"):
        rows = query_all("SELECT recipe_id FROM favorites WHERE user_id = %s", (session["user_id"],))
        favorite_ids = {row["recipe_id"] for row in rows}
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


@main_bp.route("/cook-mode")
def cook_mode():
    return render_template("cook_mode.html", recipes=all_recipes())


@main_bp.route("/pantry", methods=["GET", "POST"])
def cookies():
    if request.method == "POST":
        response = redirect(url_for("main.cookies"))
        response.set_cookie("pantry_style", request.form.get("pantry_style", "quick"), max_age=60 * 60 * 24 * 90)
        response.set_cookie("serving_size", request.form.get("serving_size", "4"), max_age=60 * 60 * 24 * 90)
        flash("Pantry preferences saved.", "success")
        return response
    return render_template(
        "cookies.html",
        pantry_style=request.cookies.get("pantry_style", "quick"),
        serving_size=request.cookies.get("serving_size", "4"),
    )