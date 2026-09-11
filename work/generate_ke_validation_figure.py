"""Render the Phase 10C analytical-vs-FEMM Ke comparison figure.

Every number is read from ``validation_data/fea_results/`` -- nothing is typed
into this script. Re-running it after a new validation campaign regenerates the
figure from whatever the evidence then says.

Usage::

    .venv\\Scripts\\python.exe work\\generate_ke_validation_figure.py
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DECOMPOSITION = (
    ROOT / "validation_data" / "fea_results" / "phase10c_self_consistent"
    / "ke_error_decomposition.json"
)
OUTPUT = ROOT / "docs" / "assets" / "ke_validation_phase10c.png"

# Deliberately restrained palette: one colour for analytical, one for FEA, grey
# for the superseded historical case so it cannot be mistaken for a headline.
ANALYTICAL = "#3b6ea5"
FEA = "#c1663a"
MUTED = "#9a9a9a"
INK = "#222222"


def main() -> None:
    d = json.loads(DECOMPOSITION.read_text(encoding="utf-8"))

    ke_self = d["ke_analytical_self_consistent"]
    ke_fea = d["ke_fea"]
    ke_hist = d["ke_analytical_manual"]
    residual = d["self_consistent_ke_error_percent"]
    hist_residual = d["historical_ke_error_percent"]
    kw_geom = d["geometry_winding_factor"]
    kw_manual = d["manual_winding_factor"]
    kw_err = (kw_manual / kw_geom - 1.0) * 100.0
    flux_err = d["flux_residual_fea_vs_analytical_percent"]
    mesh = d["mesh_sensitivity_percent"]
    solver = f"{d['solver']} {d['solver_version']}"
    tier = d["fea_tier"]

    fig, (ax, bx) = plt.subplots(
        1, 2, figsize=(11.5, 5.0), gridspec_kw={"width_ratios": [1.05, 1.0]}
    )
    fig.patch.set_facecolor("white")

    # ---------------------------------------------------------------- left
    labels = ["Analytical\n(geometry-consistent $k_w$)", "FEMM\n(2D mean-radius slice)"]
    values = [ke_self, ke_fea]
    bars = ax.bar(labels, values, color=[ANALYTICAL, FEA], width=0.52, zorder=3)
    for bar, value in zip(bars, values):
        ax.text(
            bar.get_x() + bar.get_width() / 2, value + max(values) * 0.015,
            f"{value:.6f}", ha="center", va="bottom",
            fontsize=10.5, fontweight="bold", color=INK,
        )

    top = max(values)
    y = top * 1.10
    ax.annotate(
        "", xy=(0, y), xytext=(1, y),
        arrowprops=dict(arrowstyle="<->", color=INK, lw=1.3),
    )
    ax.text(
        0.5, y * 1.018,
        f"FEMM higher by {residual:+.2f}%",
        ha="center", va="bottom", fontsize=11.5, fontweight="bold", color=INK,
    )

    ax.set_ylabel(r"$K_e$  [V$\cdot$s/rad, phase RMS, mechanical]", fontsize=10.5)
    ax.set_ylim(0, top * 1.30)
    ax.set_title(
        "No-load back-EMF constant\nanalytical vs FEMM",
        fontsize=12.5, fontweight="bold", pad=12,
    )
    ax.grid(axis="y", alpha=0.25, zorder=0)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)

    # --------------------------------------------------------------- right
    #
    # One convention only, stated on the axis: every bar is the ANALYTICAL value
    # relative to its reference. Mixing conventions is what made a +7.06% and a
    # -6.59% look like two different findings during Phase 10C, so the panel
    # that explains the cancellation must not repeat that mistake.
    flux_analytical_vs_fea = (1.0 / (1.0 + flux_err / 100.0) - 1.0) * 100.0
    ke_self_analytical_vs_fea = (ke_self / ke_fea - 1.0) * 100.0
    ke_hist_analytical_vs_fea = (ke_hist / ke_fea - 1.0) * 100.0

    names = [
        "Winding factor $k_w$\nentered vs geometry",
        "Flux per pole\nanalytical vs FEMM",
        "$K_e$ historical — net\n(the two above, multiplied)",
        "$K_e$ geometry-consistent\n(Phase 10C result)",
    ]
    errs = [
        kw_err,
        flux_analytical_vs_fea,
        ke_hist_analytical_vs_fea,
        ke_self_analytical_vs_fea,
    ]
    colours = [MUTED, MUTED, MUTED, FEA]
    positions = range(len(names))

    bx.barh(list(positions), errs, color=colours, height=0.5, zorder=3)
    bx.axvline(0, color=INK, lw=1.0, zorder=4)
    for i, value in enumerate(errs):
        offset = 0.4 if value >= 0 else -0.4
        bx.text(
            value + offset, i, f"{value:+.2f}%",
            va="center", ha="left" if value >= 0 else "right",
            fontsize=10, fontweight="bold", color=INK,
        )

    bx.set_yticks(list(positions))
    bx.set_yticklabels(names, fontsize=9.5)
    bx.invert_yaxis()
    bx.set_xlabel(
        "Analytical relative to FEMM  [%]   (one convention throughout)", fontsize=10.0
    )
    bx.set_xlim(-11.5, 11.5)
    bx.set_ylim(3.75, -0.75)
    bx.set_title(
        "Why the historical result looked better\nthan the model actually was",
        fontsize=12.5, fontweight="bold", pad=12,
    )
    bx.grid(axis="x", alpha=0.25, zorder=0)
    bx.set_axisbelow(True)
    for side in ("top", "right"):
        bx.spines[side].set_visible(False)

    bx.legend(
        handles=[
            Patch(facecolor=FEA, label="Current result (Phase 10C)"),
            Patch(facecolor=MUTED, label="Superseded / contributing error"),
        ],
        loc="lower right", fontsize=8.5, framealpha=0.95,
    )

    caption = (
        f"Solver: {solver}  ·  fidelity {tier} (2D mean-radius unrolled AFPM slice, "
        f"not a 3D equivalence claim)  ·  mesh sensitivity {mesh:.3f}%\n"
        f"Left panel is stated as FEMM relative to analytical ({residual:+.2f}%); the "
        f"right panel inverts that convention so the cancellation is visible in one "
        f"direction. NUMERICAL_FEA is not experimental validation."
    )
    fig.text(0.5, 0.015, caption, ha="center", va="bottom", fontsize=8.6, color="#444444")

    fig.tight_layout(rect=(0, 0.10, 1, 1))
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUTPUT, dpi=170, facecolor="white")
    print(f"wrote {OUTPUT.relative_to(ROOT)}")
    print(f"  analytical Ke {ke_self:.8f}   FEMM Ke {ke_fea:.8f}   residual {residual:+.4f}%")


if __name__ == "__main__":
    main()
