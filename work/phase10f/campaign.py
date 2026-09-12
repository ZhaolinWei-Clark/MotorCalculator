"""Phase 10F: torque and cogging validation campaign.

Same-basis rule
---------------
The production model's ``rated_torque_nm`` is ``P_rated / omega_mech``: a shaft
/ output torque derived from a rated-power *input*, not an output of the
magnetic model. FEMM reports electromagnetic torque. Comparing the two directly
would be the basis error this phase exists to avoid.

The same-basis analytical quantity is built from values the production model
already publishes, without modifying any of them:

    T_em = Kt_rms * I_phase_rms = 3 * E_phase_rms * I_phase_rms / omega_mech

which is the power balance ``P_em = 3 E I`` for a sinusoidal PMSM at ``id = 0``.
That is what the FEMM block-integral torque is compared against.

Solve policy
------------
Torque uses the repository's own sampling policy so all three designs share one
definition. Cogging is swept over one cogging period at three mesh levels,
because a cogging claim is worthless without knowing the numerical floor.
"""

from __future__ import annotations

import dataclasses
import json
import math
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "motor_calculator"))

from motor_calculator.fea.adapter import generate_case_scripts
from motor_calculator.fea.availability import detect_femm
from motor_calculator.fea.case_builder import build_validation_case
from motor_calculator.fea.models import FEAValidationTarget
from motor_calculator.fea.reference_cases import (
    PHASE10A_REFERENCE_MODELLING,
    PHASE10A_REFERENCE_PARAMETERS,
    resolve_self_consistent_winding_factor,
)
from motor_calculator.motor_core.calculations import LegacyGuiMotorModelBridge
from motor_calculator.motor_core.validation import parse_legacy_gui_params

OUT = ROOT / "validation_data" / "fea_results" / "phase10f_torque_cogging"
WS = ROOT / "work" / "phase10f" / "femm_workspace"
KW_STAR = resolve_self_consistent_winding_factor().value

DESIGNS = (
    ("A_baseline", {"alpha_p": 0.70}),
    ("B_narrow_arc", {"alpha_p": 0.60}),
    ("C_wide_arc_thick_gap", {"alpha_p": 0.85, "h_coil": 8.0, "h_mag": 7.0}),
)

#: Mesh tiers as multipliers on every declared mesh size. A cogging signal that
#: scales with the mesh is a discretisation artefact, not a machine property.
MESH_TIERS = (("COARSE", 1.6), ("BASE", 1.0), ("FINE", 0.625))

#: Minimum justified torque sweep, per Part D.
#:
#: The repository's default policy resolves up to electrical harmonic 18, which
#: costs 73 loaded solves per design. Phase 10F asks three questions of the
#: torque waveform: the mean, the peak-to-peak ripple, and the dominant ripple
#: harmonic. For a balanced three-phase machine the ripple is carried by the
#: 6th and 12th electrical harmonics.
#:
#: Sampling one electrical period at N equally spaced points returns a mean that
#: is exact for every harmonic below N -- the aliasing that would fold a
#: harmonic onto DC needs order N or above. N = 25 therefore gives an exact mean
#: through harmonic 24, and resolves the 6th and 12th with 4.2 and 2.1 samples
#: per cycle respectively.
#:
#: Going to 73 buys resolution of harmonics 13 to 18, which are not what this
#: phase is asking about, at three times the solve cost.
TORQUE_SAMPLE_COUNT = 25
TORQUE_SAMPLE_RATIONALE = (
    "one electrical period at 25 equally spaced rotor positions: the mean is "
    "exact for every harmonic below 25, and the 6th and 12th ripple harmonics "
    "are resolved at 4.2 and 2.1 samples per cycle. The repository default of "
    "73 additionally resolves harmonics 13-18, which this phase does not ask "
    "about, at three times the solve cost."
)


def build_case(overrides: dict, target: FEAValidationTarget):
    params = dict(PHASE10A_REFERENCE_PARAMETERS)
    params.update(overrides)
    params["k_w"] = KW_STAR
    bridge = LegacyGuiMotorModelBridge(parse_legacy_gui_params(params))
    analysis = bridge.run_full_analysis()
    case = build_validation_case(
        bridge.input_data, analysis, target=target,
        modelling=PHASE10A_REFERENCE_MODELLING,
        winding_factor_provenance="phase10f_slot_star",
    )
    return bridge, analysis, case


def scale_mesh(case, factor: float):
    policy = case.mesh_policy
    scaled = {}
    for field in dataclasses.fields(policy):
        value = getattr(policy, field.name)
        if field.name.endswith("_size_m") and isinstance(value, (int, float)):
            scaled[field.name] = value * factor
    scaled["name"] = f"{policy.name}_x{factor}"
    return dataclasses.replace(case, mesh_policy=dataclasses.replace(policy, **scaled))


#: Electrical angle of the rotor d-axis at rotor_angle_mech = 0, derived from
#: the no-load flux linkage rather than fitted.
#:
#: At rotor angle 0 the solved no-load linkages are lambda_A = -0.866 * peak,
#: lambda_B = +0.866 * peak and lambda_C ~ 0. A phase links peak flux when the
#: d-axis is on its own axis, so cos(theta_d) = -0.866 with lambda_B positive
#: places the d-axis at 150 electrical degrees from the phase-A axis.
#:
#: The bridge's own default is 0.0, which is why the first campaign produced a
#: mean torque of the wrong sign. That default is a defect; it is documented for
#: Phase 10G rather than patched here, because the fix belongs in the geometry
#: layer that knows where the magnets were placed.
DERIVED_D_AXIS_OFFSET_DEG = 150.0


def run_sweep(case, tag: str, *, alignment_offset_deg: float = 0.0) -> dict:
    """Solve every rotor position and return the force/torque series."""

    workspace = WS / tag
    workspace.mkdir(parents=True, exist_ok=True)
    scripts = generate_case_scripts(
        case, workspace, electrical_alignment_offset_deg=alignment_offset_deg
    )
    executable = detect_femm().executable_path
    started = time.perf_counter()
    for script in scripts:
        done = subprocess.run(
            [str(executable), "-lua-script=" + str(script), "-windowhide"],
            cwd=str(workspace), capture_output=True, text=True,
            timeout=900.0, shell=False, check=False,
        )
        if done.returncode != 0:
            raise SystemExit(f"{tag}: FEMM rc={done.returncode} on {script.name}")
    seconds = time.perf_counter() - started

    csv = workspace / "fea_samples.csv"
    rows = [r for r in csv.read_text(encoding="utf-8").splitlines() if r.strip()]
    header = rows[0].split(",")
    angle_i = header.index("rotor_angle_mech_deg")
    force_i = header.index("circumferential_force_n")
    element_i = header.index("element_count")
    angles, forces, elements = [], [], []
    for row in rows[1:]:
        parts = row.split(",")
        angles.append(float(parts[angle_i]))
        forces.append(float(parts[force_i]))
        elements.append(int(float(parts[element_i])))
    radius = case.geometry.mean_radius_m
    torque = np.array(forces) * radius
    return {
        "angles_mech_deg": angles,
        "torque_nm": torque.tolist(),
        "element_counts": elements,
        "solve_count": len(scripts),
        "seconds": seconds,
        "mean_radius_m": radius,
    }


def harmonics(torque: np.ndarray, *, electrical_periods: float = 1.0) -> dict:
    spectrum = np.fft.rfft(torque)
    amplitude = np.abs(spectrum) * 2.0 / torque.size
    orders = {}
    for order in (6, 12, 18, 24):
        index = int(round(order * electrical_periods))
        if 0 < index < amplitude.size:
            orders[order] = float(amplitude[index])
    return orders


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    WS.mkdir(parents=True, exist_ok=True)
    total_solves = 0
    payload = {
        "schema_version": "phase10f.torque_cogging.v1",
        "diagnostic_only": True,
        "calibration_performed": False,
        "same_basis_rule": (
            "FEMM electromagnetic torque is compared against "
            "T_em = 3 * E_phase_rms * I_phase_rms / omega_mech, NOT against the "
            "production rated_torque_nm = P_rated / omega_mech, which is a shaft "
            "torque derived from a rated-power input"
        ),
        "torque_sample_count": TORQUE_SAMPLE_COUNT,
        "derived_d_axis_offset_deg": DERIVED_D_AXIS_OFFSET_DEG,
        "ampere_turns_fix_applied": True,
        "torque_sample_rationale": TORQUE_SAMPLE_RATIONALE,
        "designs": [],
        "cogging": [],
    }

    # ------------------------------------------------------------------ torque
    for tag, overrides in DESIGNS:
        bridge, analysis, case = build_case(overrides, FEAValidationTarget.AVERAGE_TORQUE)
        # Part D: reduce the sweep to the minimum that answers this phase's
        # questions, and record why. Nothing else about the case changes.
        case = dataclasses.replace(
            case,
            operating_point=dataclasses.replace(
                case.operating_point,
                rotor_angle_sample_count=TORQUE_SAMPLE_COUNT,
                sampling_rationale=TORQUE_SAMPLE_RATIONALE,
            ),
        )
        case = dataclasses.replace(case, case_id="")
        from motor_calculator.fea.hashing import compute_case_hash
        case = dataclasses.replace(case, case_id=compute_case_hash(case))
        mi = bridge.input_data
        omega = mi.mechanical_speed_rpm * 2.0 * math.pi / 60.0
        e_rms = analysis.electrical.back_emf_phase_rms_v
        i_rms = case.operating_point.phase_current_rms_a
        t_em_analytical = 3.0 * e_rms * i_rms / omega
        t_shaft_production = analysis.performance.rated_torque_nm

        print(f"=== TORQUE {tag} ===", flush=True)
        print(f"  I_phase_rms {i_rms:.6f} A at {case.operating_point.current_angle_electrical_deg} deg elec", flush=True)
        print(f"  E_phase_rms {e_rms:.6f} V   omega_mech {omega:.4f} rad/s", flush=True)
        print(f"  analytical T_em (same basis) {t_em_analytical:.6f} N.m", flush=True)
        print(f"  production rated (shaft)     {t_shaft_production:.6f} N.m", flush=True)
        print(f"  solving {case.operating_point.rotor_angle_sample_count} positions...", flush=True)

        sweep = run_sweep(case, f"torque_{tag}", alignment_offset_deg=DERIVED_D_AXIS_OFFSET_DEG)
        total_solves += sweep["solve_count"]
        torque = np.array(sweep["torque_nm"])
        mean = float(torque.mean())
        ripple_pp = float(np.ptp(torque))
        record = {
            "design": tag,
            "alpha_p": mi.pole_arc_coefficient,
            "phase_current_rms_a": i_rms,
            "current_angle_electrical_deg": case.operating_point.current_angle_electrical_deg,
            "back_emf_phase_rms_v": e_rms,
            "omega_mech_rad_s": omega,
            "analytical_electromagnetic_torque_nm": t_em_analytical,
            "production_rated_shaft_torque_nm": t_shaft_production,
            "femm_mean_torque_nm": mean,
            "femm_min_torque_nm": float(torque.min()),
            "femm_max_torque_nm": float(torque.max()),
            "femm_peak_to_peak_nm": ripple_pp,
            "femm_ripple_percent": float(ripple_pp / abs(mean) * 100.0) if mean else None,
            "residual_percent": float((mean / t_em_analytical - 1.0) * 100.0),
            "harmonics_nm": harmonics(torque),
            "solve_count": sweep["solve_count"],
            "seconds": sweep["seconds"],
            "element_count_min": min(sweep["element_counts"]),
            "element_count_max": max(sweep["element_counts"]),
        }
        payload["designs"].append(record)
        print(f"  FEMM mean {mean:.6f} N.m   residual {record['residual_percent']:+.4f} %"
              f"   ripple {record['femm_ripple_percent']:.3f} %   ({sweep['seconds']:.0f} s)", flush=True)
        print(flush=True)

    # ----------------------------------------------------------------- cogging
    bridge, analysis, base_case = build_case(
        {"alpha_p": 0.70}, FEAValidationTarget.COGGING_TORQUE
    )
    print("=== COGGING (design A, coreless) ===", flush=True)
    print(f"  phase current {base_case.operating_point.phase_current_rms_a} A (PM excitation only)", flush=True)
    print(f"  span {base_case.operating_point.rotor_angle_span_mech_deg} mech deg"
          f" = one cogging period, {base_case.operating_point.rotor_angle_sample_count} samples", flush=True)
    for name, factor in MESH_TIERS:
        case = scale_mesh(base_case, factor)
        sweep = run_sweep(case, f"cogging_{name}")
        total_solves += sweep["solve_count"]
        torque = np.array(sweep["torque_nm"])
        payload["cogging"].append(
            {
                "mesh_tier": name,
                "mesh_scale": factor,
                "phase_current_rms_a": case.operating_point.phase_current_rms_a,
                "span_mech_deg": case.operating_point.rotor_angle_span_mech_deg,
                "sample_count": sweep["solve_count"],
                "max_positive_nm": float(torque.max()),
                "max_negative_nm": float(torque.min()),
                "peak_to_peak_nm": float(np.ptp(torque)),
                "mean_nm": float(torque.mean()),
                "harmonics_nm": harmonics(torque),
                "element_count_min": min(sweep["element_counts"]),
                "element_count_max": max(sweep["element_counts"]),
                "seconds": sweep["seconds"],
            }
        )
        print(f"  {name:7s} x{factor:<6} p-p {np.ptp(torque):.8f} N.m   "
              f"elements {min(sweep['element_counts'])}-{max(sweep['element_counts'])}   "
              f"({sweep['seconds']:.0f} s)", flush=True)

    payload["total_femm_solves"] = total_solves
    (OUT / "phase10f_campaign.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8", newline="\n"
    )
    print(f"\n  total FEMM solves: {total_solves}", flush=True)
    print(f"  wrote {(OUT / 'phase10f_campaign.json').relative_to(ROOT)}", flush=True)


if __name__ == "__main__":
    main()
