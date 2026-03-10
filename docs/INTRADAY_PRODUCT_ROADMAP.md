# Intraday Product Roadmap (Streak-like Capability Plan)

This roadmap focuses on features intraday users typically value most.

## 1. P0: Must-Have (Immediate)

- Live multi-timeframe model matrix.
- Indicator heatmap by timeframe.
- Intraday scanner with confidence and signal filters.
- Strategy quick backtest (template strategies).
- Risk-aware signal view (`signal` vs `approved_signal`).

Status:
- Implemented in V2 APIs and React UI.

## 2. P1: Streak-like Rule Builder

Goal:
- Let users define conditions without coding.

Suggested features:
- Condition blocks:
  - `EMA(12) > EMA(26)`
  - `RSI(14) < 30`
  - `Close crosses above VWAP`
- Grouping:
  - `ALL` / `ANY` conditions
- Timeframe binding per condition
- Entry and exit condition sets
- Risk block:
  - target
  - stop-loss
  - trailing stop
- Save strategy templates and clone variants

Technical approach:
- Introduce strategy DSL JSON schema in backend.
- Build evaluator that outputs boolean signal by candle.
- Plug evaluator into backtest engine and scanner.

## 3. P2: Alerts and Automation-Ready Layer

- Real-time alerts:
  - in-app toast
  - webhook
  - Telegram/Slack
- Alert deduplication and cooldown.
- Watchlist-specific alert routing.

## 4. P3: Advanced Backtesting

- Time-window backtest (market regime slicing).
- Slippage model by symbol liquidity.
- Partial fills and position sizing simulation.
- Session-only intraday flat-at-close rules.
- Equity curve chart and monthly heatmap.

## 5. P4: Trader Experience Features

- Workspace presets (`Scalp`, `Momentum`, `Reversal`).
- Multi-chart layout + linked crosshair.
- Replay mode (bar-by-bar playback).
- Journal tagging for signal outcome review.

## 6. Recommended KPI Tracking

- scanner hit-to-trade ratio
- alert click-through rate
- strategy adoption per template
- average strategy retention (7/30-day)
- time-to-first-useful-signal

## 7. Suggested Delivery Order

1. Rule Builder MVP (single timeframe conditions)
2. Saved strategies + scanner integration
3. Alert channels + cooldown profile per user
4. Advanced backtester with slippage/session rules
5. Replay + journaling
