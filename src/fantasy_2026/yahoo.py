"""Small, dependency-free Yahoo Fantasy OAuth and data downloader."""

from __future__ import annotations

import argparse
import base64
import json
import os
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

AUTHORIZE_URL = "https://api.login.yahoo.com/oauth2/request_auth"
TOKEN_URL = "https://api.login.yahoo.com/oauth2/get_token"
FANTASY_API_URL = "https://fantasysports.yahooapis.com/fantasy/v2"
TOKEN_PATH = Path("data/private/yahoo_tokens.json")


def settings() -> tuple[str, str, str]:
    client_id = os.environ.get("YAHOO_CLIENT_ID")
    client_secret = os.environ.get("YAHOO_CLIENT_SECRET")
    redirect_uri = os.environ.get("YAHOO_REDIRECT_URI")
    if not all((client_id, client_secret, redirect_uri)):
        raise ValueError("Set YAHOO_CLIENT_ID, YAHOO_CLIENT_SECRET, and YAHOO_REDIRECT_URI first.")
    return client_id, client_secret, redirect_uri


def authorization_url() -> str:
    client_id, _, redirect_uri = settings()
    return AUTHORIZE_URL + "?" + urlencode({
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "language": "en-us",
    })


def token_request(values: dict[str, str]) -> dict[str, object]:
    client_id, client_secret, _ = settings()
    credentials = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    request = Request(
        TOKEN_URL,
        data=urlencode(values).encode(),
        headers={
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )
    with urlopen(request, timeout=30) as response:
        return json.load(response)


def save_tokens(tokens: dict[str, object]) -> None:
    TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    tokens["saved_at"] = int(time.time())
    TOKEN_PATH.write_text(json.dumps(tokens, indent=2), encoding="utf-8")
    print(f"Saved tokens locally at {TOKEN_PATH}; this path is ignored by Git.")


def load_tokens() -> dict[str, object]:
    if not TOKEN_PATH.exists():
        raise ValueError("No token file found. Run the authorize and exchange commands first.")
    return json.loads(TOKEN_PATH.read_text(encoding="utf-8"))


def exchange_code(code: str) -> None:
    _, _, redirect_uri = settings()
    save_tokens(token_request({"grant_type": "authorization_code", "redirect_uri": redirect_uri, "code": code}))


def access_token() -> str:
    tokens = load_tokens()
    expires_at = int(tokens.get("saved_at", 0)) + int(tokens.get("expires_in", 0)) - 60
    if int(time.time()) >= expires_at:
        refresh_token = tokens.get("refresh_token")
        if not isinstance(refresh_token, str):
            raise ValueError("Token expired and no refresh token was saved. Authorize again.")
        refreshed = token_request({"grant_type": "refresh_token", "redirect_uri": settings()[2], "refresh_token": refresh_token})
        if "refresh_token" not in refreshed:
            refreshed["refresh_token"] = refresh_token
        save_tokens(refreshed)
        tokens = refreshed
    token = tokens.get("access_token")
    if not isinstance(token, str):
        raise ValueError("Yahoo response did not include an access token.")
    return token


def fetch(resource: str) -> dict[str, object]:
    separator = "&" if "?" in resource else "?"
    request = Request(
        f"{FANTASY_API_URL}/{resource}{separator}format=json",
        headers={"Authorization": f"Bearer {access_token()}"},
    )
    with urlopen(request, timeout=30) as response:
        return json.load(response)


def save_json(payload: dict[str, object], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {output}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("authorize", help="Print the Yahoo consent URL")
    exchange = commands.add_parser("exchange", help="Exchange the returned authorization code for tokens")
    exchange.add_argument("--code", required=True)
    download = commands.add_parser("download", help="Download a Yahoo Fantasy API resource as local JSON")
    download.add_argument("--resource", required=True, help="Example: league/your_league_key/settings")
    download.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    if args.command == "authorize":
        print(authorization_url())
    elif args.command == "exchange":
        exchange_code(args.code)
    else:
        save_json(fetch(args.resource), args.output)


if __name__ == "__main__":
    main()
