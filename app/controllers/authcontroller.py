from werkzeug.security import check_password_hash, generate_password_hash

from app.models import User, db


def create_user(name, email, password):
    user = User(
        name=name.strip(),
        email=email.strip().lower(),
        password_hash=generate_password_hash(password),
    )
    db.session.add(user)
    db.session.commit()


def find_user_by_email(email):
    return User.query.filter_by(email=email.strip().lower()).first()


def verify_user(email, password):
    user = find_user_by_email(email)
    if user and check_password_hash(user.password_hash, password):
        return user
    return None
