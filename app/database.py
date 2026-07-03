from app.models import Recipe, db


def create_tables():
    db.create_all()


def seed_recipes():
    if Recipe.query.count():
        return

    recipes = [
        Recipe(
            title="Lemon Herb Pasta",
            description="A bright weeknight pasta with basil, lemon, garlic, and toasted crumbs.",
            cuisine="Italian",
            difficulty="Easy",
            minutes=22,
            servings=3,
            image_url="https://images.unsplash.com/photo-1556761223-4c4282c73f77?auto=format&fit=crop&w=1000&q=80",
            ingredients="spaghetti\nlemon zest\nbasil\ngarlic\nolive oil\nparmesan\nbreadcrumbs",
            steps="Boil pasta until just tender.\nToast crumbs with garlic and oil.\nToss pasta with lemon, basil, and parmesan.\nFinish with crumbs and black pepper.",
        ),
        Recipe(
            title="Miso Maple Bowls",
            description="Roasted vegetables, rice, and tofu glazed with a salty-sweet miso sauce.",
            cuisine="Japanese-inspired",
            difficulty="Medium",
            minutes=35,
            servings=4,
            image_url="https://images.unsplash.com/photo-1546069901-ba9599a7e63c?auto=format&fit=crop&w=1000&q=80",
            ingredients="rice\ntofu\nmiso paste\nmaple syrup\nbroccoli\ncarrots\nsesame seeds",
            steps="Cook rice and keep warm.\nRoast vegetables and tofu until golden.\nWhisk miso, maple, soy sauce, and lime.\nSpoon glaze over bowls and scatter sesame seeds.",
        ),
        Recipe(
            title="Coconut Chickpea Stew",
            description="A cozy tomato-coconut stew with ginger, chickpeas, and greens.",
            cuisine="Comfort",
            difficulty="Easy",
            minutes=30,
            servings=5,
            image_url="https://images.unsplash.com/photo-1547592166-23ac45744acd?auto=format&fit=crop&w=1000&q=80",
            ingredients="chickpeas\ncoconut milk\ntomatoes\nginger\nspinach\nonion\nchili flakes",
            steps="Soften onion with ginger and chili.\nAdd tomatoes, chickpeas, and coconut milk.\nSimmer until thick.\nFold in spinach and serve with rice or flatbread.",
        ),
    ]
    db.session.add_all(recipes)
    db.session.commit()
