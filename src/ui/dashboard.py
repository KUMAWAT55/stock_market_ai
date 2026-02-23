import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import numpy as np
import json
import os
import sys
import hmac
import hashlib
import secrets
from html import escape
from textwrap import dedent
from pathlib import Path
from datetime import datetime, timedelta
from sqlalchemy import text

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from src.storage.db.connection import engine
from src.storage.db.models import (
    Base,
    AppUser,
    UserSubscription,
    ComplianceConsent,
    ComplianceAuditLog,
)


COMPLIANCE_DISCLAIMER_VERSION = "sebi_phase1_v1_2026-02-22"
APP_VERSION = "tradeiq_phase2_auth_2026-02-22"
PASSWORD_ITERATIONS = 260000
SUBSCRIPTION_PLAN_NAME = "TradeIQ Pro"
SUBSCRIPTION_DURATION_DAYS = 30
SUBSCRIPTION_REDEEM_CODE = os.getenv("TRADEIQ_SUBSCRIPTION_CODE", "TRADEIQ-PRO-2026")


st.set_page_config(
    page_title="TradeIQ",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Manrope:wght@500;600;700;800&family=Source+Sans+3:wght@400;500;600;700&display=swap');

    :root {
        --bg: #050505;
        --bg-soft: #0d0d0d;
        --surface: #171717;
        --surface-soft: #212121;
        --border: #2f2f2f;
        --border-strong: #474747;
        --text-main: #f0f0f0;
        --text-dim: #b4b4b4;
        --brand: #8d8d8d;
        --brand-dark: #6f6f6f;
        --brand-soft: #2b2b2b;
        --pos: #34d399;
        --neg: #f87171;
        --neu: #fbbf24;
        --shadow-sm: 0 6px 16px rgba(0, 0, 0, 0.35);
        --shadow-md: 0 12px 26px rgba(0, 0, 0, 0.45);
    }

    .stApp {
        font-family: "Source Sans 3", "Segoe UI", sans-serif;
        color: var(--text-main);
        background:
            radial-gradient(900px 520px at -8% -18%, rgba(120, 120, 120, 0.14), transparent 72%),
            radial-gradient(760px 420px at 108% -8%, rgba(90, 90, 90, 0.10), transparent 68%),
            linear-gradient(180deg, var(--bg) 0%, var(--bg-soft) 100%);
    }

    .main .block-container {
        max-width: 1320px;
        padding-top: 0.9rem;
        padding-bottom: 1rem;
        padding-left: 1rem;
        padding-right: 1rem;
    }

    header[data-testid="stHeader"] {
        background: transparent;
    }

    div[data-testid="stToolbar"] {
        background: transparent;
    }

    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #121212 0%, #0b0b0b 100%);
        border-right: 1px solid var(--border);
    }

    section[data-testid="stSidebar"] label,
    section[data-testid="stSidebar"] p,
    section[data-testid="stSidebar"] .stMarkdown,
    section[data-testid="stSidebar"] [data-testid="stSelectbox"] {
        font-family: "Manrope", "Segoe UI", sans-serif !important;
    }

    .sidebar-title {
        margin-bottom: 0.55rem;
        padding: 0.55rem 0.65rem;
        border-radius: 10px;
        background: var(--surface);
        border: 1px solid var(--border);
        box-shadow: var(--shadow-sm);
    }

    .sidebar-kicker {
        color: #adadad;
        font-size: 0.65rem;
        text-transform: uppercase;
        letter-spacing: 0.09em;
        font-weight: 800;
        margin-bottom: 0.15rem;
    }

    .sidebar-heading {
        color: #f0f0f0;
        font-size: 0.94rem;
        font-weight: 800;
    }

    section[data-testid="stSidebar"] [data-baseweb="select"] > div {
        background: var(--surface) !important;
        border: 1px solid var(--border) !important;
        border-radius: 10px !important;
        box-shadow: none !important;
    }

    div[data-testid="stSelectbox"] [data-baseweb="select"] > div {
        background: var(--surface) !important;
        border: 1px solid var(--border) !important;
        border-radius: 10px !important;
        box-shadow: none !important;
    }

    section[data-testid="stSidebar"] [data-baseweb="select"] > div:hover,
    div[data-testid="stSelectbox"] [data-baseweb="select"] > div:hover {
        border-color: var(--border-strong) !important;
    }

    section[data-testid="stSidebar"] [data-baseweb="select"] > div:focus-within,
    div[data-testid="stSelectbox"] [data-baseweb="select"] > div:focus-within {
        border-color: var(--brand) !important;
        box-shadow: 0 0 0 3px rgba(141, 141, 141, 0.26) !important;
    }

    section[data-testid="stSidebar"] [data-baseweb="select"] span {
        color: #ededed !important;
        font-weight: 700;
    }

    div[data-testid="stSelectbox"] [data-baseweb="select"] span {
        color: #ededed !important;
        font-weight: 700;
    }

    section[data-testid="stSidebar"] [data-baseweb="select"] input {
        color: #ededed !important;
        background: transparent !important;
    }
    section[data-testid="stSidebar"] [data-baseweb="select"] svg {
        fill: #a7a7a7 !important;
    }
    div[data-baseweb="popover"],
    div[data-baseweb="popover"] > div,
    div[role="listbox"],
    ul[role="listbox"],
    [data-baseweb="menu"],
    [data-baseweb="select"] [role="listbox"] {
        background: #151515 !important;
        border: 1px solid var(--border) !important;
        border-radius: 10px !important;
        box-shadow: 0 12px 24px rgba(0, 0, 0, 0.45) !important;
    }

    div[data-baseweb="popover"] ul,
    div[data-baseweb="popover"] li {
        background: transparent !important;
    }
    div[data-baseweb="popover"] [role="option"],
    div[role="listbox"] [role="option"],
    ul[role="listbox"] li,
    [data-baseweb="menu"] li {
        color: #f0f0f0 !important;
        background: transparent !important;
        font-weight: 600 !important;
        opacity: 1 !important;
    }
    div[data-baseweb="popover"] [role="option"][aria-selected="true"],
    div[role="listbox"] [role="option"][aria-selected="true"] {
        background: rgba(141, 141, 141, 0.24) !important;
    }

    div[data-baseweb="popover"] [role="option"]:hover,
    div[role="listbox"] [role="option"]:hover {
        background: rgba(141, 141, 141, 0.16) !important;
    }

    div[data-baseweb="popover"] [role="menuitem"],
    div[data-baseweb="popover"] [role="menuitem"] *,
    [data-baseweb="menu"] [role="menuitem"],
    [data-baseweb="menu"] [role="menuitem"] *,
    [data-baseweb="menu"] button,
    [data-baseweb="menu"] a,
    [data-baseweb="menu"] span,
    [data-baseweb="menu"] div {
        color: #f1f1f1 !important;
        opacity: 1 !important;
    }

    div[data-baseweb="popover"] [role="menuitem"]:hover,
    [data-baseweb="menu"] [role="menuitem"]:hover,
    [data-baseweb="menu"] li:hover {
        background: rgba(141, 141, 141, 0.16) !important;
    }

    header[data-testid="stHeader"] [data-baseweb="popover"],
    header[data-testid="stHeader"] [data-baseweb="popover"] > div,
    header[data-testid="stHeader"] [data-baseweb="menu"],
    div[data-testid="stToolbar"] [data-baseweb="popover"],
    div[data-testid="stToolbar"] [data-baseweb="popover"] > div,
    div[data-testid="stToolbar"] [data-baseweb="menu"] {
        background: #151515 !important;
        border: 1px solid var(--border) !important;
        color: #f1f1f1 !important;
    }

    /* Streamlit deploy modal (different from st.dialog) */
    div[data-baseweb="modal"],
    div[data-baseweb="modal"] > div,
    div[aria-modal="true"][role="dialog"],
    div[aria-modal="true"][role="dialog"] > div {
        background: #141414 !important;
        color: #efefef !important;
        border-color: var(--border) !important;
    }

    div[data-baseweb="modal"] h1,
    div[data-baseweb="modal"] h2,
    div[data-baseweb="modal"] h3,
    div[data-baseweb="modal"] h4,
    div[data-baseweb="modal"] p,
    div[data-baseweb="modal"] span,
    div[data-baseweb="modal"] label,
    div[data-baseweb="modal"] li,
    div[data-baseweb="modal"] a,
    div[aria-modal="true"][role="dialog"] h1,
    div[aria-modal="true"][role="dialog"] h2,
    div[aria-modal="true"][role="dialog"] h3,
    div[aria-modal="true"][role="dialog"] h4,
    div[aria-modal="true"][role="dialog"] p,
    div[aria-modal="true"][role="dialog"] span,
    div[aria-modal="true"][role="dialog"] label,
    div[aria-modal="true"][role="dialog"] li,
    div[aria-modal="true"][role="dialog"] a {
        color: #e8e8e8 !important;
        opacity: 1 !important;
    }

    div[data-baseweb="modal"] [data-baseweb="card"],
    div[data-baseweb="modal"] [role="button"],
    div[aria-modal="true"][role="dialog"] [data-baseweb="card"],
    div[aria-modal="true"][role="dialog"] [role="button"] {
        background: #171717 !important;
        border-color: var(--border) !important;
        color: #efefef !important;
    }

    div[data-baseweb="modal"] button,
    div[aria-modal="true"][role="dialog"] button {
        color: #efefef !important;
        border-color: var(--border) !important;
    }

    div[data-baseweb="modal"] button,
    div[data-baseweb="modal"] [data-baseweb="button"],
    div[data-baseweb="modal"] [role="button"],
    div[data-baseweb="modal"] a[role="button"],
    div[aria-modal="true"][role="dialog"] button,
    div[aria-modal="true"][role="dialog"] [data-baseweb="button"],
    div[aria-modal="true"][role="dialog"] [role="button"],
    div[aria-modal="true"][role="dialog"] a[role="button"] {
        background: #1c1c1c !important;
        background-image: none !important;
        color: #efefef !important;
        border: 1px solid var(--border) !important;
        opacity: 1 !important;
    }

    div[data-baseweb="modal"] button[kind="primary"],
    div[data-baseweb="modal"] [data-baseweb="button"][kind="primary"],
    div[aria-modal="true"][role="dialog"] button[kind="primary"],
    div[aria-modal="true"][role="dialog"] [data-baseweb="button"][kind="primary"] {
        background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%) !important;
        border-color: #f87171 !important;
        color: #ffffff !important;
    }

    div[data-baseweb="modal"] button[kind="secondary"],
    div[data-baseweb="modal"] button[kind="tertiary"],
    div[data-baseweb="modal"] [data-baseweb="button"][kind="secondary"],
    div[data-baseweb="modal"] [data-baseweb="button"][kind="tertiary"],
    div[aria-modal="true"][role="dialog"] button[kind="secondary"],
    div[aria-modal="true"][role="dialog"] button[kind="tertiary"],
    div[aria-modal="true"][role="dialog"] [data-baseweb="button"][kind="secondary"],
    div[aria-modal="true"][role="dialog"] [data-baseweb="button"][kind="tertiary"] {
        background: #1c1c1c !important;
        color: #efefef !important;
        border: 1px solid var(--border) !important;
    }

    div[data-baseweb="modal"] button:disabled,
    div[data-baseweb="modal"] [data-baseweb="button"][disabled],
    div[data-baseweb="modal"] [role="button"][aria-disabled="true"],
    div[data-baseweb="modal"] a[role="button"][aria-disabled="true"],
    div[aria-modal="true"][role="dialog"] button:disabled,
    div[aria-modal="true"][role="dialog"] [data-baseweb="button"][disabled],
    div[aria-modal="true"][role="dialog"] [role="button"][aria-disabled="true"],
    div[aria-modal="true"][role="dialog"] a[role="button"][aria-disabled="true"] {
        background: #171717 !important;
        color: #8f8f8f !important;
        border-color: #2f2f2f !important;
        opacity: 1 !important;
        box-shadow: none !important;
    }

    div[data-baseweb="modal"] button:hover,
    div[aria-modal="true"][role="dialog"] button:hover {
        border-color: var(--border-strong) !important;
    }

    div[data-baseweb="modal"] svg,
    div[aria-modal="true"][role="dialog"] svg {
        fill: #d0d0d0 !important;
        stroke: #d0d0d0 !important;
    }

    div[data-testid="stDialog"] > div[role="dialog"],
    div[data-testid="stDialog"] [role="dialog"] {
        background: #141414 !important;
        border: 1px solid var(--border) !important;
        border-radius: 14px !important;
        box-shadow: 0 20px 48px rgba(0, 0, 0, 0.62) !important;
    }

    div[data-testid="stDialog"] [data-testid="stDialogHeader"] {
        background: #141414 !important;
        border-bottom: 1px solid var(--border) !important;
    }

    div[data-testid="stDialog"] [data-testid="stDialogHeader"] * {
        color: #f2f2f2 !important;
    }

    div[data-testid="stDialog"] [data-testid="stDialogContent"] {
        background: #141414 !important;
    }

    div[data-testid="stDialog"] button[aria-label*="Close"],
    div[data-testid="stDialog"] button[aria-label*="close"] {
        color: #d7d7d7 !important;
        background: #1a1a1a !important;
        border: 1px solid var(--border) !important;
        border-radius: 8px !important;
    }

    div[data-testid="stDialog"] button[aria-label*="Close"]:hover,
    div[data-testid="stDialog"] button[aria-label*="close"]:hover {
        background: #222222 !important;
        border-color: var(--border-strong) !important;
    }

    div[data-testid="stForm"] {
        background: #141414 !important;
        border: 1px solid var(--border) !important;
        border-radius: 12px !important;
        padding: 0.7rem 0.8rem 0.55rem !important;
    }

    div[data-baseweb="base-input"],
    div[data-baseweb="input"] > div,
    div[data-testid="stTextInput"] > div > div,
    div[data-testid="stNumberInput"] > div > div,
    div[data-testid="stDateInput"] > div > div,
    div[data-testid="stTimeInput"] > div > div,
    div[data-testid="stTextArea"] > div > div {
        background: #1a1a1a !important;
        border: 1px solid var(--border) !important;
        border-radius: 10px !important;
        box-shadow: none !important;
    }

    div[data-baseweb="base-input"]:hover,
    div[data-baseweb="input"] > div:hover,
    div[data-testid="stTextInput"] > div > div:hover,
    div[data-testid="stNumberInput"] > div > div:hover,
    div[data-testid="stDateInput"] > div > div:hover,
    div[data-testid="stTimeInput"] > div > div:hover,
    div[data-testid="stTextArea"] > div > div:hover {
        border-color: var(--border-strong) !important;
    }

    div[data-baseweb="base-input"]:focus-within,
    div[data-baseweb="input"] > div:focus-within,
    div[data-testid="stTextInput"] > div > div:focus-within,
    div[data-testid="stNumberInput"] > div > div:focus-within,
    div[data-testid="stDateInput"] > div > div:focus-within,
    div[data-testid="stTimeInput"] > div > div:focus-within,
    div[data-testid="stTextArea"] > div > div:focus-within {
        border-color: var(--brand) !important;
        box-shadow: 0 0 0 3px rgba(141, 141, 141, 0.20) !important;
    }

    div[data-testid="stTextInput"] input,
    div[data-testid="stNumberInput"] input,
    div[data-testid="stDateInput"] input,
    div[data-testid="stTimeInput"] input,
    div[data-testid="stTextArea"] textarea,
    input, textarea {
        background: transparent !important;
        color: #ececec !important;
        caret-color: #ececec !important;
    }

    div[data-testid="stTextInput"] input::placeholder,
    div[data-testid="stNumberInput"] input::placeholder,
    div[data-testid="stDateInput"] input::placeholder,
    div[data-testid="stTimeInput"] input::placeholder,
    div[data-testid="stTextArea"] textarea::placeholder,
    input::placeholder,
    textarea::placeholder {
        color: #909090 !important;
        opacity: 1 !important;
    }

    div[data-testid="stTextInput"] label,
    div[data-testid="stNumberInput"] label,
    div[data-testid="stDateInput"] label,
    div[data-testid="stTimeInput"] label,
    div[data-testid="stTextArea"] label,
    div[data-testid="stCheckbox"] label {
        color: #d6d6d6 !important;
    }

    div[data-testid="stTextInput"] button,
    div[data-testid="stNumberInput"] button,
    div[data-testid="stDateInput"] button,
    div[data-testid="stTimeInput"] button {
        background: transparent !important;
        border: 0 !important;
        color: #bdbdbd !important;
    }

    div[data-testid="stTextInput"] svg,
    div[data-testid="stNumberInput"] svg,
    div[data-testid="stDateInput"] svg,
    div[data-testid="stTimeInput"] svg {
        fill: #bdbdbd !important;
    }

    div[data-testid="stButton"] > button,
    div[data-testid="stFormSubmitButton"] > button {
        width: 100%;
        background: linear-gradient(135deg, #242424 0%, #1a1a1a 100%) !important;
        color: #f2f2f2 !important;
        border: 1px solid var(--border) !important;
        border-radius: 10px !important;
        font-weight: 700 !important;
        box-shadow: var(--shadow-sm) !important;
    }

    div[data-testid="stButton"] > button:hover,
    div[data-testid="stFormSubmitButton"] > button:hover {
        border-color: var(--border-strong) !important;
        background: linear-gradient(135deg, #2c2c2c 0%, #202020 100%) !important;
        color: #ffffff !important;
    }

    div[data-testid="stButton"] > button:disabled,
    div[data-testid="stFormSubmitButton"] > button:disabled {
        background: #1a1a1a !important;
        color: #8b8b8b !important;
        border-color: #2a2a2a !important;
        opacity: 1 !important;
        cursor: not-allowed !important;
    }

    div[data-testid="stCheckbox"] input {
        accent-color: #6f6f6f !important;
    }

    div[data-testid="stSidebar"] div[data-testid="stTextInput"] > div > div,
    div[data-testid="stSidebar"] div[data-testid="stNumberInput"] > div > div,
    div[data-testid="stSidebar"] div[data-testid="stDateInput"] > div > div,
    div[data-testid="stSidebar"] div[data-testid="stTimeInput"] > div > div {
        background: #171717 !important;
    }

    div[data-testid="stSidebar"] div[data-testid="stButton"] > button,
    div[data-testid="stSidebar"] div[data-testid="stFormSubmitButton"] > button {
        background: linear-gradient(135deg, #2a2a2a 0%, #1d1d1d 100%) !important;
    }

    h1, h2, h3 {
        font-family: "Manrope", "Segoe UI", sans-serif;
        letter-spacing: 0.01em;
        color: var(--text-main);
        opacity: 1 !important;
    }
    p, label, span, div {
        color: var(--text-main);
        opacity: 1;
    }

    .app-title {
        position: relative;
        background: linear-gradient(135deg, #1d1d1d 0%, #262626 52%, #1a1a1a 100%);
        border: 1px solid #3a3a3a;
        border-radius: 14px;
        padding: 0.9rem 1rem;
        margin-bottom: 0.75rem;
        box-shadow: var(--shadow-md);
        overflow: hidden;
    }

    .app-title > * {
        position: relative;
        z-index: 1;
    }

    .app-title::before {
        content: "";
        position: absolute;
        inset: 0 auto 0 0;
        width: 6px;
        background: linear-gradient(180deg, #8d8d8d, #5f5f5f);
        z-index: 0;
    }

    .app-title::after {
        content: "";
        position: absolute;
        inset: 0;
        background: radial-gradient(440px 220px at 92% -18%, rgba(160, 160, 160, 0.16), transparent 70%);
        pointer-events: none;
        z-index: 0;
    }

    .app-kicker {
        color: #bfbfbf;
        font-size: 0.66rem;
        letter-spacing: 0.11em;
        text-transform: uppercase;
        font-weight: 800;
        margin-bottom: 0.18rem;
    }

    .app-heading {
        font-size: 1.54rem;
        line-height: 1.08;
        font-weight: 800;
        margin: 0;
        color: #fafafa;
    }

    .app-sub {
        color: #c9c9c9;
        margin-top: 0.28rem;
        font-size: 0.79rem;
        font-weight: 600;
    }

    .compliance-banner {
        border: 1px solid var(--border);
        border-radius: 12px;
        padding: 0.7rem 0.85rem;
        margin-bottom: 0.65rem;
        box-shadow: var(--shadow-sm);
    }

    .compliance-banner.pending {
        background: linear-gradient(135deg, rgba(180, 83, 9, 0.16), rgba(23, 23, 23, 0.92));
        border-color: rgba(251, 191, 36, 0.42);
    }

    .compliance-banner.active {
        background: linear-gradient(135deg, rgba(22, 163, 74, 0.16), rgba(23, 23, 23, 0.92));
        border-color: rgba(52, 211, 153, 0.42);
    }

    .compliance-title {
        font-size: 0.86rem;
        font-weight: 800;
        margin-bottom: 0.2rem;
        color: #f3f3f3;
    }

    .compliance-text {
        font-size: 0.76rem;
        color: #d0d0d0;
        line-height: 1.35;
        margin-bottom: 0.16rem;
        font-weight: 600;
    }

    .compliance-links {
        font-size: 0.74rem;
        color: #c9c9c9;
        margin-top: 0.1rem;
    }

    .compliance-links a {
        color: #d4d4d4;
        font-weight: 700;
        text-decoration: underline;
    }

    .technical-summary-card {
        background: linear-gradient(160deg, #171717 0%, #141414 100%);
        border: 1px solid var(--border);
        border-radius: 14px;
        padding: 0.78rem 0.84rem 0.74rem;
        box-shadow: var(--shadow-sm);
        margin-bottom: 0.42rem;
    }

    .technical-summary-title {
        color: #b9b9b9;
        font-size: 0.84rem;
        font-weight: 700;
        margin-bottom: 0.06rem;
    }

    .technical-summary-signal {
        font-size: 1.18rem;
        font-weight: 800;
        margin-bottom: 0.52rem;
        line-height: 1.1;
    }

    .technical-summary-grid {
        display: grid;
        grid-template-columns: minmax(0, 1fr) 0.62fr;
        gap: 0.72rem;
        align-items: center;
    }

    .technical-track-wrap {
        position: relative;
        padding-bottom: 0.44rem;
    }

    .technical-track {
        display: grid;
        grid-template-columns: repeat(28, minmax(0, 1fr));
        gap: 0.22rem;
        align-items: end;
        width: 100%;
    }

    .technical-seg {
        height: 1.72rem;
        border-radius: 999px;
        border: 1px solid rgba(255, 255, 255, 0.07);
        box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.03);
    }

    .technical-pointer {
        position: absolute;
        bottom: 0;
        transform: translateX(-50%);
        width: 0;
        height: 0;
        border-left: 0.36rem solid transparent;
        border-right: 0.36rem solid transparent;
        border-top: 0.58rem solid #cfcfcf;
        filter: drop-shadow(0 1px 2px rgba(0, 0, 0, 0.35));
    }

    .technical-legend {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 0.48rem;
    }

    .technical-legend-item {
        display: flex;
        flex-direction: column;
        align-items: flex-start;
        gap: 0.05rem;
    }

    .technical-legend-head {
        display: inline-flex;
        align-items: center;
        gap: 0.26rem;
        color: #d3d3d3;
        font-size: 0.82rem;
        font-weight: 700;
        line-height: 1;
    }

    .technical-dot {
        width: 0.54rem;
        height: 0.54rem;
        border-radius: 999px;
    }

    .technical-legend-val {
        color: #f0f0f0;
        font-size: 0.98rem;
        font-weight: 800;
        padding-left: 0.8rem;
        line-height: 1.1;
    }

    .decision-card,
    .snapshot-card {
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: 12px;
        padding: 0.65rem 0.75rem;
        margin-bottom: 0.45rem;
        box-shadow: var(--shadow-sm);
        transition: border-color 160ms ease, box-shadow 160ms ease;
    }

    .decision-card:hover,
    .snapshot-card:hover,
    .news-card:hover,
    .indicator-box:hover,
    div[data-testid="stPlotlyChart"]:hover {
        border-color: var(--border-strong);
        box-shadow: var(--shadow-md);
    }

    .snapshot-label {
        color: #b0b0b0;
        font-size: 0.67rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        margin-bottom: 0.14rem;
        font-weight: 800;
    }

    .snapshot-value {
        color: var(--text-main);
        font-size: 1.03rem;
        font-weight: 800;
        line-height: 1.2;
    }

    .news-card {
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: 12px;
        padding: 0.65rem 0.75rem;
        margin-bottom: 0.45rem;
        box-shadow: var(--shadow-sm);
    }

    .news-title {
        color: var(--text-main);
        font-weight: 700;
        margin-bottom: 0.24rem;
        font-size: 0.87rem;
        line-height: 1.3;
    }

    .news-meta {
        color: var(--text-dim);
        font-size: 0.76rem;
        margin-bottom: 0.16rem;
        font-weight: 600;
    }

    .news-link {
        color: var(--brand);
        text-decoration: none;
        font-size: 0.77rem;
        font-weight: 700;
        border-bottom: 1px solid rgba(181, 181, 181, 0.42);
    }

    .news-link:hover {
        color: #e4e4e4;
        border-bottom-color: rgba(228, 228, 228, 0.65);
    }

    .metric-grid {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 0.45rem;
        margin-bottom: 0.25rem;
    }

    .metric-grid .snapshot-card {
        margin-bottom: 0;
    }

    .indicator-grid {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 0.42rem;
        margin-bottom: 0.1rem;
    }

    .indicator-box {
        border-radius: 10px;
        padding: 0.52rem 0.56rem;
        border: 1px solid var(--border);
        box-shadow: var(--shadow-sm);
    }

    div[data-testid="stPlotlyChart"] {
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: 12px;
        padding: 0.42rem;
        box-shadow: var(--shadow-sm);
        transition: border-color 160ms ease, box-shadow 160ms ease;
    }

    div[data-testid="stPlotlyChart"] .js-plotly-plot,
    div[data-testid="stPlotlyChart"] .plot-container,
    div[data-testid="stPlotlyChart"] .svg-container {
        background: transparent !important;
    }

    .indicator-name {
        font-size: 0.7rem;
        font-weight: 700;
        margin-bottom: 0.12rem;
        color: #d3d3d3;
    }

    .indicator-signal {
        font-size: 0.82rem;
        font-weight: 800;
        color: #f1f1f1;
    }

    h3 {
        font-size: 1.03rem !important;
        margin-top: 0.2rem !important;
        margin-bottom: 0.38rem !important;
        color: #f5f5f5 !important;
    }

    div[data-testid="stHeading"] {
        margin-top: 0.05rem !important;
        margin-bottom: 0.15rem !important;
    }

    .indicator-bull {
        background: rgba(52, 211, 153, 0.16);
        border-color: rgba(52, 211, 153, 0.42);
        color: var(--pos);
    }

    .indicator-bear {
        background: rgba(248, 113, 113, 0.16);
        border-color: rgba(248, 113, 113, 0.42);
        color: var(--neg);
    }

    .indicator-neutral {
        background: rgba(251, 191, 36, 0.14);
        border-color: rgba(251, 191, 36, 0.38);
        color: var(--neu);
    }

    .stDataFrame,
    .stTable {
        border: 1px solid var(--border);
        border-radius: 12px;
        overflow: hidden;
        box-shadow: var(--shadow-sm);
        background: var(--surface);
    }

    div[data-testid="stDataFrame"],
    div[data-testid="stDataFrame"] > div,
    div[data-testid="stDataFrame"] [data-testid="stDataFrameResizable"],
    div[data-testid="stTable"],
    div[data-testid="stTable"] > div {
        background: var(--surface) !important;
        border-color: var(--border) !important;
    }

    div[data-testid="stDataFrame"] [role="columnheader"] {
        background: #202020 !important;
        color: #f0f0f0 !important;
        border-bottom: 1px solid var(--border) !important;
        font-weight: 700 !important;
    }

    div[data-testid="stDataFrame"] [role="gridcell"] {
        background: #171717 !important;
        color: #ededed !important;
        border-bottom: 1px solid rgba(71, 71, 71, 0.45) !important;
    }

    div[data-testid="stDataFrame"] [role="row"]:hover [role="gridcell"] {
        background: #1f1f1f !important;
    }

    .themed-table {
        width: 100%;
        overflow-x: auto;
        border: 1px solid var(--border);
        border-radius: 12px;
        background: var(--surface);
        box-shadow: var(--shadow-sm);
    }

    .themed-table table {
        width: 100%;
        border-collapse: collapse;
        background: #171717 !important;
        color: #ededed !important;
        font-size: 0.84rem;
    }

    .themed-table thead th {
        background: #202020 !important;
        color: #f0f0f0 !important;
        border-bottom: 1px solid var(--border);
        padding: 0.48rem 0.52rem;
        text-align: left;
        font-weight: 700;
    }

    .themed-table tbody td {
        background: #171717 !important;
        color: #ededed !important;
        border-bottom: 1px solid rgba(71, 71, 71, 0.45);
        padding: 0.44rem 0.52rem;
    }

    .themed-table tbody tr:hover td {
        background: #1f1f1f !important;
    }

    div[data-testid="stExpander"],
    div[data-testid="stExpander"] > details,
    details[data-testid="stExpander"] {
        border: 1px solid var(--border);
        border-radius: 12px;
        background: var(--surface);
        box-shadow: var(--shadow-sm);
        overflow: hidden;
    }

    div[data-testid="stAlert"] {
        background: #1a1a1a !important;
        border: 1px solid var(--border) !important;
        color: #efefef !important;
    }

    div[data-testid="stExpander"] > details > summary,
    div[data-testid="stExpander"] summary,
    details[data-testid="stExpander"] summary {
        font-family: "Manrope", "Segoe UI", sans-serif;
        font-weight: 700;
        color: #efefef !important;
        background: #171717 !important;
        border: 0 !important;
        border-radius: 12px;
    }

    div[data-testid="stExpander"] > details > summary:hover,
    div[data-testid="stExpander"] summary:hover,
    details[data-testid="stExpander"] summary:hover {
        background: #1f1f1f !important;
    }

    div[data-testid="stExpander"] > details[open] > summary,
    div[data-testid="stExpander"] details[open] summary,
    details[data-testid="stExpander"][open] summary {
        border-bottom: 1px solid var(--border) !important;
        border-bottom-left-radius: 0;
        border-bottom-right-radius: 0;
    }

    div[data-testid="stExpander"] summary *,
    details[data-testid="stExpander"] summary * {
        color: #efefef !important;
    }

    div[data-testid="stExpander"] summary svg,
    details[data-testid="stExpander"] summary svg {
        fill: #bcbcbc !important;
    }

    div[data-testid="stExpander"] > details > div,
    div[data-testid="stExpander"] details > div,
    details[data-testid="stExpander"] > div {
        background: #171717 !important;
    }

    div[data-testid="stExpander"] summary::marker {
        color: #bcbcbc !important;
    }

    .stDataFrame div,
    .stDataFrame span,
    .stTable div,
    .stTable span {
        color: #efefef;
        opacity: 1 !important;
    }

    @media (prefers-reduced-motion: reduce) {
        .decision-card,
        .snapshot-card,
        .news-card,
        .indicator-box,
        div[data-testid="stPlotlyChart"],
        section[data-testid="stSidebar"] [data-baseweb="select"] > div,
        div[data-testid="stSelectbox"] [data-baseweb="select"] > div {
            transition: none !important;
            animation: none !important;
        }
    }

    @media (max-width: 1200px) {
        .main .block-container {
            max-width: 100%;
            padding-left: 0.75rem;
            padding-right: 0.75rem;
        }
        .indicator-grid {
            grid-template-columns: repeat(3, minmax(0, 1fr));
        }
        .metric-grid {
            grid-template-columns: repeat(3, minmax(0, 1fr));
        }
    }

    @media (max-width: 940px) {
        .app-heading {
            font-size: 1.38rem;
        }
        .app-sub {
            font-size: 0.75rem;
        }
        .indicator-grid {
            grid-template-columns: repeat(2, minmax(0, 1fr));
        }
        .metric-grid {
            grid-template-columns: repeat(2, minmax(0, 1fr));
        }
        .technical-summary-grid {
            grid-template-columns: repeat(1, minmax(0, 1fr));
            gap: 0.54rem;
        }
        .technical-legend {
            grid-template-columns: repeat(3, minmax(0, 1fr));
        }
        div[data-testid="stHorizontalBlock"] {
            display: flex;
            flex-direction: column;
            gap: 0.7rem;
        }
        div[data-testid="column"] {
            width: 100% !important;
            flex: 1 1 100% !important;
            min-width: 100% !important;
        }
        section[data-testid="stSidebar"] {
            min-width: 250px !important;
            max-width: 300px !important;
        }
    }

    @media (max-width: 640px) {
        .main .block-container {
            padding-left: 0.5rem;
            padding-right: 0.5rem;
            padding-top: 0.55rem;
            padding-bottom: 0.7rem;
        }
        .app-heading {
            font-size: 1.21rem;
        }
        .app-kicker {
            font-size: 0.6rem;
        }
        .snapshot-value {
            font-size: 0.9rem;
        }
        .indicator-grid {
            grid-template-columns: repeat(1, minmax(0, 1fr));
            gap: 0.38rem;
        }
        .metric-grid {
            grid-template-columns: repeat(1, minmax(0, 1fr));
            gap: 0.38rem;
        }
        .technical-track {
            gap: 0.16rem;
        }
        .technical-seg {
            height: 1.52rem;
        }
        .technical-legend-head {
            font-size: 0.76rem;
        }
        .technical-legend-val {
            font-size: 0.89rem;
        }
        .decision-card,
        .snapshot-card,
        .news-card,
        .indicator-box {
            padding: 0.56rem 0.58rem;
            border-radius: 9px;
        }
        div[data-testid="stPlotlyChart"] {
            padding: 0.32rem;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ----------------------------------
# Indicator Consensus
# ----------------------------------

def _safe_series(df, col):
    return pd.to_numeric(df[col], errors="coerce")


def compute_indicator_consensus(price_df, sentiment_score):
    df = price_df.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.sort_values("date").dropna(subset=["date"]).copy()

    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = _safe_series(df, col)

    if len(df) < 60:
        return {
            "summary": "INSUFFICIENT DATA",
            "score": 0,
            "confidence": 0.0,
            "rows": pd.DataFrame(columns=["Indicator", "Signal", "Score"]),
        }

    close = df["close"]
    high = df["high"]
    low = df["low"]
    volume = df["volume"].fillna(0)
    prev_close = close.shift(1)

    sma5 = close.rolling(5).mean()
    sma20 = close.rolling(20).mean()
    ema9 = close.ewm(span=9, adjust=False).mean()
    ema21 = close.ewm(span=21, adjust=False).mean()
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()

    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, pd.NA)
    rsi14 = 100 - (100 / (1 + rs))

    macd = ema12 - ema26
    macd_signal = macd.ewm(span=9, adjust=False).mean()
    macd_hist = macd - macd_signal

    bb_mid = close.rolling(20).mean()
    bb_std = close.rolling(20).std()
    bb_upper = bb_mid + (2 * bb_std)
    bb_lower = bb_mid - (2 * bb_std)
    bb_pos = (close - bb_lower) / (bb_upper - bb_lower)

    lowest14 = low.rolling(14).min()
    highest14 = high.rolling(14).max()
    stoch_k = ((close - lowest14) / (highest14 - lowest14)) * 100
    williams_r = ((highest14 - close) / (highest14 - lowest14)) * -100

    roc10 = close.pct_change(10) * 100
    momentum10 = close - close.shift(10)

    tr = pd.concat(
        [(high - low), (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)

    obv = ((close.diff().fillna(0).apply(lambda x: 1 if x > 0 else (-1 if x < 0 else 0))) * volume).cumsum()
    obv_slope = obv.diff(5)

    volume_ratio = volume / volume.rolling(20).mean().replace(0, pd.NA)
    price_change = close.diff()
    vol_10 = close.pct_change().rolling(10).std()
    vol_30 = close.pct_change().rolling(30).std()
    vol_regime = vol_10 / vol_30.replace(0, pd.NA)

    tp = (high + low + close) / 3
    tp_ma = tp.rolling(20).mean()
    tp_dev = (tp - tp_ma).abs().rolling(20).mean()
    cci20 = (tp - tp_ma) / (0.015 * tp_dev.replace(0, pd.NA))

    plus_dm = (high.diff()).where((high.diff() > (low.shift(1) - low)) & (high.diff() > 0), 0.0)
    minus_dm = (low.shift(1) - low).where(((low.shift(1) - low) > high.diff()) & ((low.shift(1) - low) > 0), 0.0)
    plus_dm = pd.to_numeric(plus_dm, errors="coerce")
    minus_dm = pd.to_numeric(minus_dm, errors="coerce")
    tr14 = pd.to_numeric(tr.rolling(14).sum(), errors="coerce")

    plus_di = 100.0 * (plus_dm.rolling(14).sum() / tr14.replace(0, np.nan))
    minus_di = 100.0 * (minus_dm.rolling(14).sum() / tr14.replace(0, np.nan))
    plus_di = pd.to_numeric(plus_di, errors="coerce")
    minus_di = pd.to_numeric(minus_di, errors="coerce")

    dx = ((plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)) * 100.0
    dx = pd.to_numeric(dx, errors="coerce")
    adx14 = dx.rolling(14).mean()

    cum_vol = volume.cumsum().replace(0, np.nan)
    cum_tpv = (tp * volume).cumsum()
    vwap = cum_tpv / cum_vol
    vwap_slope = vwap.diff(5)

    tp_diff = tp.diff()
    raw_mf = tp * volume
    pos_mf = raw_mf.where(tp_diff > 0, 0.0)
    neg_mf = raw_mf.where(tp_diff < 0, 0.0).abs()
    mfi_ratio = pos_mf.rolling(14).sum() / neg_mf.rolling(14).sum().replace(0, np.nan)
    mfi14 = 100 - (100 / (1 + mfi_ratio))

    donchian_upper = high.rolling(20).max().shift(1)
    donchian_lower = low.rolling(20).min().shift(1)

    session_key = df["date"].dt.floor("D")
    session_open = df.groupby(session_key)["open"].transform("first")

    idx = df.index[-1]
    indicator_rows = []

    def _safe_bool(value):
        if pd.isna(value):
            return False
        try:
            return bool(value)
        except Exception:
            return False

    def add_indicator(name, bullish, bearish):
        bull = _safe_bool(bullish)
        bear = _safe_bool(bearish)
        if bull and not bear:
            indicator_rows.append({"Indicator": name, "Signal": "Bullish", "Score": 1})
        elif bear and not bull:
            indicator_rows.append({"Indicator": name, "Signal": "Bearish", "Score": -1})
        else:
            indicator_rows.append({"Indicator": name, "Signal": "Neutral", "Score": 0})

    add_indicator("SMA 5/20", sma5.loc[idx] > sma20.loc[idx], sma5.loc[idx] < sma20.loc[idx])
    add_indicator("EMA 9/21", ema9.loc[idx] > ema21.loc[idx], ema9.loc[idx] < ema21.loc[idx])
    add_indicator("RSI 14", rsi14.loc[idx] < 35, rsi14.loc[idx] > 70)
    add_indicator("MACD Histogram", macd_hist.loc[idx] > 0, macd_hist.loc[idx] < 0)
    add_indicator("Bollinger Position", bb_pos.loc[idx] < 0.2, bb_pos.loc[idx] > 0.8)
    add_indicator("Stochastic %K", stoch_k.loc[idx] < 20, stoch_k.loc[idx] > 80)
    add_indicator("Williams %R", williams_r.loc[idx] < -80, williams_r.loc[idx] > -20)
    add_indicator("ROC 10", roc10.loc[idx] > 0, roc10.loc[idx] < 0)
    add_indicator("Momentum 10", momentum10.loc[idx] > 0, momentum10.loc[idx] < 0)
    add_indicator("OBV Slope", obv_slope.loc[idx] > 0, obv_slope.loc[idx] < 0)
    add_indicator(
        "Price-Volume Impulse",
        (price_change.loc[idx] > 0) and (volume_ratio.loc[idx] > 1.1),
        (price_change.loc[idx] < 0) and (volume_ratio.loc[idx] > 1.1),
    )
    add_indicator("Volatility Regime", vol_regime.loc[idx] < 1.0, vol_regime.loc[idx] > 1.3)
    add_indicator("CCI 20", cci20.loc[idx] < -100, cci20.loc[idx] > 100)
    add_indicator(
        "ADX Trend",
        (plus_di.loc[idx] > minus_di.loc[idx]) and (adx14.loc[idx] > 20),
        (plus_di.loc[idx] < minus_di.loc[idx]) and (adx14.loc[idx] > 20),
    )
    add_indicator("VWAP Bias", close.loc[idx] > vwap.loc[idx], close.loc[idx] < vwap.loc[idx])
    add_indicator("VWAP Slope", vwap_slope.loc[idx] > 0, vwap_slope.loc[idx] < 0)
    add_indicator("MFI 14", mfi14.loc[idx] < 25, mfi14.loc[idx] > 75)
    add_indicator(
        "Donchian Breakout",
        close.loc[idx] > donchian_upper.loc[idx],
        close.loc[idx] < donchian_lower.loc[idx],
    )
    add_indicator("Session Open Bias", close.loc[idx] > session_open.loc[idx], close.loc[idx] < session_open.loc[idx])
    add_indicator("News Sentiment", sentiment_score > 0.1, sentiment_score < -0.1)

    result_df = pd.DataFrame(indicator_rows)
    result_df["Score"] = pd.to_numeric(result_df["Score"], errors="coerce").fillna(0).astype(int)
    total_score = int(result_df["Score"].sum())
    max_abs_score = len(result_df)
    confidence = abs(total_score) / max_abs_score if max_abs_score else 0.0

    if total_score >= 7:
        summary = "STRONG BULLISH"
    elif total_score >= 3:
        summary = "BULLISH"
    elif total_score <= -7:
        summary = "STRONG BEARISH"
    elif total_score <= -3:
        summary = "BEARISH"
    else:
        summary = "NEUTRAL"

    return {
        "summary": summary,
        "score": total_score,
        "confidence": confidence,
        "rows": result_df,
    }


def _signal_color_style(value):
    text = str(value).strip().lower()
    if text in {"up", "bullish", "positive"}:
        return "color: #34d399; font-weight: 700;"
    if text in {"down", "bearish", "negative"}:
        return "color: #f87171; font-weight: 700;"
    return "color: #fbbf24; font-weight: 700;"


def _signed_value_style(value):
    try:
        num = float(value)
    except (TypeError, ValueError):
        return ""
    if np.isnan(num):
        return ""
    if num > 0:
        return "color: #34d399; font-weight: 700;"
    if num < 0:
        return "color: #f87171; font-weight: 700;"
    return "color: #fbbf24; font-weight: 700;"


def _hit_rate_style(value):
    try:
        num = float(value)
    except (TypeError, ValueError):
        return ""
    if np.isnan(num):
        return ""
    if num >= 55.0:
        return "color: #34d399; font-weight: 700;"
    if num <= 45.0:
        return "color: #f87171; font-weight: 700;"
    return "color: #fbbf24; font-weight: 700;"


def _model_name_style(value):
    text = str(value).strip().lower()
    if text.startswith("ens") or "ensemble" in text:
        return "color: #e5e7eb; font-weight: 800;"
    return ""


def _format_table_value(value, fmt: str | None = None) -> str:
    if pd.isna(value):
        return "-"
    if fmt is not None:
        try:
            return fmt.format(float(value))
        except Exception:
            pass
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    return str(value)


def _table_cell_style(column: str, value) -> str:
    style = "color: #ededed; font-weight: 600;"
    if column == "Model":
        style = _model_name_style(value) or style
    elif column == "Signal":
        style = _signal_color_style(value) or style
    elif column in {"Pred Return (%)", "Strategy (%)", "Strategy Return (%)"}:
        style = _signed_value_style(value) or style
    elif column == "Hit Rate (%)":
        style = _hit_rate_style(value) or style
    return style


def _hex_to_rgb(color: str) -> tuple[int, int, int]:
    color = color.strip().lstrip("#")
    return int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)


def _rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    return "#{:02x}{:02x}{:02x}".format(*rgb)


def _lerp_color(start_hex: str, end_hex: str, t: float) -> str:
    t = max(0.0, min(1.0, float(t)))
    s = _hex_to_rgb(start_hex)
    e = _hex_to_rgb(end_hex)
    rgb = (
        int(round(s[0] + (e[0] - s[0]) * t)),
        int(round(s[1] + (e[1] - s[1]) * t)),
        int(round(s[2] + (e[2] - s[2]) * t)),
    )
    return _rgb_to_hex(rgb)


def _build_sentiment_segment_colors(segment_count: int = 28) -> list[str]:
    if segment_count <= 1:
        return ["#8b9098"]
    left = "#ff6b4a"
    middle = "#8b9098"
    right = "#10b981"
    midpoint = (segment_count - 1) / 2.0
    colors: list[str] = []
    for i in range(segment_count):
        if i <= midpoint:
            t = i / midpoint if midpoint else 1.0
            colors.append(_lerp_color(left, middle, t))
        else:
            t = (i - midpoint) / (segment_count - 1 - midpoint) if (segment_count - 1 - midpoint) else 1.0
            colors.append(_lerp_color(middle, right, t))
    return colors


def render_themed_table(df: pd.DataFrame, format_map: dict[str, str] | None = None) -> None:
    format_map = format_map or {}
    headers = "".join([f"<th>{escape(str(col))}</th>" for col in df.columns])
    rows_html: list[str] = []

    for _, row in df.iterrows():
        cell_html: list[str] = []
        for col in df.columns:
            value = row[col]
            text = _format_table_value(value, format_map.get(col))
            style = _table_cell_style(col, value)
            cell_html.append(f"<td style=\"{style}\">{escape(text)}</td>")
        rows_html.append(f"<tr>{''.join(cell_html)}</tr>")

    table_html = (
        "<div class=\"themed-table\">"
        "<table>"
        f"<thead><tr>{headers}</tr></thead>"
        f"<tbody>{''.join(rows_html)}</tbody>"
        "</table>"
        "</div>"
    )

    st.markdown(table_html, unsafe_allow_html=True)


@st.cache_resource
def ensure_portal_tables() -> bool:
    try:
        Base.metadata.create_all(
            bind=engine,
            tables=[
                AppUser.__table__,
                UserSubscription.__table__,
                ComplianceConsent.__table__,
                ComplianceAuditLog.__table__,
            ],
        )
        return True
    except Exception:
        return False


def _normalize_user_key(raw_value: str) -> str:
    value = "".join(ch for ch in str(raw_value).strip().lower() if ch.isalnum() or ch in {"_", "-", "."})
    return value or "anonymous"


def _normalize_username(raw_value: str) -> str:
    value = "".join(ch for ch in str(raw_value).strip().lower() if ch.isalnum() or ch in {"_", "-", "."})
    return value


def _hash_password(password: str, salt_hex: str | None = None) -> str:
    salt = bytes.fromhex(salt_hex) if salt_hex else secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PASSWORD_ITERATIONS,
    )
    return f"pbkdf2_sha256${PASSWORD_ITERATIONS}${salt.hex()}${digest.hex()}"


def _verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, iter_text, salt_hex, digest_hex = stored_hash.split("$")
        if algorithm != "pbkdf2_sha256":
            return False
        iterations = int(iter_text)
        candidate = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            bytes.fromhex(salt_hex),
            iterations,
        ).hex()
        return hmac.compare_digest(candidate, digest_hex)
    except Exception:
        return False


def get_user_by_username_or_email(identifier: str) -> pd.DataFrame:
    try:
        return pd.read_sql(
            text(
                """
                SELECT id, username, email, password_hash, full_name, is_active, created_at
                FROM app_users
                WHERE username = :identifier OR email = :identifier
                LIMIT 1
                """
            ),
            engine,
            params={"identifier": str(identifier).strip().lower()},
        )
    except Exception:
        return pd.DataFrame()


def get_user_by_id(user_id: int) -> pd.DataFrame:
    try:
        return pd.read_sql(
            text(
                """
                SELECT id, username, email, full_name, is_active, created_at
                FROM app_users
                WHERE id = :user_id
                LIMIT 1
                """
            ),
            engine,
            params={"user_id": int(user_id)},
        )
    except Exception:
        return pd.DataFrame()


def create_user(username: str, email: str, password: str, full_name: str | None = None) -> tuple[bool, str, int | None]:
    username_norm = _normalize_username(username)
    email_norm = str(email).strip().lower()

    if len(username_norm) < 3:
        return False, "Username must be at least 3 characters.", None
    if "@" not in email_norm or "." not in email_norm:
        return False, "Enter a valid email address.", None
    if len(password) < 8:
        return False, "Password must be at least 8 characters.", None

    password_hash = _hash_password(password)

    try:
        with engine.begin() as conn:
            inserted = conn.execute(
                text(
                    """
                    INSERT INTO app_users (username, email, password_hash, full_name, is_active, created_at)
                    VALUES (:username, :email, :password_hash, :full_name, true, :created_at)
                    RETURNING id
                    """
                ),
                {
                    "username": username_norm,
                    "email": email_norm,
                    "password_hash": password_hash,
                    "full_name": (full_name or "").strip() or None,
                    "created_at": datetime.utcnow(),
                },
            ).fetchone()

            user_id = int(inserted[0])
            conn.execute(
                text(
                    """
                    INSERT INTO user_subscriptions (user_id, plan_name, status, start_at, end_at, payment_reference, created_at)
                    VALUES (:user_id, :plan_name, 'inactive', NULL, NULL, NULL, :created_at)
                    ON CONFLICT (user_id)
                    DO NOTHING
                    """
                ),
                {
                    "user_id": user_id,
                    "plan_name": SUBSCRIPTION_PLAN_NAME,
                    "created_at": datetime.utcnow(),
                },
            )
        return True, "Registration completed. Please login.", user_id
    except Exception:
        return False, "Registration failed. Username or email may already exist.", None


def authenticate_user(identifier: str, password: str) -> tuple[bool, dict | None, str]:
    user_df = get_user_by_username_or_email(identifier)
    if user_df.empty:
        return False, None, "User not found."

    user = user_df.iloc[0]
    if not bool(user.get("is_active", False)):
        return False, None, "Your account is inactive."

    if not _verify_password(password, str(user["password_hash"])):
        return False, None, "Invalid password."

    user_payload = {
        "id": int(user["id"]),
        "username": str(user["username"]),
        "email": str(user["email"]),
        "full_name": str(user["full_name"]) if pd.notna(user.get("full_name")) else "",
    }
    return True, user_payload, "Login successful."


def get_subscription_for_user(user_id: int) -> pd.DataFrame:
    try:
        return pd.read_sql(
            text(
                """
                SELECT user_id, plan_name, status, start_at, end_at, payment_reference, created_at
                FROM user_subscriptions
                WHERE user_id = :user_id
                ORDER BY created_at DESC, user_id DESC
                LIMIT 1
                """
            ),
            engine,
            params={"user_id": int(user_id)},
        )
    except Exception:
        return pd.DataFrame()


def subscription_is_active(subscription_df: pd.DataFrame) -> bool:
    if subscription_df.empty:
        return False
    row = subscription_df.iloc[0]
    status = str(row.get("status") or "").strip().lower()
    if status != "active":
        return False
    end_at = pd.to_datetime(row.get("end_at"), errors="coerce")
    if pd.notna(end_at):
        if getattr(end_at, "tzinfo", None) is not None:
            end_at = end_at.tz_convert(None)
        if end_at < pd.Timestamp(datetime.utcnow()):
            return False
    return True


def activate_subscription(user_id: int, payment_reference: str) -> None:
    now = datetime.utcnow()
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO user_subscriptions (user_id, plan_name, status, start_at, end_at, payment_reference, created_at)
                VALUES (:user_id, :plan_name, 'active', :start_at, :end_at, :payment_reference, :created_at)
                ON CONFLICT (user_id)
                DO UPDATE SET
                    plan_name = EXCLUDED.plan_name,
                    status = EXCLUDED.status,
                    start_at = EXCLUDED.start_at,
                    end_at = EXCLUDED.end_at,
                    payment_reference = EXCLUDED.payment_reference
                """
            ),
            {
                "user_id": int(user_id),
                "plan_name": SUBSCRIPTION_PLAN_NAME,
                "start_at": now,
                "end_at": now + timedelta(days=SUBSCRIPTION_DURATION_DAYS),
                "payment_reference": payment_reference[:80],
                "created_at": now,
            },
        )


def load_latest_compliance_consent(user_key: str) -> pd.DataFrame:
    try:
        return pd.read_sql(
            text(
                """
                SELECT user_key, disclaimer_version, accepted_at, app_version
                FROM compliance_consents
                WHERE user_key = :user_key
                  AND disclaimer_version = :disclaimer_version
                ORDER BY accepted_at DESC, id DESC
                LIMIT 1
                """
            ),
            engine,
            params={
                "user_key": user_key,
                "disclaimer_version": COMPLIANCE_DISCLAIMER_VERSION,
            },
        )
    except Exception:
        return pd.DataFrame()


def save_compliance_consent(user_key: str, app_version: str = APP_VERSION) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO compliance_consents (user_key, disclaimer_version, accepted_at, app_version, created_at)
                VALUES (:user_key, :disclaimer_version, :accepted_at, :app_version, :created_at)
                ON CONFLICT (user_key, disclaimer_version)
                DO UPDATE SET
                    accepted_at = EXCLUDED.accepted_at,
                    app_version = EXCLUDED.app_version
                """
            ),
            {
                "user_key": user_key,
                "disclaimer_version": COMPLIANCE_DISCLAIMER_VERSION,
                "accepted_at": datetime.utcnow(),
                "app_version": app_version,
                "created_at": datetime.utcnow(),
            },
        )


def save_compliance_audit_event(user_key: str, event_type: str, symbol: str, payload: dict | None = None) -> None:
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO compliance_audit_logs (user_key, event_type, symbol, payload, created_at)
                    VALUES (:user_key, :event_type, :symbol, :payload, :created_at)
                    """
                ),
                {
                    "user_key": user_key,
                    "event_type": event_type,
                    "symbol": symbol,
                    "payload": json.dumps(payload or {}, ensure_ascii=True),
                    "created_at": datetime.utcnow(),
                },
            )
    except Exception:
        pass


@st.dialog("Register New User")
def show_registration_dialog() -> None:
    with st.form("register_user_form", clear_on_submit=False):
        full_name = st.text_input("Full Name")
        username = st.text_input("Username")
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        confirm_password = st.text_input("Confirm Password", type="password")
        submitted = st.form_submit_button("Create Account", use_container_width=True)

    if not submitted:
        return

    if password != confirm_password:
        st.error("Passwords do not match.")
        return

    ok, message, user_id = create_user(
        username=username,
        email=email,
        password=password,
        full_name=full_name,
    )
    if ok:
        user_df = get_user_by_id(int(user_id)) if user_id is not None else pd.DataFrame()
        if not user_df.empty:
            user_row = user_df.iloc[0]
            st.session_state["auth_user"] = {
                "id": int(user_row["id"]),
                "username": str(user_row["username"]),
                "email": str(user_row["email"]),
                "full_name": str(user_row["full_name"]) if pd.notna(user_row.get("full_name")) else "",
            }
            st.session_state["auth_feedback"] = "Registration completed and login successful."
        else:
            st.session_state["auth_feedback"] = message
        st.session_state["show_registration_dialog"] = False
        if user_id is not None:
            save_compliance_audit_event(
                _normalize_user_key(username),
                "user_registered",
                "",
                {"user_id": user_id, "email": str(email).strip().lower()},
            )
            save_compliance_audit_event(
                _normalize_user_key(username),
                "user_login",
                "",
                {"user_id": user_id, "source": "post_registration"},
            )
        st.rerun()
    else:
        st.error(message)


def _clear_auth_session() -> None:
    st.session_state["auth_user"] = None
    st.session_state["show_registration_dialog"] = False


def require_authenticated_user(schema_ready: bool) -> dict:
    st.session_state.setdefault("auth_user", None)
    st.session_state.setdefault("show_registration_dialog", False)
    st.session_state.setdefault("auth_feedback", "")

    if not schema_ready:
        st.error("Portal tables are unavailable. Run the pipeline once to initialize schema.")
        st.stop()

    auth_user = st.session_state.get("auth_user")
    if auth_user:
        current_user_df = get_user_by_id(int(auth_user["id"]))
        if not current_user_df.empty and bool(current_user_df.iloc[0]["is_active"]):
            return auth_user
        _clear_auth_session()
        st.warning("Session expired. Please login again.")

    st.subheader("Portal Access")
    st.caption("Only registered users can access the dashboard.")
    feedback = st.session_state.get("auth_feedback")
    if feedback:
        st.success(feedback)
        st.session_state["auth_feedback"] = ""

    with st.form("login_form", clear_on_submit=False):
        identifier = st.text_input("Username or Email")
        password = st.text_input("Password", type="password")
        login_submitted = st.form_submit_button("Login", use_container_width=True)

    login_col, reg_col = st.columns([1, 1], gap="small")
    with reg_col:
        if st.button("Register", use_container_width=True):
            st.session_state["show_registration_dialog"] = True

    if st.session_state.get("show_registration_dialog"):
        show_registration_dialog()

    if login_submitted:
        ok, user_payload, message = authenticate_user(identifier, password)
        if ok and user_payload is not None:
            st.session_state["auth_user"] = user_payload
            st.session_state["show_registration_dialog"] = False
            save_compliance_audit_event(
                _normalize_user_key(user_payload["username"]),
                "user_login",
                "",
                {"user_id": user_payload["id"]},
            )
            st.rerun()
        st.error(message)
        if message == "User not found.":
            st.session_state["show_registration_dialog"] = True
            show_registration_dialog()

    with login_col:
        st.info("If you are a new user, click Register.")
    st.stop()

st.markdown(
    """
    <div class="app-title">
        <div class="app-kicker">Intraday Intelligence Desk</div>
        <h1 class="app-heading">TradeIQ</h1>
        <div class="app-sub">Signal Depth. Execution Edge.</div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ----------------------------------
# Sidebar
# ----------------------------------

@st.cache_data(ttl=3600)
def load_symbols():
    symbols_df = pd.read_sql(
        """
        SELECT symbol, name
        FROM symbols_master
        WHERE active = true
        ORDER BY symbol
        """,
        engine,
    )

    if not symbols_df.empty:
        return symbols_df

    fallback_df = pd.read_sql(
        """
        SELECT DISTINCT symbol, NULL AS name
        FROM market_data
        ORDER BY symbol
        """,
        engine,
    )
    return fallback_df


# ----------------------------------
# Load Data
# ----------------------------------

@st.cache_data(ttl=120)
def load_prices(sym):

    return pd.read_sql(f"""
        SELECT *
        FROM market_data
        WHERE symbol='{sym}'
        ORDER BY date
    """, engine)


@st.cache_data(ttl=120)
def load_news(sym):

    return pd.read_sql(f"""
        SELECT *
        FROM market_news
        WHERE symbol='{sym.replace(".NS","")}'
        ORDER BY published_at DESC
        LIMIT 5
    """, engine)


@st.cache_data(ttl=120)
def load_latest_prediction(sym):

    try:
        return pd.read_sql(
            f"""
            SELECT *
            FROM stock_predictions
            WHERE symbol='{sym}'
            ORDER BY target_date DESC
            LIMIT 1
            """,
            engine,
        )
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=120)
def load_model_predictions(sym):
    try:
        df = pd.read_sql(
            f"""
            SELECT *
            FROM stock_predictions
            WHERE symbol='{sym}'
            ORDER BY target_date DESC, created_at DESC
            LIMIT 200
            """,
            engine,
        )
        if df.empty:
            return df
        return df.sort_values(
            by=["target_date", "created_at"], ascending=[False, False]
        ).drop_duplicates(subset=["model_name"], keep="first")
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=120)
def load_backtest_results(sym):
    try:
        df = pd.read_sql(
            f"""
            SELECT *
            FROM model_backtest_results
            WHERE symbol='{sym}'
            ORDER BY run_date DESC, created_at DESC
            LIMIT 200
            """,
            engine,
        )
        if df.empty:
            return df
        return df.sort_values(
            by=["run_date", "created_at"], ascending=[False, False]
        ).drop_duplicates(subset=["model_name"], keep="first")
    except Exception:
        return pd.DataFrame()


# ----------------------------------
# Sidebar
# ----------------------------------

portal_schema_ready = ensure_portal_tables()
authenticated_user = require_authenticated_user(portal_schema_ready)
user_id = int(authenticated_user["id"])
username = str(authenticated_user["username"])
display_name = str(authenticated_user.get("full_name") or username)
compliance_user_key = _normalize_user_key(username)

symbols_df = load_symbols()

if symbols_df.empty:
    st.warning("No symbols found in symbols_master or market_data.")
    st.stop()

symbol_labels = symbols_df.apply(
    lambda row: f"{row['symbol']} - {row['name']}" if pd.notna(row["name"]) and row["name"] else row["symbol"],
    axis=1,
).tolist()
label_to_symbol = dict(zip(symbol_labels, symbols_df["symbol"]))

st.sidebar.markdown(
    dedent(
        f"""
        <div class="sidebar-title">
            <div class="sidebar-kicker">Workspace</div>
            <div class="sidebar-heading">Market Controls</div>
            <div class="news-meta" style="margin:0.1rem 0 0;">Tracked Symbols: {len(symbol_labels)}</div>
        </div>
        """
    ),
    unsafe_allow_html=True,
)

selected_label = st.sidebar.selectbox(
    "Select Stock / Ticker",
    symbol_labels,
)
symbol = label_to_symbol[selected_label]

st.sidebar.markdown("### Account")
st.sidebar.caption(f"Signed in as: `{display_name}`")
st.sidebar.caption(f"Username: `{username}`")
if st.sidebar.button("Logout", use_container_width=True):
    save_compliance_audit_event(
        compliance_user_key,
        "user_logout",
        symbol,
        {"user_id": user_id},
    )
    _clear_auth_session()
    st.rerun()

subscription_df = get_subscription_for_user(user_id)
subscription_active = subscription_is_active(subscription_df)
subscription_status_text = "INACTIVE"
subscription_end_text = "-"
if not subscription_df.empty:
    sub_row = subscription_df.iloc[0]
    subscription_status_text = str(sub_row.get("status") or "inactive").upper()
    sub_end = pd.to_datetime(sub_row.get("end_at"), errors="coerce")
    if pd.notna(sub_end):
        subscription_end_text = sub_end.strftime("%Y-%m-%d %H:%M:%S")
if subscription_active:
    subscription_status_text = "ACTIVE"

st.sidebar.markdown("### Subscription")
st.sidebar.caption(f"Plan: `{SUBSCRIPTION_PLAN_NAME}`")
st.sidebar.caption(f"Status: `{subscription_status_text}`")
st.sidebar.caption(f"Valid Until: `{subscription_end_text}`")
if not subscription_active:
    st.sidebar.warning("Predictions are locked until paid subscription is active.")
    payment_reference = st.sidebar.text_input("Payment Reference", key="payment_reference")
    redeem_code = st.sidebar.text_input("Subscription Code", key="subscription_redeem_code")
    if st.sidebar.button("Activate Subscription", use_container_width=True):
        if not SUBSCRIPTION_REDEEM_CODE:
            st.sidebar.error("Subscription activation is disabled. Contact admin.")
        elif redeem_code.strip() != SUBSCRIPTION_REDEEM_CODE:
            st.sidebar.error("Invalid subscription code.")
            save_compliance_audit_event(
                compliance_user_key,
                "subscription_activation_failed",
                symbol,
                {"reason": "invalid_code"},
            )
        elif not payment_reference.strip():
            st.sidebar.error("Enter payment reference.")
        else:
            activate_subscription(user_id, payment_reference.strip())
            save_compliance_audit_event(
                compliance_user_key,
                "subscription_activated",
                symbol,
                {
                    "payment_reference": payment_reference.strip(),
                    "duration_days": SUBSCRIPTION_DURATION_DAYS,
                },
            )
            st.rerun()

consent_df = (
    load_latest_compliance_consent(compliance_user_key)
    if portal_schema_ready
    else pd.DataFrame()
)
compliance_ready = portal_schema_ready and not consent_df.empty
consent_time_text = "-"
if compliance_ready:
    consent_time = pd.to_datetime(consent_df.iloc[0]["accepted_at"], errors="coerce")
    if pd.notna(consent_time):
        consent_time_text = consent_time.strftime("%Y-%m-%d %H:%M:%S")

st.sidebar.caption(f"Policy Version: `{COMPLIANCE_DISCLAIMER_VERSION}`")
if compliance_ready:
    st.sidebar.success(f"Consent active for `{compliance_user_key}`")
    st.sidebar.caption(f"Accepted at: {consent_time_text}")
else:
    if portal_schema_ready:
        st.sidebar.warning("Predictions are locked until compliance consent is accepted.")
        accept_key = f"accept_compliance_{compliance_user_key}"
        accept_checked = st.sidebar.checkbox(
            "I understand this is educational analytics, not assured returns.",
            key=accept_key,
        )
        if st.sidebar.button("Accept & Unlock Predictions", use_container_width=True):
            if accept_checked:
                save_compliance_consent(compliance_user_key)
                save_compliance_audit_event(
                    compliance_user_key,
                    "consent_accepted",
                    symbol,
                    {
                        "policy_version": COMPLIANCE_DISCLAIMER_VERSION,
                        "user_id": user_id,
                    },
                )
                st.rerun()
            else:
                st.sidebar.error("Enable the checkbox before unlocking predictions.")
    else:
        st.sidebar.error("Compliance table setup failed. Run pipeline once to initialize schema.")


# ----------------------------------
# Fetch
# ----------------------------------

prices = load_prices(symbol)
news = load_news(symbol)
prediction_df = load_latest_prediction(symbol)
model_predictions_df = load_model_predictions(symbol)
backtest_df = load_backtest_results(symbol)

predictions_unlocked = compliance_ready and subscription_active
lock_reasons: list[str] = []
if not compliance_ready:
    lock_reasons.append("compliance consent pending")
if not subscription_active:
    lock_reasons.append("subscription inactive")
lock_reason_text = ", ".join(lock_reasons) if lock_reasons else "all checks passed"

access_event_key = f"portal_access_{compliance_user_key}_{symbol}_{int(predictions_unlocked)}"
if not st.session_state.get(access_event_key):
    save_compliance_audit_event(
        compliance_user_key,
        "dashboard_access_unlocked" if predictions_unlocked else "dashboard_access_locked",
        symbol,
        {
            "policy_version": COMPLIANCE_DISCLAIMER_VERSION,
            "subscription_active": subscription_active,
            "reason": lock_reason_text,
        },
    )
    st.session_state[access_event_key] = True

if prices.empty:
    st.warning(f"No market data found for {symbol}.")
    st.stop()

latest_close = float(prices["close"].iloc[-1])
latest_high = float(prices["high"].iloc[-1])
latest_low = float(prices["low"].iloc[-1])
latest_volume = float(prices["volume"].iloc[-1]) if "volume" in prices and not pd.isna(prices["volume"].iloc[-1]) else 0.0
latest_date = pd.to_datetime(prices["date"].iloc[-1], errors="coerce")
latest_date_text = latest_date.strftime("%d %b %Y") if pd.notna(latest_date) else "-"
sentiment_avg = float(news["sentiment_score"].fillna(0).mean()) if not news.empty and "sentiment_score" in news.columns else 0.0
prediction_text = "Not available"
prediction_target = "-"
next_close_text = "Not available"
next_close_target = "-"
next_close_price = "-"

if not predictions_unlocked:
    prediction_df = pd.DataFrame()
    model_predictions_df = pd.DataFrame()
    backtest_df = pd.DataFrame()
    prediction_text = "LOCKED"
    next_close_text = "LOCKED"
    prediction_target = lock_reason_text.title()
    next_close_target = lock_reason_text.title()
    next_close_price = "-"

if not prediction_df.empty:
    p = prediction_df.iloc[0]
    pred_ret = float(p["predicted_return"]) * 100.0 if pd.notna(p["predicted_return"]) else 0.0
    prediction_text = f"{p['direction'].upper()} ({pred_ret:+.2f}%)"
    prediction_target = str(p["target_date"])

if not model_predictions_df.empty:
    ensemble_row = model_predictions_df[
        model_predictions_df["model_name"] == "ensemble_v1"
    ]
    if not ensemble_row.empty:
        p = ensemble_row.iloc[0]
        pred_ret = float(p["predicted_return"]) * 100.0 if pd.notna(p["predicted_return"]) else 0.0
        prediction_text = f"{p['direction'].upper()} ({pred_ret:+.2f}%)"
        prediction_target = str(p["target_date"])

    next_close_row = model_predictions_df[
        model_predictions_df["model_name"] == "ensemble_next_close_v1"
    ]
    if not next_close_row.empty:
        p = next_close_row.iloc[0]
        next_ret = float(p["predicted_return"]) * 100.0 if pd.notna(p["predicted_return"]) else 0.0
        next_close_text = f"{str(p['direction']).upper()} ({next_ret:+.2f}%)"
        next_close_target = str(p["target_date"])
        next_close_price = f"{float(p['predicted_close']):,.2f}" if pd.notna(p["predicted_close"]) else "-"

indicator_consensus = compute_indicator_consensus(prices, sentiment_avg)
indicator_summary = indicator_consensus["summary"]
indicator_score = indicator_consensus["score"]
indicator_conf = indicator_consensus["confidence"] * 100.0
indicator_rows = indicator_consensus["rows"]
indicator_count = int(len(indicator_rows))

# ----------------------------------
# Layout
# ----------------------------------

prev_close = float(prices["close"].iloc[-2]) if len(prices) > 1 else latest_close
day_change_pct = ((latest_close - prev_close) / prev_close * 100.0) if prev_close else 0.0
day_change_text = f"{day_change_pct:+.2f}%"
day_change_color = "#15803d" if day_change_pct > 0 else ("#b91c1c" if day_change_pct < 0 else "#b45309")
day_range_text = f"{latest_low:,.2f} - {latest_high:,.2f}"
sentiment_color = "#15803d" if sentiment_avg > 0.1 else ("#b91c1c" if sentiment_avg < -0.1 else "#b45309")

model_order = [
    "sgd_regression_v1",
    "random_forest_v1",
    "extra_trees_v1",
    "xgboost_v1",
    "ensemble_v1",
]
model_label = {
    "sgd_regression_v1": "SGD",
    "random_forest_v1": "RF",
    "extra_trees_v1": "ET",
    "xgboost_v1": "XGB",
    "ensemble_v1": "ENS",
}
next_close_model_order = [
    "sgd_next_close_v1",
    "random_forest_next_close_v1",
    "extra_trees_next_close_v1",
    "xgboost_next_close_v1",
    "ensemble_next_close_v1",
]
next_close_model_label = {
    "sgd_next_close_v1": "SGD NC",
    "random_forest_next_close_v1": "RF NC",
    "extra_trees_next_close_v1": "ET NC",
    "xgboost_next_close_v1": "XGB NC",
    "ensemble_next_close_v1": "ENS NC",
}

final_color = "#15803d"
if "BEARISH" in indicator_summary:
    final_color = "#b91c1c"
elif "NEUTRAL" in indicator_summary or "INSUFFICIENT" in indicator_summary:
    final_color = "#0f766e"

bull_count = int((indicator_rows["Signal"] == "Bullish").sum()) if not indicator_rows.empty else 0
bear_count = int((indicator_rows["Signal"] == "Bearish").sum()) if not indicator_rows.empty else 0
neutral_count = int((indicator_rows["Signal"] == "Neutral").sum()) if not indicator_rows.empty else 0
decision_label = str(indicator_summary).replace("_", " ").title()
if decision_label == "Strong Bullish":
    decision_label = "Strongly Bullish"
elif decision_label == "Strong Bearish":
    decision_label = "Strongly Bearish"
segment_count = 28
segment_colors = _build_sentiment_segment_colors(segment_count)
segment_html = "".join(
    f"<span class=\"technical-seg\" style=\"background:{color};\"></span>"
    for color in segment_colors
)
if indicator_count > 0:
    pointer_position_pct = ((indicator_score + indicator_count) / (2.0 * indicator_count)) * 100.0
else:
    pointer_position_pct = 50.0
pointer_position_pct = max(2.0, min(98.0, pointer_position_pct))

model_snapshot_rows = []
if not model_predictions_df.empty:
    for model_name in model_order:
        model_row = model_predictions_df[model_predictions_df["model_name"] == model_name]
        if model_row.empty:
            continue
        row = model_row.iloc[0]
        pred_ret = float(row["predicted_return"]) * 100.0 if pd.notna(row["predicted_return"]) else 0.0
        direction = str(row["direction"]).upper()
        model_snapshot_rows.append(
            {
                "Model": model_label.get(model_name, model_name),
                "Signal": direction,
                "Pred Return (%)": round(pred_ret, 2),
            }
        )

next_close_snapshot_rows = []
if not model_predictions_df.empty:
    for model_name in next_close_model_order:
        model_row = model_predictions_df[model_predictions_df["model_name"] == model_name]
        if model_row.empty:
            continue
        row = model_row.iloc[0]
        pred_ret = float(row["predicted_return"]) * 100.0 if pd.notna(row["predicted_return"]) else 0.0
        pred_close = float(row["predicted_close"]) if pd.notna(row["predicted_close"]) else np.nan
        direction = str(row["direction"]).upper()
        target_dt = str(row["target_date"])
        next_close_snapshot_rows.append(
            {
                "Model": next_close_model_label.get(model_name, model_name),
                "Signal": direction,
                "Pred Return (%)": round(pred_ret, 2),
                "Pred Close": round(pred_close, 2) if pd.notna(pred_close) else np.nan,
                "Target": target_dt,
            }
        )

backtest_snapshot_rows = []
if not backtest_df.empty:
    for model_name in model_order:
        model_row = backtest_df[backtest_df["model_name"] == model_name]
        if model_row.empty:
            continue
        row = model_row.iloc[0]
        hit = float(row["directional_accuracy"]) * 100.0 if pd.notna(row["directional_accuracy"]) else 0.0
        strat_ret = float(row["strategy_return"]) * 100.0 if pd.notna(row["strategy_return"]) else 0.0
        backtest_snapshot_rows.append(
            {
                "Model": model_label.get(model_name, model_name),
                "Hit Rate (%)": round(hit, 1),
                "Strategy (%)": round(strat_ret, 2),
            }
        )

compliance_banner_class = "active" if predictions_unlocked else "pending"
compliance_status_text = (
    f"Access active for `{compliance_user_key}`. Compliance accepted at {consent_time_text}; subscription is active."
    if predictions_unlocked
    else f"Predictions locked for `{compliance_user_key}`: {lock_reason_text}."
)
st.markdown(
    dedent(
        f"""
        <div class="compliance-banner {compliance_banner_class}">
            <div class="compliance-title">Compliance Status</div>
            <div class="compliance-text">{compliance_status_text}</div>
            <div class="compliance-text">No assured returns. Analytics are for research/education workflow unless you are fully SEBI-registered and operationally compliant.</div>
            <div class="compliance-links">
                Grievance channels: <a href="https://scores.sebi.gov.in/" target="_blank">SCORES</a> |
                <a href="https://smartodr.in/" target="_blank">ODR</a>
            </div>
        </div>
        """
    ),
    unsafe_allow_html=True,
)

st.subheader("Decision Board")
decision_col, metric_col = st.columns([1.2, 1.0], gap="small")

with decision_col:
    st.markdown(
        dedent(
            f"""
            <div class="technical-summary-card">
                <div class="technical-summary-title">Based on technicals, this stock is</div>
                <div class="technical-summary-signal" style="color:{final_color};">{decision_label}</div>
                <div class="technical-summary-grid">
                    <div class="technical-track-wrap">
                        <div class="technical-track">
                            {segment_html}
                        </div>
                        <div class="technical-pointer" style="left:{pointer_position_pct:.2f}%;"></div>
                    </div>
                    <div class="technical-legend">
                        <div class="technical-legend-item">
                            <div class="technical-legend-head">
                                <span class="technical-dot" style="background:#ff6b4a;"></span>Bearish
                            </div>
                            <div class="technical-legend-val">{bear_count}</div>
                        </div>
                        <div class="technical-legend-item">
                            <div class="technical-legend-head">
                                <span class="technical-dot" style="background:#8b9098;"></span>Neutral
                            </div>
                            <div class="technical-legend-val">{neutral_count}</div>
                        </div>
                        <div class="technical-legend-item">
                            <div class="technical-legend-head">
                                <span class="technical-dot" style="background:#10b981;"></span>Bullish
                            </div>
                            <div class="technical-legend-val">{bull_count}</div>
                        </div>
                    </div>
                </div>
            </div>
            <div class="decision-card">
                <div class="snapshot-label">Signal Diagnostics</div>
                <div class="news-meta">As of: {latest_date_text}</div>
                <div class="news-meta">Next-Bar ML: {prediction_text}</div>
                <div class="news-meta">Next-Day Close ML: {next_close_text}</div>
                <div class="news-meta">Composite: {indicator_score:+d} / {indicator_count} | Confidence: {indicator_conf:.1f}%</div>
            </div>
            """
        ),
        unsafe_allow_html=True,
    )

with metric_col:
    st.markdown(
        dedent(
            f"""
            <div class="metric-grid">
                <div class="snapshot-card">
                    <div class="snapshot-label">Last Close</div>
                    <div class="snapshot-value">{latest_close:,.2f}</div>
                </div>
                <div class="snapshot-card">
                    <div class="snapshot-label">Day Change</div>
                    <div class="snapshot-value" style="color:{day_change_color};">{day_change_text}</div>
                </div>
                <div class="snapshot-card">
                    <div class="snapshot-label">Day Range</div>
                    <div class="snapshot-value">{day_range_text}</div>
                </div>
                <div class="snapshot-card">
                    <div class="snapshot-label">Volume</div>
                    <div class="snapshot-value">{latest_volume:,.0f}</div>
                </div>
                <div class="snapshot-card">
                    <div class="snapshot-label">Avg Sentiment</div>
                    <div class="snapshot-value" style="color:{sentiment_color};">{sentiment_avg:+.2f}</div>
                </div>
                <div class="snapshot-card">
                    <div class="snapshot-label">Next-Bar Target</div>
                    <div class="snapshot-value">{prediction_target}</div>
                </div>
                <div class="snapshot-card">
                    <div class="snapshot-label">Next-Day Close Target</div>
                    <div class="snapshot-value">{next_close_target}</div>
                </div>
                <div class="snapshot-card">
                    <div class="snapshot-label">Next-Day Close ML</div>
                    <div class="snapshot-value">{next_close_text}</div>
                </div>
                <div class="snapshot-card">
                    <div class="snapshot-label">Pred Next-Day Close</div>
                    <div class="snapshot-value">{next_close_price}</div>
                </div>
            </div>
            """
        ),
        unsafe_allow_html=True,
    )

main_col, side_col = st.columns([1.35, 0.9], gap="small")

with main_col:
    st.subheader(f"{symbol} Price Action")
    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=prices["date"],
        open=prices["open"],
        high=prices["high"],
        low=prices["low"],
        close=prices["close"],
        name="Price",
        increasing_line_color="#16a34a",
        increasing_fillcolor="rgba(22,163,74,0.35)",
        decreasing_line_color="#dc2626",
        decreasing_fillcolor="rgba(220,38,38,0.35)",
    ))
    fig.update_layout(
        paper_bgcolor="#111111",
        plot_bgcolor="#0b0b0b",
        font=dict(color="#ececec", family="Source Sans 3"),
        xaxis_rangeslider_visible=False,
        margin=dict(l=8, r=8, t=8, b=8),
        height=360,
    )
    fig.update_xaxes(
        gridcolor="rgba(120,120,120,0.20)",
        linecolor="rgba(160,160,160,0.30)",
        tickfont=dict(size=12, color="#d4d4d4"),
        showline=True,
    )
    fig.update_yaxes(
        gridcolor="rgba(120,120,120,0.20)",
        linecolor="rgba(160,160,160,0.30)",
        tickfont=dict(size=12, color="#d4d4d4"),
        showline=True,
    )
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Indicator Breakdown")
    if not indicator_rows.empty:
        indicator_cards = []
        for _, row in indicator_rows.sort_values(by="Indicator").iterrows():
            signal = str(row["Signal"]).strip().lower()
            box_class = "indicator-neutral"
            if signal == "bullish":
                box_class = "indicator-bull"
            elif signal == "bearish":
                box_class = "indicator-bear"
            indicator_cards.append(
                f"""
                <div class="indicator-box {box_class}">
                    <div class="indicator-name">{row['Indicator']}</div>
                    <div class="indicator-signal">{row['Signal']}</div>
                </div>
                """
            )
        st.markdown(
            dedent(
                f"""
                <div class="indicator-grid">
                    {''.join(indicator_cards)}
                </div>
                """
            ),
            unsafe_allow_html=True,
        )

with side_col:
    st.subheader("Next-Bar Models")
    if model_snapshot_rows:
        model_snapshot_df = pd.DataFrame(model_snapshot_rows)
        render_themed_table(
            model_snapshot_df,
            format_map={"Pred Return (%)": "{:+.2f}"},
        )
    else:
        st.info(
            f"Predictions locked: {lock_reason_text}."
            if not predictions_unlocked
            else "No model predictions available."
        )

    st.subheader("Next-Day Close Models")
    if next_close_snapshot_rows:
        next_close_snapshot_df = pd.DataFrame(next_close_snapshot_rows)
        render_themed_table(
            next_close_snapshot_df,
            format_map={
                "Pred Return (%)": "{:+.2f}",
                "Pred Close": "{:,.2f}",
            },
        )
    else:
        st.info(
            f"Next-day close predictions locked: {lock_reason_text}."
            if not predictions_unlocked
            else "No next-day close model predictions available."
        )

    st.subheader("Backtest Snapshot")
    if backtest_snapshot_rows:
        backtest_snapshot_df = pd.DataFrame(backtest_snapshot_rows)
        render_themed_table(
            backtest_snapshot_df,
            format_map={
                "Hit Rate (%)": "{:.1f}",
                "Strategy (%)": "{:+.2f}",
            },
        )
    else:
        st.info(
            f"Backtest metrics locked: {lock_reason_text}."
            if not predictions_unlocked
            else "No backtest results available."
        )

st.subheader("News Snapshot")
if not news.empty:
    for _, row in news.head(2).iterrows():
        sentiment = (row.get("sentiment_label") or "neutral").lower()
        score = row.get("sentiment_score")
        color_map = {"positive": "#15803d", "negative": "#b91c1c", "neutral": "#ca8a04"}
        color = color_map.get(sentiment, "#ca8a04")
        score_text = f"{float(score):.2f}" if pd.notna(score) else "0.00"
        st.markdown(
            dedent(
                f"""
                <div class="news-card">
                    <div class="news-title">{row['title']}</div>
                    <div class="news-meta">Source: {row['source']}</div>
                    <div class="news-meta">
                        Sentiment: <span style="color:{color}; font-weight:700;">{sentiment.title()} ({score_text})</span>
                    </div>
                    <a class="news-link" href="{row['url']}" target="_blank">Read More</a>
                </div>
                """
            ),
            unsafe_allow_html=True,
        )
else:
    st.info("No recent news")

with st.expander("Detailed Backtest Metrics", expanded=False):
    if not backtest_df.empty:
        backtest_view = backtest_df.copy()
        backtest_view["directional_accuracy"] = (
            pd.to_numeric(backtest_view["directional_accuracy"], errors="coerce") * 100.0
        ).round(2)
        backtest_view["mae"] = pd.to_numeric(backtest_view["mae"], errors="coerce").round(5)
        backtest_view["rmse"] = pd.to_numeric(backtest_view["rmse"], errors="coerce").round(5)
        backtest_view["strategy_return"] = (
            pd.to_numeric(backtest_view["strategy_return"], errors="coerce") * 100.0
        ).round(2)
        backtest_detail_df = backtest_view[
            ["model_name", "run_date", "sample_count", "directional_accuracy", "mae", "rmse", "strategy_return"]
        ].rename(
            columns={
                "model_name": "Model",
                "run_date": "Run Date",
                "sample_count": "Samples",
                "directional_accuracy": "Hit Rate (%)",
                "mae": "MAE",
                "rmse": "RMSE",
                "strategy_return": "Strategy Return (%)",
            }
        )
        render_themed_table(
            backtest_detail_df,
            format_map={
                "Hit Rate (%)": "{:.2f}",
                "MAE": "{:.5f}",
                "RMSE": "{:.5f}",
                "Strategy Return (%)": "{:+.2f}",
            },
        )
    else:
        st.info(
            f"Detailed backtest metrics are locked: {lock_reason_text}."
            if not predictions_unlocked
            else "No backtest results available yet."
        )

with st.expander("More News", expanded=False):
    if not news.empty and len(news) > 2:
        for _, row in news.iloc[2:].iterrows():
            sentiment = (row.get("sentiment_label") or "neutral").lower()
            score = row.get("sentiment_score")
            color_map = {"positive": "#15803d", "negative": "#b91c1c", "neutral": "#ca8a04"}
            color = color_map.get(sentiment, "#ca8a04")
            score_text = f"{float(score):.2f}" if pd.notna(score) else "0.00"
            st.markdown(
                dedent(
                    f"""
                    <div class="news-card">
                        <div class="news-title">{row['title']}</div>
                        <div class="news-meta">Source: {row['source']}</div>
                        <div class="news-meta">
                            Sentiment: <span style="color:{color}; font-weight:700;">{sentiment.title()} ({score_text})</span>
                        </div>
                        <a class="news-link" href="{row['url']}" target="_blank">Read More</a>
                    </div>
                    """
                ),
                unsafe_allow_html=True,
            )
    elif news.empty:
        st.info("No recent news.")
    else:
        st.info("No additional news beyond the snapshot.")
