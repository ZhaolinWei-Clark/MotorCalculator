"""Phase 10E Part C: replicate the Phase 10D decomposition across designs.

FEMM solve policy
-----------------
A 52-position campaign per design would be four campaigns for a question that a
single rotor position can answer. Phase 10D established the cheaper route and
this script validates it before relying on it:

    lambda_peak = N * k_w_meshed * Phi1_coil_mean
    Ke          = p * lambda_peak / sqrt(2)

every term of which comes from one solved rotor position. On the baseline design
that route is checked against the real 52-position campaign Ke. If it reproduces
it, designs B and C use one solve each.

Nothing here is fitted. The designs were chosen to straddle the pole-arc value
where the flat-top/fundamental conversion changes sign, which is derived from the
definition rather than from any observed agreement.
"""

from __future__ import annotations

import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "motor_calculator"))

from motor_calculator.fea.adapter import _mesh_size_map
from motor_calculator.fea.airgap_probe import (
    build_airgap_probe_script,
    parse_airgap_csv,
    rectangular_to_fundamental_form_factor,
    spatial_harmonics,
    vector_potential_fundamental_flux_per_pole_wb,
)
from motor_calculator.fea.availability import detect_femm
from motor_calculator.fea.case_builder import build_validation_case
from motor_calculator.fea.geometry import build_slice_model
from motor_calculator.fea.meshed_winding import meshed_winding_factor_for_case
from motor_calculator.fea.models import FEAValidationTarget
from motor_calculator.fea.reference_cases import (
    PHASE10A_REFERENCE_MODELLING,
    PHASE10A_REFERENCE_PARAMETERS,
    resolve_self_consistent_winding_factor,
)
from motor_calculator.motor_core.calculations import LegacyGuiMotorModelBridge
from motor_calculator.motor_core.constants import LEGACY_SINE_EMF_FACTOR
from motor_calculator.motor_core.validation import parse_legacy_gui_params

SAMPLES = 4096
OUT = ROOT / "validation_data" / "fea_results" / "phase10e_replication"
WS = ROOT / "work" / "phase10e" / "femm_workspace"
WS10D = ROOT / "work" / "phase10d" / "femm_workspace"

KW_STAR = resolve_self_consistent_winding_factor().value

#: Same winding, same slot/pole combination, three magnetic designs.
#: alpha_p straddles the conversion sign change; design C also thickens the
#: coil and the magnet so the gap ratio moves too.
DESIGNS = (
    ("A_baseline", {"alpha_p": 0.70}),
    ("B_narrow_arc", {"alpha_p": 0.60}),
    ("C_wide_arc_thick_gap", {"alpha_p": 0.85, "h_coil": 8.0, "h_mag": 7.0}),
)


def convention_crossover() -> float:
    """The pole arc where ``(8/pi^2) sin(a pi/2) / a`` equals 1, by bisection."""

    f = lambda a: rectangular_to_fundamental_form_factor(a) - 1.0
    lo, hi = 0.5, 0.99
    for _ in range(200):
        mid = (lo + hi) / 2.0
        if f(lo) * f(mid) <= 0.0:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2.0


def analytical(overrides: dict):
    params = dict(PHASE10A_REFERENCE_PARAMETERS)
    params.update(overrides)
    params["k_w"] = KW_STAR
    bridge = LegacyGuiMotorModelBridge(parse_legacy_gui_params(params))
    result = bridge.run_full_analysis()
    omega_mech = bridge.input_data.mechanical_speed_rpm * 2.0 * math.pi / 60.0
    return bridge, result, result.electrical.back_emf_phase_rms_v / omega_mech


def solve_field(case, tag: str, *, reuse: Path | None = None):
    geom = case.geometry
    model = build_slice_model(
        geom,
        slot_layers=case.winding.slot_layers(),
        mesh_sizes=_mesh_size_map(case),
        symmetry=case.symmetry,
        rotor_angle_mech_deg=0.0,
    )
    half = geom.winding_region_thickness_m / 2.0
    planes = tuple(round(v, 9) for v in np.linspace(0.0, half, 11))
    csv = reuse if reuse is not None else WS / f"{tag}.csv"
    solved_now = False
    if reuse is None:
        WS.mkdir(parents=True, exist_ok=True)
        script = WS / f"{tag}.lua"
        script.write_text(
            build_airgap_probe_script(
                case, model,
                fem_path=str(WS / f"{tag}.fem"),
                output_path=str(csv),
                planes_y_m=planes,
                sample_count=SAMPLES,
            ),
            encoding="utf-8", newline="\n",
        )
        rep = detect_femm()
        done = subprocess.run(
            [str(rep.executable_path), "-lua-script=" + str(script), "-windowhide"],
            cwd=str(WS), capture_output=True, text=True, timeout=1800.0,
            shell=False, check=False,
        )
        if done.returncode != 0 or not csv.is_file():
            raise SystemExit(f"FEMM failed for {tag}: rc={done.returncode} {done.stderr[:300]}")
        solved_now = True

    scans = parse_airgap_csv(
        csv.read_text(encoding="utf-8"),
        span_m=model.modelled_span_m,
        pole_pairs=geom.pole_pairs,
        radial_length_m=model.depth_m,
    )
    coil = [s for s in scans if s.plane_y_m <= half + 1e-12]
    ys = np.array([s.plane_y_m for s in coil])
    phis = np.array([vector_potential_fundamental_flux_per_pole_wb(s) for s in coil])
    phi_mean = float(np.trapezoid(phis, ys) / (ys[-1] - ys[0]))
    mid = spatial_harmonics(coil[0])
    return {
        "phi1_coil_mean_wb": phi_mean,
        "peak_abs_bn_t": mid.peak_t,
        "b1_stator_plane_t": mid.fundamental_amplitude_t,
        "thd": mid.total_harmonic_distortion,
        "solved_now": solved_now,
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    crossover = convention_crossover()
    print(f"=== flat-top/fundamental conversion crossover (derived): alpha_p = {crossover:.6f} ===")
    print(f"    form factor at 0.60 {rectangular_to_fundamental_form_factor(0.60):.6f}")
    print(f"    form factor at 0.70 {rectangular_to_fundamental_form_factor(0.70):.6f}")
    print(f"    form factor at 0.85 {rectangular_to_fundamental_form_factor(0.85):.6f}")
    print()

    rows = []
    solves = 0
    for tag, overrides in DESIGNS:
        bridge, result, ke_an = analytical(overrides)
        mi = bridge.input_data
        case = build_validation_case(
            mi, result,
            target=FEAValidationTarget.NO_LOAD_BACK_EMF,
            modelling=PHASE10A_REFERENCE_MODELLING,
            winding_factor_provenance="phase10e_replication_slot_star",
        )
        kw_mesh = meshed_winding_factor_for_case(case).value
        reuse = WS10D / "airgap_profile.csv" if tag == "A_baseline" else None
        if reuse is not None and not reuse.is_file():
            reuse = None
        field = solve_field(case, tag, reuse=reuse)
        solves += int(field["solved_now"])

        n = float(case.winding.turns_per_phase)
        p = case.geometry.pole_pairs
        lam_peak = n * kw_mesh * field["phi1_coil_mean_wb"]
        ke_fea = p * lam_peak / math.sqrt(2.0)

        phi_flat = result.magnetic.pole_flux_wb
        form = rectangular_to_fundamental_form_factor(mi.pole_arc_coefficient)
        f_kw = kw_mesh / KW_STAR
        f_conv = form
        f_wave = field["phi1_coil_mean_wb"] / (phi_flat * form)
        f_444 = (2.0 * math.pi / math.sqrt(2.0)) / LEGACY_SINE_EMF_FACTOR
        product = f_kw * f_conv * f_wave * f_444
        observed = ke_fea / ke_an

        row = {
            "design": tag,
            "alpha_p": mi.pole_arc_coefficient,
            "coil_thickness_m": mi.coil_height_m,
            "magnet_thickness_m": mi.magnet_thickness_m,
            "effective_gap_m": mi.coil_height_m + 2.0 * mi.air_gap_per_side_m,
            "gap_over_pole_pitch": (mi.coil_height_m + 2.0 * mi.air_gap_per_side_m) / case.geometry.pole_pitch_m,
            "turns_per_phase": n,
            "winding_factor_ideal_slot_star": KW_STAR,
            "winding_factor_meshed_geometry": kw_mesh,
            "analytical_peak_b_t": result.magnetic.air_gap_flux_density_peak_t,
            "femm_peak_abs_bn_t": field["peak_abs_bn_t"],
            "peak_b_agreement_percent": (field["peak_abs_bn_t"] / result.magnetic.air_gap_flux_density_peak_t - 1.0) * 100.0,
            "femm_thd": field["thd"],
            "analytical_flat_top_flux_wb": phi_flat,
            "femm_direct_fundamental_flux_wb": field["phi1_coil_mean_wb"],
            "ke_analytical": ke_an,
            "ke_femm_field_route": ke_fea,
            "ke_residual_percent": (observed - 1.0) * 100.0,
            "budget": {
                "winding_factor": f_kw,
                "convention": f_conv,
                "waveform_and_averaging": f_wave,
                "sine_emf_rounding": f_444,
                "product": product,
                "observed": observed,
                "unresolved_remainder_percent": (product / observed - 1.0) * 100.0,
            },
            "new_femm_solve": field["solved_now"],
        }
        rows.append(row)

        print(f"=== {tag} ===")
        print(f"  alpha_p {row['alpha_p']:.3f}   g_eff {row['effective_gap_m']*1000:.2f} mm   "
              f"h_mag {row['magnet_thickness_m']*1000:.2f} mm   g_eff/tau_p {row['gap_over_pole_pitch']:.4f}")
        print(f"  k_w star {KW_STAR:.6f}   k_w meshed {kw_mesh:.6f}   ratio {f_kw:.6f}")
        print(f"  peak B: analytical {row['analytical_peak_b_t']:.6f} T   FEMM {row['femm_peak_abs_bn_t']:.6f} T"
              f"   agreement {row['peak_b_agreement_percent']:+.4f} %   THD {row['femm_thd']*100:.2f} %")
        print(f"  flux:   flat-top {phi_flat:.6e}   FEMM fundamental {field['phi1_coil_mean_wb']:.6e}")
        print(f"  Ke:     analytical {ke_an:.8f}   FEMM {ke_fea:.8f}   residual {row['ke_residual_percent']:+.4f} %")
        print(f"  budget: kw {(f_kw-1)*100:+.3f} %  conv {(f_conv-1)*100:+.3f} %  "
              f"wave {(f_wave-1)*100:+.3f} %  4.44 {(f_444-1)*100:+.3f} %")
        print(f"          product {(product-1)*100:+.3f} %   observed {(observed-1)*100:+.3f} %   "
              f"remainder {row['budget']['unresolved_remainder_percent']:+.4f} %")
        print()

    # Validate the low-cost Ke route against the real 52-position campaign.
    campaign = json.loads(
        (ROOT / "validation_data" / "fea_results" / "phase10c_self_consistent"
         / "ke_error_decomposition.json").read_text(encoding="utf-8")
    )["ke_fea"]
    baseline_field = rows[0]["ke_femm_field_route"]
    print("=== FEMM solve policy justification ===")
    print(f"  baseline Ke, 52-position campaign   {campaign:.8f}")
    print(f"  baseline Ke, single-solve field     {baseline_field:.8f}")
    print(f"  agreement                           {(baseline_field/campaign-1)*100:+.4f} %")
    print(f"  new FEMM solves this phase          {solves}")

    payload = {
        "schema_version": "phase10e.replication.v1",
        "diagnostic_only": True,
        "calibration_performed": False,
        "convention_crossover_alpha_p": crossover,
        "winding_factor_ideal_slot_star": KW_STAR,
        "ke_route_validation": {
            "campaign_52_position_ke": campaign,
            "single_solve_field_route_ke": baseline_field,
            "agreement_percent": (baseline_field / campaign - 1.0) * 100.0,
        },
        "new_femm_solves": solves,
        "designs": rows,
    }
    (OUT / "phase10e_replication.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8", newline="\n"
    )
    print(f"\n  wrote {(OUT / 'phase10e_replication.json').relative_to(ROOT)}")


if __name__ == "__main__":
    main()
