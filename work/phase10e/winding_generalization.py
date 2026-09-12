"""Phase 10E: does the slot-star / meshed winding-factor gap generalise?

The three replication designs vary the magnetic circuit but share one winding, so
they all inherit the same winding-factor term and cannot test whether that
finding is specific to the Phase 10A reference. This sweep varies the winding
instead: slot and pole combinations, coil spans, and the layer count that sets
how far the side-by-side construction displaces a coil side.

No FEMM solve is involved. Both winding factors are geometric, so the comparison
is exact arithmetic, not a measurement.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "motor_calculator"))

from motor_calculator.fea.flux_budget import meshed_winding_factor
from motor_calculator.motor_core.winding_factor import (
    WindingFactorError,
    compute_fundamental_winding_factor,
)

OUT = ROOT / "validation_data" / "fea_results" / "phase10e_replication"

#: ``(slots, pole_pairs, coil_span_slots)`` combinations that admit a balanced
#: symmetric three-phase winding. Chosen to span concentrated and distributed
#: layouts, not chosen for the size of the effect.
COMBINATIONS = (
    (24, 8, 1),
    (24, 2, 4),
    (24, 4, 3),
    (36, 3, 6),
    (12, 5, 1),
    (48, 10, 2),
    (18, 3, 3),
    (36, 6, 3),
)

#: Circumference cancels out of both factors, so any positive value works; a
#: realistic one keeps the printed pitches readable.
CIRCUMFERENCE_M = 0.3298672286269283


def main() -> None:
    rows = []
    print("  slots  2p  span   tau_p[mm]  slot[mm]  layer[mm]  k_star    k_mesh    mesh/star")
    for slots, pole_pairs, span_slots in COMBINATIONS:
        try:
            star = compute_fundamental_winding_factor(
                slots=slots, pole_pairs=pole_pairs, coil_span_slots=span_slots, phases=3
            ).fundamental_winding_factor
        except (WindingFactorError, ValueError) as error:
            print(f"  {slots:5d} {2*pole_pairs:3d} {span_slots:5d}   unbalanced: {error}")
            continue

        tau = CIRCUMFERENCE_M / (2 * pole_pairs)
        slot_pitch = CIRCUMFERENCE_M / slots
        # Side-by-side double layer: two layers share the coil width, so a coil
        # side centre is displaced by half the coil width from the slot centre
        # and the go/return pair is one slot pitch plus one layer width apart.
        coil_width = slot_pitch * 0.509  # same width fraction as the reference model
        layer_width = coil_width / 2.0
        pitch = span_slots * slot_pitch + layer_width

        mesh = meshed_winding_factor(
            coil_pitch_m=pitch, coil_side_width_m=layer_width, pole_pitch_m=tau
        )
        rows.append(
            {
                "slots": slots,
                "pole_pairs": pole_pairs,
                "coil_span_slots": span_slots,
                "pole_pitch_m": tau,
                "slot_pitch_m": slot_pitch,
                "layer_width_m": layer_width,
                "winding_factor_ideal_slot_star": star,
                "winding_factor_meshed_geometry": mesh,
                "meshed_over_star": mesh / star,
                "meshed_over_star_percent": (mesh / star - 1.0) * 100.0,
            }
        )
        print(
            f"  {slots:5d} {2*pole_pairs:3d} {span_slots:5d}   {tau*1000:8.3f}  "
            f"{slot_pitch*1000:7.3f}  {layer_width*1000:8.3f}  "
            f"{star:.6f}  {mesh:.6f}  {mesh/star:+.6f}"
        )

    deltas = [abs(r["meshed_over_star_percent"]) for r in rows]
    same_sign = len({r["meshed_over_star"] > 1.0 for r in rows}) == 1
    print()
    print(f"  combinations tested        {len(rows)}")
    print(f"  |mesh/star - 1| range      {min(deltas):.3f} % .. {max(deltas):.3f} %")
    print(f"  all differ by more than 1% {all(d > 1.0 for d in deltas)}")
    print(f"  all in the same direction  {same_sign}")
    print()
    print("  The displacement is structural: a side-by-side double layer always moves")
    print("  the two sides of a coil apart by an extra layer width, and a finite-width")
    print("  side always loses a little to its own sinc. The star models neither, so")
    print("  the gap is a property of the construction, not of the Phase 10A design.")
    print()
    print("  The SIGN is not universal, and that matters. Where the ideal winding is")
    print("  short-pitched the extra displacement moves the coil toward full pitch and")
    print("  raises k_w; where the ideal winding is already full-pitched it moves past")
    print("  full pitch and, together with the width sinc, lowers it. A correction")
    print("  applied with a fixed sign would therefore be wrong for some windings,")
    print("  which is exactly why the bridge measures the geometry instead.")

    payload = {
        "schema_version": "phase10e.winding_generalization.v1",
        "femm_solves": 0,
        "note": "both factors are geometric; this is exact arithmetic, not a measurement",
        "combinations": rows,
        "all_exceed_one_percent": all(d > 1.0 for d in deltas),
        "all_same_direction": same_sign,
        "min_abs_percent": min(deltas),
        "max_abs_percent": max(deltas),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "phase10e_winding_generalization.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8", newline="\n"
    )
    print(f"\n  wrote {(OUT / 'phase10e_winding_generalization.json').relative_to(ROOT)}")


if __name__ == "__main__":
    main()
