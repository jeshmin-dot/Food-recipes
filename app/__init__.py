import os
import secrets
from datetime import datetime

from flask import Flask, abort, render_template, request, session

import config
from app.blueprints.account import account_bp
from app.blueprints.admin import admin_bp
from app.blueprints.main import main_bp
from app.blueprints.meal_planner import meal_planner_bp
from app.blueprints.recipes import recipes_bp
from app.controllers.database import initialize_database
from app.models import db
from app.routes.authroutes import auth_bp


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = config.SECRET_KEY
    app.config["DEBUG"] = config.DEBUG
    # Read DATABASE_URL from the live environment on every call, not just
    # config.DATABASE_URL (a value computed once, the first time the config
    # module is imported). Without this, calling create_app() more than
    # once in the same process - which is exactly what the test suite does,
    # once per test, each pointed at its own throwaway SQLite file - would
    # keep reusing whichever database URL was in effect the first time
    # config.py loaded, silently sharing one database across every test.
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", config.DATABASE_URL)
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SESSION_COOKIE_HTTPONLY"] = config.SESSION_COOKIE_HTTPONLY
    app.config["SESSION_COOKIE_SAMESITE"] = config.SESSION_COOKIE_SAMESITE
    app.config["SESSION_COOKIE_SECURE"] = config.SESSION_COOKIE_SECURE

    db.init_app(app)
    with app.app_context():
        initialize_database()

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(recipes_bp)
    app.register_blueprint(account_bp)
    app.register_blueprint(meal_planner_bp)
    app.register_blueprint(admin_bp)

    def get_csrf_token():
        token = session.get("csrf_token")
        if not token:
            token = secrets.token_urlsafe(32)
            session["csrf_token"] = token
        return token

    @app.context_processor
    def inject_layout_data():
        return {
            "app_name": config.APP_NAME,
            "year": datetime.now().year,
            "csrf_token": get_csrf_token,
            "current_user": session.get("user_name"),
            "is_admin": session.get("user_role") == "admin",
        }

    @app.before_request
    def protect_forms():
        if request.method == "POST":
            sent = request.form.get("csrf_token", "")
            stored = session.get("csrf_token", "")
            if not sent or not stored or not secrets.compare_digest(sent, stored):
                abort(400, description="Invalid form token.")

    @app.errorhandler(403)
    def handle_forbidden(_error):
        return render_template(
            "error.html",
            error_title="Access denied",
            error_message="You don't have permission to view this page.",
        ), 403

    @app.errorhandler(404)
    def handle_not_found(_error):
        return render_template(
            "error.html",
            error_title="Page not found",
            error_message="We couldn't find the page you were looking for.",
        ), 404

    @app.errorhandler(429)
    def handle_rate_limited(_error):
        return render_template(
            "error.html",
            error_title="Slow down",
            error_message="Too many attempts. Please wait a few minutes and try again.",
        ), 429

    @app.errorhandler(500)
    def handle_server_error(_error):
        db.session.rollback()
        return render_template(
            "error.html",
            error_title="Something went wrong",
            error_message="An unexpected error occurred. Please try again.",
        ), 500

    return app