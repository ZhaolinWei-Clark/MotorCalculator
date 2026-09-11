"""Phase 10D: measure the winding factor of the geometry FEMM actually meshed.

Phase 10C replaced an entered 0.93 with 0.8660254 from the slot-EMF star, on the
reasoning that the star describes the winding. The star describes a winding whose
coil sides sit at slot *centres*, one slot apart. The model that was meshed uses
SIDE_BY_SIDE_DOUBLE_LAYER_GO_THEN_RETURN: the two sides of a coil sit in adjacent
layer positions, so the centre-to-centre pitch is a slot pitch **plus one layer
width**, and each side has a finite width rather than being a filament.

This script measures the meshed pitch from the region polygons, predicts the
winding factor analytically from that geometry, and independently measures it
from the solved field via the reconstructed flux linkage. Two routes agreeing
establishes the number; neither is fitted.
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

from motor_calculator.fea.adapter import _mesh_size_map
from motor_calculator.fea.airgap_probe import parse_airgap_csv
from motor_calculator.fea.geometry import build_slice_model
from motor_calculator.fea.serialization import case_from_dict

OUT = ROOT / "validation_data" / "fea_results" / "phase10d_flux_diagnosis"
EV10C = ROOT / "validation_data" / "fea_results" / "phase10c_self_consistent"
WS = ROOT / "work" / "phase10d" / "femm_workspace"


def main() -> None:
    case = case_from_dict(
        json.loads((EV10C / "fea_case.json").read_text(encoding="utf-8"))["case"]
    )
    raw = json.loads((EV10C / "fea_raw_result.json").read_text(encoding="utf-8"))["result"]
    baseline = json.loads((OUT / "phase10d_baseline.json").read_text(encoding="utf-8"))
    profile = json.loads((OUT / "phase10d_airgap_axial_profile.json").read_text(encoding="utf-8"))
    geom = case.geometry
    model = build_slice_model(
        geom,
        slot_layers=case.winding.slot_layers(),
        mesh_sizes=_mesh_size_map(case),
        symmetry=case.symmetry,
        rotor_angle_mech_deg=0.0,
    )
    tau = geom.pole_pitch_m
    windings = [r for r in model.regions if r.role == "winding"]

    # ---------- route 1: geometry of the meshed winding ----------
    a_pos = sorted(
        (min(p[0] for p in r.polygon_m) + max(p[0] for p in r.polygon_m)) / 2.0
        for r in windings
        if r.circuit_name == "A" and float(r.signed_turns) > 0
    )
    a_neg = sorted(
        (min(p[0] for p in r.polygon_m) + max(p[0] for p in r.polygon_m)) / 2.0
        for r in windings
        if r.circuit_name == "A" and float(r.signed_turns) < 0
    )
    widths = {
        round(max(p[0] for p in r.polygon_m) - min(p[0] for p in r.polygon_m), 9)
        for r in windings
    }
    width = float(next(iter(widths)))
    pitch = a_neg[0] - a_pos[0]

    k = math.pi / tau  # spatial wavenumber of the fundamental
    k_pitch = abs(math.sin(k * pitch / 2.0))
    k_width = math.sin(k * width / 2.0) / (k * width / 2.0)
    k_meshed = k_pitch * k_width

    print("=== route 1: winding factor implied by the meshed geometry ===")
    print(f"  pole pitch tau                      {tau:.9f} m")
    print(f"  slot pitch                          {geom.slot_pitch_m:.9f} m")
    print(f"  coil-side width (layer)             {width:.9f} m   (distinct widths: {len(widths)})")
    print(f"  meshed coil pitch (centre-centre)   {pitch:.9f} m  = {pitch/geom.slot_pitch_m:.6f} slot pitches")
    print(f"                                                       = {pitch/tau:.6f} pole pitches")
    print(f"  pitch factor  sin(pi/2 * pitch/tau) {k_pitch:.9f}")
    print(f"  finite-width factor  sinc(pi w/2tau){k_width:.9f}")
    print(f"  k_w of the meshed winding           {k_meshed:.9f}")
    print(f"  k_w used by Phase 10C (slot star)   {baseline['analytical_winding_factor']:.9f}")
    print(f"  ratio meshed / star                 {k_meshed/baseline['analytical_winding_factor']:.6f}")
    print()

    # ---------- route 2: measured from the solved field ----------
    scans = parse_airgap_csv(
        (WS / "airgap_profile.csv").read_text(encoding="utf-8"),
        span_m=model.modelled_span_m,
        pole_pairs=geom.pole_pairs,
        radial_length_m=model.depth_m,
    )
    half_coil = geom.winding_region_thickness_m / 2.0
    coil_scans = [s for s in scans if s.plane_y_m <= half_coil + 1e-12]
    ys = np.array([s.plane_y_m for s in coil_scans])
    x = np.asarray(coil_scans[0].x_m)
    a_grid = np.vstack([np.asarray(s.a_wb_per_m) for s in coil_scans])
    a_mean_x = np.trapezoid(a_grid, ys, axis=0) / (ys[-1] - ys[0])

    # Reconstruct the physical flux linkage. signed_turns already carries the
    # physical turns per coil side, so no unit-turns rescaling belongs here.
    lam = {}
    for name in model.circuit_names:
        total = 0.0
        for r in windings:
            if r.circuit_name != name:
                continue
            x0 = min(p[0] for p in r.polygon_m)
            x1 = max(p[0] for p in r.polygon_m)
            mask = (x >= x0) & (x < x1)
            total += float(r.signed_turns) * model.depth_m * float(a_mean_x[mask].mean())
        lam[name] = total

    femm_row = next(s for s in raw["samples"] if abs(float(s["rotor_angle_mech_deg"])) < 1e-12)
    print("=== reconstruction of FEMM's own flux linkage (rotor angle 0) ===")
    for name in model.circuit_names:
        rep = float(femm_row["phase_flux_linkage_wb_turn"][name])
        if abs(rep) > 1e-6:
            print(f"    {name}: reconstructed {lam[name]:+.9e}   FEMM {rep:+.9e}   ratio {lam[name]/rep:.6f}")
        else:
            print(f"    {name}: reconstructed {lam[name]:+.9e}   FEMM {rep:+.9e}   (near zero crossing)")
    print()

    # At rotor angle 0 phase C sits at its zero crossing, so |lambda_A| is the
    # peak times cos(30 deg); recover the fundamental peak from that.
    lam_peak = abs(lam["A"]) / math.cos(math.radians(30.0))
    n_phase = float(case.winding.turns_per_phase)
    phi_coil_mean = profile["coil_thickness_mean_phi1_wb"]
    k_measured = lam_peak / (n_phase * phi_coil_mean)

    print("=== route 2: winding factor measured from the solved field ===")
    print(f"  reconstructed lambda_A(0)           {lam['A']:+.9e} Wb-turn")
    print(f"  implied fundamental peak lambda     {lam_peak:.9e} Wb-turn")
    print(f"  turns per phase                     {n_phase:.0f}")
    print(f"  directly measured fundamental flux  {phi_coil_mean:.9e} Wb  (coil-thickness mean)")
    print(f"  k_w measured = lambda / (N * Phi1)  {k_measured:.9f}")
    print()
    print(f"  route 1 (geometry)  {k_meshed:.9f}")
    print(f"  route 2 (field)     {k_measured:.9f}")
    print(f"  agreement           {(k_measured/k_meshed-1)*100:+.4f} %")

    payload = {
        "schema_version": "phase10d.winding_factor_truth.v1",
        "pole_pitch_m": tau,
        "slot_pitch_m": geom.slot_pitch_m,
        "coil_side_width_m": width,
        "meshed_coil_pitch_m": pitch,
        "meshed_coil_pitch_in_slot_pitches": pitch / geom.slot_pitch_m,
        "meshed_coil_pitch_in_pole_pitches": pitch / tau,
        "pitch_factor_meshed": k_pitch,
        "finite_width_factor": k_width,
        "winding_factor_meshed_geometry": k_meshed,
        "winding_factor_measured_from_field": k_measured,
        "winding_factor_routes_agreement_percent": (k_measured / k_meshed - 1.0) * 100.0,
        "winding_factor_slot_star_phase10c": baseline["analytical_winding_factor"],
        "meshed_over_star_ratio": k_meshed / baseline["analytical_winding_factor"],
        "reconstructed_flux_linkage_wb_turn": lam,
        "femm_reported_flux_linkage_wb_turn": {
            n: float(femm_row["phase_flux_linkage_wb_turn"][n]) for n in model.circuit_names
        },
    }
    (OUT / "phase10d_winding_factor_truth.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8", newline="\n"
    )
    print(f"\n  wrote {(OUT / 'phase10d_winding_factor_truth.json').relative_to(ROOT)}")


if __name__ == "__main__":
    main()
