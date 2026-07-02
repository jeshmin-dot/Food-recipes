from app.database import create_tables, get_connection, seed_recipes


def initialize_database():
    create_tables()
    seed_recipes()


def recipe_count():
    with get_connection() as db:
        return db.execute("SELECT COUNT(*) FROM recipes").fetchone()[0]
