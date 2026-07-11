from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import validates

db = SQLAlchemy()


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), nullable=False, unique=True, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="cook")
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    recipes = db.relationship("Recipe", backref="owner", lazy=True)
    favorites = db.relationship("Favorite", backref="user", lazy=True)
    reviews = db.relationship("Review", backref="user", lazy=True)

    @validates("email")
    def validate_email(self, key, value):
        value = value.strip().lower()
        if "@" not in value or "." not in value.split("@")[-1]:
            raise ValueError("That doesn't look like a valid email address.")
        return value


class Category(db.Model):
    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True, index=True)

    recipes = db.relationship("Recipe", backref="category", lazy=True)


class Recipe(db.Model):
    __tablename__ = "recipes"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False, index=True)
    description = db.Column(db.Text, nullable=False)
    difficulty = db.Column(db.String(20), nullable=False, index=True)
    minutes = db.Column(db.Integer, nullable=False)
    servings = db.Column(db.Integer, nullable=False)
    image_url = db.Column(db.String(500), nullable=False)
    ingredients = db.Column(db.Text, nullable=False)
    steps = db.Column(db.Text, nullable=False)
    nutrition = db.Column(db.String(255), nullable=True)
    # Optional: lets the search page offer a calorie filter. Nullable so
    # recipes added before this column existed (and anyone who leaves the
    # field blank) don't break - "no data" is a valid state, not an error.
    calories = db.Column(db.Integer, nullable=True)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=False, index=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"), index=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), index=True)

    favorites = db.relationship("Favorite", backref="recipe", lazy=True, cascade="all, delete-orphan")
    reviews = db.relationship("Review", backref="recipe", lazy=True, cascade="all, delete-orphan")

    __table_args__ = (
        db.CheckConstraint("minutes > 0", name="minutes_must_be_positive"),
        db.CheckConstraint("servings > 0", name="servings_must_be_positive"),
        db.CheckConstraint("calories IS NULL OR calories >= 0", name="calories_must_not_be_negative"),
    )

    @validates("minutes", "servings")
    def validate_positive(self, key, value):
        if value is None or value <= 0:
            raise ValueError(f"{key} must be a positive number.")
        return value

    @validates("calories")
    def validate_calories(self, key, value):
        if value is not None and value < 0:
            raise ValueError("Calories cannot be negative.")
        return value

    @property
    def cuisine(self):
        return self.category.name if self.category else ""

    @property
    def average_rating(self):
        if not self.reviews:
            return None
        return round(sum(r.rating for r in self.reviews) / len(self.reviews), 1)


class Favorite(db.Model):
    __tablename__ = "favorites"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    recipe_id = db.Column(db.Integer, db.ForeignKey("recipes.id"), nullable=False, index=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    __table_args__ = (db.UniqueConstraint("user_id", "recipe_id", name="one_favorite_per_user_recipe"),)


class Review(db.Model):
    __tablename__ = "reviews"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    recipe_id = db.Column(db.Integer, db.ForeignKey("recipes.id"), nullable=False, index=True)
    rating = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    __table_args__ = (
        db.CheckConstraint("rating >= 1 AND rating <= 5", name="rating_between_1_and_5"),
        # One review per user per recipe - resubmitting the review form
        # updates the existing row instead of stacking duplicates that
        # would skew Recipe.average_rating.
        db.UniqueConstraint("user_id", "recipe_id", name="one_review_per_user_recipe"),
    )

    @validates("rating")
    def validate_rating(self, key, value):
        if value is None or value < 1 or value > 5:
            raise ValueError("Rating must be between 1 and 5.")
        return value


class MealPlanEntry(db.Model):
    __tablename__ = "meal_plan_entries"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    recipe_id = db.Column(db.Integer, db.ForeignKey("recipes.id"), nullable=False, index=True)
    day_of_week = db.Column(db.String(20), nullable=False)
    meal_type = db.Column(db.String(20), nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    user = db.relationship("User", backref="meal_plan_entries")
    recipe = db.relationship("Recipe")

    __table_args__ = (
        db.UniqueConstraint("user_id", "day_of_week", "meal_type", name="one_recipe_per_slot"),
    )