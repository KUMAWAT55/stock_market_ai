#!/usr/bin/env python3
from __future__ import annotations

"""Manual historical backfill runner (separate from FastAPI)."""

import argparse
import asyncio
from typing import Iterable

from loguru import logger

from config.config import get_settings
from realtime.realtime_engine import RealtimePredictionEngine


def _parse_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip().upper() for item in value.split(",") if item.strip()]


def _resolve_symbols(args: argparse.Namespace, settings) -> list[str]:
    symbols = []
    if args.symbol:
        symbols.extend([item.strip().upper() for item in args.symbol if item.strip()])
    symbols.extend(_parse_csv(args.symbols))
    if symbols:
        return sorted(set(symbols))
    return settings.load_symbol_universe()


def _resolve_timeframes(args: argparse.Namespace, settings) -> list[str]:
    timeframes = []
    if args.timeframe:
        timeframes.extend([item.strip().lower() for item in args.timeframe if item.strip()])
    timeframes.extend([item.lower() for item in _parse_csv(args.timeframes)])
    if timeframes:
        return timeframes
    return list(settings.candle_timeframes)


async def _run_backfill(
    *,
    symbols: Iterable[str],
    timeframes: Iterable[str],
    days_override: int | None,
) -> int:
    settings = get_settings()
    engine = RealtimePredictionEngine()

    attempted = 0
    succeeded = 0

    for symbol in symbols:
        for timeframe in timeframes:
            attempted += 1
            days = days_override if days_override is not None else settings.auto_backfill_days(timeframe)
            try:
                result = await engine.backfill_historical(symbol=symbol, timeframe=timeframe, days=days)
                logger.info(
                    "Backfill {} {} days={} inserted={} prediction_status={}",
                    symbol,
                    timeframe,
                    days,
                    result.get("inserted"),
                    result.get("prediction_status"),
                )
                succeeded += 1
            except Exception as exc:
                logger.error("Backfill failed for {} {} days={}: {}", symbol, timeframe, days, exc)

    logger.info("Backfill summary attempted={} succeeded={} failed={}", attempted, succeeded, attempted - succeeded)
    return 0 if attempted == succeeded else 2


def main() -> int:
    parser = argparse.ArgumentParser(description="Manual historical backfill runner")
    parser.add_argument("--symbol", action="append", default=[], help="Symbol to backfill (repeatable)")
    parser.add_argument("--symbols", default="", help="Comma-separated symbols")
    parser.add_argument("--timeframe", action="append", default=[], help="Timeframe to backfill (repeatable)")
    parser.add_argument("--timeframes", default="", help="Comma-separated timeframes")
    parser.add_argument(
        "--days",
        type=int,
        default=None,
        help="Override lookback days for all timeframes (defaults to auto_backfill_days)",
    )
    args = parser.parse_args()

    settings = get_settings()
    symbols = _resolve_symbols(args, settings)
    timeframes = _resolve_timeframes(args, settings)

    if not symbols:
        logger.error("No symbols resolved. Check config/instruments.json or provide --symbol/--symbols.")
        return 2
    if not timeframes:
        logger.error("No timeframes resolved. Check CANDLE_TIMEFRAMES or provide --timeframe/--timeframes.")
        return 2

    logger.info("Running manual backfill symbols={} timeframes={} days_override={}", symbols, timeframes, args.days)
    return asyncio.run(_run_backfill(symbols=symbols, timeframes=timeframes, days_override=args.days))


if __name__ == "__main__":
    raise SystemExit(main())
