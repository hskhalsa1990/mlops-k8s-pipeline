import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "check_metrics.py"


def run(tmp_path, acc, threshold):
    (tmp_path / "metrics.txt").write_text(f"accuracy {acc}\nmacro_f1 0.5\n")
    return subprocess.run(
        [sys.executable, str(SCRIPT)], cwd=tmp_path, capture_output=True,
        env={"MIN_ACCURACY": threshold, "PATH": ""},
    )


def test_passes_above_threshold(tmp_path):
    assert run(tmp_path, "0.9", "0.8").returncode == 0


def test_fails_below_threshold(tmp_path):
    assert run(tmp_path, "0.7", "0.8").returncode == 1
