"""
auth.py — Admin authentication.

Password is never stored in source code: only a bcrypt hash, supplied via
Streamlit secrets or an environment variable (see config.py). A short
per-session lockout after repeated failed attempts discourages naive
brute-forcing without needing any extra infrastructure.
"""

import time
import bcrypt
import streamlit as st
from config import ADMIN_USERNAME, ADMIN_PASSWORD_HASH

MAX_ATTEMPTS = 5
LOCKOUT_SECONDS = 60


def _check_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False


def _locked_out() -> bool:
    until = st.session_state.get("login_lockout_until", 0)
    return time.time() < until


def login_form() -> None:
    """Render a compact login form. Sets st.session_state.authenticated on success."""
    if _locked_out():
        remaining = int(st.session_state["login_lockout_until"] - time.time())
        st.error(f"Too many failed attempts. Try again in {remaining}s.")
        return

    st.markdown("### 🔐 Admin Login")
    with st.form("login_form", clear_on_submit=True):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Log in")

    if submitted:
        if not ADMIN_PASSWORD_HASH:
            st.error(
                "No admin password configured. Set ADMIN_PASSWORD_HASH in "
                "Streamlit secrets or your .env file."
            )
            return
        if username == ADMIN_USERNAME and _check_password(password, ADMIN_PASSWORD_HASH):
            st.session_state["authenticated"] = True
            st.session_state["username"] = username
            st.session_state["failed_attempts"] = 0
            st.success("Logged in successfully.")
            st.rerun()
        else:
            st.session_state["failed_attempts"] = st.session_state.get("failed_attempts", 0) + 1
            if st.session_state["failed_attempts"] >= MAX_ATTEMPTS:
                st.session_state["login_lockout_until"] = time.time() + LOCKOUT_SECONDS
                st.session_state["failed_attempts"] = 0
                st.error(f"Too many failed attempts. Locked for {LOCKOUT_SECONDS}s.")
            else:
                st.error("Invalid credentials.")


def logout() -> None:
    st.session_state["authenticated"] = False
    st.session_state.pop("username", None)
    st.rerun()


def is_authenticated() -> bool:
    return bool(st.session_state.get("authenticated", False))


def require_auth() -> bool:
    if is_authenticated():
        return True
    login_form()
    return False
