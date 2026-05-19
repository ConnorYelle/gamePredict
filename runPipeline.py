#!/usr/bin/env python3
"""
MLB Game Prediction Pipeline Orchestrator
Unified script that runs: Stats Collection → Game Fetching → C++ Prediction Engine
"""

import subprocess
import os
import sys
import json
from datetime import datetime
from pathlib import Path

class PredictionPipeline:
    def __init__(self):
        self.root_dir = Path(__file__).parent
        self.data_dir = self.root_dir / "rawData"
        self.stats_dir = self.data_dir / datetime.now().strftime("%m-%d-%y")
        self.cpp_executable = self.root_dir / "main.exe"
        
    def log(self, message: str, level: str = "INFO"):
        """Log with timestamp"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        prefix = f"[{timestamp}] [{level}]"
        print(f"{prefix} {message}")
    
    def run_command(self, command: list, description: str) -> bool:
        """Run a command and return success status"""
        self.log(f"[RUNNING] {description}", "STEP")
        try:
            result = subprocess.run(command, cwd=str(self.root_dir), check=True)
            self.log(f"[OK] {description} completed", "SUCCESS")
            return True
        except subprocess.CalledProcessError as e:
            self.log(f"[FAILED] {description} failed with code {e.returncode}", "ERROR")
            return False
        except FileNotFoundError as e:
            self.log(f"[FAILED] Command not found: {e}", "ERROR")
            return False
    
    def step_1_collect_statistics(self) -> bool:
        """Step 1: Run stats collector"""
        self.log("=" * 60)
        self.log("STEP 1: COLLECTING BASEBALL STATISTICS", "SECTION")
        self.log("=" * 60)
        
        # Create stats directory
        self.stats_dir.mkdir(parents=True, exist_ok=True)
        os.chdir(str(self.root_dir))
        
        success = self.run_command(
            [sys.executable, "statsCollector.py"],
            "Fetching team batting, pitching, and fielding statistics"
        )
        
        if success:
            # Move CSV files to dated stats directory
            csv_files = ['team_batting_stats.csv', 'team_pitching_stats.csv', 'team_fielding_stats.csv']
            for csv_file in csv_files:
                src = self.root_dir / csv_file
                dst = self.stats_dir / csv_file
                if src.exists():
                    src.rename(dst)
                    self.log(f"Moved {csv_file} to {self.stats_dir}", "INFO")
        
        return success
    
    def step_2_fetch_games(self) -> bool:
        """Step 2: Run schedule fetcher"""
        self.log("")
        self.log("=" * 60)
        self.log("STEP 2: FETCHING TODAY'S GAMES", "SECTION")
        self.log("=" * 60)
        
        success = self.run_command(
            [sys.executable, "scheduleFetcher.py"],
            "Fetching today's MLB schedule"
        )
        
        if success and Path("games.txt").exists():
            with open("games.txt", 'r') as f:
                games = f.readlines()
            self.log(f"Found {len(games)} games", "INFO")
        
        return success
    
    def step_3_enhance_team_data(self) -> bool:
        """Step 3: Enhance Team.h with advanced metrics"""
        self.log("")
        self.log("=" * 60)
        self.log("STEP 3: ENHANCING TEAM DATA", "SECTION")
        self.log("=" * 60)
        
        try:
            # Convert CSV stats to Team objects by reading CSVs
            self.log("Loading advanced statistics into Team format", "INFO")
            
            # Create advanced stats JSON for C++ to use
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
            
            # Save to JSON for C++ to consume
            stats_config = self.root_dir / "stats_config.json"
            with open(stats_config, 'w') as f:
                json.dump(advanced_stats, f, indent=2)
            
            self.log(f"[OK] Created stats configuration", "SUCCESS")
            return True
        except Exception as e:
            self.log(f"[FAILED] Error enhancing team data: {e}", "ERROR")
            return False
    
    def step_4_compile_cpp(self) -> bool:
        """Step 4: Compile C++ code"""
        self.log("")
        self.log("=" * 60)
        self.log("STEP 4: COMPILING C++ PREDICTION ENGINE", "SECTION")
        self.log("=" * 60)
        
        success = self.run_command(
            ["g++.exe", "-fdiagnostics-color=always", "-g", 
             "main.cpp", "GamePredictor.cpp", "-o", "main.exe"],
            "Compiling prediction engine with g++"
        )
        
        if success and self.cpp_executable.exists():
            self.log(f"Executable: {self.cpp_executable}", "INFO")
        
        return success
    
    def step_5_run_predictions(self) -> bool:
        """Step 5: Run C++ predictor"""
        self.log("")
        self.log("=" * 60)
        self.log("STEP 5: GENERATING PREDICTIONS", "SECTION")
        self.log("=" * 60)
        
        if not self.cpp_executable.exists():
            self.log(f"[FAILED] Executable not found: {self.cpp_executable}", "ERROR")
            return False
        
        success = self.run_command(
            [str(self.cpp_executable)],
            "Running prediction engine"
        )
        
        return success
    
    def step_6_generate_report(self) -> bool:
        """Step 6: Generate prediction report"""
        self.log("")
        self.log("=" * 60)
        self.log("STEP 6: GENERATING REPORT", "SECTION")
        self.log("=" * 60)
        
        try:
            # Read predictions if output file exists
            if Path("predictions.txt").exists():
                with open("predictions.txt", 'r') as f:
                    predictions = f.read()
                
                # Create report
                report_file = self.root_dir / f"prediction_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                with open(report_file, 'w') as f:
                    f.write(f"GAME PREDICTION REPORT\n")
                    f.write(f"Generated: {datetime.now().isoformat()}\n")
                    f.write(f"Stats Directory: {self.stats_dir}\n")
                    f.write("=" * 60 + "\n\n")
                    f.write(predictions)
                
                self.log(f"[OK] Report saved to {report_file.name}", "SUCCESS")
                return True
            else:
                self.log("No predictions output file found", "INFO")
                return True
        except Exception as e:
            self.log(f"[FAILED] Error generating report: {e}", "ERROR")
            return False
    
    def run_full_pipeline(self) -> bool:
        """Execute complete pipeline"""
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
        ]
        
        for i, step in enumerate(steps, 1):
            if not step():
                self.log(f"Pipeline failed at step {i}", "ERROR")
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
        self.log(f"Predictions executable: {self.cpp_executable}", "INFO")
        self.log("")
        
        return True


def main():
    """Main entry point"""
    pipeline = PredictionPipeline()
    success = pipeline.run_full_pipeline()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
