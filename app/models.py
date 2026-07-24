"""Database schema.

The ORM has been removed; the application now talks to MySQL with raw,
parameterised SQL (see app/db.py). These CREATE TABLE statements define the
six tables and are run once at start-up by app/database.py. `IF NOT EXISTS`
means an existing database is left untouched, while a fresh database gets
the full schema, including the primary keys, foreign keys, unique keys and
CHECK constraints that keep the data valid.
"""

SCHEMA = [
    """
    CREATE TABLE IF NOT EXISTS users (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(120) NOT NULL,
        email VARCHAR(255) NOT NULL UNIQUE,
        password_hash VARCHAR(255) NOT NULL,
        role VARCHAR(20) NOT NULL DEFAULT 'cook',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS categories (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(100) NOT NULL UNIQUE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS recipes (
        id INT AUTO_INCREMENT PRIMARY KEY,
        title VARCHAR(200) NOT NULL,
        description TEXT NOT NULL,
        difficulty VARCHAR(20) NOT NULL,
        minutes INT NOT NULL,
        servings INT NOT NULL,
        image_url VARCHAR(500) NOT NULL,
        ingredients TEXT NOT NULL,
        steps TEXT NOT NULL,
        nutrition VARCHAR(255) NULL,
        calories INT NULL,
        category_id INT NOT NULL,
        owner_id INT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (category_id) REFERENCES categories(id),
        FOREIGN KEY (owner_id) REFERENCES users(id),
        CONSTRAINT minutes_must_be_positive CHECK (minutes > 0),
        CONSTRAINT servings_must_be_positive CHECK (servings > 0),
        CONSTRAINT calories_must_not_be_negative CHECK (calories IS NULL OR calories >= 0)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS favorites (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id INT NOT NULL,
        recipe_id INT NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        UNIQUE KEY one_favorite_per_user_recipe (user_id, recipe_id),
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (recipe_id) REFERENCES recipes(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS reviews (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id INT NOT NULL,
        recipe_id INT NOT NULL,
        rating INT NOT NULL,
        comment TEXT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        UNIQUE KEY one_review_per_user_recipe (user_id, recipe_id),
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (recipe_id) REFERENCES recipes(id),
        CONSTRAINT rating_between_1_and_5 CHECK (rating >= 1 AND rating <= 5)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS meal_plan_entries (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id INT NOT NULL,
        recipe_id INT NOT NULL,
        day_of_week VARCHAR(20) NOT NULL,
        meal_type VARCHAR(20) NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        UNIQUE KEY one_recipe_per_slot (user_id, day_of_week, meal_type),
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (recipe_id) REFERENCES recipes(id)
    )
    """,
]