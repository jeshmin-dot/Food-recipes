from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False)
    email = db.Column(db.String, nullable=False, unique=True)
    password_hash = db.Column(db.String, nullable=False)
    role = db.Column(db.String, nullable=False, default="cook")
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    recipes = db.relationship("Recipe", backref="owner", lazy=True)


class Recipe(db.Model):
    __tablename__ = "recipes"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String, nullable=False)
    description = db.Column(db.Text, nullable=False)
    cuisine = db.Column(db.String, nullable=False)
    difficulty = db.Column(db.String, nullable=False)
    minutes = db.Column(db.Integer, nullable=False)
    servings = db.Column(db.Integer, nullable=False)
    image_url = db.Column(db.String, nullable=False)
    ingredients = db.Column(db.Text, nullable=False)
    steps = db.Column(db.Text, nullable=False)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, server_default=db.func.now())
