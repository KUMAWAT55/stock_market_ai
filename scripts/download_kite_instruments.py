#!/usr/bin/env python3
from __future__ import annotations

"""Download Kite instruments and write to JSON."""

import argparse
import csv
import json
import os
import sys
from io import StringIO
from pathlib import Path
from typing import Any


def _fetch_with_kiteconnect() -> list[dict[str, Any]] | None:
    api_key = os.getenv("KITE_API_KEY", "")
    access_token = os.getenv("KITE_ACCESS_TOKEN", "")
    if not api_key or not access_token:
        return None
    try:
        from kiteconnect import KiteConnect  # type: ignore
    except Exception:
        return None

    kite = KiteConnect(api_key=api_key)
    kite.set_access_token(access_token)
    return kite.instruments()


def _fetch_with_http() -> list[dict[str, Any]]:
    try:
        import requests  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("requests is required for HTTP download fallback") from exc

    url = "https://api.kite.trade/instruments"
    response = requests.get(url, timeout=60)
    response.raise_for_status()
    content = response.text
    reader = csv.DictReader(StringIO(content))
    return [dict(row) for row in reader]


def _normalize_rows(
    rows: list[dict[str, Any]],
    instrument_type: str | None,
    exchange: str | None,
) -> dict[str, str]:
    out: dict[str, str] = {}
    for row in rows:
        if instrument_type and str(row.get("instrument_type", "")).strip().upper() != instrument_type:
            continue
        if exchange and str(row.get("exchange", "")).strip().upper() != exchange:
            continue
        token = row.get("instrument_token") or row.get("instrument_token ")
        symbol = row.get("tradingsymbol") or row.get("symbol")
        if token in (None, "", "nan") or symbol in (None, "", "nan"):
            continue
        out[str(token).strip()] = str(symbol).strip()
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Download Kite instruments to JSON map.")
    parser.add_argument(
        "--out",
        default="config/all_instruments.json",
        help="Output JSON file path (default: config/all_instruments.json).",
    )
    parser.add_argument(
        "--instrument-type",
        default="",
        help="Filter by instrument_type (e.g., EQ).",
    )
    parser.add_argument(
        "--exchange",
        default="",
        help="Filter by exchange (e.g., NSE, BSE).",
    )
    args = parser.parse_args()

    rows = _fetch_with_kiteconnect()
    if rows is None:
        rows = _fetch_with_http()

    instrument_type = args.instrument_type.strip().upper() or None
    exchange = args.exchange.strip().upper() or None
    mapping = _normalize_rows(rows, instrument_type, exchange)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(mapping, indent=2, sort_keys=True), encoding="utf-8")
    print(f"Wrote {len(mapping)} instruments to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
