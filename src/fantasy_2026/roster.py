"""Summarize a Yahoo roster against an open-data player pool."""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path

from .valuation import COUNTING_CATEGORIES, read_players, value_players


def normalize(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def read_roster(path: Path) -> set[str]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or "player" not in reader.fieldnames:
            raise ValueError("Roster CSV needs a player column.")
        return {normalize(row["player"]) for row in reader if row["player"].strip()}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--players", type=Path, required=True)
    parser.add_argument("--roster", type=Path, required=True)
    args = parser.parse_args()

    roster = read_roster(args.roster)
    players = value_players(read_players(args.players))
    matched = [player for player in players if normalize(str(player["player"])) in roster]
    unmatched = roster - {normalize(str(player["player"])) for player in matched}
    if not matched:
        raise ValueError("No roster names matched the player input.")

    categories = ("fg_pct", "ft_pct", *COUNTING_CATEGORIES, "tov")
    print(f"Matched {len(matched)} rostered players. Total auction value: ${sum(float(p['auction_value']) for p in matched):.0f}")
    print("Category profile (z-scores; positive is better):")
    for category in categories:
        total = sum(float(player[f"z_{category}"]) for player in matched)
        print(f"  {category:6} {total:+.2f}")
    if unmatched:
        print("Unmatched names: " + ", ".join(sorted(unmatched)))


if __name__ == "__main__":
    main()
