import sqlite3
from pathlib import Path

import config


def get_connection():
    Path(config.DATABASE_PATH).parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(config.DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def create_tables():
    with get_connection() as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'cook',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS recipes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                cuisine TEXT NOT NULL,
                difficulty TEXT NOT NULL,
                minutes INTEGER NOT NULL,
                servings INTEGER NOT NULL,
                image_url TEXT NOT NULL,
                ingredients TEXT NOT NULL,
                steps TEXT NOT NULL,
                owner_id INTEGER,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(owner_id) REFERENCES users(id)
            );
            """
        )


def seed_recipes():
    recipes = [
        (
            "Lemon Herb Pasta",
            "A bright weeknight pasta with basil, lemon, garlic, and toasted crumbs.",
            "Italian",
            "Easy",
            22,
            3,
            "https://images.unsplash.com/photo-1556761223-4c4282c73f77?auto=format&fit=crop&w=1000&q=80",
            "spaghetti\nlemon zest\nbasil\ngarlic\nolive oil\nparmesan\nbreadcrumbs",
            "Boil pasta until just tender.\nToast crumbs with garlic and oil.\nToss pasta with lemon, basil, and parmesan.\nFinish with crumbs and black pepper.",
        ),
        (
            "Miso Maple Bowls",
            "Roasted vegetables, rice, and tofu glazed with a salty-sweet miso sauce.",
            "Japanese-inspired",
            "Medium",
            35,
            4,
            "https://images.unsplash.com/photo-1546069901-ba9599a7e63c?auto=format&fit=crop&w=1000&q=80",
            "rice\ntofu\nmiso paste\nmaple syrup\nbroccoli\ncarrots\nsesame seeds",
            "Cook rice and keep warm.\nRoast vegetables and tofu until golden.\nWhisk miso, maple, soy sauce, and lime.\nSpoon glaze over bowls and scatter sesame seeds.",
        ),
        (
            "Coconut Chickpea Stew",
            "A cozy tomato-coconut stew with ginger, chickpeas, and greens.",
            "Comfort",
            "Easy",
            30,
            5,
            "https://images.unsplash.com/photo-1547592166-23ac45744acd?auto=format&fit=crop&w=1000&q=80",
            "chickpeas\ncoconut milk\ntomatoes\nginger\nspinach\nonion\nchili flakes",
            "Soften onion with ginger and chili.\nAdd tomatoes, chickpeas, and coconut milk.\nSimmer until thick.\nFold in spinach and serve with rice or flatbread.",
        ),
    ]
    with get_connection() as db:
        count = db.execute("SELECT COUNT(*) FROM recipes").fetchone()[0]
        if count:
            return
        db.executemany(
            """
            INSERT INTO recipes
            (title, description, cuisine, difficulty, minutes, servings, image_url, ingredients, steps)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            recipes,
        )
