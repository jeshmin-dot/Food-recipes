"""Shared view decorators: access control and basic abuse protection.

These used to be defined as closures inside create_app(). Pulling them out
into their own module lets every blueprint import the same decorator
instead of each blueprint needing a reference to the app factory.
"""

import time
from collections import defaultdict
from functools import wraps

from flask import abort, flash, redirect, request, session, url_for

# ---------------------------------------------------------------------------
# Access control
# ---------------------------------------------------------------------------


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            flash("Please log in to continue.", "error")
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)

    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if session.get("user_role") != "admin":
            abort(403, description="You don't have permission to view this page.")
        return view(*args, **kwargs)

    return wrapped


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------
# A minimal in-memory fixed-window limiter for the login/register forms,
# which are the two endpoints most exposed to credential-stuffing and
# account-enumeration attacks. It is intentionally dependency-free so the
# project doesn't need an extra package (or a Redis instance) just for a
# classroom assignment - see REPORT.md ("Challenges Faced and
# Improvements") for why a shared cache (e.g. Flask-Limiter + Redis) would
# be the right upgrade for a multi-process production deployment, where a
# plain in-process dict no longer works because each worker process would
# keep its own counters.

_attempts = defaultdict(list)


def _client_key():
    # X-Forwarded-For is attacker-controlled unless a trusted proxy strips
    # it, but request.remote_addr is the best we can do without knowing the
    # deployment's proxy setup.
    return request.remote_addr or "unknown"


def rate_limit(max_attempts=5, window_seconds=300):
    """Limit POSTs to `max_attempts` per client per `window_seconds`.

    GET requests are never limited (only the form submission matters for
    brute-force protection).
    """

    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if request.method == "POST":
                now = time.time()
                key = (view.__name__, _client_key())
                attempts = _attempts[key]
                attempts[:] = [ts for ts in attempts if now - ts < window_seconds]
                if len(attempts) >= max_attempts:
                    abort(429, description="Too many attempts. Please wait a few minutes and try again.")
                attempts.append(now)
            return view(*args, **kwargs)

        return wrapped

    return decorator


def _reset_rate_limits():
    """Test-only helper: clears rate-limit state between test runs."""
    _attempts.clear()