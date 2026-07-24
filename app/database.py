"""Database setup: create the tables (if missing) and seed starter recipes.

All access is raw parameterised SQL through app/db.py - no ORM.
"""

from app.db import execute, get_db, query_one
from app.models import SCHEMA


def create_tables():
    conn = get_db()
    with conn.cursor() as cursor:
        for statement in SCHEMA:
            cursor.execute(statement)
    conn.commit()


def get_or_create_category(name):
    """Return the id of the category with this name, creating it if needed."""
    row = query_one("SELECT id FROM categories WHERE name = %s", (name,))
    if row:
        return row["id"]
    return execute("INSERT INTO categories (name) VALUES (%s)", (name,))


def seed_recipes():
    # Only seed when the recipes table is empty, so restarting the app
    # doesn't keep adding duplicate starter recipes.
    row = query_one("SELECT COUNT(*) AS total FROM recipes")
    if row and row["total"]:
        return

    italian = get_or_create_category("Italian")
    japanese = get_or_create_category("Japanese-inspired")
    comfort = get_or_create_category("Comfort")

    recipes = [
        (
            "Lemon Herb Pasta",
            "A bright weeknight pasta with basil, lemon, garlic, and toasted crumbs.",
            italian, "Easy", 22, 3,
            "https://images.unsplash.com/photo-1556761223-4c4282c73f77?auto=format&fit=crop&w=1000&q=80",
            "spaghetti\nlemon zest\nbasil\ngarlic\nolive oil\nparmesan\nbreadcrumbs",
            "Boil pasta until just tender.\nToast crumbs with garlic and oil.\nToss pasta with lemon, basil, and parmesan.\nFinish with crumbs and black pepper.",
            "480 kcal, 16g protein, 62g carbs", 480,
        ),
        (
            "Miso Maple Bowls",
            "Roasted vegetables, rice, and tofu glazed with a salty-sweet miso sauce.",
            japanese, "Medium", 35, 4,
            "https://images.unsplash.com/photo-1546069901-ba9599a7e63c?auto=format&fit=crop&w=1000&q=80",
            "rice\ntofu\nmiso paste\nmaple syrup\nbroccoli\ncarrots\nsesame seeds",
            "Cook rice and keep warm.\nRoast vegetables and tofu until golden.\nWhisk miso, maple, soy sauce, and lime.\nSpoon glaze over bowls and scatter sesame seeds.",
            "540 kcal, 22g protein, 70g carbs", 540,
        ),
        (
            "Coconut Chickpea Stew",
            "A cozy tomato-coconut stew with ginger, chickpeas, and greens.",
            comfort, "Easy", 30, 5,
            "https://images.unsplash.com/photo-1547592166-23ac45744acd?auto=format&fit=crop&w=1000&q=80",
            "chickpeas\ncoconut milk\ntomatoes\nginger\nspinach\nonion\nchili flakes",
            "Soften onion with ginger and chili.\nAdd tomatoes, chickpeas, and coconut milk.\nSimmer until thick.\nFold in spinach and serve with rice or flatbread.",
            "390 kcal, 12g protein, 45g carbs", 390,
        ),
    ]

    conn = get_db()
    with conn.cursor() as cursor:
        cursor.executemany(
            """
            INSERT INTO recipes
                (title, description, category_id, difficulty, minutes, servings,
                 image_url, ingredients, steps, nutrition, calories)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            recipes,
        )
    conn.commit()