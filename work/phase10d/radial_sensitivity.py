"""Phase 10D Step 11: how much does the mean-radius 2D slice cost?

The validation model is one unrolled slice taken at the mean radius. The magnet
thickness and the air gap do not change with radius, but the pole pitch does, so
the ratio that governs fringing changes from the inner to the outer radius. That
makes the field shape radius-dependent in a way a single slice cannot represent.

Three slices are solved at the inner, mean and outer radius. These are three
independent 2D problems, NOT a 3D solution, and nothing here is presented as one.
The result is an estimate of how far the mean-radius slice sits from a
radially-integrated value, which is a statement about the *validation reference*,
not about the analytical model.
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

from motor_calculator.fea.adapter import _mesh_size_map
from motor_calculator.fea.airgap_probe import (
    build_airgap_probe_script,
    parse_airgap_csv,
    spatial_harmonics,
    vector_potential_fundamental_flux_per_pole_wb,
)
from motor_calculator.fea.availability import detect_femm
from motor_calculator.fea.geometry import build_slice_model
from motor_calculator.fea.serialization import case_from_dict

SAMPLES = 2048
OUT = ROOT / "validation_data" / "fea_results" / "phase10d_flux_diagnosis"
EV10C = ROOT / "validation_data" / "fea_results" / "phase10c_self_consistent"
WS = ROOT / "work" / "phase10d" / "femm_workspace"


def geometry_at_radius(geom, radius_m: float):
    """Same machine, same axial stack, unrolled at a different radius."""

    circumference = 2.0 * math.pi * radius_m
    pole_pitch = circumference / (2.0 * geom.pole_pairs)
    return dataclasses.replace(
        geom,
        mean_radius_m=radius_m,
        circumference_m=circumference,
        pole_pitch_m=pole_pitch,
        magnet_arc_length_m=pole_pitch * geom.pole_arc_coefficient,
        slot_pitch_m=circumference / geom.slot_count,
        air_domain_margin_m=pole_pitch,
    )


def solve(case, geom, tag: str):
    model = build_slice_model(
        geom,
        slot_layers=case.winding.slot_layers(),
        mesh_sizes=_mesh_size_map(case),
        symmetry=case.symmetry,
        rotor_angle_mech_deg=0.0,
    )
    half = geom.winding_region_thickness_m / 2.0
    planes = tuple(round(v, 9) for v in np.linspace(0.0, half, 6))
    script = WS / f"radial_{tag}.lua"
    csv = WS / f"radial_{tag}.csv"
    script.write_text(
        build_airgap_probe_script(
            case, model,
            fem_path=str(WS / f"radial_{tag}.fem"),
            output_path=str(csv),
            planes_y_m=planes,
            sample_count=SAMPLES,
        ),
        encoding="utf-8", newline="\n",
    )
    rep = detect_femm()
    done = subprocess.run(
        [str(rep.executable_path), "-lua-script=" + str(script), "-windowhide"],
        cwd=str(WS), capture_output=True, text=True, timeout=1800.0, shell=False, check=False,
    )
    if done.returncode != 0 or not csv.is_file():
        raise SystemExit(f"FEMM failed at {tag}: rc={done.returncode} {done.stderr[:300]}")
    scans = parse_airgap_csv(
        csv.read_text(encoding="utf-8"),
        span_m=model.modelled_span_m,
        pole_pairs=geom.pole_pairs,
        radial_length_m=model.depth_m,
    )
    ys = np.array([s.plane_y_m for s in scans])
    b1 = np.array([spatial_harmonics(s).fundamental_amplitude_t for s in scans])
    peak = float(spatial_harmonics(scans[0]).peak_t)
    # Coil-thickness mean of the fundamental amplitude: the quantity the winding
    # sees, consistent with how the winding factor was measured.
    b1_mean = float(np.trapezoid(b1, ys) / (ys[-1] - ys[0]))
    phi = np.array([vector_potential_fundamental_flux_per_pole_wb(s) for s in scans])
    phi_mean = float(np.trapezoid(phi, ys) / (ys[-1] - ys[0]))
    return {
        "tag": tag,
        "radius_m": geom.mean_radius_m,
        "pole_pitch_m": geom.pole_pitch_m,
        "b1_coil_mean_t": b1_mean,
        "b1_stator_plane_t": float(b1[0]),
        "peak_abs_bn_stator_plane_t": peak,
        "phi1_coil_mean_wb": phi_mean,
        "magnet_thickness_over_pole_pitch": geom.magnet_thickness_m / geom.pole_pitch_m,
    }


def main() -> None:
    case = case_from_dict(
        json.loads((EV10C / "fea_case.json").read_text(encoding="utf-8"))["case"]
    )
    base = json.loads((OUT / "phase10d_baseline.json").read_text(encoding="utf-8"))
    geom = case.geometry
    r_in, r_out = 0.070 / 2.0, 0.140 / 2.0
    r_mean = geom.mean_radius_m
    WS.mkdir(parents=True, exist_ok=True)

    rows = []
    for tag, r in (("inner", r_in), ("mean", r_mean), ("outer", r_out)):
        row = solve(case, geometry_at_radius(geom, r), tag)
        rows.append(row)
        print(
            f"  {tag:<6s} r={r*1000:6.2f} mm  tau_p={row['pole_pitch_m']*1000:7.3f} mm  "
            f"h_m/tau_p={row['magnet_thickness_over_pole_pitch']:.4f}  "
            f"B1_coilmean={row['b1_coil_mean_t']:.6f} T  peak={row['peak_abs_bn_stator_plane_t']:.6f} T"
        )

    # Radially integrate the fundamental flux the winding links.
    #   Phi1(r) = (2/pi) * B1(r) * tau_p(r) * dr, tau_p(r) = pi*r/p
    # Simpson over the three radii, against the mean-radius slice scaled by the
    # exact pole-pitch area the analytical model already uses.
    p = geom.pole_pairs
    b1 = np.array([r["b1_coil_mean_t"] for r in rows])
    radii = np.array([r_in, r_mean, r_out])
    integrand = (2.0 / math.pi) * b1 * (math.pi * radii / p)
    h = (r_out - r_in) / 2.0
    phi_radial = float(h / 3.0 * (integrand[0] + 4.0 * integrand[1] + integrand[2]))

    tau_l = base["pole_pitch_times_radial_length_m2"]
    phi_meanslice = float((2.0 / math.pi) * b1[1] * tau_l)

    print()
    print("=== mean-radius approximation ===")
    print(f"  radially integrated fundamental flux   {phi_radial:.9e} Wb  (Simpson over 3 slices)")
    print(f"  mean-radius slice, exact area          {phi_meanslice:.9e} Wb")
    print(f"  mean-radius error                      {(phi_meanslice/phi_radial-1)*100:+.4f} %")
    print()
    print(f"  B1 spread inner->outer                 {(b1[2]/b1[0]-1)*100:+.3f} %")
    print(f"  B1 at mean vs arithmetic mean of ends  {(b1[1]/((b1[0]+b1[2])/2)-1)*100:+.3f} %")

    payload = {
        "schema_version": "phase10d.radial.v1",
        "note": "three independent 2D slices; NOT a 3D solution",
        "slices": rows,
        "radially_integrated_phi1_wb": phi_radial,
        "mean_radius_slice_phi1_wb": phi_meanslice,
        "mean_radius_error_percent": (phi_meanslice / phi_radial - 1.0) * 100.0,
        "b1_inner_to_outer_spread_percent": (b1[2] / b1[0] - 1.0) * 100.0,
    }
    (OUT / "phase10d_radial_sensitivity.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8", newline="\n"
    )
    print(f"\n  wrote {(OUT / 'phase10d_radial_sensitivity.json').relative_to(ROOT)}")


if __name__ == "__main__":
    main()
