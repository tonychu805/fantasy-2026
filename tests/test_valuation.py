from src.fantasy_2026.valuation import value_players
from src.fantasy_2026.simulation import Player, can_fill_roster, simulate_once
from src.fantasy_2026.projections import project


def player(name, **stats):
    defaults = dict(fgm=5, fga=10, ftm=3, fta=4, fg3m=1, pts=14, reb=5, ast=3, stl=1, blk=0.5, tov=2)
    defaults.update(stats)
    return {"player": name, **defaults}


def test_values_sum_to_league_budget_and_turnovers_are_inverse():
    players = [player("Careful", tov=1), player("Careless", tov=5), player("Middle", tov=3)]
    valued = value_players(players, rostered_players=3, league_budget=30, minimum_bid=1)
    by_name = {entry["player"]: entry for entry in valued}
    assert by_name["Careful"]["z_tov"] > by_name["Careless"]["z_tov"]
    assert round(sum(entry["auction_value"] for entry in valued)) == 30


def test_auction_prices_never_exceed_the_legal_pool():
    import random

    players = [Player(f"Player {index}", 10, 10, frozenset()) for index in range(156)]
    prices = simulate_once(players, random.Random(7))
    assert len(prices) == 156
    assert sum(prices.values()) <= 12 * 200
    assert min(prices.values()) >= 1


def test_roster_needs_two_eligible_centers():
    wings = [Player(f"Wing {index}", 1, 1, frozenset({"PG", "SG", "SF", "PF"})) for index in range(13)]
    centers = [Player(f"Center {index}", 1, 1, frozenset({"C"})) for index in range(2)]
    assert not can_fill_roster(wings)
    assert can_fill_roster(wings[:11] + centers)


def test_projection_weights_recent_season_and_separates_minutes():
    history = [
        {"player": "Example", "season": "2025-26", "gp": 70.0, "min": 2100.0, "fgm": 350.0, "fga": 700.0, "ftm": 100.0, "fta": 125.0, "fg3m": 100.0, "pts": 900.0, "reb": 300.0, "ast": 200.0, "stl": 70.0, "blk": 30.0, "tov": 100.0},
        {"player": "Example", "season": "2024-25", "gp": 60.0, "min": 1200.0, "fgm": 100.0, "fga": 250.0, "ftm": 50.0, "fta": 65.0, "fg3m": 40.0, "pts": 300.0, "reb": 150.0, "ast": 80.0, "stl": 30.0, "blk": 20.0, "tov": 50.0},
    ]
    row = project(history, "2026-27")[0]
    assert row["projected_gp"] == 66.8
    assert row["projected_mpg"] > 25
