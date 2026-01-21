# Project Structure

## Main Sections

### Fetcher
Monitors all the trades being made and stores the addresses. It is useful to understand who is actually active at the moment.

```bash
# Terminal 1: Start Phase 1 (Fetcher)
cd fetcher && python3 main.py
```

### Analyzer
Retrieves the traders' account history to process an analysis of the traders 'ability' (does he makes money?). A score is assigned to each
trader based on a monte carlo simulation. [the score system needs to be checked because I am not sure is very effective]

```bash
# Terminal 2: Start Phase 2 (Analyzer)
cd analyzer && python3 main.py 
```

### Contrarin
Fetches the open positions of traders who scored worst and determines their bias. We then what to take the opposite side.

```bash
# Terminal 3: Start Phase 3 (Contrarian)
python3 contrarian/main.py
```

### Simulator
It was meant to simulate the performance of a portfolio that acts on the signal based from 'contrarian'. I later realized that the code is wrong and the simulation is not accurate.
To better simulate the performance I created strat-analyzer.ipynb 

## Add-ons

### Market-makers
It is a copy of analyzer to find market makers active. The only thing that changes from analyzer are the parameters to filter for high volume, high account equity. Market makers may move funds so to track the active ones, this module needs to be started periodically. Of course this needs new address so it must be started parallel with 'Fetcher'.

### Observer
This module was not used much so there are some issues. The idea was to retrieve the traders' data individually and judge them manually. I wanted to verify that the 'Analyzer' module was doing a good job. Haven't used it much tho.


NOTE: All the other folders dont need particular explanation.

## Findings and Observations

My thesis was that the signal would change more drastically when the price was overextended, anticipating an immediate pivot point. This was not the case and I actually recorded only a short signal for the whole duration of the test. The price ended up falling later but I am not sure it is accurate. A new test needs to be done in a while to check if something changes in the signal (or continued monitoring of course).

I monitored more closely btc, eth and sol and I found that the signal was not changing much. Perhaps following smallest asset may have a different result.

I am still convinced that one can find alpha by inverting the trades of bad market paricipants. The biggest flow of this project is the valuation method imo. I think a big change is needed there and a bit more thought.

Overall fun stuff. I will keep this for reference.