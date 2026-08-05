"""Generate the deterministic Phase 7B.1 external AFPM metric report."""

from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MOTOR_CALCULATOR_ROOT = REPO_ROOT / "motor_calculator"
if str(MOTOR_CALCULATOR_ROOT) not in sys.path:
    sys.path.insert(0, str(MOTOR_CALCULATOR_ROOT))

from validation.phase7b1_campaign import run_phase7b1_campaign


def main() -> int:
    result = run_phase7b1_campaign(REPO_ROOT)
    print("Phase 7B.1 report generated without model or parameter updates.")
    print(f"Rows: {len(result.rows)}")
    print(f"Comparability: {result.comparability_counts}")
    print(f"Outcomes: {result.outcome_counts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
