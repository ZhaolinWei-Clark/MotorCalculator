"""Phase 10D Step 5-7: direct FEMM air-gap flux extraction.

Why a new FEMM solve is required
--------------------------------
The retained Phase 10B/10C results contain only per-phase circuit flux linkages
and a block-integral force. No air-gap field sample was ever written, so the
data needed for a direct flux integration simply does not exist in the frozen
evidence. Re-solving is the only way to obtain it.

The cost is deliberately minimal: the spatial field distribution at a *single*
rotor position is sufficient for a spatial harmonic decomposition. This is one
solve, not the 52-position campaign.

Diagnostic only. No production value is written and nothing is fitted to FEMM.
"""

from __future__ import annotations

import json
import math
import subprocess
import sys
from pathlib import Path

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
    signed_pole_flux_wb,
    spatial_harmonics,
)
from motor_calculator.fea.availability import detect_femm
from motor_calculator.fea.geometry import build_slice_model
from motor_calculator.fea.serialization import case_from_dict

SAMPLE_COUNT = 4096
TIMEOUT_S = 900.0
OUT = ROOT / "validation_data" / "fea_results" / "phase10d_flux_diagnosis"


def load_case():
    payload = json.loads(
        (
            ROOT
            / "validation_data"
            / "fea_results"
            / "phase10c_self_consistent"
            / "fea_case.json"
        ).read_text(encoding="utf-8")
    )
    return case_from_dict(payload["case"])


def solve_airgap(case, workspace: Path, *, geometry=None, tag: str = "mean"):
    """Solve one rotor position and sample the field on three planes."""

    geom = geometry if geometry is not None else case.geometry
    workspace.mkdir(parents=True, exist_ok=True)
    model = build_slice_model(
        geom,
        slot_layers=case.winding.slot_layers(),
        mesh_sizes=_mesh_size_map(case),
        symmetry=case.symmetry,
        rotor_angle_mech_deg=0.0,
    )
    half_coil = geom.winding_region_thickness_m / 2.0
    gap = geom.mechanical_air_gap_per_side_m
    planes = (
        0.0,                      # stator mid-plane: where the coils sit
        half_coil,                # coil surface
        half_coil + gap / 2.0,    # mid mechanical gap
    )
    script = workspace / f"airgap_{tag}.lua"
    csv = workspace / f"airgap_{tag}.csv"
    fem = workspace / f"airgap_{tag}.fem"
    script.write_text(
        build_airgap_probe_script(
            case,
            model,
            fem_path=str(fem),
            output_path=str(csv),
            planes_y_m=planes,
            sample_count=SAMPLE_COUNT,
        ),
        encoding="utf-8",
        newline="\n",
    )
    report = detect_femm()
    if not report.is_available:
        raise SystemExit("FEMM is not available; cannot run the Phase 10D probe")
    completed = subprocess.run(
        [str(report.executable_path), "-lua-script=" + str(script), "-windowhide"],
        cwd=str(workspace),
        capture_output=True,
        text=True,
        timeout=TIMEOUT_S,
        shell=False,
        check=False,
    )
    if completed.returncode != 0 or not csv.is_file():
        raise SystemExit(
            f"FEMM failed (rc={completed.returncode}): "
            f"{completed.stderr.strip() or completed.stdout.strip()}"
        )
    scans = parse_airgap_csv(
        csv.read_text(encoding="utf-8"),
        span_m=model.modelled_span_m,
        pole_pairs=geom.pole_pairs,
        radial_length_m=model.depth_m,
    )
    return model, scans


def describe(scans, *, label: str) -> dict:
    rows = []
    for scan in scans:
        h = spatial_harmonics(scan)
        rows.append(
            {
                "plane_y_m": scan.plane_y_m,
                "peak_abs_bn_t": h.peak_t,
                "fundamental_amplitude_t": h.fundamental_amplitude_t,
                "thd": h.total_harmonic_distortion,
                "harmonic_ratios": {
                    str(k): h.amplitude_ratio(k) for k in sorted(h.amplitudes_t) if k <= 13
                },
                "signed_pole_flux_wb": signed_pole_flux_wb(scan),
                "absolute_pole_flux_wb": absolute_pole_flux_wb(scan),
                "fundamental_flux_per_pole_wb": fundamental_flux_per_pole_wb(scan, h),
            }
        )
        print(f"  [{label}] plane y = {scan.plane_y_m*1000:7.3f} mm")
        print(f"      peak |B_n|                 {h.peak_t:.6f} T")
        print(f"      fundamental B1             {h.fundamental_amplitude_t:.6f} T")
        print(f"      THD (orders >= 2)          {h.total_harmonic_distortion*100:.3f} %")
        ratios = "  ".join(
            f"h{k}={h.amplitude_ratio(k)*100:.2f}%"
            for k in sorted(h.amplitudes_t)
            if k in (3, 5, 7, 9, 11, 13)
        )
        print(f"      odd harmonics              {ratios}")
        print(f"      signed pole flux           {signed_pole_flux_wb(scan):.10e} Wb")
        print(f"      absolute pole flux         {absolute_pole_flux_wb(scan):.10e} Wb")
        print(f"      fundamental pole flux      {fundamental_flux_per_pole_wb(scan, h):.10e} Wb")
        print()
    return {"label": label, "planes": rows}


def main() -> None:
    case = load_case()
    baseline = json.loads((OUT / "phase10d_baseline.json").read_text(encoding="utf-8"))
    workspace = ROOT / "work" / "phase10d" / "femm_workspace"

    print("=== STEP 5: direct FEMM air-gap field extraction (mean radius) ===")
    print(f"  probe {AIRGAP_PROBE_VERSION}, {SAMPLE_COUNT} samples per plane, 1 rotor position")
    model, scans = solve_airgap(case, workspace, tag="mean")
    print(f"  modelled span {model.modelled_span_m:.9f} m, depth {model.depth_m:.6f} m")
    print()
    result = describe(scans, label="mean-radius")

    # ---- Step 7: reconstruct Ke from the direct fundamental flux ----
    stator_plane = next(r for r in result["planes"] if r["plane_y_m"] == 0.0)
    phi_direct = stator_plane["fundamental_flux_per_pole_wb"]
    phi_linkage = baseline["fea_equivalent_flux_per_pole_wb"]
    phi_analytical = baseline["analytical_pole_flux_wb"]

    print("=== STEP 6/7: two independent FEMM flux routes ===")
    print(f"  A. flux-linkage-derived fundamental flux  {phi_linkage:.10e} Wb")
    print(f"  B. direct air-gap fundamental flux        {phi_direct:.10e} Wb")
    print(f"  B/A - 1                                   {(phi_direct/phi_linkage-1)*100:+.4f} %")
    print()
    print(f"  C. analytical flat-top pole flux          {phi_analytical:.10e} Wb")
    print(f"  A/C - 1  (Phase 10C residual)             {(phi_linkage/phi_analytical-1)*100:+.4f} %")
    print(f"  B/C - 1  (direct residual)                {(phi_direct/phi_analytical-1)*100:+.4f} %")
    print()
    print(f"  analytical B_g peak                       {baseline['analytical_b_gap_peak_t']:.6f} T")
    print(f"  FEMM peak |B_n| at stator plane           {stator_plane['peak_abs_bn_t']:.6f} T")
    print(f"  FEMM/analytical peak                      {(stator_plane['peak_abs_bn_t']/baseline['analytical_b_gap_peak_t']-1)*100:+.4f} %")
    print(f"  FEMM absolute pole flux                   {stator_plane['absolute_pole_flux_wb']:.10e} Wb")
    print(f"  FEMM abs / analytical flat-top            {(stator_plane['absolute_pole_flux_wb']/phi_analytical-1)*100:+.4f} %")

    OUT.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "phase10d.airgap.v1",
        "probe_version": AIRGAP_PROBE_VERSION,
        "case_id": case.case_id,
        "rotor_angle_mech_deg": 0.0,
        "sample_count": SAMPLE_COUNT,
        "modelled_span_m": model.modelled_span_m,
        "depth_m": model.depth_m,
        "scans": result,
        "flux_routes": {
            "flux_linkage_derived_fundamental_wb": phi_linkage,
            "direct_airgap_fundamental_wb": phi_direct,
            "direct_vs_linkage_percent": (phi_direct / phi_linkage - 1.0) * 100.0,
            "analytical_flat_top_wb": phi_analytical,
            "linkage_vs_analytical_percent": (phi_linkage / phi_analytical - 1.0) * 100.0,
            "direct_vs_analytical_percent": (phi_direct / phi_analytical - 1.0) * 100.0,
        },
    }
    (OUT / "phase10d_airgap_mean_radius.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8", newline="\n"
    )
    print(f"\n  wrote {(OUT / 'phase10d_airgap_mean_radius.json').relative_to(ROOT)}")


if __name__ == "__main__":
    main()
