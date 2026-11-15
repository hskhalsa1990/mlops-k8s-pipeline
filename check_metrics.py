"""Quality gate: exit non-zero if accuracy in metrics.txt is below the threshold."""
import os
import sys
from pathlib import Path


def main() -> int:
    threshold = float(os.getenv("MIN_ACCURACY", "0.80"))
    metrics = dict(
        line.split() for line in Path("metrics.txt").read_text().splitlines() if line.strip()
    )
    accuracy = float(metrics["accuracy"])
    print(f"accuracy={accuracy:.4f} threshold={threshold:.2f}")
    if accuracy < threshold:
        print("FAILED: accuracy below threshold", file=sys.stderr)
        return 1
    print("PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
