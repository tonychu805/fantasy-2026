"""Simple 12-team auction simulations for the configured Yahoo league."""

from __future__ import annotations

import argparse
import csv
import random
import statistics
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path


ROSTER_SIZE = 13
DEFAULT_TEAMS = 12
DEFAULT_BUDGET = 200
MIN_BID = 1
ROSTER_SLOTS = ("PG", "SG", "G", "SF", "PF", "F", "C", "C", "UTIL", "UTIL", "BN", "BN", "BN")


@dataclass(frozen=True)
class Player:
    name: str
    model_value: float
    market_value: float
    positions: frozenset[str]


@dataclass
class Manager:
    style: str
    budget: int = DEFAULT_BUDGET
    players: int = 0
    roster: list[Player] = field(default_factory=list)

    @property
    def open_spots(self) -> int:
        return ROSTER_SIZE - self.players

    @property
    def maximum_bid(self) -> int:
        """Maximum legal bid while retaining $1 for every remaining roster spot."""
        return self.budget - (self.open_spots - 1) * MIN_BID

    def can_add(self, player: Player) -> bool:
        return self.open_spots > 0 and can_fill_roster(self.roster + [player])

    def add(self, player: Player, price: int) -> None:
        self.budget -= price
        self.players += 1
        self.roster.append(player)


# Repeating this mix makes a realistic room without pretending we know each
# league mate's personality before we observe their bids.
STYLES = (
    "balanced", "balanced", "balanced", "stars", "stars", "patient",
    "patient", "patient", "market", "market", "category", "category",
)


def read_pool(path: Path) -> list[Player]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or "player" not in reader.fieldnames:
            raise ValueError("Auction CSV needs a player column.")
        if "auction_value" not in reader.fieldnames:
            raise ValueError("Run valuation.py first; auction_value is required.")
        players = []
        for row in reader:
            if not row["player"].strip():
                continue
            model = float(row["auction_value"] or 0)
            market = float(row.get("yahoo_avg_auction_value") or model)
            positions = frozenset(
                position.strip().upper() for position in (row.get("positions") or "").split(",") if position.strip()
            )
            players.append(Player(row["player"], model, market, positions))
    if len(players) < DEFAULT_TEAMS * ROSTER_SIZE:
        raise ValueError("Need at least 156 players for a 12-team, 13-player simulation.")
    return players


def fits_slot(positions: frozenset[str], slot: str) -> bool:
    """Use Yahoo eligibility, while treating blank eligibility as unknown.

    Blank positions remain permissible so a market-only first run still works;
    a real draft board should always supply Yahoo positions.
    """
    if not positions or slot in {"UTIL", "BN"}:
        return True
    if slot == "G":
        return bool(positions & {"PG", "SG"})
    if slot == "F":
        return bool(positions & {"SF", "PF"})
    return slot in positions


def can_fill_roster(players: list[Player]) -> bool:
    """Check whether the current players can fit the league's slot layout."""
    ordered = sorted(players, key=lambda player: sum(fits_slot(player.positions, slot) for slot in ROSTER_SLOTS))
    assignments: list[Player | None] = [None] * len(ROSTER_SLOTS)

    def assign(player: Player, tried: set[int]) -> bool:
        for index, slot in enumerate(ROSTER_SLOTS):
            if index in tried or not fits_slot(player.positions, slot):
                continue
            tried.add(index)
            if assignments[index] is None or assign(assignments[index], tried):
                assignments[index] = player
                return True
        return False

    return all(assign(player, set()) for player in ordered)


def willingness(player: Player, manager: Manager, rng: random.Random) -> float:
    """A manager's private maximum before their hard budget cap.

    Auction behaviour is intentionally transparent: market cost is the anchor,
    while styles shift demand for elite names or waiting for bargains.
    """
    anchor = 0.65 * player.market_value + 0.35 * player.model_value
    if manager.style == "stars":
        style_bonus = max(0.0, player.market_value - 20) * 0.22 - max(0.0, 12 - player.market_value) * 0.12
    elif manager.style == "patient":
        style_bonus = -max(0.0, player.market_value - 20) * 0.14 + max(0.0, 12 - player.market_value) * 0.12
    elif manager.style == "category":
        # Category builders create a little extra bid variance, which is what
        # matters before their actual build is known.
        style_bonus = rng.uniform(-3.0, 4.0)
    else:
        style_bonus = 0.0
    centers_rostered = sum("C" in rostered.positions for rostered in manager.roster)
    if "C" in player.positions and centers_rostered < 2 and manager.open_spots <= 6:
        style_bonus += 2.5 * (2 - centers_rostered)
    noise = rng.gauss(0, max(1.5, 0.12 * max(anchor, 8)))
    return max(MIN_BID, anchor + style_bonus + noise)


def simulate_once(players: list[Player], rng: random.Random, teams: int = DEFAULT_TEAMS) -> dict[str, int]:
    managers = [Manager(STYLES[index % len(STYLES)]) for index in range(teams)]
    pool = list(players)
    rng.shuffle(pool)
    prices: dict[str, int] = {}

    while pool and any(manager.open_spots for manager in managers):
        player = pool.pop()
        bidders = []
        for index, manager in enumerate(managers):
            if manager.open_spots <= 0 or manager.maximum_bid < MIN_BID or not manager.can_add(player):
                continue
            bid_limit = min(manager.maximum_bid, int(willingness(player, manager, rng)))
            if bid_limit >= MIN_BID:
                bidders.append((bid_limit, rng.random(), index))
        if not bidders:
            continue
        bidders.sort(reverse=True)
        winning_limit, _, winner_index = bidders[0]
        runner_up = bidders[1][0] if len(bidders) > 1 else MIN_BID - 1
        price = min(winning_limit, max(MIN_BID, runner_up + 1))
        winner = managers[winner_index]
        winner.add(player, price)
        prices[player.name] = price
    return prices


def percentile(values: list[int], point: float) -> float:
    values = sorted(values)
    if not values:
        return 0.0
    index = (len(values) - 1) * point
    lower, upper = int(index), min(int(index) + 1, len(values) - 1)
    return values[lower] + (values[upper] - values[lower]) * (index - lower)


def simulate(players: list[Player], runs: int, seed: int) -> list[dict[str, object]]:
    rng = random.Random(seed)
    outcomes: dict[str, list[int]] = defaultdict(list)
    for _ in range(runs):
        for name, price in simulate_once(players, rng).items():
            outcomes[name].append(price)

    result = []
    for player in players:
        prices = outcomes[player.name]
        result.append({
            "player": player.name,
            "positions": ",".join(sorted(player.positions)),
            "model_value": round(player.model_value),
            "yahoo_avg_auction_value": round(player.market_value),
            "sim_median_price": round(statistics.median(prices)) if prices else 0,
            "sim_p25": round(percentile(prices, 0.25)),
            "sim_p75": round(percentile(prices, 0.75)),
            "rostered_pct": round(100 * len(prices) / runs, 1),
        })
    for row in result:
        row["model_minus_sim_median"] = int(row["model_value"]) - int(row["sim_median_price"])
    return sorted(result, key=lambda row: int(row["sim_median_price"]), reverse=True)


def write_results(rows: list[dict[str, object]], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "player", "positions", "model_value", "yahoo_avg_auction_value", "sim_median_price",
        "sim_p25", "sim_p75", "rostered_pct", "model_minus_sim_median",
    ]
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="CSV produced by valuation.py")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--runs", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=2026, help="Makes results reproducible")
    args = parser.parse_args()
    if args.runs < 1:
        raise ValueError("--runs must be at least 1")
    rows = simulate(read_pool(args.input), args.runs, args.seed)
    write_results(rows, args.output)
    print(f"Wrote {args.output} from {args.runs:,} auction simulations.")


if __name__ == "__main__":
    main()
