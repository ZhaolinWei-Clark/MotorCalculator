"""Phase 10G Step 17: minimal loaded torque recheck with the derived alignment.

One design, one electrical period. Phase 10F needed a hard-coded 150 degree
offset to obtain a positive torque; this passes no offset argument at all.
"""

from __future__ import annotations

import dataclasses
import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "motor_calculator"))

from motor_calculator.fea.adapter import generate_case_scripts
from motor_calculator.fea.availability import detect_femm
from motor_calculator.fea.hashing import compute_case_hash
from motor_calculator.fea.models import FEAValidationTarget
from motor_calculator.fea.reference_cases import (
    PHASE10A_REFERENCE_PARAMETERS,
    build_self_consistent_reference_case,
    resolve_self_consistent_winding_factor,
)
from motor_calculator.motor_core.calculations import LegacyGuiMotorModelBridge
from motor_calculator.motor_core.validation import parse_legacy_gui_params
from motor_calculator.winding.electrical_axis import electrical_axes_for_case

OUT = ROOT / "validation_data" / "fea_results" / "phase10g_winding"
WS = ROOT / "work" / "phase10g" / "femm_workspace"


def main() -> None:
    params = dict(PHASE10A_REFERENCE_PARAMETERS)
    params["k_w"] = resolve_self_consistent_winding_factor().value
    bridge = LegacyGuiMotorModelBridge(parse_legacy_gui_params(params))
    analysis = bridge.run_full_analysis()

    case = build_self_consistent_reference_case(FEAValidationTarget.AVERAGE_TORQUE)
    case = dataclasses.replace(
        case,
        operating_point=dataclasses.replace(
            case.operating_point,
            rotor_angle_sample_count=25,
            sampling_rationale=(
                "Phase 10G minimal recheck: 25 positions, mean exact below harmonic 25"
            ),
        ),
    )
    case = dataclasses.replace(case, case_id="")
    case = dataclasses.replace(case, case_id=compute_case_hash(case))

    omega = bridge.input_data.mechanical_speed_rpm * 2.0 * math.pi / 60.0
    expected = (
        3.0
        * analysis.electrical.back_emf_phase_rms_v
        * case.operating_point.phase_current_rms_a
        / omega
    )
    axes = electrical_axes_for_case(case, rotor_angle_mech_deg=0.0)
    print(f"  derived d-axis from phase A at theta_m=0: {axes.d_axis_from_phase_a_elec_deg:.4f} deg", flush=True)
    print(f"  same-basis analytical T_em: {expected:.6f} N.m", flush=True)
    print(f"  solving {case.operating_point.rotor_angle_sample_count} positions, NO offset argument", flush=True)

    workspace = WS / "recheck"
    workspace.mkdir(parents=True, exist_ok=True)
    scripts = generate_case_scripts(case, workspace)
    executable = detect_femm().executable_path
    for script in scripts:
        done = subprocess.run(
            [str(executable), "-lua-script=" + str(script), "-windowhide"],
            cwd=str(workspace), capture_output=True, text=True,
            timeout=900.0, shell=False, check=False,
        )
        if done.returncode != 0:
            raise SystemExit(f"FEMM rc={done.returncode} on {script.name}")

    rows = [r.split(",") for r in (workspace / "fea_samples.csv").read_text().splitlines() if r.strip()]
    force_index = rows[0].index("circumferential_force_n")
    torque = np.array([float(r[force_index]) for r in rows[1:]]) * case.geometry.mean_radius_m
    mean = float(torque.mean())
    residual = (mean / expected - 1.0) * 100.0
    ripple = float(np.ptp(torque) / abs(mean) * 100.0)

    print(f"  FEMM mean torque {mean:+.6f} N.m   residual {residual:+.4f} %   ripple {ripple:.3f} %", flush=True)
    print(f"  positive iq gives positive torque: {mean > 0}", flush=True)

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "phase10g_torque_recheck.json").write_text(
        json.dumps(
            {
                "schema_version": "phase10g.torque_recheck.v1",
                "diagnostic_only": True,
                "calibration_performed": False,
                "hard_coded_offset_used": False,
                "derived_d_axis_from_phase_a_deg": axes.d_axis_from_phase_a_elec_deg,
                "analytical_electromagnetic_torque_nm": expected,
                "femm_mean_torque_nm": mean,
                "residual_percent": residual,
                "ripple_percent": ripple,
                "positive_iq_gives_positive_torque": bool(mean > 0),
                "solves": len(scripts),
            },
            indent=2, sort_keys=True,
        ),
        encoding="utf-8", newline="\n",
    )
    print(f"  wrote {(OUT / 'phase10g_torque_recheck.json').relative_to(ROOT)}", flush=True)


if __name__ == "__main__":
    main()
