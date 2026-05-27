#!/usr/bin/env python3
"""
MLB Game Prediction Pipeline Orchestrator
Runs statistics collection, schedule scraping, compilation, predictions, reporting, and social post generation.
"""

import subprocess
import os
import sys
import json
from datetime import datetime
from pathlib import Path

from scripts.social_post_generator import SocialPostManager

class PredictionPipeline:
    def __init__(self):
        self.root_dir = Path(__file__).parent
        self.data_dir = self.root_dir / "data" / "rawData"
        self.stats_dir = self.data_dir / datetime.now().strftime("%m-%d-%y")
        self.build_dir = self.root_dir / "build"
        self.cpp_executable = self.build_dir / "main.exe"
        self.outputs_dir = self.root_dir / "outputs"
        self.games_file = self.outputs_dir / "games.txt"
        self.predictions_file = self.outputs_dir / "predictions.txt"
        self.reports_dir = self.outputs_dir / "reports"
        self.social_dir = self.outputs_dir / "social_posts"

    def log(self, message: str, level: str = "INFO"):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] [{level}] {message}")

    def run_command(self, command: list, description: str, capture_output: bool = False) -> subprocess.CompletedProcess:
        self.log(f"Running: {description}", "STEP")
        try:
            result = subprocess.run(
                command,
                cwd=str(self.root_dir),
                check=False,
                capture_output=capture_output,
                text=True
            )
            if result.returncode != 0:
                self.log(f"Command failed: {description}", "ERROR")
                if capture_output:
                    self.log(result.stderr.strip(), "ERROR")
            else:
                self.log(f"Completed: {description}", "SUCCESS")
            return result
        except FileNotFoundError as e:
            self.log(f"Command not found: {e}", "ERROR")
            raise

    def step_1_collect_statistics(self) -> bool:
        self.log("=" * 60)
        self.log("STEP 1: COLLECTING STATS", "SECTION")
        self.log("=" * 60)

        self.stats_dir.mkdir(parents=True, exist_ok=True)
        self.build_dir.mkdir(parents=True, exist_ok=True)
        self.outputs_dir.mkdir(parents=True, exist_ok=True)
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        os.chdir(str(self.root_dir))

        result = self.run_command(
            [sys.executable, "scripts/statsCollector.py"],
            "Fetch team statistics",
            capture_output=False
        )

        if result.returncode != 0:
            return False

        csv_files = ['team_batting_stats.csv', 'team_pitching_stats.csv', 'team_fielding_stats.csv']
        for csv_file in csv_files:
            src = self.root_dir / csv_file
            dst = self.stats_dir / csv_file
            if src.exists():
                src.replace(dst)
                self.log(f"Moved {csv_file} to {dst}", "INFO")

        return True

    def step_2_fetch_games(self) -> bool:
        self.log("")
        self.log("=" * 60)
        self.log("STEP 2: FETCHING GAME SCHEDULE", "SECTION")
        self.log("=" * 60)

        result = self.run_command(
            [sys.executable, "scripts/scheduleFetcher.py"],
            "Fetch today's MLB schedule",
            capture_output=False
        )

        if result.returncode != 0:
            return False

        if self.games_file.exists():
            with self.games_file.open('r', encoding='utf-8') as f:
                lines = [line for line in f if line.strip()]
            self.log(f"Loaded {len(lines)} games", "INFO")

        return True

    def step_3_enhance_team_data(self) -> bool:
        self.log("")
        self.log("=" * 60)
        self.log("STEP 3: ENHANCING TEAM DATA", "SECTION")
        self.log("=" * 60)

        try:
            advanced_stats = {
                "stats_directory": str(self.stats_dir),
                "timestamp": datetime.now().isoformat(),
                "include_advanced_metrics": True,
                "metrics": {
                    "batting": ["OPS+", "ISO", "BABIP"],
                    "pitching": ["K/BB_ratio", "FIP", "LOB%"],
                    "fielding": ["fielding_pct", "double_plays"]
                }
            }
            stats_config = self.root_dir / "stats_config.json"
            with stats_config.open('w', encoding='utf-8') as f:
                json.dump(advanced_stats, f, indent=2)
            self.log("Created stats configuration", "SUCCESS")
            return True
        except Exception as e:
            self.log(f"Error enhancing team data: {e}", "ERROR")
            return False

    def step_4_compile_cpp(self) -> bool:
        self.log("")
        self.log("=" * 60)
        self.log("STEP 4: COMPILING PREDICTION ENGINE", "SECTION")
        self.log("=" * 60)

        result = self.run_command(
            ["g++.exe", "-std=c++17", "-fdiagnostics-color=always", "-g", "cpp/main.cpp", "cpp/GamePredictor.cpp", "-o", str(self.cpp_executable)],
            "Compile C++ prediction engine",
            capture_output=True
        )

        return result.returncode == 0

    def step_5_run_predictions(self) -> bool:
        self.log("")
        self.log("=" * 60)
        self.log("STEP 5: RUNNING PREDICTIONS", "SECTION")
        self.log("=" * 60)

        if not self.cpp_executable.exists():
            self.log(f"Executable not found: {self.cpp_executable}", "ERROR")
            return False

        result = self.run_command(
            [str(self.cpp_executable)],
            "Run prediction engine",
            capture_output=True
        )

        if result.returncode != 0:
            return False

        with self.predictions_file.open('w', encoding='utf-8') as f:
            f.write(result.stdout)

        self.log(f"Saved prediction output to {self.predictions_file.name}", "INFO")
        return True

    def step_6_generate_report(self) -> bool:
        self.log("")
        self.log("=" * 60)
        self.log("STEP 6: GENERATING REPORT", "SECTION")
        self.log("=" * 60)

        if not self.predictions_file.exists():
            self.log("No predictions output available", "ERROR")
            return False

        predictions_file = self.predictions_file

        try:
            with predictions_file.open('r', encoding='utf-8') as f:
                predictions = f.read()

            report_file = self.reports_dir / f"prediction_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            with report_file.open('w', encoding='utf-8') as out:
                out.write("GAME PREDICTION REPORT\n")
                out.write(f"Generated: {datetime.now().isoformat()}\n")
                out.write(f"Stats Directory: {self.stats_dir}\n")
                out.write("=" * 60 + "\n\n")
                out.write(predictions)

            self.log(f"Saved report to {report_file.name}", "SUCCESS")
            return True
        except Exception as e:
            self.log(f"Error generating report: {e}", "ERROR")
            return False

    def step_7_generate_social_posts(self) -> bool:
        self.log("")
        self.log("=" * 60)
        self.log("STEP 7: GENERATING SOCIAL POSTS", "SECTION")
        self.log("=" * 60)

        if not self.predictions_file.exists():
            self.log("No prediction output available for social posts", "ERROR")
            return False

        self.social_dir.mkdir(parents=True, exist_ok=True)

        try:
            with self.predictions_file.open('r', encoding='utf-8') as f:
                predictions_text = f.read()

            manager = SocialPostManager(self.social_dir)
            manager.generate_social_posts(predictions_text)
            self.log("Social posts generated", "SUCCESS")
            return True
        except Exception as e:
            self.log(f"Error generating social posts: {e}", "ERROR")
            return False

    def run_full_pipeline(self) -> bool:
        self.log("")
        self.log("=" * 60)
        self.log("MLB GAME PREDICTION PIPELINE STARTED")
        self.log("=" * 60)
        self.log("")

        steps = [
            self.step_1_collect_statistics,
            self.step_2_fetch_games,
            self.step_3_enhance_team_data,
            self.step_4_compile_cpp,
            self.step_5_run_predictions,
            self.step_6_generate_report,
            self.step_7_generate_social_posts,
        ]

        for index, step in enumerate(steps, 1):
            if not step():
                self.log(f"Pipeline failed at step {index}", "ERROR")
                self.log("")
                self.log("=" * 60)
                self.log("PIPELINE FAILED")
                self.log("=" * 60)
                return False

        self.log("")
        self.log("=" * 60)
        self.log("PIPELINE COMPLETED SUCCESSFULLY")
        self.log("=" * 60)
        self.log("")
        self.log(f"Stats saved to: {self.stats_dir}", "INFO")
        self.log(f"Games file: games.txt", "INFO")
        self.log(f"Prediction output: predictions.txt", "INFO")
        self.log(f"Social posts saved to: {self.social_dir}", "INFO")
        self.log("")

        return True


def main():
    pipeline = PredictionPipeline()
    success = pipeline.run_full_pipeline()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
