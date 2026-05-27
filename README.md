# MLB Game Prediction Engine

A data pipeline that combines baseball-reference scraping, team analytics, and a C++ prediction engine to forecast MLB game outcomes.

## Purpose

The goal of this project is to automatically gather MLB team statistics, fetch the daily schedule, and generate game predictions with probabilities.

It is also intended to support future automation for publishing results as social media posts with captions for Twitter and Instagram.

## Getting Started

### Prerequisites
- Python 3.7 or newer
- G++ compiler available in PATH
- Internet access for data scraping

### Install and run

1. Clone the repository and change into the project folder:
```bash
git clone https://github.com/ConnorYelle/gamePredict.git
cd gamePredict
```

2. Run the full pipeline:
```bash
python runPipeline.py
```

If the pipeline completes successfully, the project will have generated updated team statistics, games, and predictions.

## Pipeline Overview

This project is built as a complete end-to-end pipeline:

1. `statsCollector.py`
   - Scrapes team-level batting, pitching, and fielding data from baseball-reference.
   - Calculates additional analytics such as OPS+, BABIP, ISO, FIP, LOB%, and K/BB ratio.
   - Writes CSV files into `rawData/<date>/`.

2. `scheduleFetcher.py`
   - Scrapes today’s MLB schedule from baseball-reference.
   - Writes matchups into `games.txt` in the format `Home Team | Away Team`.

3. `runPipeline.py`
   - Orchestrates the full process.
   - Runs the stats collector.
   - Runs the schedule fetcher.
   - Compiles the C++ prediction engine.
   - Executes the prediction engine.
   - Optionally saves a generated report.

4. `main.cpp` / `GamePredictor.cpp`
   - Loads configuration from `config.json`.
   - Loads team data from the generated CSV files.
   - Loads game matchups from `games.txt`.
   - Produces win probability predictions for each matchup.

## Project Structure

```
gamePredict/
├── main.cpp                     # C++ entry point
├── GamePredictor.h              # Prediction engine interface
├── GamePredictor.cpp            # Prediction logic and data loading
├── Team.h                       # Team statistics data structure
├── CSVReader.h                  # CSV helper for parsing stats
├── config.json                  # Prediction weighting configuration
├── statsCollector.py            # MLB stats scraper
├── scheduleFetcher.py           # Game schedule scraper
├── runPipeline.py               # Full pipeline orchestrator
├── games.txt                    # Daily matchups
├── rawData/                     # Scraped statistics output
└── tests/                       # Validation tests
```

## Usage

### Run the full pipeline
```bash
python runPipeline.py
```

### Run individual steps

Collect statistics only:
```bash
python statsCollector.py
```

Fetch today’s schedule only:
```bash
python scheduleFetcher.py
```

Compile and run the C++ predictor only:
```bash
g++ -g main.cpp GamePredictor.cpp -o main.exe
./main.exe
```

### Run tests
```bash
g++ tests/scheduleFetcherTest.cpp -o tests/scheduleFetcherTest.exe
./tests/scheduleFetcherTest.exe
```

## Output

After the pipeline runs, the following files are produced:

- `games.txt` — today's matchups
- `rawData/<date>/team_batting_stats.csv`
- `rawData/<date>/team_pitching_stats.csv`
- `rawData/<date>/team_fielding_stats.csv`
- `main.exe` — compiled prediction engine
- Optional prediction report files if enabled by the C++ engine

## How the Prediction Model Works

The predictor compares home and away teams using offensive and defensive ratings.

- Offensive strength is based on batting and power metrics.
- Defensive strength is based on pitching and fielding metrics.
- Home teams receive a small advantage multiplier.

A simple probability model is used:

```text
homeScore = homeTeamRating * homeFieldAdvantage
awayScore = awayTeamRating
probability = homeScore / (homeScore + awayScore)
```

The result is a win probability for the home team.

## Configuration

Update `config.json` if you want to tune the prediction weights:

```json
{
  "weights": {
    "runsPerGameWeight": 0.4,
    "onBasePercentageWeight": 50,
    "sluggingPercentageWeight": 30,
    "offenseWeight": 0.6,
    "defenseWeight": 0.4,
    "homeFieldAdvantage": 1.05
  }
}
```

## Social Media Automation Goal

The long-term objective is to convert the prediction output into social content automatically.

That includes:
- generating short Twitter posts with game predictions and probability summaries
- generating Instagram captions and post text for visual recap slides
- including hashtags, team emojis, and brief insights
- publishing posts automatically through API integrations

This repo currently generates the prediction data and the next step is to add a content generation layer that builds formatted posts from the prediction results.

## Improvement Opportunities

These improvements would make the project stronger:

- Add post generation for Twitter and Instagram from prediction results
- Include player injury and lineup data in the prediction model
- Add weather effects for each ballpark
- Store historical outputs and compare predictions to actual results
- Add a dashboard or REST API for easier access
- Improve schedule scraping reliability with more robust HTML parsing or API usage
- Add unit tests for the C++ prediction logic and CSV parsing

## Notes

- The current project expects stats to be loaded from `rawData/<date>/`.
- `games.txt` must use the format `Home Team | Away Team`.
- The pipeline is intended for batch use and should be run daily for new predictions.

## License

MIT License

## Model validation (latest)
Generated: 2026-05-27 13:51 UTC

- Predictions parsed: 15
- Actual outcomes parsed: 15
- Matched games: 15
- Unmatched games: 0
- Pick accuracy: 86.67%
- Average probability assigned to winners: 51.37%
- Brier score: 0.2369
- Stats directory used: data/rawData\05-13-26
