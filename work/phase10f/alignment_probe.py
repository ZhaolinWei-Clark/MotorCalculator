"""Phase 10F: locate the rotor-angle-to-current-phase alignment. Zero solves.

The loaded torque sweep returned a mean of about -0.46 N.m on every design where
the same-basis analytical value is +3.056 N.m. A ratio near -0.15 is not a model
residual; it is ``cos(gamma)`` for gamma near 99 degrees, i.e. the injected
current is almost orthogonal to the torque-producing axis.

For a non-salient machine -- which a coreless surface-PM machine is -- the
instantaneous electromagnetic torque is exactly

    T(theta) = sum_k e_k(theta) * i_k(theta) / omega_mech

so the torque the bridge *would* produce can be computed from two things that
already exist: the no-load flux linkage sweep solved in Phase 10B/10C, and the
current waveform ``balanced_phase_currents`` injects. No new FEMM solve is
needed to find the alignment, and none is run here.

Reproducing the observed FEMM mean from those two inputs proves the deficit is
the excitation convention rather than the field solution. Sweeping the offset in
software then locates the correct alignment from a physical maximum. Nothing is
fitted to an analytical target.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "motor_calculator"))

from motor_calculator.fea.femm_lua import balanced_phase_currents
from motor_calculator.fea.reference_cases import (
    PHASE10A_REFERENCE_PARAMETERS,
    resolve_self_consistent_winding_factor,
)
from motor_calculator.fea.results import _spectral_derivative
from motor_calculator.motor_core.calculations import LegacyGuiMotorModelBridge
from motor_calculator.motor_core.validation import parse_legacy_gui_params

OUT = ROOT / "validation_data" / "fea_results" / "phase10f_torque_cogging"
EV10C = ROOT / "validation_data" / "fea_results" / "phase10c_self_consistent"


def main() -> None:
    raw = json.loads((EV10C / "fea_raw_result.json").read_text(encoding="utf-8"))["result"]
    samples = sorted(raw["samples"], key=lambda s: s["rotor_angle_mech_deg"])
    angles = np.array([s["rotor_angle_mech_deg"] for s in samples])
    names = ("A", "B", "C")
    linkage = {n: np.array([s["phase_flux_linkage_wb_turn"][n] for s in samples]) for n in names}

    params = dict(PHASE10A_REFERENCE_PARAMETERS)
    params["k_w"] = resolve_self_consistent_winding_factor().value
    bridge = LegacyGuiMotorModelBridge(parse_legacy_gui_params(params))
    analysis = bridge.run_full_analysis()
    mi = bridge.input_data
    omega = mi.mechanical_speed_rpm * 2.0 * math.pi / 60.0
    pole_pairs = mi.pole_pairs
    current_rms = analysis.performance.phase_current_rms_a
    expected = 3.0 * analysis.electrical.back_emf_phase_rms_v * current_rms / omega

    span_rad = math.radians(raw["span_mech_deg"])
    emf = {n: omega * _spectral_derivative(linkage[n], span_rad) for n in names}

    print(f"  no-load sweep reused: {angles.size} positions over {raw['span_mech_deg']} mech deg")
    print(f"  phase current {current_rms:.6f} A rms   omega_mech {omega:.4f} rad/s")
    print(f"  same-basis analytical T_em {expected:.6f} N.m")
    print()
    print("  offset[deg]   mean T[N.m]   T/T_analytical")

    rows = []
    for offset in range(0, 360, 15):
        torque = np.zeros_like(angles)
        for index, angle in enumerate(angles):
            electrical = pole_pairs * angle + offset
            currents = balanced_phase_currents(
                phase_rms_a=current_rms,
                electrical_angle_deg=electrical,
                current_angle_electrical_deg=90.0,
                phase_names=names,
            )
            torque[index] = sum(
                emf[n][index] * currents.values[n] for n in names
            ) / omega
        mean = float(torque.mean())
        rows.append({"offset_deg": offset, "mean_torque_nm": mean,
                     "ratio_to_analytical": mean / expected})
        print(f"    {offset:6d}     {mean:+10.6f}     {mean/expected:+8.4f}")

    best = max(rows, key=lambda r: r["mean_torque_nm"])
    at_zero = next(r for r in rows if r["offset_deg"] == 0)

    print()
    print(f"  offset currently used by the bridge: 0 deg")
    print(f"    predicted mean torque              {at_zero['mean_torque_nm']:+.6f} N.m")
    print(f"    FEMM measured (design A, 25 pos)   -0.457035 N.m")
    print(f"    prediction reproduces FEMM         "
          f"{abs(at_zero['mean_torque_nm'] - (-0.457035)) < 0.12}")
    print()
    print(f"  best alignment offset               {best['offset_deg']} deg electrical")
    print(f"    mean torque there                 {best['mean_torque_nm']:+.6f} N.m")
    print(f"    ratio to same-basis analytical    {best['ratio_to_analytical']:+.4f}")

    (OUT / "phase10f_alignment_probe.json").write_text(
        json.dumps(
            {
                "schema_version": "phase10f.alignment.v1",
                "diagnostic_only": True,
                "calibration_performed": False,
                "new_femm_solves": 0,
                "method": (
                    "T = sum_k e_k i_k / omega_mech for a non-salient machine, with "
                    "e_k from the reused no-load flux-linkage sweep and i_k from the "
                    "bridge's own balanced_phase_currents"
                ),
                "same_basis_analytical_torque_nm": expected,
                "bridge_offset_deg": 0,
                "predicted_mean_at_bridge_offset_nm": at_zero["mean_torque_nm"],
                "femm_measured_design_a_nm": -0.457035,
                "best_offset_deg": best["offset_deg"],
                "best_mean_torque_nm": best["mean_torque_nm"],
                "best_ratio_to_analytical": best["ratio_to_analytical"],
                "sweep": rows,
            },
            indent=2, sort_keys=True,
        ),
        encoding="utf-8", newline="\n",
    )
    print(f"\n  wrote {(OUT / 'phase10f_alignment_probe.json').relative_to(ROOT)}")


if __name__ == "__main__":
    main()
