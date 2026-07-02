from app.database import create_tables, seed_recipes


def initialize_database():
    create_tables()
    seed_recipes()
