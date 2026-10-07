from src.fantasy_2026.valuation import value_players
from src.fantasy_2026.simulation import Player, can_fill_roster, simulate_once


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
