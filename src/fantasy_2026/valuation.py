"""Convert a public player-stat CSV into 9-category auction values."""

from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path

STAT_COLUMNS = ("fgm", "fga", "ftm", "fta", "fg3m", "pts", "reb", "ast", "stl", "blk", "tov")
COUNTING_CATEGORIES = ("fg3m", "pts", "reb", "ast", "stl", "blk")


def mean(values: list[float]) -> float:
    return sum(values) / len(values)


def population_sd(values: list[float]) -> float:
    average = mean(values)
    return math.sqrt(sum((value - average) ** 2 for value in values) / len(values))


def zscores(values: list[float], inverse: bool = False) -> list[float]:
    average, deviation = mean(values), population_sd(values)
    if deviation == 0:
        return [0.0] * len(values)
    sign = -1 if inverse else 1
    return [sign * (value - average) / deviation for value in values]


def read_players(path: Path) -> list[dict[str, object]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError("The input CSV needs a header row.")
        required = {"player", *STAT_COLUMNS}
        missing = required - set(reader.fieldnames)
        if missing:
            raise ValueError(f"Missing required columns: {', '.join(sorted(missing))}")
        players = []
        for row in reader:
            if not row["player"].strip():
                continue
            player: dict[str, object] = dict(row)
            for column in STAT_COLUMNS:
                player[column] = float(row[column] or 0)
            players.append(player)
    if len(players) < 2:
        raise ValueError("At least two players are required to calculate z-scores.")
    return players


def value_players(players: list[dict[str, object]], rostered_players: int = 156,
                  league_budget: int = 2400, minimum_bid: int = 1) -> list[dict[str, object]]:
    """Return player rows with volume-adjusted category scores and auction values."""
    if len(players) < rostered_players:
        raise ValueError(f"Need at least {rostered_players} players for this league.")

    league_fg = sum(float(p["fgm"]) for p in players) / sum(float(p["fga"]) for p in players)
    league_ft = sum(float(p["ftm"]) for p in players) / sum(float(p["fta"]) for p in players)
    category_values: dict[str, list[float]] = {
        "fg_pct": [float(p["fgm"]) - league_fg * float(p["fga"]) for p in players],
        "ft_pct": [float(p["ftm"]) - league_ft * float(p["fta"]) for p in players],
    }
    for category in COUNTING_CATEGORIES:
        category_values[category] = [float(p[category]) for p in players]
    category_values["tov"] = [float(p["tov"]) for p in players]

    for category, values in category_values.items():
        for player, score in zip(players, zscores(values, inverse=category == "tov")):
            player[f"z_{category}"] = score
    for player in players:
        player["z_total"] = sum(float(player[f"z_{category}"]) for category in category_values)

    ranked = sorted(players, key=lambda p: float(p["z_total"]), reverse=True)
    replacement = float(ranked[rostered_players - 1]["z_total"])
    premium_pool = league_budget - rostered_players * minimum_bid
    weights = [max(0.0, float(player["z_total"]) - replacement) for player in ranked[:rostered_players]]
    total_weight = sum(weights)
    for index, player in enumerate(ranked):
        player["rostered_rank"] = index + 1
        if index < rostered_players and total_weight:
            player["auction_value"] = minimum_bid + premium_pool * weights[index] / total_weight
        else:
            player["auction_value"] = 0.0

    # Auction rooms bid whole dollars. Largest-remainder rounding preserves the
    # exact $2,400 league pool rather than leaving a rounding discrepancy.
    rostered = ranked[:rostered_players]
    rounded = [math.floor(float(player["auction_value"])) for player in rostered]
    remaining_dollars = league_budget - sum(rounded)
    fractional_order = sorted(
        range(len(rostered)),
        key=lambda index: float(rostered[index]["auction_value"]) - rounded[index],
        reverse=True,
    )
    for index, dollar_value in enumerate(rounded):
        rostered[index]["auction_value"] = dollar_value + (1 if index in fractional_order[:remaining_dollars] else 0)
    return ranked


def write_values(players: list[dict[str, object]], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    base_fields = [
        "rostered_rank", "player", "team", "positions", "yahoo_avg_auction_value",
        "auction_value", "z_total",
    ]
    z_fields = [f"z_{name}" for name in ("fg_pct", "ft_pct", *COUNTING_CATEGORIES, "tov")]
    available = set().union(*(player.keys() for player in players))
    fields = [field for field in base_fields + z_fields if field in available]
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for player in players:
            row = dict(player)
            row["z_total"] = round(float(row["z_total"]), 3)
            for field in z_fields:
                if field in row:
                    row[field] = round(float(row[field]), 3)
            writer.writerow(row)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--rostered-players", type=int, default=156)
    parser.add_argument("--league-budget", type=int, default=2400)
    args = parser.parse_args()
    players = value_players(read_players(args.input), args.rostered_players, args.league_budget)
    write_values(players, args.output)
    print(f"Wrote {args.output} ({args.rostered_players} rostered players; ${args.league_budget} pool).")


if __name__ == "__main__":
    main()
