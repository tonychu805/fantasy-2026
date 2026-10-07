"""Normalize CC BY 4.0 BoxScore Lab season-total CSVs for this project."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

SOURCE_COLUMNS = {
    "player": "player_name",
    "season": "season",
    "gp": "games_played",
    "min": "minutes",
    "fgm": "field_goals_made",
    "fga": "field_goal_attempts",
    "ftm": "free_throws_made",
    "fta": "free_throw_attempts",
    "fg3m": "three_point_makes",
    "pts": "points",
    "reb": "rebounds",
    "ast": "assists",
    "stl": "steals",
    "blk": "blocks",
    "tov": "turnovers",
    "team": "team",
}


def convert(inputs: list[Path]) -> list[dict[str, str]]:
    rows = []
    for input_path in inputs:
        with input_path.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None:
                raise ValueError(f"{input_path} has no header row.")
            missing = set(SOURCE_COLUMNS.values()) - set(reader.fieldnames)
            if missing:
                raise ValueError(f"{input_path} is missing: {', '.join(sorted(missing))}")
            for source in reader:
                if not source["player_name"].strip():
                    continue
                row = {target: source[source_column] for target, source_column in SOURCE_COLUMNS.items()}
                # Yahoo eligibility must come from Yahoo; generic NBA G/F/C labels
                # are deliberately not converted into potentially wrong PG/SG/etc.
                row["positions"] = ""
                row["yahoo_avg_auction_value"] = ""
                rows.append(row)
    return sorted(rows, key=lambda row: (row["player"], row["season"]))


def write_history(rows: list[dict[str, str]], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "player", "season", "gp", "min", "fgm", "fga", "ftm", "fta", "fg3m", "pts", "reb",
        "ast", "stl", "blk", "tov", "team", "positions", "yahoo_avg_auction_value",
    ]
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, nargs="+", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = convert(args.input)
    write_history(rows, args.output)
    print(f"Wrote {len(rows)} player-seasons to {args.output}")


if __name__ == "__main__":
    main()
