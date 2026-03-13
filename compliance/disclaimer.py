from __future__ import annotations
"""Central SEBI-oriented disclaimer content used across API and dashboard."""

from dataclasses import dataclass


DISCLAIMER_VERSION = "sebi_research_signal_v1_2026-02-23"


@dataclass(frozen=True, slots=True)
class ComplianceDisclaimer:
    """Structured disclaimer payload for consistent rendering."""

    title: str
    body: str
    risk_disclosure: str


def get_disclaimer() -> ComplianceDisclaimer:
    """Return immutable research-only disclaimer and risk disclosure text."""
    return ComplianceDisclaimer(
        title="SEBI Compliance Notice",
        body=(
            "This dashboard generates research signals (BULLISH/BEARISH/HOLD) for analytics only. "
            "It does not place or automate trade execution. Past or simulated performance does not guarantee future returns."
        ),
        risk_disclosure=(
            "Equity and derivatives are subject to market risk. Review your risk profile, drawdown tolerance, and "
            "capital allocation before acting on any signal."
        ),
    )
