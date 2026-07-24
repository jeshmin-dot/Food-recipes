from werkzeug.security import check_password_hash, generate_password_hash

from app.db import execute, query_one


def create_user(name, email, password):
    execute(
        "INSERT INTO users (name, email, password_hash) VALUES (%s, %s, %s)",
        (name.strip(), email.strip().lower(), generate_password_hash(password)),
    )


def find_user_by_email(email):
    return query_one("SELECT * FROM users WHERE email = %s", (email.strip().lower(),))


def verify_user(email, password):
    user = find_user_by_email(email)
    if user and check_password_hash(user["password_hash"], password):
        return user
    return None