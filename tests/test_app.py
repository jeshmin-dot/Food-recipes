"""Automated tests for the Recipe Garden application.

The suite runs against a throwaway in-memory SQLite database (see
conftest.py) so `pytest` works on any machine without a MySQL server. Every
database check below is written as raw parameterised SQL through app/db.py -
the same data layer the application itself uses - so the tests exercise the
real query path rather than an ORM stand-in.
"""

import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def make_test_client():
    from app import create_app
    from app.decorators import _reset_rate_limits

    _reset_rate_limits()
    app = create_app()
    app.config["TESTING"] = True
    return app, app.test_client()


def with_csrf(client, data=None):
    """Populate a session CSRF token and return form data that includes it,
    matching how the real app protects every POST request."""
    with client.session_transaction() as sess:
        sess["csrf_token"] = "test-token"
    form = dict(data or {})
    form["csrf_token"] = "test-token"
    return form


# Small raw-SQL helpers so the assertions stay readable. Each opens an app
# context and runs a parameterised query through the application's own db
# layer (app/db.py), exactly as the views do.

def _query_one(app, sql, params=()):
    with app.app_context():
        from app.db import query_one
        return query_one(sql, params)


def _query_all(app, sql, params=()):
    with app.app_context():
        from app.db import query_all
        return query_all(sql, params)


def _scalar(app, sql, params=()):
    row = _query_one(app, sql, params)
    if row is None:
        return None
    # Return the single selected value regardless of its column name.
    return next(iter(row.values()))


def _first_recipe_id(app):
    row = _query_one(app, "SELECT id FROM recipes ORDER BY id LIMIT 1")
    return row["id"]


# ---------- Registration ----------

def test_registration_creates_user():
    app, client = make_test_client()
    response = client.post(
        "/register",
        data=with_csrf(client, {"name": "Ada", "email": "ada@example.com", "password": "secretpw!"}),
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert _query_one(app, "SELECT id FROM users WHERE email = %s", ("ada@example.com",)) is not None


def test_registration_duplicate_email_rejected():
    app, client = make_test_client()
    data = {"name": "Ada", "email": "dupe@example.com", "password": "secretpw!"}
    client.post("/register", data=with_csrf(client, data))
    response = client.post("/register", data=with_csrf(client, data), follow_redirects=True)
    assert response.status_code == 200
    assert _scalar(app, "SELECT COUNT(*) FROM users WHERE email = %s", ("dupe@example.com",)) == 1


def test_password_is_hashed_not_plaintext():
    app, client = make_test_client()
    client.post(
        "/register",
        data=with_csrf(client, {"name": "Ada", "email": "hash@example.com", "password": "secretpw!"}),
    )
    user = _query_one(app, "SELECT password_hash FROM users WHERE email = %s", ("hash@example.com",))
    assert user["password_hash"] != "secretpw!"
    assert user["password_hash"].startswith(("pbkdf2:", "scrypt:"))


# ---------- Login / logout ----------

def test_login_success():
    app, client = make_test_client()
    client.post(
        "/register",
        data=with_csrf(client, {"name": "Ada", "email": "login@example.com", "password": "secretpw!"}),
    )
    response = client.post(
        "/login",
        data=with_csrf(client, {"email": "login@example.com", "password": "secretpw!"}),
        follow_redirects=True,
    )
    assert response.status_code == 200
    with client.session_transaction() as sess:
        assert sess.get("user_id") is not None


def test_login_wrong_password_fails():
    app, client = make_test_client()
    client.post(
        "/register",
        data=with_csrf(client, {"name": "Ada", "email": "wrongpw@example.com", "password": "secretpw!"}),
    )
    client.post(
        "/login",
        data=with_csrf(client, {"email": "wrongpw@example.com", "password": "notright"}),
    )
    with client.session_transaction() as sess:
        assert sess.get("user_id") is None


def test_logout_clears_session():
    app, client = make_test_client()
    client.post(
        "/register",
        data=with_csrf(client, {"name": "Ada", "email": "logout@example.com", "password": "secretpw!"}),
    )
    client.post(
        "/login",
        data=with_csrf(client, {"email": "logout@example.com", "password": "secretpw!"}),
    )
    client.get("/logout")
    with client.session_transaction() as sess:
        assert sess.get("user_id") is None


# ---------- CRUD ----------

def _login_new_user(client, email="crud@example.com"):
    client.post(
        "/register",
        data=with_csrf(client, {"name": "Cook", "email": email, "password": "secretpw!"}),
    )
    client.post("/login", data=with_csrf(client, {"email": email, "password": "secretpw!"}))


def _recipe_form(**overrides):
    data = {
        "title": "Test Soup",
        "description": "A soup for testing.",
        "cuisine": "Testland",
        "difficulty": "Easy",
        "minutes": "20",
        "servings": "2",
        "image_url": "https://example.com/image.jpg",
        "ingredients": "water\nsalt",
        "steps": "Boil water.\nAdd salt.",
    }
    data.update(overrides)
    return data


def test_dashboard_requires_login():
    app, client = make_test_client()
    response = client.get("/dashboard")
    assert response.status_code == 302


def test_favoriting_requires_login():
    app, client = make_test_client()
    recipe_id = _first_recipe_id(app)  # one of the seeded starter recipes
    response = client.post(f"/recipes/{recipe_id}/favorite", data=with_csrf(client))
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_downloading_pdf_requires_login():
    app, client = make_test_client()
    recipe_id = _first_recipe_id(app)  # one of the seeded starter recipes
    response = client.get(f"/recipes/{recipe_id}/download")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_add_recipe_creates_recipe():
    app, client = make_test_client()
    _login_new_user(client)
    client.post("/dashboard", data=with_csrf(client, _recipe_form()))
    assert _query_one(app, "SELECT id FROM recipes WHERE title = %s", ("Test Soup",)) is not None


def test_edit_recipe_updates_fields():
    app, client = make_test_client()
    _login_new_user(client)
    client.post("/dashboard", data=with_csrf(client, _recipe_form()))
    recipe_id = _scalar(app, "SELECT id FROM recipes WHERE title = %s", ("Test Soup",))
    client.post(f"/recipes/{recipe_id}/edit", data=with_csrf(client, _recipe_form(title="Updated Soup")))
    title = _scalar(app, "SELECT title FROM recipes WHERE id = %s", (recipe_id,))
    assert title == "Updated Soup"


def test_non_owner_cannot_edit_recipe():
    app, client = make_test_client()
    _login_new_user(client, email="owner@example.com")
    client.post("/dashboard", data=with_csrf(client, _recipe_form()))
    recipe_id = _scalar(app, "SELECT id FROM recipes WHERE title = %s", ("Test Soup",))

    client.get("/logout")
    _login_new_user(client, email="intruder@example.com")
    response = client.get(f"/recipes/{recipe_id}/edit")
    assert response.status_code == 403


def test_delete_recipe_removes_it():
    app, client = make_test_client()
    _login_new_user(client)
    client.post("/dashboard", data=with_csrf(client, _recipe_form()))
    recipe_id = _scalar(app, "SELECT id FROM recipes WHERE title = %s", ("Test Soup",))
    client.post(f"/recipes/{recipe_id}/delete", data=with_csrf(client))
    assert _query_one(app, "SELECT id FROM recipes WHERE id = %s", (recipe_id,)) is None


# ---------- Search ----------

def test_search_finds_matching_recipe():
    app, client = make_test_client()
    _login_new_user(client)
    client.post("/dashboard", data=with_csrf(client, _recipe_form(title="Spicy Ramen")))
    response = client.get("/recipes?q=ramen")
    assert response.status_code == 200
    assert b"Spicy Ramen" in response.data


def test_search_no_match_shows_empty_state():
    app, client = make_test_client()
    response = client.get("/recipes?q=zzznonexistentzzz")
    assert response.status_code == 200
    assert b"No recipes found" in response.data


# ---------- Security ----------

def test_post_without_csrf_token_rejected():
    app, client = make_test_client()
    _login_new_user(client)
    response = client.post("/dashboard", data=_recipe_form())  # no csrf_token included
    assert response.status_code == 400


def test_search_handles_sql_special_characters_safely():
    app, client = make_test_client()
    response = client.get("/recipes?q=" + "' OR '1'='1")
    assert response.status_code == 200


def test_unknown_route_returns_404():
    app, client = make_test_client()
    response = client.get("/this-page-does-not-exist")
    assert response.status_code == 404


def test_admin_route_blocked_for_regular_user():
    app, client = make_test_client()
    _login_new_user(client)
    response = client.get("/admin")
    assert response.status_code == 403


# ---------- File uploads ----------

def test_disallowed_file_extension_rejected():
    from app.utils import allowed_file
    assert allowed_file("virus.exe") is False
    assert allowed_file("photo.jpg") is True


def test_upload_saves_with_unique_filename(tmp_path):
    from werkzeug.datastructures import FileStorage

    from app.utils import save_uploaded_image

    fake_image = FileStorage(stream=io.BytesIO(b"fake image bytes"), filename="photo.jpg")
    saved_name = save_uploaded_image(fake_image, str(tmp_path))

    assert saved_name is not None
    assert saved_name != "photo.jpg"  # renamed, not the original filename
    assert (tmp_path / saved_name).exists()


# ---------- Registration / auth hardening ----------

def test_registration_rejects_short_password():
    app, client = make_test_client()
    response = client.post(
        "/register",
        data=with_csrf(client, {"name": "Ada", "email": "short@example.com", "password": "abc"}),
    )
    assert response.status_code == 200  # re-renders the form, no redirect
    assert _query_one(app, "SELECT id FROM users WHERE email = %s", ("short@example.com",)) is None


def test_registration_rejects_password_without_special_character():
    # Long enough (8+ chars) but no special character - should still be
    # rejected, since length alone isn't the whole policy.
    app, client = make_test_client()
    response = client.post(
        "/register",
        data=with_csrf(client, {"name": "Ada", "email": "nospecial@example.com", "password": "longenough"}),
    )
    assert response.status_code == 200  # re-renders the form, no redirect
    assert _query_one(app, "SELECT id FROM users WHERE email = %s", ("nospecial@example.com",)) is None


def test_registration_rejects_malformed_email():
    app, client = make_test_client()
    response = client.post(
        "/register",
        data=with_csrf(client, {"name": "Ada", "email": "not-an-email", "password": "secretpw!"}),
    )
    assert response.status_code == 200  # re-renders the form, no redirect
    assert _query_one(app, "SELECT id FROM users WHERE email = %s", ("not-an-email",)) is None


def test_registration_accepts_valid_strong_password():
    app, client = make_test_client()
    client.post(
        "/register",
        data=with_csrf(client, {"name": "Ada", "email": "strongpw@example.com", "password": "correcthorse!9"}),
    )
    assert _query_one(app, "SELECT id FROM users WHERE email = %s", ("strongpw@example.com",)) is not None


def test_login_rate_limited_after_repeated_attempts():
    app, client = make_test_client()
    client.post(
        "/register",
        data=with_csrf(client, {"name": "Ada", "email": "limited@example.com", "password": "secretpw!"}),
    )
    last_response = None
    for _ in range(10):
        last_response = client.post(
            "/login",
            data=with_csrf(client, {"email": "limited@example.com", "password": "wrong-password"}),
        )
    assert last_response.status_code == 429


# ---------- Reviews ----------

def test_resubmitting_review_updates_instead_of_duplicating():
    app, client = make_test_client()
    _login_new_user(client, email="reviewer@example.com")
    client.post("/dashboard", data=with_csrf(client, _recipe_form()))
    recipe_id = _scalar(app, "SELECT id FROM recipes WHERE title = %s", ("Test Soup",))

    client.post(f"/recipes/{recipe_id}/review", data=with_csrf(client, {"rating": "3", "comment": "Okay"}))
    client.post(f"/recipes/{recipe_id}/review", data=with_csrf(client, {"rating": "5", "comment": "Great!"}))

    reviews = _query_all(app, "SELECT rating, comment FROM reviews WHERE recipe_id = %s", (recipe_id,))
    assert len(reviews) == 1
    assert reviews[0]["rating"] == 5
    assert reviews[0]["comment"] == "Great!"


# ---------- Uploaded file cleanup ----------

def test_deleting_recipe_removes_its_uploaded_image(tmp_path, monkeypatch):
    app, client = make_test_client()
    monkeypatch.setattr(app, "static_folder", str(tmp_path))
    (tmp_path / "uploads").mkdir()
    image_path = tmp_path / "uploads" / "orphan-test.jpg"
    image_path.write_bytes(b"fake image bytes")

    _login_new_user(client, email="cleanup@example.com")
    with client.session_transaction() as sess:
        user_id = sess["user_id"]

    with app.app_context():
        from app.database import get_or_create_category
        from app.db import execute

        category_id = get_or_create_category("Testland")
        recipe_id = execute(
            """
            INSERT INTO recipes
                (title, description, category_id, difficulty, minutes, servings,
                 image_url, ingredients, steps, owner_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                "Cleanup Soup", "desc", category_id, "Easy", 10, 1,
                "/static/uploads/orphan-test.jpg", "water", "Boil.", user_id,
            ),
        )

    client.post(f"/recipes/{recipe_id}/delete", data=with_csrf(client))
    assert not image_path.exists()


# ---------- Calories (optional field + search filter) ----------

def test_add_recipe_with_calories_saves_value():
    app, client = make_test_client()
    _login_new_user(client)
    client.post("/dashboard", data=with_csrf(client, _recipe_form(calories="410")))
    calories = _scalar(app, "SELECT calories FROM recipes WHERE title = %s", ("Test Soup",))
    assert calories == 410


def test_add_recipe_without_calories_still_works():
    # Calories is optional - omitting it entirely must not block saving,
    # since older recipes and quick entries won't always have it.
    app, client = make_test_client()
    _login_new_user(client, email="nocal@example.com")
    client.post("/dashboard", data=with_csrf(client, _recipe_form()))
    recipe = _query_one(app, "SELECT calories FROM recipes WHERE title = %s", ("Test Soup",))
    assert recipe is not None
    assert recipe["calories"] is None


def test_add_recipe_rejects_negative_calories():
    app, client = make_test_client()
    _login_new_user(client, email="negcal@example.com")
    client.post("/dashboard", data=with_csrf(client, _recipe_form(title="Bad Cal Soup", calories="-5")))
    assert _query_one(app, "SELECT id FROM recipes WHERE title = %s", ("Bad Cal Soup",)) is None


def test_calorie_filter_narrows_results():
    app, client = make_test_client()
    _login_new_user(client)
    client.post("/dashboard", data=with_csrf(client, _recipe_form(title="Light Salad", calories="200")))
    client.post("/dashboard", data=with_csrf(client, _recipe_form(title="Heavy Roast", calories="900")))

    response = client.get("/recipes?calories=under300")
    assert response.status_code == 200
    assert b"Light Salad" in response.data
    assert b"Heavy Roast" not in response.data


# ---------- PDF download ----------
# These two cover the exact gap that let a real crash reach the browser
# before it was caught by anything automated - see _break_long_words()
# and _write_line() in app/blueprints/recipes.py for the fixes they cover.

def test_download_recipe_pdf_returns_pdf():
    app, client = make_test_client()
    _login_new_user(client)
    client.post("/dashboard", data=with_csrf(client, _recipe_form()))
    recipe_id = _scalar(app, "SELECT id FROM recipes WHERE title = %s", ("Test Soup",))

    response = client.get(f"/recipes/{recipe_id}/download")
    assert response.status_code == 200
    assert response.mimetype == "application/pdf"
    assert response.data[:4] == b"%PDF"


def test_download_recipe_pdf_handles_long_unbroken_field():
    # Regression test: a recipe field with one long run of characters and
    # no spaces (e.g. the free-text Cuisine box) used to crash FPDF
    # entirely with "Not enough horizontal space to render a single
    # character" instead of wrapping the line.
    app, client = make_test_client()
    _login_new_user(client, email="longword@example.com")
    client.post(
        "/dashboard",
        data=with_csrf(client, _recipe_form(title="Long Word Soup", cuisine="a" * 200)),
    )
    recipe_id = _scalar(app, "SELECT id FROM recipes WHERE title = %s", ("Long Word Soup",))

    response = client.get(f"/recipes/{recipe_id}/download")
    assert response.status_code == 200
    assert response.mimetype == "application/pdf"
