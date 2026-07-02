from werkzeug.security import check_password_hash, generate_password_hash

from app.database import get_connection


def create_user(name, email, password):
    with get_connection() as db:
        db.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            (name.strip(), email.strip().lower(), generate_password_hash(password)),
        )


def find_user_by_email(email):
    with get_connection() as db:
        return db.execute("SELECT * FROM users WHERE email = ?", (email.strip().lower(),)).fetchone()


def verify_user(email, password):
    user = find_user_by_email(email)
    if user and check_password_hash(user["password_hash"], password):
        return user
    return None
