"""Generate the deterministic Phase 7A pre-calibration baseline report."""

from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MOTOR_CALCULATOR_ROOT = REPO_ROOT / "motor_calculator"
if str(MOTOR_CALCULATOR_ROOT) not in sys.path:
    sys.path.insert(0, str(MOTOR_CALCULATOR_ROOT))

from validation.phase7a_baseline import run_phase7a_accuracy_baseline


def main() -> int:
    result = run_phase7a_accuracy_baseline(repo_root=REPO_ROOT)
    print("Phase 7A baseline generated without parameter updates.")
    print(f"Rows: {len(result.rows)}")
    print(f"Target status counts: {result.target_status_counts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
