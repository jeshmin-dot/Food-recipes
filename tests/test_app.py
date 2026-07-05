import io
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def make_test_client():
    tmp_dir = tempfile.mkdtemp()
    os.environ["DATABASE_PATH"] = os.path.join(tmp_dir, "test.db")

    from app import create_app

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


# ---------- Registration ----------

def test_registration_creates_user():
    app, client = make_test_client()
    response = client.post(
        "/register",
        data=with_csrf(client, {"name": "Ada", "email": "ada@example.com", "password": "secretpw"}),
        follow_redirects=True,
    )
    assert response.status_code == 200
    with app.app_context():
        from app.models import User
        assert User.query.filter_by(email="ada@example.com").first() is not None


def test_registration_duplicate_email_rejected():
    app, client = make_test_client()
    data = {"name": "Ada", "email": "dupe@example.com", "password": "secretpw"}
    client.post("/register", data=with_csrf(client, data))
    response = client.post("/register", data=with_csrf(client, data), follow_redirects=True)
    assert response.status_code == 200
    with app.app_context():
        from app.models import User
        assert User.query.filter_by(email="dupe@example.com").count() == 1


def test_password_is_hashed_not_plaintext():
    app, client = make_test_client()
    client.post(
        "/register",
        data=with_csrf(client, {"name": "Ada", "email": "hash@example.com", "password": "secretpw"}),
    )
    with app.app_context():
        from app.models import User
        user = User.query.filter_by(email="hash@example.com").first()
        assert user.password_hash != "secretpw"
        assert user.password_hash.startswith(("pbkdf2:", "scrypt:"))


# ---------- Login / logout ----------

def test_login_success():
    app, client = make_test_client()
    client.post(
        "/register",
        data=with_csrf(client, {"name": "Ada", "email": "login@example.com", "password": "secretpw"}),
    )
    response = client.post(
        "/login",
        data=with_csrf(client, {"email": "login@example.com", "password": "secretpw"}),
        follow_redirects=True,
    )
    assert response.status_code == 200
    with client.session_transaction() as sess:
        assert sess.get("user_id") is not None


def test_login_wrong_password_fails():
    app, client = make_test_client()
    client.post(
        "/register",
        data=with_csrf(client, {"name": "Ada", "email": "wrongpw@example.com", "password": "secretpw"}),
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
        data=with_csrf(client, {"name": "Ada", "email": "logout@example.com", "password": "secretpw"}),
    )
    client.post(
        "/login",
        data=with_csrf(client, {"email": "logout@example.com", "password": "secretpw"}),
    )
    client.get("/logout")
    with client.session_transaction() as sess:
        assert sess.get("user_id") is None


# ---------- CRUD ----------

def _login_new_user(client, email="crud@example.com"):
    client.post(
        "/register",
        data=with_csrf(client, {"name": "Cook", "email": email, "password": "secretpw"}),
    )
    client.post("/login", data=with_csrf(client, {"email": email, "password": "secretpw"}))


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


def test_add_recipe_creates_recipe():
    app, client = make_test_client()
    _login_new_user(client)
    client.post("/dashboard", data=with_csrf(client, _recipe_form()))
    with app.app_context():
        from app.models import Recipe
        assert Recipe.query.filter_by(title="Test Soup").first() is not None


def test_edit_recipe_updates_fields():
    app, client = make_test_client()
    _login_new_user(client)
    client.post("/dashboard", data=with_csrf(client, _recipe_form()))
    with app.app_context():
        from app.models import Recipe
        recipe_id = Recipe.query.filter_by(title="Test Soup").first().id
    client.post(f"/recipes/{recipe_id}/edit", data=with_csrf(client, _recipe_form(title="Updated Soup")))
    with app.app_context():
        from app.models import Recipe
        assert Recipe.query.get(recipe_id).title == "Updated Soup"


def test_non_owner_cannot_edit_recipe():
    app, client = make_test_client()
    _login_new_user(client, email="owner@example.com")
    client.post("/dashboard", data=with_csrf(client, _recipe_form()))
    with app.app_context():
        from app.models import Recipe
        recipe_id = Recipe.query.filter_by(title="Test Soup").first().id

    client.get("/logout")
    _login_new_user(client, email="intruder@example.com")
    response = client.get(f"/recipes/{recipe_id}/edit")
    assert response.status_code == 403


def test_delete_recipe_removes_it():
    app, client = make_test_client()
    _login_new_user(client)
    client.post("/dashboard", data=with_csrf(client, _recipe_form()))
    with app.app_context():
        from app.models import Recipe
        recipe_id = Recipe.query.filter_by(title="Test Soup").first().id
    client.post(f"/recipes/{recipe_id}/delete", data=with_csrf(client))
    with app.app_context():
        from app.models import Recipe
        assert Recipe.query.get(recipe_id) is None


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
