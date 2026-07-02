# Food Recipes

A Flask recipe website. Started as a simple in-memory recipe list
(`app.py` / `recipes.py`) and is being combined with a fuller version
(`app/`) that adds a real database, user accounts, and a dashboard for
adding recipes.

## Project structure

- `app/` — the main application package (routes, database, templates, static files)
- `app.py`, `recipes.py` — the original simple version, being folded into `app/`
- `config.py` — environment-based configuration
- `run.py` — dev server entry point
- `test.py`, `test/` — test files, being consolidated into `tests/`

## Run locally

1. Create and activate a virtual environment
2. Install dependencies:
```bash
   pip install -r requirements.txt
```
3. Start the app:
```bash
   python app.py
```
4. Open `http://127.0.0.1:5000` in your browser



