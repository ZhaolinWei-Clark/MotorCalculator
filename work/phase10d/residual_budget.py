"""Phase 10D Steps 4, 8, 9, 10, 12, 13: analytical-side diagnostics and budget.

Every case here is DIAGNOSTIC_ONLY. Nothing writes a production default, nothing
is stored as a correction factor, and no coefficient is chosen because it makes
the FEMM difference smaller. Each diagnostic re-evaluates the published
magnetic-circuit equation with one input replaced, in a local copy, and reports
what happens.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "motor_calculator"))

from motor_calculator.fea.airgap_probe import rectangular_to_fundamental_form_factor
from motor_calculator.motor_core.constants import LEGACY_SINE_EMF_FACTOR, MU0

OUT = ROOT / "validation_data" / "fea_results" / "phase10d_flux_diagnosis"


def pole_flux(
    *,
    g_eff: float,
    tau_p_l: float,
    alpha_p: float,
    carter: float,
    leakage: float,
    mu_r: float,
    h_m: float,
    br: float,
) -> float:
    """The published magnetic-circuit equation, re-evaluated locally.

    This is a transcription of ``calculate_magnetic_circuit`` so that one input
    at a time can be varied without touching the protected production module.
    Its agreement with the engine is asserted before any diagnostic is trusted.
    """

    a_pole = tau_p_l * alpha_p
    r_gap = (g_eff * carter) / (MU0 * a_pole)
    r_mag = (2.0 * h_m) / (MU0 * mu_r * a_pole)
    mmf = 2.0 * (br / MU0) * h_m / mu_r
    return mmf / (r_gap + leakage * r_mag)


def main() -> None:
    base = json.loads((OUT / "phase10d_baseline.json").read_text(encoding="utf-8"))
    prof = json.loads((OUT / "phase10d_airgap_axial_profile.json").read_text(encoding="utf-8"))
    kwt = json.loads((OUT / "phase10d_winding_factor_truth.json").read_text(encoding="utf-8"))

    ref = dict(
        g_eff=base["effective_gap_m"],
        tau_p_l=base["pole_pitch_times_radial_length_m2"],
        alpha_p=base["pole_arc_coefficient"],
        carter=base["carter_factor"],
        leakage=base["leakage_factor"],
        mu_r=base["magnet_relative_permeability"],
        h_m=0.005,
        br=base["remanence_t"],
    )
    phi0 = pole_flux(**ref)
    assert math.isclose(phi0, base["analytical_pole_flux_wb"], rel_tol=1e-12), "local transcription must match the engine"
    print(f"  local transcription matches the production engine: {phi0:.12e} Wb")

    phi_fea = prof["coil_thickness_mean_phi1_wb"]
    ke_res = base["ke_residual_fea_vs_analytical_percent"]
    print(f"  FEA fundamental flux the winding links             {phi_fea:.9e} Wb")
    print(f"  observed Ke residual (FEA vs analytical)           {ke_res:+.4f} %")
    print()

    def show(label: str, phi: float, note: str = "") -> dict:
        d_flux = (phi / phi0 - 1.0) * 100.0
        fea_vs = (phi_fea / phi - 1.0) * 100.0
        print(f"  {label:<46s} {phi:.6e}  flux {d_flux:+7.3f} %   FEA-vs-analytical {fea_vs:+7.3f} %  {note}")
        return {"label": label, "flux_wb": phi, "flux_change_percent": d_flux,
                "fea_vs_analytical_percent": fea_vs, "note": note}

    rows = []
    print("=== STEP 4: leakage-factor diagnostic (DIAGNOSTIC_ONLY) ===")
    rows.append(show("sigma_m = 1.15  (production default)", phi0, "reference"))
    for s in (1.0, 1.05, 1.10, 1.20):
        rows.append(show(f"sigma_m = {s:.2f}", pole_flux(**{**ref, "leakage": s})))
    print()

    print("=== STEP 8: effective-gap treatment (DIAGNOSTIC_ONLY) ===")
    print("  production g_eff = h_coil + 2g = 7.000 mm; Carter = 1.0 for slot_type 'wu cao' (slotless).")
    rows.append(show("g_eff = h_coil + 2g          (production)", phi0, "reference"))
    for label, g in (
        ("g_eff = h_coil + 2g + 2*h_m/mu_r (magnet in gap)", ref["g_eff"] + 2 * 0.005 / 1.05),
        ("g_eff = h_coil only", 0.005),
        ("g_eff = h_coil + 2g, Carter 1.05", None),
    ):
        if g is None:
            rows.append(show(label, pole_flux(**{**ref, "carter": 1.05})))
        else:
            rows.append(show(label, pole_flux(**{**ref, "g_eff": g})))
    print()

    print("=== STEP 9: magnet finite permeability (DIAGNOSTIC_ONLY) ===")
    print("  The production model already treats the magnet as finite-permeability:")
    print("  mu_r appears in BOTH the magnet reluctance and the MMF, so F/R_mag = Br*A exactly.")
    rows.append(show("mu_r = 1.05  (production, = FEMM material)", phi0, "reference"))
    for mu in (1.0, 1.10):
        rows.append(show(f"mu_r = {mu:.2f}", pole_flux(**{**ref, "mu_r": mu})))
    print()

    print("=== STEP 10: magnet arc / pole coverage (DIAGNOSTIC_ONLY) ===")
    print("  alpha_p enters A_pole, so it scales BOTH reluctances and cancels in B_peak;")
    print("  it changes total flux linearly but leaves the peak flux density unchanged.")
    rows.append(show("alpha_p = 0.70  (production)", phi0, "reference"))
    for a in (0.65, 0.75, 0.80):
        rows.append(show(f"alpha_p = {a:.2f}", pole_flux(**{**ref, "alpha_p": a})))
    print()

    # ---------------- Step 12 + 13: the budget ----------------
    kw_star = base["analytical_winding_factor"]
    kw_meshed = kwt["winding_factor_meshed_geometry"]
    form = rectangular_to_fundamental_form_factor(ref["alpha_p"])
    phi_ideal_fund = phi0 * form
    exact = 2.0 * math.pi / math.sqrt(2.0)

    f_kw = kw_meshed / kw_star
    f_conv = form
    f_wave = phi_fea / phi_ideal_fund
    f_444 = exact / LEGACY_SINE_EMF_FACTOR
    product = f_kw * f_conv * f_wave * f_444
    observed = 1.0 + ke_res / 100.0

    print("=== STEP 12/13: multiplicative residual budget ===")
    print("  Ke is proportional to k_w * Phi, so contributions compose as a PRODUCT.")
    print()
    print(f"  {'component':<52s} {'factor':>12s} {'as %':>10s}")
    budget = [
        ("winding factor: meshed geometry vs Phase 10C slot star", f_kw),
        ("convention: flat-top Phi used where fundamental required", f_conv),
        ("waveform + axial averaging in the coreless gap", f_wave),
        ("4.44 rounding vs exact 2*pi/sqrt(2)", f_444),
    ]
    for label, f in budget:
        print(f"  {label:<52s} {f:12.6f} {(f-1)*100:+9.3f} %")
    print(f"  {'-'*52} {'-'*12} {'-'*10}")
    print(f"  {'product of the above':<52s} {product:12.6f} {(product-1)*100:+9.3f} %")
    print(f"  {'observed Ke residual':<52s} {observed:12.6f} {(observed-1)*100:+9.3f} %")
    print(f"  {'unresolved remainder':<52s} {product/observed:12.6f} {(product/observed-1)*100:+9.3f} %")
    print()
    print("  Sub-evidence for the waveform component:")
    print(f"    analytical B_peak                    {base['analytical_b_gap_peak_t']:.6f} T")
    mid = next(p for p in prof["planes"] if p["plane_y_m"] == 0.0)
    print(f"    FEMM peak |B_n| at the stator plane  {mid['peak_abs_bn_t']:.6f} T")
    print(f"    peak agreement                       {(mid['peak_abs_bn_t']/base['analytical_b_gap_peak_t']-1)*100:+.4f} %")
    print(f"    FEMM B1/B_peak measured              {mid['fundamental_amplitude_t']/mid['peak_abs_bn_t']:.6f}")
    print(f"    ideal alpha_p=0.7 rectangle B1/Bpeak {(4/math.pi)*math.sin(0.7*math.pi/2):.6f}")
    print(f"    pure sinusoid                        1.000000")
    print(f"    FEMM THD at the stator plane         {mid['thd']*100:.3f} %")

    payload = {
        "schema_version": "phase10d.residual_budget.v1",
        "diagnostic_only": True,
        "calibration_performed": False,
        "production_defaults_mutated": False,
        "reference_inputs": ref,
        "diagnostic_cases": rows,
        "budget": {
            "winding_factor_meshed_vs_star": f_kw,
            "flat_top_to_fundamental_convention": f_conv,
            "waveform_and_axial_averaging": f_wave,
            "sine_emf_rounding": f_444,
            "product": product,
            "observed": observed,
            "unresolved_remainder": product / observed,
            "unresolved_remainder_percent": (product / observed - 1.0) * 100.0,
        },
        "peak_flux_density_agreement_percent": (
            mid["peak_abs_bn_t"] / base["analytical_b_gap_peak_t"] - 1.0
        ) * 100.0,
        "femm_b1_over_peak": mid["fundamental_amplitude_t"] / mid["peak_abs_bn_t"],
        "ideal_rectangle_b1_over_peak": (4 / math.pi) * math.sin(0.7 * math.pi / 2),
        "femm_thd_stator_plane": mid["thd"],
    }
    (OUT / "phase10d_residual_budget.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8", newline="\n"
    )
    print(f"\n  wrote {(OUT / 'phase10d_residual_budget.json').relative_to(ROOT)}")


if __name__ == "__main__":
    main()
