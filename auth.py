"""
auth.py — Admin authentication for the portfolio dashboard.

Uses bcrypt for password hashing. The password hash is stored in
environment variables / Streamlit secrets — never in the source code.

Usage
-----
Generate a hash once:
    python -c "import bcrypt; print(bcrypt.hashpw(b'yourpassword', bcrypt.gensalt()).decode())"
Paste the result into .env as ADMIN_PASSWORD_HASH=<hash>
"""

import bcrypt
import streamlit as st
from config import ADMIN_USERNAME, ADMIN_PASSWORD_HASH


def _check_password(plain: str, hashed: str) -> bool:
    """Return True if plain text matches the stored bcrypt hash."""
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False


def login_form() -> None:
    """Render a compact login form. Sets st.session_state.authenticated on success."""
    st.markdown("### 🔐 Admin Login")
    with st.form("login_form", clear_on_submit=True):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Log in")

    if submitted:
        if not ADMIN_PASSWORD_HASH:
            st.error(
                "No admin password configured. "
                "Set ADMIN_PASSWORD_HASH in your .env or Streamlit secrets."
            )
            return
        if username == ADMIN_USERNAME and _check_password(password, ADMIN_PASSWORD_HASH):
            st.session_state["authenticated"] = True
            st.session_state["username"] = username
            st.success("Logged in successfully.")
            st.rerun()
        else:
            st.error("Invalid credentials.")


def logout() -> None:
    st.session_state["authenticated"] = False
    st.session_state.pop("username", None)
    st.rerun()


def is_authenticated() -> bool:
    """Return True if the current session is an authenticated admin."""
    return bool(st.session_state.get("authenticated", False))


def require_auth() -> bool:
    """
    Show login form if not authenticated.
    Returns True when the user is authenticated.
    """
    if is_authenticated():
        return True
    login_form()
    return False
