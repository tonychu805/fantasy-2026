# fantasy-2026

Open-data toolkit for a 12-team Yahoo Fantasy Basketball auction league.

## League rules modelled

- 9-cat H2H: FG%, FT%, 3PM, PTS, REB, AST, STL, BLK, TO (lower is better)
- 12 teams; 13 players per team (10 active + 3 bench)
- $200 auction budget and $1 minimum bid
- Positions: PG, SG, G, SF, PF, F, 2 C, 2 UTIL

## Data inputs

The valuation engine uses player totals or per-game projections containing these columns:

```text
player,fgm,fga,ftm,fta,fg3m,pts,reb,ast,stl,blk,tov
```

Optional columns such as `team`, `gp`, and `positions` are preserved in the output. For an auction board, use a rest-of-season projection export where possible; recent actuals are useful for waiver decisions but are not forecasts.

Add these optional Yahoo-specific columns when available:

```text
positions,yahoo_avg_auction_value
```

`positions` must use Yahoo eligibility (for example `PG,SG`), not a generic NBA depth-chart position. `yahoo_avg_auction_value` is the market price other Yahoo managers are paying; the output retains it beside the model's `auction_value` so you can target players where the two differ.

Suggested public sources:

- NBA Stats' league dashboard includes the complete base-stat columns used here. The [`nba_api` endpoint documentation](https://github.com/swar/nba_api/blob/master/docs/nba_api/stats/endpoints/leaguedashplayerstats.md) lists its fields.
- The NBA's public static [league schedule JSON](https://cdn.nba.com/static/json/staticData/scheduleLeagueV2.json) supplies team game counts for weekly streaming analysis.
- Yahoo's Fantasy Sports API is the canonical source for Yahoo eligibility and league draft results, but requires OAuth. Its [player and draft-result resources](https://sports.yahoo.com/developer/docs/) are appropriate for a personal integration.
- For a current public reference table, Hashtag Basketball exposes positions, Yahoo average auction price, and its model value; its complete export is subscription-gated.

Keep raw downloads in `data/raw/`; they are ignored by Git. Do not commit Yahoo exports containing league-member information.

## Run the auction model

No packages are required.

```bash
python3 -m src.fantasy_2026.valuation \
  --input data/raw/player_projections.csv \
  --output data/processed/auction_values.csv
```

The model first reserves $1 for each of 156 league roster spots, then distributes the remaining $2,244 among above-replacement players according to nine-category z-score value. FG% and FT% use makes/attempts, so high-volume efficiency is rewarded correctly. Auction dollars always sum to the $2,400 league pool.

To inspect a current roster against the player pool:

```bash
python3 -m src.fantasy_2026.roster \
  --players data/raw/player_projections.csv \
  --roster data/raw/my_roster.csv
```

`my_roster.csv` needs one `player` column; names are normalized for matching.

## Simulate the auction room

After adding Yahoo average auction values and positions to the valuation output,
simulate a mixed room of 12 managers:

```bash
python3 -m src.fantasy_2026.simulation \
  --input data/processed/auction_values.csv \
  --output data/processed/simulated_prices.csv \
  --runs 2000
```

The output gives a likely price range (`sim_p25` to `sim_p75`) and the model's
expected surplus versus the simulated median. It enforces your PG/SG/G/SF/PF/F/
2C/2UTIL/3BN roster structure when Yahoo positions are provided. It starts with
transparent, generic opponent styles; after the real draft begins, observed
purchases can replace those assumptions.

## Connect Yahoo securely

The Yahoo connector obtains live Yahoo eligibility, league settings, rosters,
and draft results. Yahoo now reviews new Fantasy API applications; the old
Yahoo Developer Network registration path may not load or grant Fantasy access.

1. Submit the [Yahoo Fantasy API access application](https://sports.yahoo.com/developer/access/).
   Describe this as a personal, non-commercial, read-only 12-team basketball
   league analytics tool; expected users: 1.
2. After Yahoo approves and provisions access, create/register the OAuth client
   as instructed by Yahoo and use an exact redirect URI such as
   `http://localhost:8080/callback`.
3. Export the credentials shown in `.env.example` into your terminal. Do not
   commit credentials or the generated token file.

```bash
cd /home/tonychu/repository/fantasy-2026
export YAHOO_CLIENT_ID='your client id'
export YAHOO_CLIENT_SECRET='your client secret'
export YAHOO_REDIRECT_URI='http://localhost:8080/callback'
export YAHOO_LEAGUE_KEY='your league key'

python3 -m src.fantasy_2026.yahoo authorize
```

Open the printed URL, approve access, copy the `code` query parameter from the
redirect URL, and exchange it:

```bash
python3 -m src.fantasy_2026.yahoo exchange --code 'returned-code'
python3 -m src.fantasy_2026.yahoo download \
  --resource "league/$YAHOO_LEAGUE_KEY/settings" \
  --output data/private/league_settings.json
```

Other useful resources are `league/$YAHOO_LEAGUE_KEY/players;start=0;count=25`
and `league/$YAHOO_LEAGUE_KEY/draftresults`. Downloaded private data and tokens
are excluded from Git.

## Notes

This is a decision aid, not a projection feed. Update the input data before the draft, adjust inflated auction prices manually as the room reveals its strategy, and never use raw FG%/FT% alone.
