from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from sqlalchemy.exc import SQLAlchemyError

from app.constants import DAYS, MEALS
from app.decorators import login_required
from app.models import MealPlanEntry, db
from app.services import all_recipes

meal_planner_bp = Blueprint("meal_planner", __name__)


@meal_planner_bp.route("/meal-planner", methods=["GET", "POST"])
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
        return redirect(url_for("meal_planner.meal_planner"))

    entries = MealPlanEntry.query.filter_by(user_id=session["user_id"]).all()
    plan = {(e.day_of_week, e.meal_type): e.recipe for e in entries}
    return render_template(
        "meal_planner.html",
        days=DAYS,
        meals=MEALS,
        plan=plan,
        all_recipes=all_recipes(),
    )


@meal_planner_bp.route("/meal-planner/shopping-list")
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