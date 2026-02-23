from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from threading import RLock
from typing import Any

from config.config import get_settings


@dataclass(slots=True)
class RiskDecision:
    approved_signal: str
    position_size: float
    stop_loss_price: float | None
    reason: str
    drawdown_pct: float
    throttled: bool


class RiskManager:
    """Simulation-only risk and governance controls for signal outputs."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self._lock = RLock()
        self._last_signal_time: dict[tuple[str, str], datetime] = {}
        self._equity_curve: dict[tuple[str, str], list[float]] = {}

    def evaluate(
        self,
        symbol: str,
        timeframe: str,
        signal: str,
        confidence: float,
        last_price: float,
        realized_return: float | None = None,
    ) -> RiskDecision:
        key = (symbol, timeframe)
        now = datetime.utcnow()

        with self._lock:
            throttled = self._is_throttled(key=key, now=now)
            drawdown_pct = self._update_drawdown(key=key, realized_return=realized_return)

            if drawdown_pct >= self.settings.max_drawdown_pct:
                return RiskDecision(
                    approved_signal="HOLD",
                    position_size=0.0,
                    stop_loss_price=None,
                    reason="Drawdown limit reached",
                    drawdown_pct=drawdown_pct,
                    throttled=throttled,
                )

            if throttled:
                return RiskDecision(
                    approved_signal="HOLD",
                    position_size=0.0,
                    stop_loss_price=None,
                    reason="Signal cooldown active",
                    drawdown_pct=drawdown_pct,
                    throttled=True,
                )

            if signal == "HOLD":
                return RiskDecision(
                    approved_signal="HOLD",
                    position_size=0.0,
                    stop_loss_price=None,
                    reason="Model neutral",
                    drawdown_pct=drawdown_pct,
                    throttled=False,
                )

            size = round(
                max(0.01, min(self.settings.max_capital_allocation_pct, confidence * self.settings.max_capital_allocation_pct)),
                4,
            )
            stop_loss = (
                last_price * (1.0 - self.settings.stop_loss_pct)
                if signal == "BUY"
                else last_price * (1.0 + self.settings.stop_loss_pct)
            )
            self._last_signal_time[key] = now

            return RiskDecision(
                approved_signal=signal,
                position_size=size,
                stop_loss_price=round(stop_loss, 4),
                reason="Approved",
                drawdown_pct=drawdown_pct,
                throttled=False,
            )

    def _is_throttled(self, key: tuple[str, str], now: datetime) -> bool:
        last = self._last_signal_time.get(key)
        if last is None:
            return False
        cooldown = timedelta(seconds=self.settings.signal_cooldown_seconds)
        return now < (last + cooldown)

    def _update_drawdown(self, key: tuple[str, str], realized_return: float | None) -> float:
        curve = self._equity_curve.setdefault(key, [1.0])
        if realized_return is not None:
            curve.append(curve[-1] * (1.0 + realized_return))

        peak = max(curve)
        trough = curve[-1]
        if peak <= 0:
            return 0.0
        return max(0.0, (peak - trough) / peak)

    @staticmethod
    def to_payload(decision: RiskDecision) -> dict[str, Any]:
        return {
            "approved_signal": decision.approved_signal,
            "position_size": decision.position_size,
            "stop_loss_price": decision.stop_loss_price,
            "reason": decision.reason,
            "drawdown_pct": round(decision.drawdown_pct, 6),
            "throttled": decision.throttled,
        }
