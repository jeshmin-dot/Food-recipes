# Recipe Garden

A full-featured Flask recipe website: browse, search, and filter recipes,
save favorites, leave reviews, plan meals for the week, and generate a
shopping list from your plan. Built incrementally as a learning project for
module RTW504CA1 (The Internet and Web Technologies).

**Report:** see [REPORT.md](REPORT.md) for architecture/database diagrams,
security measures, and design decisions.
**Video demonstration:** *[add your unlisted YouTube / Google Drive link
here before submission]*

## Features

- Browse, search, and filter recipes by cuisine, difficulty, cooking time,
  and calories
- Sort recipes (newest, quickest, A-Z)
- Recipe cards with a bookmark toggle, star rating badge, and calorie badge
- Recipe detail pages with nutrition info, an interactive ingredient
  checklist, ratings, reviews, and related recipes
- Download any recipe as a standalone PDF (requires being logged in), or
  share its link (native share sheet on mobile, copy-to-clipboard
  elsewhere - sharing itself doesn't require an account)
- User accounts: registration (validated email format, passwords require 8+
  characters and a special character), secure login (hashed passwords),
  sessions
- Add, edit, and delete your own recipes, with image upload or URL
- Favorite recipes and leave star ratings + written reviews (one review per
  recipe - resubmitting updates it rather than stacking duplicates)
- Weekly meal planner with an auto-generated shopping list
- User profile page (your recipes + your favorites)
- Admin panel: manage users, recipes, and reviews
- Responsive layout with a mobile navigation menu
- CSRF protection, role-based access control, secure file upload validation,
  rate-limited login/register forms

## Project structure

```text
Food-recipes/
+-- app/
|   +-- __init__.py           # Thin app factory: config + blueprint registration
|   +-- constants.py           # DAYS, MEALS, REQUIRED_RECIPE_FIELDS
|   +-- decorators.py          # login_required, admin_required, rate_limit
|   +-- services.py            # Shared helpers used by more than one blueprint
|   +-- models.py              # User, Recipe, Category, Favorite, Review, MealPlanEntry
|   +-- database.py            # Connection helper + category lookup
|   +-- utils.py               # Secure image upload validation
|   +-- controllers/
|   |   +-- database.py         # initialize_database()
|   |   +-- authcontroller.py   # User creation / login verification
|   +-- routes/
|   |   +-- authroutes.py       # /login, /register, /logout, /forgot-password
|   +-- blueprints/
|   |   +-- main.py             # Home page, cook mode, pantry preferences
|   |   +-- recipes.py          # Browse/search, detail, add/edit/delete, favorites, reviews
|   |   +-- account.py          # Profile, account settings, favorites list
|   |   +-- meal_planner.py     # Weekly planner + shopping list
|   |   +-- admin.py            # User/recipe/review management
|   +-- templates/             # Jinja templates (incl. admin/ subfolder)
|   +-- static/
|       +-- css/style.css
|       +-- js/app.js
|       +-- uploads/            # User-uploaded recipe images (not committed)
+-- tests/
|   +-- test_app.py            # Registration, login, CRUD, search, security, upload tests
+-- config.py                  # Reads settings from environment / .env
+-- app.py, run.py             # Entry points
+-- requirements.txt
+-- .env.example                # Copy to .env and fill in real values
+-- REPORT.md                   # Coursework report (architecture, DB, security)
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
3. Install MySQL locally (or use one already running) and create the
   database - MySQL doesn't auto-create it the way SQLite auto-created a
   file:
```sql
   CREATE DATABASE recipe_garden;
```
4. Copy `.env.example` to `.env`, set a real `SECRET_KEY`, and fill in your
   MySQL connection details (`DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`,
   `DB_PASSWORD`):
```bash
   python -c "import secrets; print(secrets.token_hex(32))"
```
5. Run the app:
```bash
   python app.py
```
6. Open `http://127.0.0.1:5000`

The tables are created automatically on first run (via `db.create_all()`)
and seeded with a few starter recipes.

### Migrating an existing database

`db.create_all()` only creates tables that don't exist yet - it will not
add a new column to a `recipes` table that's already there from an earlier
run. If you already had this app running against MySQL before the
`calories` column was added, run this once against your existing database:

```sql
ALTER TABLE recipes ADD COLUMN calories INT NULL;
```

## Running tests

The test suite points itself at a throwaway SQLite file instead of MySQL,
so it can run without a MySQL server available (see REPORT.md's "Testing"
notes) - you don't need step 3/4 above just to run `pytest`.

```bash
pip install pytest
python -m pytest tests/test_app.py -v
```

## Notes

- `.env` is intentionally not committed (see `.gitignore`) - it holds
  local secrets and MySQL credentials, not source code.
- Uploaded images live in `app/static/uploads/` and are also not committed;
  deleting or replacing a recipe's image cleans up the old file on disk.