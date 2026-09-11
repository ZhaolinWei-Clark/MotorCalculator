"""Phase 10D Step 2: reproduce and freeze the Phase 10C baseline.

Diagnostic only. Reads production values; changes nothing.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "motor_calculator"))

from motor_calculator.fea.reference_cases import (
    PHASE10A_REFERENCE_PARAMETERS,
    resolve_self_consistent_winding_factor,
)
from motor_core import legacy_params_to_model_input, MotorAnalysisEngine
from motor_calculator.motor_core.constants import LEGACY_SINE_EMF_FACTOR, MU0, SLOT_TYPES

EV = ROOT / "validation_data" / "fea_results" / "phase10c_self_consistent"


def main() -> None:
    dec = json.loads((EV / "ke_error_decomposition.json").read_text(encoding="utf-8"))

    params = dict(PHASE10A_REFERENCE_PARAMETERS)
    kw_geom = resolve_self_consistent_winding_factor()
    kw_geom = kw_geom.value

    # Self-consistent analytical run: geometry winding factor, everything else stock.
    params_sc = dict(params)
    params_sc["k_w"] = kw_geom
    mi = legacy_params_to_model_input(params_sc)
    res = MotorAnalysisEngine(mi).run_full_analysis()
    mag = res.magnetic

    print("=== PHASE 10D BASELINE (reproduced from source) ===")
    print(f"  winding factor (geometry)      {kw_geom!r}")
    print(f"  analytical pole flux    [Wb]   {mag.pole_flux_wb!r}")
    print(f"  evidence  pole flux     [Wb]   {dec['analytical_flux_per_pole_wb']!r}")
    print(f"  reproduces evidence            {math.isclose(mag.pole_flux_wb, dec['analytical_flux_per_pole_wb'], rel_tol=1e-12)}")
    print(f"  analytical B_g peak     [T]    {mag.air_gap_flux_density_peak_t!r}")
    print()

    ke_sc = res.electrical.back_emf_phase_rms_v / (mi.mechanical_speed_rpm * 2.0 * math.pi / 60.0)
    print(f"  analytical Ke self-consistent  {ke_sc!r}")
    print(f"  evidence  Ke self-consistent   {dec['ke_analytical_self_consistent']!r}")
    print(f"  reproduces evidence            {math.isclose(ke_sc, dec['ke_analytical_self_consistent'], rel_tol=1e-9)}")
    print(f"  FEMM Ke                        {dec['ke_fea']!r}")
    print(f"  Ke residual  FEA vs analytical {dec['self_consistent_ke_error_percent']:.6f} %")
    print()
    print(f"  FEA fundamental-equiv flux[Wb] {dec['fea_equivalent_flux_per_pole_wb']!r}")
    print(f"  flux residual FEA vs analyt.   {dec['flux_residual_fea_vs_analytical_percent']:.6f} %")
    print(f"  mesh sensitivity               {dec['mesh_sensitivity_percent']:.6f} %")
    print()

    # ---- analytical magnetic-circuit intermediates, recomputed transparently ----
    i = mi
    g_eff = i.coil_height_m + 2.0 * i.air_gap_per_side_m
    tau_p_L = (math.pi / (2.0 * i.pole_pairs)) * ((i.outer_diameter_m / 2.0) ** 2 - (i.inner_diameter_m / 2.0) ** 2)
    a_pole = tau_p_L * i.pole_arc_coefficient
    carter = SLOT_TYPES.get(i.slot_type, {"carter_factor": 1.0})["carter_factor"]
    r_gap = (g_eff * carter) / (MU0 * a_pole)
    r_mag = (2.0 * i.magnet_thickness_m) / (MU0 * i.magnet_relative_permeability * a_pole)
    mmf = 2.0 * (i.remanence_t / MU0) * i.magnet_thickness_m / i.magnet_relative_permeability
    phi = mmf / (r_gap + i.leakage_factor * r_mag)

    print("=== ANALYTICAL MAGNETIC CIRCUIT INTERMEDIATES ===")
    print(f"  effective gap g_eff = h_coil + 2g   {g_eff!r} m")
    print(f"  tau_p * L (full pole-pitch area)    {tau_p_L!r} m^2")
    print(f"  A_pole = tau_p*L*alpha_p            {a_pole!r} m^2")
    print(f"  pole_arc_coefficient alpha_p        {i.pole_arc_coefficient!r}")
    print(f"  carter factor (slot_type={i.slot_type!r}) {carter!r}")
    print(f"  leakage factor sigma_m              {i.leakage_factor!r}")
    print(f"  magnet mu_r                         {i.magnet_relative_permeability!r}")
    print(f"  Br                                  {i.remanence_t!r} T")
    print(f"  R_gap  [A/Wb]                       {r_gap!r}")
    print(f"  R_mag  [A/Wb]                       {r_mag!r}")
    print(f"  sigma_m * R_mag                     {i.leakage_factor * r_mag!r}")
    print(f"  MMF    [A]                          {mmf!r}")
    print(f"  Phi_pole [Wb] (recomputed)          {phi!r}")
    print(f"  matches engine                      {math.isclose(phi, mag.pole_flux_wb, rel_tol=1e-12)}")
    print()
    print(f"  reluctance split: gap {r_gap/(r_gap+i.leakage_factor*r_mag)*100:.3f} %  magnet {i.leakage_factor*r_mag/(r_gap+i.leakage_factor*r_mag)*100:.3f} %")
    print()

    # ---- the convention question, stated as arithmetic ----
    alpha = i.pole_arc_coefficient
    form = (8.0 / math.pi**2) * math.sin(alpha * math.pi / 2.0) / alpha
    print("=== RECTANGULAR vs FUNDAMENTAL FLUX CONVENTION ===")
    print("  Phi_analytical = B_peak * A_pole      (flat top over the magnet arc)")
    print("  Phi_fundamental = (8/pi^2)*B_peak*tau_p*L*sin(alpha_p*pi/2)")
    print(f"  ratio Phi_1/Phi_tot = (8/pi^2)*sin(alpha*pi/2)/alpha = {form!r}")
    print(f"  i.e. a fundamental-basis analytical flux would be {(form-1)*100:+.4f} % higher")

    out = {
        "schema_version": "phase10d.baseline.v1",
        "source_case_id": dec["case_id"],
        "analytical_winding_factor": kw_geom,
        "analytical_pole_flux_wb": mag.pole_flux_wb,
        "analytical_b_gap_peak_t": mag.air_gap_flux_density_peak_t,
        "analytical_ke_self_consistent": ke_sc,
        "fea_ke": dec["ke_fea"],
        "fea_equivalent_flux_per_pole_wb": dec["fea_equivalent_flux_per_pole_wb"],
        "ke_residual_fea_vs_analytical_percent": dec["self_consistent_ke_error_percent"],
        "flux_residual_fea_vs_analytical_percent": dec["flux_residual_fea_vs_analytical_percent"],
        "mesh_sensitivity_percent": dec["mesh_sensitivity_percent"],
        "effective_gap_m": g_eff,
        "pole_pitch_times_radial_length_m2": tau_p_L,
        "pole_area_m2": a_pole,
        "pole_arc_coefficient": alpha,
        "carter_factor": carter,
        "leakage_factor": i.leakage_factor,
        "magnet_relative_permeability": i.magnet_relative_permeability,
        "remanence_t": i.remanence_t,
        "reluctance_gap_a_per_wb": r_gap,
        "reluctance_magnet_a_per_wb": r_mag,
        "mmf_a": mmf,
        "rectangular_to_fundamental_form_factor": form,
        "legacy_sine_emf_factor": LEGACY_SINE_EMF_FACTOR,
        "exact_sine_emf_factor": 2.0 * math.pi / math.sqrt(2.0),
    }
    dest = ROOT / "validation_data" / "fea_results" / "phase10d_flux_diagnosis"
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "phase10d_baseline.json").write_text(
        json.dumps(out, indent=2, sort_keys=True), encoding="utf-8", newline="\n"
    )
    print(f"\n  wrote {(dest / 'phase10d_baseline.json').relative_to(ROOT)}")


if __name__ == "__main__":
    main()
