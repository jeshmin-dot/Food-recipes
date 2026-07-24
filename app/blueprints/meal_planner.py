import pymysql
from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from app.constants import DAYS, MEALS
from app.db import Row, get_db, query_all
from app.decorators import login_required
from app.services import all_recipes

meal_planner_bp = Blueprint("meal_planner", __name__)


@meal_planner_bp.route("/meal-planner", methods=["GET", "POST"])
@login_required
def meal_planner():
    user_id = session["user_id"]

    if request.method == "POST":
        conn = get_db()
        try:
            with conn.cursor() as cursor:
                for day in DAYS:
                    for meal in MEALS:
                        recipe_id = request.form.get(f"{day}_{meal}", "").strip()
                        if not recipe_id:
                            cursor.execute(
                                "DELETE FROM meal_plan_entries WHERE user_id = %s AND day_of_week = %s AND meal_type = %s",
                                (user_id, day, meal),
                            )
                            continue
                        cursor.execute(
                            """
                            INSERT INTO meal_plan_entries (user_id, recipe_id, day_of_week, meal_type)
                            VALUES (%s, %s, %s, %s)
                            ON DUPLICATE KEY UPDATE recipe_id = VALUES(recipe_id)
                            """,
                            (user_id, int(recipe_id), day, meal),
                        )
            conn.commit()
            flash("Meal plan saved.", "success")
        except pymysql.MySQLError:
            conn.rollback()
            flash("We could not save your meal plan. Please try again.", "error")
        return redirect(url_for("meal_planner.meal_planner"))

    entries = query_all(
        "SELECT recipe_id, day_of_week, meal_type FROM meal_plan_entries WHERE user_id = %s",
        (user_id,),
    )
    plan = {(e.day_of_week, e.meal_type): Row(id=e.recipe_id) for e in entries}
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
    entries = query_all(
        """
        SELECT r.ingredients
        FROM meal_plan_entries m
        JOIN recipes r ON r.id = m.recipe_id
        WHERE m.user_id = %s
        """,
        (session["user_id"],),
    )

    counts = {}
    for entry in entries:
        for line in entry.ingredients.split("\n"):
            line = line.strip()
            if not line:
                continue
            key = line.lower()
            label, count = counts.get(key, (line, 0))
            counts[key] = (label, count + 1)

    combined = sorted(counts.values(), key=lambda pair: pair[0].lower())
    return render_template("shopping_list.html", ingredients=combined, has_plan=bool(entries))