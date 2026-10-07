# Data sources

## Historical NBA season totals

The initial historical inputs use [BoxScore Lab's free NBA downloads](https://www.boxscorelab.com/downloads/), specifically player-season-total CSV files for 2023-24, 2024-25, and 2025-26. The publisher releases them under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/); retain attribution when publishing work based on these data.

Raw downloaded data stay in `data/raw/` and are not committed. Run
`python3 -m src.fantasy_2026.boxscorelab` to convert them to the model's stable
historical schema.
