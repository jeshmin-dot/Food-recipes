# Recipe Garden

A full-featured Flask recipe website: browse, search, and filter recipes,
save favorites, leave reviews, plan meals for the week, and generate a
shopping list from your plan. Built incrementally as a learning project.

## Features

- Browse, search, and filter recipes by cuisine, difficulty, and cooking time
- Sort recipes (newest, quickest, A-Z)
- Recipe detail pages with nutrition info, ratings, reviews, and related recipes
- User accounts: registration, secure login (hashed passwords), sessions
- Add, edit, and delete your own recipes, with image upload or URL
- Favorite recipes and leave star ratings + written reviews
- Weekly meal planner with an auto-generated shopping list
- User profile page (your recipes + your favorites)
- Admin panel: manage users, recipes, and reviews
- Dark mode (saved to your browser)
- Responsive layout with a mobile navigation menu
- CSRF protection, role-based access control, secure file upload validation

## Project structure

```text
Food-recipes/
+-- app/
¦   +-- __init__.py          # App factory: all routes live here
¦   +-- models.py             # User, Recipe, Category, Favorite, Review, MealPlanEntry
¦   +-- database.py           # Connection helper + category lookup
¦   +-- utils.py              # Secure image upload validation
¦   +-- controllers/
¦   ¦   +-- database.py         # initialize_database()
¦   ¦   +-- authcontroller.py   # User creation / login verification
¦   +-- routes/
¦   ¦   +-- authroutes.py       # /login, /register, /logout
¦   +-- templates/             # Jinja templates (incl. admin/ subfolder)
¦   +-- static/
¦       +-- css/style.css
¦       +-- js/app.js
¦       +-- uploads/            # User-uploaded recipe images (not committed)
+-- tests/
¦   +-- test_app.py           # Registration, login, CRUD, search, security, upload tests
+-- config.py                 # Reads settings from environment / .env
+-- app.py, run.py            # Entry points
+-- requirements.txt
+-- .env.example               # Copy to .env and fill in real values
+-- README.md
```

## Setup

1. Create and activate a virtual environment:
```bash
   python -m venv .venv
   .venv\Scripts\activate      # Windows
   source .venv/bin/activate   # macOS/Linux
```
2. Install dependencies:
```bash
   pip install -r requirements.txt
```
3. Copy `.env.example` to `.env` and set a real `SECRET_KEY`:
```bash
   python -c "import secrets; print(secrets.token_hex(32))"
```
4. Run the app:
```bash
   python app.py
```
5. Open `http://127.0.0.1:5000`

The database is created automatically on first run and seeded with a few
starter recipes.

## Running tests

```bash
pip install pytest
python -m pytest tests/test_app.py -v
```

## Notes

- `instance/recipe_garden.db` and `.env` are intentionally not committed
  (see `.gitignore`) - they're local/generated, not source code.
- Uploaded images live in `app/static/uploads/` and are also not committed.
