"""Create transparent rest-of-season-style projections from player-season history."""

from __future__ import annotations

import argparse
import csv
import re
from collections import defaultdict
from pathlib import Path

from .valuation import STAT_COLUMNS

HISTORY_COLUMNS = ("player", "season", "gp", "min", *STAT_COLUMNS)


def season_start(season: str) -> int:
    match = re.match(r"(\d{4})", season)
    if not match:
        raise ValueError(f"Season must start with a year, received {season!r}")
    return int(match.group(1))


def read_history(path: Path) -> list[dict[str, object]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(line for line in handle if not line.startswith("#"))
        if reader.fieldnames is None:
            raise ValueError("The historical CSV needs a header row.")
        missing = set(HISTORY_COLUMNS) - set(reader.fieldnames)
        if missing:
            raise ValueError(f"Missing required columns: {', '.join(sorted(missing))}")
        rows = []
        for row in reader:
            if not row["player"].strip() or float(row["gp"] or 0) <= 0:
                continue
            parsed: dict[str, object] = dict(row)
            for column in ("gp", "min", *STAT_COLUMNS):
                parsed[column] = float(row[column] or 0)
            rows.append(parsed)
    if not rows:
        raise ValueError("No usable player-season rows found.")
    return rows


def weighted_average(values: list[tuple[float, float]]) -> float:
    return sum(value * weight for value, weight in values) / sum(weight for _, weight in values)


def project(history: list[dict[str, object]], target_season: str, games_in_season: int = 82) -> list[dict[str, object]]:
    """Project totals using three most recent seasons and exponentially declining weights.

    Per-minute rates are projected separately from minutes and availability. This
    avoids accidentally treating a past minutes spike as a permanent skills jump.
    """
    target_start = season_start(target_season)
    by_player: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in history:
        if season_start(str(row["season"])) < target_start:
            by_player[str(row["player"])].append(row)

    projections = []
    for name, rows in by_player.items():
        rows = sorted(rows, key=lambda row: season_start(str(row["season"])), reverse=True)[:3]
        weights = [0.60, 0.28, 0.12][:len(rows)]
        # The most recent season has the largest influence; rows beyond three
        # seasons are deliberately ignored to keep the model responsive.
        projected_gp = min(games_in_season, weighted_average([(float(row["gp"]), weight) for row, weight in zip(rows, weights)]))
        projected_mpg = weighted_average([
            (float(row["min"]) / float(row["gp"]), weight)
            for row, weight in zip(rows, weights)
        ])
        projection: dict[str, object] = {
            "player": name,
            "projected_gp": round(projected_gp, 1),
            "projected_mpg": round(projected_mpg, 1),
            "source_seasons": ",".join(str(row["season"]) for row in rows),
            "team": rows[0].get("team", ""),
            "positions": rows[0].get("positions", ""),
            "yahoo_avg_auction_value": rows[0].get("yahoo_avg_auction_value", ""),
        }
        projected_minutes = projected_gp * projected_mpg
        historical_minutes = sum(float(row["min"]) * weight for row, weight in zip(rows, weights))
        for stat in STAT_COLUMNS:
            per_minute = sum(float(row[stat]) * weight for row, weight in zip(rows, weights)) / historical_minutes
            projection[stat] = round(per_minute * projected_minutes, 2)
        projections.append(projection)
    return sorted(projections, key=lambda row: str(row["player"]))


def write_projections(rows: list[dict[str, object]], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "player", "team", "positions", "yahoo_avg_auction_value", "projected_gp", "projected_mpg",
        "source_seasons", *STAT_COLUMNS,
    ]
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="One row per player-season using season totals")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--target-season", default="2026-27")
    args = parser.parse_args()
    rows = project(read_history(args.input), args.target_season)
    write_projections(rows, args.output)
    print(f"Wrote {len(rows)} projections to {args.output}")


if __name__ == "__main__":
    main()
