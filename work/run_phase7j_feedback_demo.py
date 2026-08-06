"""Run the synthetic Phase 7J local-feedback demonstration."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MOTOR_CALCULATOR_ROOT = REPO_ROOT / "motor_calculator"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(MOTOR_CALCULATOR_ROOT) not in sys.path:
    sys.path.insert(0, str(MOTOR_CALCULATOR_ROOT))

from validation.phase7j_feedback_demo import run_phase7j_demo


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="phase7j-demo-") as directory:
        result = run_phase7j_demo(REPO_ROOT, Path(directory) / "feedback_records.jsonl")
    record = result.submission_result.record
    print("SYNTHETIC DEMO ONLY - not a real bench measurement")
    print(f"compatibility={record.comparability.value}")
    print(f"evidence_quality={record.evidence_quality.value}")
    print(f"absolute_error={record.absolute_error:.6f} {record.unit}")
    print(f"absolute_percentage_error={record.absolute_percentage_error:.6f}%")
    print(f"envelope_position={result.envelope_comparison.position.value}")
    print(f"validation_coverage={result.summary.validation_coverage.value}")
    print(f"bias={result.aggregate.bias_candidate.status.value}")
    print("No parameter or model update was performed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
