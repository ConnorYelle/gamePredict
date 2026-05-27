import os
import shutil
import subprocess
import unittest
from pathlib import Path


class PipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parent.parent
        cls.build_dir = cls.root / "build"
        cls.main_test_exe = cls.build_dir / "main_test.exe"
        cls.gpp = shutil.which("g++.exe") or shutil.which("g++")
        if cls.gpp is None:
            raise unittest.SkipTest("g++ compiler not found in PATH")

    def test_cpp_prediction_engine_compiles(self):
        self.build_dir.mkdir(parents=True, exist_ok=True)

        result = subprocess.run(
            [
                self.gpp,
                "-std=c++17",
                "-g",
                str(self.root / "cpp" / "main.cpp"),
                str(self.root / "cpp" / "GamePredictor.cpp"),
                "-o",
                str(self.main_test_exe),
            ],
            cwd=self.root,
            capture_output=True,
            text=True,
        )

        self.assertEqual(
            result.returncode,
            0,
            msg=(
                "C++ prediction engine failed to compile. "
                f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
            ),
        )

    def test_cpp_prediction_engine_runs(self):
        if not self.main_test_exe.exists():
            self.skipTest("Compiled prediction engine is not available")

        games_file = self.root / "outputs" / "games.txt"
        self.assertTrue(games_file.exists(), "Existing outputs/games.txt is required for this test")

        result = subprocess.run(
            [str(self.main_test_exe)],
            cwd=self.root,
            capture_output=True,
            text=True,
        )

        self.assertEqual(
            result.returncode,
            0,
            msg=(
                "Prediction engine failed at runtime. "
                f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
            ),
        )
        self.assertIn("=== Game Predictions ===", result.stdout)
        self.assertGreater(result.stdout.count("Favorite:"), 0)
