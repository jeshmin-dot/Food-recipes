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
    return app.test_client()


def test_home_page_loads():
    client = make_test_client()
    response = client.get("/")
    assert response.status_code == 200
    assert b"Recipe Garden" in response.data


def test_recipe_pages_load():
    client = make_test_client()
    assert client.get("/recipes").status_code == 200
    assert client.get("/cook-mode").status_code == 200


def test_dashboard_requires_login():
    client = make_test_client()
    response = client.get("/dashboard")
    assert response.status_code == 302


if __name__ == "__main__":
    test_home_page_loads()
    test_recipe_pages_load()
    test_dashboard_requires_login()
    print("Recipe Garden smoke test passed.")
