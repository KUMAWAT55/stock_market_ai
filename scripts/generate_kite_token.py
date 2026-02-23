#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
from urllib.parse import quote_plus

from kiteconnect import KiteConnect


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate Kite access token from request token."
    )
    parser.add_argument("--api-key", default=os.getenv("KITE_API_KEY", ""))
    parser.add_argument("--api-secret", default=os.getenv("KITE_API_SECRET", ""))
    parser.add_argument("--request-token", default="")
    parser.add_argument(
        "--print-login-url",
        action="store_true",
        help="Print Kite login URL for obtaining request_token.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if not args.api_key:
        print("Error: missing api key. Pass --api-key or set KITE_API_KEY.", file=sys.stderr)
        return 1

    login_url = f"https://kite.trade/connect/login?api_key={quote_plus(args.api_key)}&v=3"
    if args.print_login_url:
        print("Login URL:")
        print(login_url)
        print("\nAfter login, copy `request_token` from the redirect URL and run again with --request-token.")
        if not args.request_token:
            return 0

    request_token = args.request_token.strip()
    if not request_token:
        request_token = input("Enter request_token: ").strip()
    if not request_token:
        print("Error: request_token is required.", file=sys.stderr)
        return 1

    api_secret = args.api_secret.strip()
    if not api_secret:
        api_secret = input("Enter api_secret: ").strip()
    if not api_secret:
        print("Error: api_secret is required.", file=sys.stderr)
        return 1

    kite = KiteConnect(api_key=args.api_key)
    session_data = kite.generate_session(request_token=request_token, api_secret=api_secret)
    access_token = session_data["access_token"]

    print("\nAccess token generated successfully.")
    print(f"KITE_ACCESS_TOKEN={access_token}")
    print("\nExport command:")
    print(f"export KITE_API_KEY='{args.api_key}'")
    print(f"export KITE_ACCESS_TOKEN='{access_token}'")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
