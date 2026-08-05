"""Generate the deterministic Phase 7C blocker-resolution report."""

from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MOTOR_CALCULATOR_ROOT = REPO_ROOT / "motor_calculator"
if str(MOTOR_CALCULATOR_ROOT) not in sys.path:
    sys.path.insert(0, str(MOTOR_CALCULATOR_ROOT))

from validation.phase7c_reconstruction import run_phase7c_reconstruction


def main() -> int:
    result = run_phase7c_reconstruction(REPO_ROOT)
    print("Phase 7C report generated without model or parameter updates.")
    print(f"Cases: {len(result.cases)}")
    print(f"Blocker rows: {len(result.blockers)}")
    print(f"Before: {result.before_counts}")
    print(f"After: {result.after_counts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
