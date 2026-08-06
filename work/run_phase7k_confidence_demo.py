"""Print the reproducible synthetic Phase 7K confidence UX scenario."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MOTOR_CALCULATOR_ROOT = REPO_ROOT / "motor_calculator"
for import_root in (REPO_ROOT, MOTOR_CALCULATOR_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from validation.confidence_summary import render_confidence_summary_text
from validation.phase7k_confidence_demo import run_phase7k_confidence_demo


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="phase7k-demo-") as directory:
        result = run_phase7k_confidence_demo(
            REPO_ROOT, Path(directory) / "feedback_records.jsonl"
        )
    print("SYNTHETIC PHASE 7K UX DEMO - not external validation")
    print(render_confidence_summary_text(result.confidence_summary), end="")
    print(f"Demo reference: {result.feedback_record.reference_value:.4f} V")
    print(f"Demo APE: {result.feedback_record.absolute_percentage_error:.6f}%")
    print(f"Envelope position: {result.envelope_comparison.position.value}")
    print("No calibration, upload, or production update was performed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
