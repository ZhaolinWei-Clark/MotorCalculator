"""Phase 10D Step 6: reconcile the two FEA flux routes before judging the model.

The first probe put the direct air-gap fundamental flux 11.5 % below the
flux-linkage-derived value. Step 6 requires that disagreement be diagnosed as an
extraction-convention question before any statement is made about the analytical
magnetic circuit.

Two candidate explanations are testable here:

1. the sampling plane. The coil occupies a finite axial thickness, and the field
   is weakest at the stator mid-plane, so a single y = 0 line understates what
   the winding actually links;
2. the vector potential. A circuit flux linkage is a difference of ``A`` at the
   conductor positions, not a line integral of ``B_n``.

Both are measured rather than assumed.
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
    AIRGAP_PROBE_VERSION,
    absolute_pole_flux_wb,
    build_airgap_probe_script,
    fundamental_flux_per_pole_wb,
    parse_airgap_csv,
    spatial_harmonics,
    vector_potential_fundamental_flux_per_pole_wb,
    vector_potential_peak_to_peak_flux_wb,
)
from motor_calculator.fea.availability import detect_femm
from motor_calculator.fea.geometry import build_slice_model
from motor_calculator.fea.serialization import case_from_dict

SAMPLE_COUNT = 4096
OUT = ROOT / "validation_data" / "fea_results" / "phase10d_flux_diagnosis"
EV10C = ROOT / "validation_data" / "fea_results" / "phase10c_self_consistent"


def main() -> None:
    case = case_from_dict(
        json.loads((EV10C / "fea_case.json").read_text(encoding="utf-8"))["case"]
    )
    baseline = json.loads((OUT / "phase10d_baseline.json").read_text(encoding="utf-8"))
    geom = case.geometry
    half_coil = geom.winding_region_thickness_m / 2.0
    gap = geom.mechanical_air_gap_per_side_m

    # Planes spanning the coil thickness, plus the mechanical gap and magnet face.
    planes = tuple(
        round(v, 9)
        for v in list(np.linspace(0.0, half_coil, 11)) + [half_coil + gap / 2.0, half_coil + gap]
    )

    workspace = ROOT / "work" / "phase10d" / "femm_workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    model = build_slice_model(
        geom,
        slot_layers=case.winding.slot_layers(),
        mesh_sizes=_mesh_size_map(case),
        symmetry=case.symmetry,
        rotor_angle_mech_deg=0.0,
    )
    script = workspace / "airgap_profile.lua"
    csv = workspace / "airgap_profile.csv"
    script.write_text(
        build_airgap_probe_script(
            case,
            model,
            fem_path=str(workspace / "airgap_profile.fem"),
            output_path=str(csv),
            planes_y_m=planes,
            sample_count=SAMPLE_COUNT,
        ),
        encoding="utf-8",
        newline="\n",
    )
    report = detect_femm()
    completed = subprocess.run(
        [str(report.executable_path), "-lua-script=" + str(script), "-windowhide"],
        cwd=str(workspace),
        capture_output=True,
        text=True,
        timeout=1800.0,
        shell=False,
        check=False,
    )
    if completed.returncode != 0 or not csv.is_file():
        raise SystemExit(f"FEMM failed rc={completed.returncode}: {completed.stderr[:400]}")

    scans = parse_airgap_csv(
        csv.read_text(encoding="utf-8"),
        span_m=model.modelled_span_m,
        pole_pairs=geom.pole_pairs,
        radial_length_m=model.depth_m,
    )

    print("=== axial profile of the fundamental flux (probe %s) ===" % AIRGAP_PROBE_VERSION)
    print("   y [mm]   B1 [T]    Phi1_from_B [Wb]   Phi1_from_A [Wb]   A-vs-B   region")
    rows = []
    for scan in scans:
        h = spatial_harmonics(scan)
        phi_b = fundamental_flux_per_pole_wb(scan, h)
        phi_a = vector_potential_fundamental_flux_per_pole_wb(scan)
        region = (
            "coil" if scan.plane_y_m <= half_coil + 1e-12
            else ("mech gap" if scan.plane_y_m < half_coil + gap - 1e-12 else "magnet face")
        )
        print(
            f"  {scan.plane_y_m*1000:7.3f}  {h.fundamental_amplitude_t:8.6f}  "
            f"{phi_b:16.9e}  {phi_a:16.9e}  {(phi_a/phi_b-1)*100:+7.4f}%  {region}"
        )
        rows.append(
            {
                "plane_y_m": scan.plane_y_m,
                "region": region,
                "fundamental_amplitude_t": h.fundamental_amplitude_t,
                "peak_abs_bn_t": h.peak_t,
                "thd": h.total_harmonic_distortion,
                "phi1_from_bn_wb": phi_b,
                "phi1_from_a_wb": phi_a,
                "phi_peak_to_peak_from_a_wb": vector_potential_peak_to_peak_flux_wb(scan),
                "absolute_pole_flux_wb": absolute_pole_flux_wb(scan),
            }
        )

    coil_rows = [r for r in rows if r["region"] == "coil"]
    ys = np.array([r["plane_y_m"] for r in coil_rows])
    phis = np.array([r["phi1_from_a_wb"] for r in coil_rows])
    # The coil is symmetric about y = 0, so averaging |y| over [0, half_coil]
    # is the average over the full winding thickness.
    coil_mean = float(np.trapezoid(phis, ys) / (ys[-1] - ys[0]))

    phi_linkage = baseline["fea_equivalent_flux_per_pole_wb"]
    phi_analytical = baseline["analytical_pole_flux_wb"]
    mid = coil_rows[0]["phi1_from_a_wb"]
    surf = coil_rows[-1]["phi1_from_a_wb"]

    print()
    print("=== reconciliation of the two FEA flux routes ===")
    print(f"  direct, stator mid-plane y=0          {mid:.9e} Wb")
    print(f"  direct, coil surface y=+h/2           {surf:.9e} Wb")
    print(f"  direct, averaged over coil thickness  {coil_mean:.9e} Wb")
    print(f"  flux-linkage-derived (Phase 10C)      {phi_linkage:.9e} Wb")
    print()
    print(f"  mid-plane   vs linkage                {(mid/phi_linkage-1)*100:+.4f} %")
    print(f"  coil-mean   vs linkage                {(coil_mean/phi_linkage-1)*100:+.4f} %")
    print(f"  coil-surface vs linkage               {(surf/phi_linkage-1)*100:+.4f} %")
    print()
    print(f"  analytical flat-top pole flux         {phi_analytical:.9e} Wb")
    print(f"  coil-mean vs analytical               {(coil_mean/phi_analytical-1)*100:+.4f} %")

    payload = {
        "schema_version": "phase10d.airgap_profile.v1",
        "probe_version": AIRGAP_PROBE_VERSION,
        "case_id": case.case_id,
        "sample_count": SAMPLE_COUNT,
        "winding_region_thickness_m": geom.winding_region_thickness_m,
        "mechanical_air_gap_per_side_m": gap,
        "planes": rows,
        "coil_thickness_mean_phi1_wb": coil_mean,
        "stator_midplane_phi1_wb": mid,
        "coil_surface_phi1_wb": surf,
        "flux_linkage_derived_phi1_wb": phi_linkage,
        "analytical_flat_top_phi_wb": phi_analytical,
        "coil_mean_vs_linkage_percent": (coil_mean / phi_linkage - 1.0) * 100.0,
        "midplane_vs_linkage_percent": (mid / phi_linkage - 1.0) * 100.0,
        "coil_mean_vs_analytical_percent": (coil_mean / phi_analytical - 1.0) * 100.0,
    }
    (OUT / "phase10d_airgap_axial_profile.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8", newline="\n"
    )
    print(f"\n  wrote {(OUT / 'phase10d_airgap_axial_profile.json').relative_to(ROOT)}")


if __name__ == "__main__":
    main()
