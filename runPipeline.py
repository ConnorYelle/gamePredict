#!/usr/bin/env python3
"""
MLB Game Prediction Pipeline Orchestrator
Runs statistics collection, schedule scraping, compilation, predictions, reporting, and social post generation.
"""

import subprocess
import os
import sys
import json
import time
from datetime import datetime, timedelta
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
        self.pipeline_start = None
        self.step_times = {}

    def log(self, message: str, level: str = "INFO"):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] [{level}] {message}")

    def log_step_start(self, step_num: int, step_name: str):
        """Log the start of a step with timestamp"""
        start_time = time.time()
        self.step_times[step_num] = {"name": step_name, "start": start_time, "end": None}
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] STEP {step_num}: {step_name}")
        print("-" * 70)
        return start_time

    def log_step_end(self, step_num: int):
        """Log the completion of a step with elapsed time"""
        end_time = time.time()
        if step_num in self.step_times:
            self.step_times[step_num]["end"] = end_time
            elapsed = end_time - self.step_times[step_num]["start"]
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Completed in {elapsed:.2f}s")

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
        self.log_step_start(1, "COLLECTING STATISTICS")

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
            self.log_step_end(1)
            return False

        csv_files = ['team_batting_stats.csv', 'team_pitching_stats.csv', 'team_fielding_stats.csv']
        for csv_file in csv_files:
            src = self.root_dir / csv_file
            dst = self.stats_dir / csv_file
            if src.exists():
                src.replace(dst)

        self.log_step_end(1)
        return True

    def step_2_fetch_games(self) -> bool:
        self.log_step_start(2, "FETCHING GAME SCHEDULE")

        result = self.run_command(
            [sys.executable, "scripts/scheduleFetcher.py"],
            "Fetch today's MLB schedule",
            capture_output=False
        )

        if result.returncode != 0:
            self.log_step_end(2)
            return False

        if self.games_file.exists():
            with self.games_file.open('r', encoding='utf-8') as f:
                lines = [line for line in f if line.strip()]
            self.log(f"Loaded {len(lines)} games", "INFO")

        self.log_step_end(2)
        return True

    def step_collect_pitchers(self) -> bool:
        self.log_step_start(3, "COLLECTING STARTING PITCHERS")

        # Optional: writes StartingPitchers.csv next to the team CSVs so the
        # predictor can factor in the probable starters. Failure is non-fatal;
        # the model falls back to team-only when pitcher data is missing.
        result = self.run_command(
            [sys.executable, "scripts/collect_pitchers.py"],
            "Fetch probable starting pitchers and their stats",
            capture_output=False
        )

        if result.returncode != 0:
            self.log("Starting pitcher collection failed; continuing team-only", "WARN")

        self.log_step_end(3)
        return True

    def step_3_enhance_team_data(self) -> bool:
        self.log_step_start(3, "ENHANCING TEAM DATA")

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
            self.log_step_end(3)
            return True
        except Exception as e:
            self.log(f"Error enhancing team data: {e}", "ERROR")
            self.log_step_end(3)
            return False

    def step_4_compile_cpp(self) -> bool:
        self.log_step_start(4, "COMPILING PREDICTION ENGINE")

        # Compile prediction engine
        result1 = self.run_command(
            ["g++.exe", "-std=c++17", "-fdiagnostics-color=always", "-g", "cpp/main.cpp", "cpp/GamePredictor.cpp", "-o", str(self.cpp_executable)],
            "Compile C++ prediction engine",
            capture_output=True
        )

        # Compile social post generator
        social_exe = self.build_dir / "social_posts.exe"
        result2 = self.run_command(
            ["g++.exe", "-std=c++17", "-fdiagnostics-color=always", "-g", "cpp/social_posts.cpp", "-o", str(social_exe)],
            "Compile C++ social post generator",
            capture_output=True
        )

        self.log_step_end(4)
        return (result1.returncode == 0) and (result2.returncode == 0)

    def step_5_run_predictions(self) -> bool:
        self.log_step_start(5, "RUNNING PREDICTIONS")

        if not self.cpp_executable.exists():
            self.log(f"Executable not found: {self.cpp_executable}", "ERROR")
            self.log_step_end(5)
            return False

        result = self.run_command(
            [str(self.cpp_executable)],
            "Run prediction engine",
            capture_output=True
        )

        if result.returncode != 0:
            self.log_step_end(5)
            return False

        with self.predictions_file.open('w', encoding='utf-8') as f:
            f.write(result.stdout)

        self.log_step_end(5)
        return True

    def step_6_generate_report(self) -> bool:
        self.log_step_start(6, "GENERATING REPORT")

        if not self.predictions_file.exists():
            self.log("No predictions output available", "ERROR")
            self.log_step_end(6)
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

            self.log_step_end(6)
            return True
        except Exception as e:
            self.log(f"Error generating report: {e}", "ERROR")
            self.log_step_end(6)
            return False

    def step_7_generate_social_posts(self) -> bool:
        self.log_step_start(7, "GENERATING SOCIAL POSTS")

        if not self.predictions_file.exists():
            self.log("No prediction output available for social posts", "ERROR")
            self.log_step_end(7)
            return False

        self.social_dir.mkdir(parents=True, exist_ok=True)

        social_exe = self.build_dir / "social_posts.exe"
        if social_exe.exists():
            cmd = [str(social_exe), str(self.predictions_file), str(self.social_dir), str(self.root_dir / "mlb_logos")]
            result = self.run_command(cmd, "Run C++ social post generator", capture_output=True)
            if result.returncode == 0:
                self.log_step_end(7)
                return True
            else:
                self.log("C++ social post generator failed, falling back to Python generator", "WARN")

        # fallback to existing Python generator
        try:
            with self.predictions_file.open('r', encoding='utf-8') as f:
                predictions_text = f.read()

            manager = SocialPostManager(self.social_dir)
            manager.generate_social_posts(predictions_text)
            self.log_step_end(7)
            return True
        except Exception as e:
            self.log(f"Error generating social posts: {e}", "ERROR")
            self.log_step_end(7)
            return False

    def run_full_pipeline(self) -> bool:
        print("\n" + "=" * 70)
        print("MLB GAME PREDICTION PIPELINE")
        print("=" * 70)

        steps = [
            self.step_1_collect_statistics,
            self.step_2_fetch_games,
            self.step_collect_pitchers,
            self.step_3_enhance_team_data,
            self.step_4_compile_cpp,
            self.step_5_run_predictions,
            self.step_6_generate_report,
            self.step_7_generate_social_posts,
        ]

        for index, step in enumerate(steps, 1):
            if not step():
                print("\n" + "=" * 70)
                print(f"PIPELINE FAILED AT STEP {index}")
                print("=" * 70 + "\n")
                return False

        print("\n" + "=" * 70)
        print("PIPELINE COMPLETED SUCCESSFULLY")
        print("=" * 70)
        print(f"\nStats saved to: {self.stats_dir}")
        print(f"Predictions saved to: {self.predictions_file}")
        print(f"Social posts saved to: {self.social_dir}\n")

        return True


def main():
    pipeline = PredictionPipeline()
    success = pipeline.run_full_pipeline()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
