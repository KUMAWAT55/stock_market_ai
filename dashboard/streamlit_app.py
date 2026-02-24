from __future__ import annotations
"""Streamlit dashboard for authenticated, compliance-gated research analytics."""

import hashlib
import hmac
import json
import os
import secrets
import sys
import time
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError

# Ensure project-root imports work when Streamlit is launched from any directory.
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from compliance.disclaimer import DISCLAIMER_VERSION, get_disclaimer
from config.config import get_settings
from features.indicators import add_indicators


API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")
APP_VERSION = "tradeiq_dashboard_auth_v1_2026-02-24"
PASSWORD_ITERATIONS = 260000


def _apply_theme() -> None:
    """Inject unified dashboard CSS theme and component-level style overrides."""
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Manrope:wght@600;700;800&family=Source+Sans+3:wght@400;600;700&display=swap');

        :root {
            --bg: #060606;
            --bg-soft: #101010;
            --surface: #171717;
            --surface-soft: #1d1d1d;
            --surface-strong: #252525;
            --border: #303030;
            --border-strong: #4a4a4a;
            --text-main: #f2f2f2;
            --text-dim: #b8b8b8;
            --text-muted: #969696;
            --brand: #8c8c8c;
            --ok: #34d399;
            --warn: #fbbf24;
            --error: #f87171;
        }

        .stApp {
            color: var(--text-main);
            font-family: "Source Sans 3", sans-serif;
            background:
                radial-gradient(950px 560px at -8% -20%, rgba(118, 118, 118, 0.14), transparent 72%),
                radial-gradient(780px 420px at 108% -6%, rgba(84, 84, 84, 0.12), transparent 66%),
                linear-gradient(180deg, var(--bg) 0%, var(--bg-soft) 100%);
        }

        .main .block-container {
            max-width: 1320px;
            padding-top: 0.85rem;
            padding-bottom: 1.1rem;
            padding-left: 1rem;
            padding-right: 1rem;
        }

        header[data-testid="stHeader"],
        div[data-testid="stToolbar"],
        div[data-testid="stDecoration"] {
            background: transparent !important;
        }

        h1, h2, h3 {
            font-family: "Manrope", sans-serif !important;
            color: var(--text-main) !important;
            letter-spacing: 0.01em;
        }

        p, label, span, div, small {
            color: var(--text-main);
        }

        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #111111 0%, #0a0a0a 100%);
            border-right: 1px solid var(--border);
        }

        [data-testid="stSidebar"] * {
            color: var(--text-main) !important;
        }

        .auth-card,
        .panel-card {
            background: linear-gradient(160deg, #171717 0%, #131313 100%);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 0.78rem 0.84rem;
            margin-bottom: 0.5rem;
        }

        .app-title {
            position: relative;
            border: 1px solid #3a3a3a;
            border-radius: 14px;
            padding: 0.9rem 1rem;
            margin-bottom: 0.65rem;
            background: linear-gradient(135deg, #1d1d1d 0%, #282828 52%, #1a1a1a 100%);
            overflow: hidden;
        }

        .app-title::before {
            content: "";
            position: absolute;
            inset: 0 auto 0 0;
            width: 6px;
            background: linear-gradient(180deg, #8d8d8d, #5f5f5f);
        }

        .app-title > * {
            position: relative;
            z-index: 1;
        }

        .app-kicker {
            color: #bfbfbf;
            font-size: 0.66rem;
            letter-spacing: 0.11em;
            text-transform: uppercase;
            font-weight: 800;
            margin-bottom: 0.2rem;
        }

        .app-sub {
            color: var(--text-dim);
            font-size: 0.82rem;
            font-weight: 600;
            margin-top: 0.2rem;
        }

        .consent-pending {
            border: 1px solid rgba(251, 191, 36, 0.44);
            border-radius: 12px;
            background: linear-gradient(135deg, rgba(180, 83, 9, 0.16), rgba(23, 23, 23, 0.92));
            padding: 0.7rem 0.8rem;
            margin-bottom: 0.6rem;
        }

        .consent-active {
            border: 1px solid rgba(52, 211, 153, 0.42);
            border-radius: 12px;
            background: linear-gradient(135deg, rgba(22, 163, 74, 0.16), rgba(23, 23, 23, 0.92));
            padding: 0.7rem 0.8rem;
            margin-bottom: 0.6rem;
        }

        [data-baseweb="select"] > div,
        div[data-baseweb="base-input"],
        div[data-baseweb="input"] > div,
        div[data-testid="stTextInput"] > div > div,
        div[data-testid="stNumberInput"] > div > div,
        div[data-testid="stTextArea"] > div > div,
        div[data-testid="stDateInput"] > div > div,
        div[data-testid="stTimeInput"] > div > div {
            background: var(--surface) !important;
            border: 1px solid var(--border) !important;
            border-radius: 10px !important;
            box-shadow: none !important;
        }

        [data-baseweb="select"] > div:hover,
        div[data-baseweb="base-input"]:hover,
        div[data-baseweb="input"] > div:hover,
        div[data-testid="stTextInput"] > div > div:hover,
        div[data-testid="stNumberInput"] > div > div:hover,
        div[data-testid="stTextArea"] > div > div:hover,
        div[data-testid="stDateInput"] > div > div:hover,
        div[data-testid="stTimeInput"] > div > div:hover {
            border-color: var(--border-strong) !important;
        }

        [data-baseweb="select"] > div:focus-within,
        div[data-baseweb="base-input"]:focus-within,
        div[data-baseweb="input"] > div:focus-within,
        div[data-testid="stTextInput"] > div > div:focus-within,
        div[data-testid="stNumberInput"] > div > div:focus-within,
        div[data-testid="stTextArea"] > div > div:focus-within,
        div[data-testid="stDateInput"] > div > div:focus-within,
        div[data-testid="stTimeInput"] > div > div:focus-within {
            border-color: var(--brand) !important;
            box-shadow: 0 0 0 3px rgba(140, 140, 140, 0.2) !important;
        }

        div[data-testid="stTextInput"] input,
        div[data-testid="stNumberInput"] input,
        div[data-testid="stDateInput"] input,
        div[data-testid="stTimeInput"] input,
        div[data-testid="stTextArea"] textarea,
        input[type="number"],
        input[type="text"],
        input[type="password"],
        textarea {
            color: var(--text-main) !important;
            background: transparent !important;
            caret-color: var(--text-main) !important;
        }

        div[data-testid="stTextInput"] input::placeholder,
        div[data-testid="stNumberInput"] input::placeholder,
        div[data-testid="stDateInput"] input::placeholder,
        div[data-testid="stTimeInput"] input::placeholder,
        div[data-testid="stTextArea"] textarea::placeholder,
        input::placeholder,
        textarea::placeholder {
            color: var(--text-muted) !important;
            opacity: 1 !important;
        }

        div[data-testid="stTextInput"] label,
        div[data-testid="stNumberInput"] label,
        div[data-testid="stDateInput"] label,
        div[data-testid="stTimeInput"] label,
        div[data-testid="stTextArea"] label,
        div[data-testid="stSelectbox"] label {
            color: #d7d7d7 !important;
            font-weight: 700 !important;
        }

        div[data-testid="stSelectbox"] [data-baseweb="select"] span,
        div[data-testid="stSelectbox"] [data-baseweb="select"] div,
        div[data-testid="stSelectbox"] [data-baseweb="select"] input {
            color: #ececec !important;
            opacity: 1 !important;
        }

        div[data-testid="stSelectbox"] [data-baseweb="select"] svg {
            fill: #bcbcbc !important;
        }

        div[data-testid="stNumberInputStepUp"],
        div[data-testid="stNumberInputStepDown"],
        div[data-testid="stTextInput"] button,
        div[data-testid="stNumberInput"] button,
        div[data-testid="stDateInput"] button,
        div[data-testid="stTimeInput"] button {
            background: #1c1c1c !important;
            border: 1px solid var(--border) !important;
            color: #d9d9d9 !important;
            border-radius: 8px !important;
        }

        div[data-testid="stNumberInputStepUp"]:hover,
        div[data-testid="stNumberInputStepDown"]:hover,
        div[data-testid="stTextInput"] button:hover,
        div[data-testid="stNumberInput"] button:hover,
        div[data-testid="stDateInput"] button:hover,
        div[data-testid="stTimeInput"] button:hover {
            border-color: var(--border-strong) !important;
        }

        [data-baseweb="popover"],
        [data-baseweb="popover"] > div,
        div[role="listbox"],
        ul[role="listbox"],
        [data-baseweb="menu"],
        [data-baseweb="select"] [role="listbox"] {
            background: #151515 !important;
            border: 1px solid var(--border) !important;
            border-radius: 10px !important;
            box-shadow: 0 12px 24px rgba(0, 0, 0, 0.45) !important;
        }

        [data-baseweb="popover"] [role="option"],
        [data-baseweb="menu"] li,
        [role="listbox"] [role="option"] {
            color: var(--text-main) !important;
            background: transparent !important;
            opacity: 1 !important;
        }

        [data-baseweb="popover"] [role="option"][aria-selected="true"],
        [role="listbox"] [role="option"][aria-selected="true"] {
            background: rgba(140, 140, 140, 0.25) !important;
        }

        [data-baseweb="popover"] [role="option"]:hover,
        [role="listbox"] [role="option"]:hover {
            background: rgba(140, 140, 140, 0.16) !important;
        }

        div[data-testid="stButton"] > button,
        div[data-testid="stFormSubmitButton"] > button {
            width: 100%;
            border-radius: 10px !important;
            border: 1px solid var(--border) !important;
            background: linear-gradient(135deg, #252525 0%, #1a1a1a 100%) !important;
            color: #f6f6f6 !important;
            font-weight: 700 !important;
        }

        div[data-testid="stButton"] > button:hover,
        div[data-testid="stFormSubmitButton"] > button:hover {
            border-color: var(--border-strong) !important;
            background: linear-gradient(135deg, #2e2e2e 0%, #202020 100%) !important;
        }

        div[data-testid="metric-container"] {
            background: linear-gradient(160deg, #171717 0%, #131313 100%);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 0.56rem 0.66rem;
            margin-bottom: 0.4rem;
        }

        [data-testid="stMetricValue"] {
            color: var(--text-main) !important;
            font-weight: 800 !important;
        }

        [data-testid="stMetricLabel"],
        [data-testid="stCaptionContainer"] * {
            color: var(--text-dim) !important;
        }

        div[data-testid="stAlert"] {
            background: #171717 !important;
            border: 1px solid var(--border) !important;
            color: var(--text-main) !important;
            border-radius: 10px !important;
        }

        [data-testid="stPlotlyChart"] {
            background: #151515 !important;
            border: 1px solid var(--border) !important;
            border-radius: 12px !important;
            padding: 0.45rem !important;
        }

        [data-testid="stPlotlyChart"] .modebar {
            background: rgba(0, 0, 0, 0.4) !important;
            border-radius: 8px !important;
        }

        [data-testid="stPlotlyChart"] .modebar-btn svg {
            fill: #d7d7d7 !important;
        }

        [data-testid="stCodeBlock"],
        [data-testid="stCodeBlock"] pre,
        [data-testid="stCodeBlock"] code,
        [data-testid="stJson"],
        [data-testid="stJson"] pre,
        [data-testid="stJson"] code {
            background: #141414 !important;
            border: 1px solid var(--border) !important;
            border-radius: 12px !important;
            color: #ececec !important;
        }

        .table-wrap {
            border: 1px solid var(--border);
            border-radius: 12px;
            overflow: auto;
            background: #151515;
        }

        table.signals-table {
            border-collapse: collapse;
            width: 100%;
            min-width: 860px;
            font-size: 0.85rem;
        }

        table.signals-table thead th {
            background: #212121;
            color: #e9e9e9;
            font-weight: 700;
            text-align: left;
            border-bottom: 1px solid var(--border);
            padding: 0.48rem 0.5rem;
            white-space: nowrap;
        }

        table.signals-table tbody td {
            background: #171717;
            color: #e5e5e5;
            border-bottom: 1px solid #2b2b2b;
            padding: 0.42rem 0.5rem;
            white-space: nowrap;
        }

        table.signals-table tbody tr:hover td {
            background: #1f1f1f;
        }

        .json-panel {
            margin: 0;
            padding: 0.72rem 0.82rem;
            border-radius: 12px;
            border: 1px solid var(--border);
            background: #141414;
            color: #e8e8e8;
            font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
            font-size: 0.86rem;
            line-height: 1.42;
            white-space: pre-wrap;
            word-break: break-word;
        }

        div[data-testid="stSelectboxVirtualDropdown"],
        div[data-testid="stSelectboxVirtualDropdown"] > div,
        div[data-testid="stSelectboxVirtualDropdown"] ul,
        div[data-testid="stSelectboxVirtualDropdown"] li {
            background: #151515 !important;
            color: #ececec !important;
            border-color: var(--border) !important;
        }

        div[data-testid="stSelectboxVirtualDropdown"] [role="option"],
        div[data-testid="stSelectboxVirtualDropdown"] [role="option"] * {
            color: #ececec !important;
            opacity: 1 !important;
        }

        div[data-testid="stSelectboxVirtualDropdown"] [role="option"]:hover,
        div[data-testid="stSelectboxVirtualDropdown"] li:hover {
            background: rgba(140, 140, 140, 0.18) !important;
        }

        div[data-testid="stSelectboxVirtualDropdown"] [aria-selected="true"] {
            background: rgba(140, 140, 140, 0.26) !important;
        }

        div[data-baseweb="popover"] ul,
        div[data-baseweb="popover"] li,
        div[data-baseweb="popover"] [role="listbox"],
        div[data-baseweb="popover"] [role="option"],
        div[data-baseweb="popover"] [role="option"] * {
            background: transparent !important;
            color: #ececec !important;
            opacity: 1 !important;
        }

        div[data-baseweb="popover"] [role="option"]:hover {
            background: rgba(140, 140, 140, 0.18) !important;
        }

        div[data-baseweb="popover"] [role="option"][aria-selected="true"] {
            background: rgba(140, 140, 140, 0.26) !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


@st.cache_resource(show_spinner=False)
def _get_engine() -> Engine:
    """Return cached SQLAlchemy engine for dashboard-side auth/compliance tables."""
    settings = get_settings()
    return create_engine(settings.database_url, pool_pre_ping=True, future=True)


def _init_portal_tables(engine: Engine) -> bool:
    """Create dashboard auth and consent tables if not present."""
    ddl = """
    CREATE TABLE IF NOT EXISTS app_users (
        id BIGSERIAL PRIMARY KEY,
        username VARCHAR(64) NOT NULL UNIQUE,
        email VARCHAR(256) NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        full_name VARCHAR(128),
        is_active BOOLEAN NOT NULL DEFAULT TRUE,
        created_at TIMESTAMP NOT NULL DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS user_subscriptions (
        id BIGSERIAL PRIMARY KEY,
        user_id BIGINT NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
        plan_name VARCHAR(64) NOT NULL DEFAULT 'TradeIQ Pro',
        status VARCHAR(32) NOT NULL DEFAULT 'active',
        start_at TIMESTAMP,
        end_at TIMESTAMP,
        payment_reference VARCHAR(128),
        created_at TIMESTAMP NOT NULL DEFAULT NOW(),
        UNIQUE(user_id)
    );

    CREATE TABLE IF NOT EXISTS compliance_consents (
        id BIGSERIAL PRIMARY KEY,
        user_key VARCHAR(128) NOT NULL,
        disclaimer_version VARCHAR(64) NOT NULL,
        accepted_at TIMESTAMP NOT NULL DEFAULT NOW(),
        app_version VARCHAR(64),
        created_at TIMESTAMP NOT NULL DEFAULT NOW(),
        UNIQUE(user_key, disclaimer_version)
    );

    CREATE TABLE IF NOT EXISTS compliance_audit_logs (
        id BIGSERIAL PRIMARY KEY,
        user_key VARCHAR(128) NOT NULL,
        event_type VARCHAR(128) NOT NULL,
        symbol VARCHAR(64),
        payload JSONB,
        created_at TIMESTAMP NOT NULL DEFAULT NOW()
    );
    """
    try:
        with engine.begin() as conn:
            for stmt in [s.strip() for s in ddl.split(";") if s.strip()]:
                conn.execute(text(stmt))
        return True
    except Exception as exc:
        st.error(f"Unable to initialize auth/compliance tables: {exc}")
        return False


def _hash_password(password: str, salt_hex: str | None = None) -> str:
    """Hash password using PBKDF2-HMAC-SHA256 with per-user salt."""
    salt = bytes.fromhex(salt_hex) if salt_hex else secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PASSWORD_ITERATIONS)
    return f"pbkdf2_sha256${PASSWORD_ITERATIONS}${salt.hex()}${digest.hex()}"


def _verify_password(password: str, stored_hash: str) -> bool:
    """Verify plain password against stored PBKDF2 hash representation."""
    try:
        algo, iterations_s, salt_hex, digest_hex = stored_hash.split("$", 3)
        if algo != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            bytes.fromhex(salt_hex),
            int(iterations_s),
        )
        return hmac.compare_digest(digest.hex(), digest_hex)
    except Exception:
        return False


def _audit_log(engine: Engine, user_key: str, event_type: str, symbol: str | None = None, payload: dict[str, Any] | None = None) -> None:
    """Write dashboard audit event for compliance and activity tracking."""
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO compliance_audit_logs (user_key, event_type, symbol, payload, created_at)
                VALUES (:user_key, :event_type, :symbol, CAST(:payload AS JSONB), :created_at)
                """
            ),
            {
                "user_key": user_key,
                "event_type": event_type,
                "symbol": symbol,
                "payload": json.dumps(payload or {}, default=str),
                "created_at": datetime.utcnow(),
            },
        )


def _create_user(engine: Engine, username: str, email: str, password: str, full_name: str) -> tuple[bool, str]:
    """Create new dashboard user and default active subscription row."""
    username = username.strip().lower()
    email = email.strip().lower()
    full_name = full_name.strip()

    if len(username) < 3:
        return False, "Username must be at least 3 characters."
    if "@" not in email:
        return False, "Provide a valid email address."
    if len(password) < 8:
        return False, "Password must be at least 8 characters."

    password_hash = _hash_password(password)
    try:
        with engine.begin() as conn:
            user_id = conn.execute(
                text(
                    """
                    INSERT INTO app_users (username, email, password_hash, full_name, is_active, created_at)
                    VALUES (:username, :email, :password_hash, :full_name, true, :created_at)
                    RETURNING id
                    """
                ),
                {
                    "username": username,
                    "email": email,
                    "password_hash": password_hash,
                    "full_name": full_name or None,
                    "created_at": datetime.utcnow(),
                },
            ).scalar_one()

            conn.execute(
                text(
                    """
                    INSERT INTO user_subscriptions (user_id, status, start_at, created_at)
                    VALUES (:user_id, 'active', :start_at, :created_at)
                    ON CONFLICT (user_id) DO NOTHING
                    """
                ),
                {
                    "user_id": int(user_id),
                    "start_at": datetime.utcnow(),
                    "created_at": datetime.utcnow(),
                },
            )
        return True, "Registration successful. Please login."
    except IntegrityError:
        return False, "Username or email already exists."
    except Exception as exc:
        return False, f"Registration failed: {exc}"


def _get_user_by_id(engine: Engine, user_id: int) -> dict[str, Any] | None:
    """Load active user profile by id."""
    with engine.begin() as conn:
        row = conn.execute(
            text(
                """
                SELECT id, username, email, full_name, is_active
                FROM app_users
                WHERE id = :id
                LIMIT 1
                """
            ),
            {"id": user_id},
        ).mappings().first()
    return dict(row) if row else None


def _authenticate_user(engine: Engine, identifier: str, password: str) -> tuple[bool, dict[str, Any] | None, str]:
    """Authenticate by username/email + password and return session-safe payload."""
    identifier = identifier.strip().lower()
    if not identifier or not password:
        return False, None, "Enter username/email and password."

    with engine.begin() as conn:
        row = conn.execute(
            text(
                """
                SELECT id, username, email, password_hash, full_name, is_active
                FROM app_users
                WHERE lower(username) = :identifier OR lower(email) = :identifier
                LIMIT 1
                """
            ),
            {"identifier": identifier},
        ).mappings().first()

    if row is None:
        return False, None, "User not found."
    user = dict(row)
    if not bool(user.get("is_active")):
        return False, None, "User is inactive."
    if not _verify_password(password, str(user["password_hash"])):
        return False, None, "Invalid password."

    payload = {
        "id": int(user["id"]),
        "username": str(user["username"]),
        "email": str(user["email"]),
        "full_name": str(user.get("full_name") or ""),
    }
    return True, payload, "Login successful."


def _load_consent(engine: Engine, user_key: str) -> dict[str, Any] | None:
    """Load latest consent decision for current disclaimer version."""
    with engine.begin() as conn:
        row = conn.execute(
            text(
                """
                SELECT user_key, disclaimer_version, accepted_at, app_version
                FROM compliance_consents
                WHERE user_key = :user_key
                  AND disclaimer_version = :disclaimer_version
                ORDER BY accepted_at DESC
                LIMIT 1
                """
            ),
            {"user_key": user_key, "disclaimer_version": DISCLAIMER_VERSION},
        ).mappings().first()
    return dict(row) if row else None


def _save_consent(engine: Engine, user_key: str) -> None:
    """Persist consent acceptance for current disclaimer version."""
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO compliance_consents (user_key, disclaimer_version, accepted_at, app_version, created_at)
                VALUES (:user_key, :disclaimer_version, :accepted_at, :app_version, :created_at)
                ON CONFLICT (user_key, disclaimer_version)
                DO UPDATE SET accepted_at = EXCLUDED.accepted_at, app_version = EXCLUDED.app_version
                """
            ),
            {
                "user_key": user_key,
                "disclaimer_version": DISCLAIMER_VERSION,
                "accepted_at": datetime.utcnow(),
                "app_version": APP_VERSION,
                "created_at": datetime.utcnow(),
            },
        )


def _load_symbols() -> list[str]:
    """Load dashboard symbol universe from configured instrument mapping."""
    settings = get_settings()
    mapping = settings.load_symbol_token_map()
    symbols = sorted(set(str(s).upper() for s in mapping.values()))
    return symbols or ["RELIANCE"]


def _get(path: str, params: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """HTTP GET helper for local API with fail-safe `None` on error."""
    try:
        resp = requests.get(f"{API_BASE_URL}{path}", params=params, timeout=8)
        if resp.status_code >= 400:
            return None
        return resp.json()
    except Exception:
        return None


def _post(path: str, params: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """HTTP POST helper for local API with structured error payload."""
    try:
        resp = requests.post(f"{API_BASE_URL}{path}", params=params, timeout=40)
        if resp.status_code >= 400:
            try:
                return {"error": resp.json()}
            except Exception:
                return {"error": {"status_code": resp.status_code, "text": resp.text}}
        return resp.json()
    except Exception as exc:
        return {"error": {"message": str(exc)}}


def _render_json_block(payload: Any) -> None:
    """Render JSON payload in theme-consistent dark panel."""
    try:
        content = json.dumps(payload, indent=2, default=str)
    except Exception:
        content = str(payload)
    st.markdown(f'<pre class="json-panel">{escape(content)}</pre>', unsafe_allow_html=True)


def _render_signals_table(frame: pd.DataFrame) -> None:
    """Render historical signals table with explicit dark HTML styling."""
    display = frame.copy()
    for col in display.columns:
        if pd.api.types.is_float_dtype(display[col]):
            display[col] = display[col].map(lambda val: f"{val:.4f}" if pd.notna(val) else "")
        elif pd.api.types.is_bool_dtype(display[col]):
            display[col] = display[col].map(lambda val: "true" if bool(val) else "false")
    html_table = display.to_html(index=False, classes="signals-table", border=0, escape=True)
    st.markdown(f'<div class="table-wrap">{html_table}</div>', unsafe_allow_html=True)


def _build_chart(candles_df: pd.DataFrame) -> go.Figure:
    """Build candlestick chart with EMA overlays."""
    frame = add_indicators(candles_df)
    fig = go.Figure()
    fig.add_trace(
        go.Candlestick(
            x=frame["candle_start"],
            open=frame["open"],
            high=frame["high"],
            low=frame["low"],
            close=frame["close"],
            name="OHLC",
        )
    )
    fig.add_trace(go.Scatter(x=frame["candle_start"], y=frame["ema_12"], name="EMA12", line=dict(width=1.2)))
    fig.add_trace(go.Scatter(x=frame["candle_start"], y=frame["ema_26"], name="EMA26", line=dict(width=1.2)))
    fig.update_layout(
        template="plotly_dark",
        height=500,
        margin=dict(l=16, r=16, t=30, b=16),
        xaxis_rangeslider_visible=False,
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    )
    return fig


def _auth_gate(engine: Engine) -> dict[str, Any] | None:
    """Render login/register gate and return authenticated user payload."""
    st.session_state.setdefault("auth_user", None)
    st.session_state.setdefault("auth_feedback", "")

    auth_user = st.session_state.get("auth_user")
    if auth_user:
        current = _get_user_by_id(engine, int(auth_user["id"]))
        if current and bool(current.get("is_active")):
            return auth_user
        st.session_state["auth_user"] = None

    st.markdown('<div class="auth-card">', unsafe_allow_html=True)
    st.markdown("### Login Required")
    st.caption("Use your dashboard account to access analytics.")

    feedback = st.session_state.get("auth_feedback")
    if feedback:
        st.info(feedback)
        st.session_state["auth_feedback"] = ""

    login_tab, register_tab = st.tabs(["Login", "Register"])

    with login_tab:
        with st.form("login_form", clear_on_submit=False):
            identifier = st.text_input("Username or Email")
            password = st.text_input("Password", type="password")
            submit_login = st.form_submit_button("Login", use_container_width=True)

        if submit_login:
            ok, payload, message = _authenticate_user(engine, identifier, password)
            if ok and payload is not None:
                st.session_state["auth_user"] = payload
                user_key = f"user:{payload['id']}:{payload['username']}"
                _audit_log(engine, user_key=user_key, event_type="user_login", payload={"identifier": identifier})
                st.rerun()
            st.error(message)

    with register_tab:
        with st.form("register_form", clear_on_submit=True):
            full_name = st.text_input("Full Name")
            username = st.text_input("Username")
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            confirm_password = st.text_input("Confirm Password", type="password")
            submit_register = st.form_submit_button("Create Account", use_container_width=True)

        if submit_register:
            if password != confirm_password:
                st.error("Passwords do not match.")
            else:
                ok, message = _create_user(engine, username=username, email=email, password=password, full_name=full_name)
                if ok:
                    st.success(message)
                else:
                    st.error(message)

    st.markdown("</div>", unsafe_allow_html=True)
    return None


def _render_header() -> None:
    """Render dashboard hero/header block."""
    st.markdown(
        """
        <div class="app-title">
          <div class="app-kicker">Realtime Research Platform</div>
          <h1 style="margin:0;">TradeIQ Realtime Signal Dashboard</h1>
          <div class="app-sub">SEBI-aware analytics, live candles, model signals, and compliance-safe audit trails.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_compliance_banner(consent_ready: bool, accepted_at: str | None = None) -> None:
    """Render consent status banner (pending vs active)."""
    disclaimer = get_disclaimer()
    if consent_ready:
        accepted_text = accepted_at or "active"
        st.markdown(
            f"""
            <div class="consent-active">
              <strong>Compliance Active</strong><br/>
              {disclaimer.body}<br/>
              Accepted at: {accepted_text}
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f"""
            <div class="consent-pending">
              <strong>Compliance Consent Required</strong><br/>
              {disclaimer.body}<br/>
              {disclaimer.risk_disclosure}
            </div>
            """,
            unsafe_allow_html=True,
        )


def main() -> None:
    """Application entrypoint for Streamlit dashboard."""
    st.set_page_config(page_title="TradeIQ", layout="wide", initial_sidebar_state="expanded")
    _apply_theme()
    _render_header()

    engine = _get_engine()
    if not _init_portal_tables(engine):
        st.stop()

    user = _auth_gate(engine)
    if user is None:
        st.stop()

    user_key = f"user:{user['id']}:{user['username']}"

    with st.sidebar:
        st.markdown("### Session")
        st.caption(f"User: `{user.get('full_name') or user['username']}`")
        st.caption(f"Email: `{user['email']}`")
        st.caption(f"App version: `{APP_VERSION}`")
        if st.button("Logout", use_container_width=True):
            _audit_log(engine, user_key=user_key, event_type="user_logout")
            st.session_state["auth_user"] = None
            st.rerun()

    consent = _load_consent(engine, user_key)
    consent_ready = consent is not None
    consent_ts = None
    if consent:
        ts = pd.to_datetime(consent.get("accepted_at"), errors="coerce")
        if pd.notna(ts):
            consent_ts = ts.strftime("%Y-%m-%d %H:%M:%S")

    _render_compliance_banner(consent_ready=consent_ready, accepted_at=consent_ts)

    if not consent_ready:
        if st.button("I Accept Compliance Disclaimer", type="primary"):
            _save_consent(engine, user_key)
            _audit_log(engine, user_key=user_key, event_type="consent_accepted", payload={"version": DISCLAIMER_VERSION})
            st.rerun()
        st.info("Accept compliance disclaimer to unlock dashboard analytics.")
        st.stop()

    disclaimer = _get("/compliance/disclaimer")
    if disclaimer:
        st.info(disclaimer["risk_disclosure"])

    symbols = _load_symbols()
    default_symbol_idx = symbols.index("RELIANCE") if "RELIANCE" in symbols else 0

    col1, col2, col3, col4, col5 = st.columns([2, 1, 1, 1, 1])
    with col1:
        symbol = st.selectbox("Stock", symbols, index=default_symbol_idx)
    with col2:
        timeframe = st.selectbox("Timeframe", ["1m", "5m", "15m", "1h", "1d"], index=2)
    with col3:
        candle_limit = st.number_input("Candles", min_value=100, max_value=1000, value=300, step=50)
    with col4:
        refresh_secs = st.number_input("Refresh (sec, 0=off)", min_value=0, max_value=60, value=5)
    with col5:
        backfill_days = st.number_input("Backfill days", min_value=1, max_value=2000, value=30, step=5)
        backfill_clicked = st.button("Backfill", use_container_width=True)

    if backfill_clicked:
        backfill_result = _post(
            "/historical/backfill",
            params={"symbol": symbol, "timeframe": timeframe, "days": int(backfill_days)},
        )
        if backfill_result and not backfill_result.get("error"):
            _audit_log(
                engine,
                user_key=user_key,
                event_type="backfill_requested",
                symbol=symbol,
                payload={"timeframe": timeframe, "days": int(backfill_days), "result": backfill_result},
            )
            st.success(
                f"Backfill complete: inserted {backfill_result.get('inserted', 0)} candles for {symbol} {timeframe}"
            )
        else:
            st.error(f"Backfill failed: {backfill_result}")

    candle_payload = _get("/candles", params={"symbol": symbol, "timeframe": timeframe, "limit": int(candle_limit)})
    history_payload = _get("/signals/history", params={"symbol": symbol, "timeframe": timeframe, "limit": 200})
    backtest_payload = _get("/backtest/latest", params={"symbol": symbol, "timeframe": timeframe}) if timeframe in {"15m", "1d"} else None

    left, right = st.columns([2.2, 1.2])

    with left:
        st.subheader(f"{symbol} Candlestick ({timeframe})")
        if candle_payload and candle_payload.get("rows"):
            candles_df = pd.DataFrame(candle_payload["rows"])
            candles_df["candle_start"] = pd.to_datetime(candles_df["candle_start"])
            candles_df["candle_end"] = pd.to_datetime(candles_df["candle_end"])
            fig = _build_chart(candles_df)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.error("No candle data available. Use Backfill or wait for live market ticks.")

    with right:
        st.subheader("Current Prediction")
        latest_row = None
        if history_payload and history_payload.get("rows"):
            latest_row = history_payload["rows"][0]

        if latest_row:
            st.metric("Signal", latest_row.get("signal", "N/A"))
            st.metric("Confidence", f"{100 * float(latest_row.get('confidence', 0.0)):.2f}%")
            st.metric("Prob Up", f"{100 * float(latest_row.get('prob_up', 0.0)):.2f}%")
            st.metric("Model Version", latest_row.get("model_version", "N/A"))
            st.caption(f"Last Update: {latest_row.get('prediction_ts')}")

            risk_snapshot = latest_row.get("risk_snapshot")
            if isinstance(risk_snapshot, dict):
                st.markdown("**Risk/Governance**")
                _render_json_block(risk_snapshot)
        else:
            if timeframe in {"15m", "1d"}:
                st.info("Prediction not available yet.")
            else:
                st.info("Predictions currently active for 15m and 1d by default.")

    st.subheader("Historical Signals")
    if history_payload and history_payload.get("rows"):
        hist_df = pd.DataFrame(history_payload["rows"])
        display_cols = [
            "prediction_ts",
            "target_ts",
            "signal",
            "confidence",
            "prob_up",
            "prob_down",
            "model_name",
            "model_version",
            "is_simulated",
        ]
        available_cols = [col for col in display_cols if col in hist_df.columns]
        _render_signals_table(hist_df[available_cols])
    else:
        st.info("No historical signals yet")

    st.subheader("Backtest Metrics (Simulated Performance)")
    if backtest_payload:
        st.caption("Simulated performance only. Not live audited returns.")
        metrics = backtest_payload.get("metrics", {})
        if isinstance(metrics, dict):
            cols = st.columns(4)
            for idx, (k, v) in enumerate(metrics.items()):
                cols[idx % 4].metric(k, f"{float(v):.4f}" if isinstance(v, (int, float)) else str(v))
        _render_json_block(backtest_payload)
    else:
        st.info("No backtest run found for this symbol/timeframe")

    st.caption(f"API: {API_BASE_URL} | User: {user['username']} | Dashboard time: {datetime.now().isoformat(timespec='seconds')}")

    if refresh_secs > 0:
        time.sleep(int(refresh_secs))
        st.rerun()


if __name__ == "__main__":
    main()
