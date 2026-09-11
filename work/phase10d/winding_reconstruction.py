"""Phase 10D Step 6 (continued): close the loop on the flux-linkage route.

The direct air-gap flux and the flux-linkage-derived flux disagree by 11.5 %, and
the linkage value corresponds to no plane inside the coil. Before any of that can
be blamed on the analytical magnetic circuit, the linkage route itself has to be
shown to mean what Phase 10C assumed it meant.

A FEMM circuit flux linkage is
``sum over conductor regions of signed_turns * depth * <A_z> over the region``.
That is reconstructed here from the sampled ``A`` field and compared against the
flux linkage FEMM itself reported for the same geometry at the same rotor angle.
If the reconstruction matches, the winding model is understood and the effective
winding factor can be measured rather than assumed.
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
from motor_calculator.fea.femm_lua import unit_turns_scale
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
    geom = case.geometry
    model = build_slice_model(
        geom,
        slot_layers=case.winding.slot_layers(),
        mesh_sizes=_mesh_size_map(case),
        symmetry=case.symmetry,
        rotor_angle_mech_deg=0.0,
    )
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
    a_grid = np.vstack([np.asarray(s.a_wb_per_m) for s in coil_scans])  # (ny, nx)

    # A is even in y for this N-S through-flux arrangement, so the average over
    # [0, h/2] equals the average over the full coil thickness [-h/2, +h/2].
    a_coil_mean_x = np.trapezoid(a_grid, ys, axis=0) / (ys[-1] - ys[0])

    windings = [r for r in model.regions if r.role == "winding"]
    scale = unit_turns_scale(model)
    span = model.modelled_span_m
    L = model.depth_m

    print("=== reconstruct the FEMM circuit flux linkage from the sampled A field ===")
    print(f"  winding regions {len(windings)}   unit-turns scale {scale!r}   depth {L} m")

    linkage = {}
    for name in model.circuit_names:
        total = 0.0
        for region in windings:
            if region.circuit_name != name:
                continue
            xs = [p[0] for p in region.polygon_m]
            x0, x1 = min(xs), max(xs)
            mask = (x >= x0) & (x < x1)
            if not mask.any():
                raise SystemExit(f"no samples inside region {region.name}")
            a_mean = float(a_coil_mean_x[mask].mean())
            total += float(region.signed_turns) * L * a_mean
        linkage[name] = total * scale

    femm_row = None
    for sample in raw["samples"]:
        if abs(float(sample["rotor_angle_mech_deg"])) < 1e-12:
            femm_row = sample
            break
    if femm_row is None:
        raise SystemExit("no rotor-angle-0 sample in the Phase 10C raw result")

    print()
    print("  phase   reconstructed [Wb-turn]    FEMM reported [Wb-turn]     ratio")
    ratios = []
    for name in model.circuit_names:
        reported = float(femm_row["phase_flux_linkage_wb_turn"][name])
        r = linkage[name] / reported if reported != 0.0 else float("nan")
        ratios.append(r)
        print(f"    {name}     {linkage[name]:+.9e}      {reported:+.9e}   {r:+.6f}")

    print()
    print("=== what this means for the effective winding factor ===")
    baseline = json.loads((OUT / "phase10d_baseline.json").read_text(encoding="utf-8"))
    profile = json.loads((OUT / "phase10d_airgap_axial_profile.json").read_text(encoding="utf-8"))
    kw_assumed = baseline["analytical_winding_factor"]
    phi_coil_mean = profile["coil_thickness_mean_phi1_wb"]
    phi_linkage = profile["flux_linkage_derived_phi1_wb"]
    kw_effective = kw_assumed * phi_linkage / phi_coil_mean
    print(f"  winding factor assumed by the inversion   {kw_assumed:.9f}")
    print(f"  coil-thickness mean fundamental flux      {phi_coil_mean:.9e} Wb")
    print(f"  flux-linkage-derived fundamental flux     {phi_linkage:.9e} Wb")
    print(f"  implied effective winding factor          {kw_effective:.9f}")
    print(f"  implied / assumed                         {kw_effective/kw_assumed:.6f}")
    print()
    print("  An effective winding factor ABOVE the ideal pitch factor is not")
    print("  physically admissible for a fundamental projection, so a value")
    print("  greater than the slot-star k_w falsifies the assumption that the")
    print("  coil-thickness mean is the flux the winding links.")

    payload = {
        "schema_version": "phase10d.winding_reconstruction.v1",
        "unit_turns_scale": scale,
        "reconstructed_flux_linkage_wb_turn": linkage,
        "femm_reported_flux_linkage_wb_turn": {
            name: float(femm_row["phase_flux_linkage_wb_turn"][name])
            for name in model.circuit_names
        },
        "reconstruction_ratios": dict(zip(model.circuit_names, ratios)),
        "winding_factor_assumed": kw_assumed,
        "winding_factor_effective_implied": kw_effective,
    }
    (OUT / "phase10d_winding_reconstruction.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8", newline="\n"
    )
    print(f"\n  wrote {(OUT / 'phase10d_winding_reconstruction.json').relative_to(ROOT)}")


if __name__ == "__main__":
    main()
