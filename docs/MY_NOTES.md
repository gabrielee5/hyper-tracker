# Personal notes

The program is divided into three main sectors: fetcher, analyzer and contrarian.
The data/db and the logs are stored in the main directory (double-check if still true).

## Fetcher - Phase 1

This monitors all the trades being taken live as to gather a bunch of addresses of active traders. Taker/maker option available in config; right now the taker flag is active as it makes more sense and excludes the market makers.

## Analyzer - Phase 2

Takes the addresses gathered in the previous phase and analyzes them one by one in search of the worst traders. An analysis of the trades taken is done to determine if the trader is statisticaly worse then random (a bunch of degens).

> **Correction (2026-09-18):** it does not determine that. The score turned out to
> be a PnL-sign classifier — every trader at `score <= 5` simply lost money, and
> every trader at `score >= 95` made money. The Monte Carlo re-encodes the t-test
> it already ran, and the null (`mean closedPnl = 0`) is wrong for a perp DEX
> where a random trader loses to fees and funding. See `analyzer/README.md`.

Considering that the speed at which the analysis is done for each addresses is way slower then the speed at which the addresses are gathered, there are not that many addresses classified as bad traders. not every address gathered is analysed.

## Contrarian - Phase 3

The traders classified as bad are monitored every x time as to have a sense of their bias. A contrarian signal is received when an extreme is reached. A confidence score is assigned to each pair; it is calculated considering the nunmber of traders (over 30 reaches the maximum and is enough) and the extremity of their bias (if 30 out of 30 traders are long, an extreme short signal is sent).

## Simulator - Phase 4

To do.

Create a simulated portfolio to track the trades based on the signals received to establish the relevance of the thesis.
