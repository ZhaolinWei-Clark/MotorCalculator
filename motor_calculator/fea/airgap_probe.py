"""Phase 10D: direct air-gap field extraction and spatial harmonic analysis.

Phase 10C inferred the FEA flux per pole *backwards* from a solved flux linkage:
``flux = lambda_fundamental / (N * k_w)``. That route is only as trustworthy as
the winding factor used to undo it, and it cannot separate a magnetic-circuit
error from a definition mismatch, because both arrive as one number.

This module adds the independent route: sample the normal air-gap flux density
along a line in the solved field, integrate it directly, and decompose it into
spatial harmonics. Two FEA-derived fluxes that disagree indicate an extraction
convention problem; two that agree license a statement about the analytical
model.

Nothing here changes a production value and nothing here is fitted to FEMM.
Every function reports a measurement or an arithmetic identity.

Flux conventions
----------------
"Flux per pole" is ambiguous, so this module never uses the bare phrase. Three
distinct quantities are computed and named:

``signed_pole_flux_wb``
    The integral of ``B_n`` over one pole pitch, times the radial length. The
    literal flux crossing one pole window, sign included.

``absolute_pole_flux_wb``
    The integral of ``|B_n|`` over the whole span, divided by the pole count,
    times the radial length. Independent of where the pole window is placed.

``fundamental_flux_per_pole_wb``
    ``(2/pi) * B1_peak * pole_pitch * radial_length``, where ``B1_peak`` is the
    amplitude of the spatial harmonic with one cycle per pole pair. This is the
    quantity the ``4.44 f N k_w Phi`` back-EMF convention actually requires, and
    the one comparable to a flux-linkage-derived value.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

AIRGAP_PROBE_VERSION = "phase10d.femm.airgap.v2"

#: Lua writes one row per sample; this is the CSV header it emits.
#:
#: ``a_wb_per_m`` is the magnetic vector potential ``A_z``. It is sampled
#: because a circuit flux linkage is built from *differences of A* at the
#: conductor positions, not from a line integral of ``B_n`` on some chosen
#: plane. Recording both is what lets the two FEA flux routes be compared on
#: equal terms instead of being assumed equivalent.
AIRGAP_CSV_HEADER = "plane_y_m,x_m,a_wb_per_m,bx_t,by_t"


@dataclass(frozen=True)
class AirgapScan:
    """One sampled line of the solved field, at constant ``y``."""

    plane_y_m: float
    x_m: tuple[float, ...]
    bx_t: tuple[float, ...]
    by_t: tuple[float, ...]
    span_m: float
    pole_pairs: int
    radial_length_m: float
    a_wb_per_m: tuple[float, ...] = ()

    def __post_init__(self) -> None:
        n = len(self.x_m)
        if n < 8:
            raise ValueError("an air-gap scan needs at least 8 samples")
        if not (len(self.bx_t) == len(self.by_t) == n):
            raise ValueError("air-gap scan columns must be the same length")
        if self.a_wb_per_m and len(self.a_wb_per_m) != n:
            raise ValueError("air-gap scan columns must be the same length")
        if self.pole_pairs <= 0:
            raise ValueError("pole_pairs must be positive")
        if self.span_m <= 0.0 or self.radial_length_m <= 0.0:
            raise ValueError("span and radial length must be positive")

    @property
    def pole_pitch_m(self) -> float:
        return self.span_m / (2.0 * self.pole_pairs)

    @property
    def normal_t(self) -> np.ndarray:
        """Normal (axial) component. ``y`` is the machine axis in the slice."""

        return np.asarray(self.by_t, dtype=float)


@dataclass(frozen=True)
class SpatialHarmonics:
    """Spatial harmonic content of a sampled air-gap field."""

    fundamental_amplitude_t: float
    fundamental_phase_rad: float
    amplitudes_t: dict[int, float] = field(default_factory=dict)
    total_harmonic_distortion: float = 0.0
    peak_t: float = 0.0

    def amplitude_ratio(self, order: int) -> float:
        if self.fundamental_amplitude_t == 0.0:
            return 0.0
        return self.amplitudes_t.get(order, 0.0) / self.fundamental_amplitude_t


def build_airgap_probe_script(
    case,
    model,
    *,
    fem_path: str,
    output_path: str,
    planes_y_m: tuple[float, ...],
    sample_count: int,
) -> str:
    """Emit Lua that solves one position and samples ``B`` along constant-y lines.

    Geometry, materials and mesh policy come from the same production emitters
    the validation campaign uses, so the field being sampled is the field the
    campaign solved. Only the post-processing differs: the campaign asked FEMM
    for circuit flux linkages, this asks for point field values.
    """

    from .femm_lua import (
        FEMM_LUA_GENERATOR_VERSION,
        SOLVER_PRECISION,
        _lua_path,
        _lua_string,
        _material_definitions,
        _num,
        emit_geometry_lua,
    )

    if sample_count < 8:
        raise ValueError("sample_count must be at least 8")
    if not planes_y_m:
        raise ValueError("at least one sampling plane is required")

    materials = case.materials
    lines: list[str] = [
        "-- MotorCalculator Phase 10D air-gap probe, generator "
        + FEMM_LUA_GENERATOR_VERSION,
        "-- probe " + AIRGAP_PROBE_VERSION,
        "-- case_id " + case.case_id,
        "-- rotor angle {0} mechanical degrees".format(model.rotor_angle_mech_deg),
        "-- This script is generated; do not edit it by hand.",
        "newdocument(0)",
        'mi_probdef(0, "meters", "planar", {p}, {d}, {a}, 0)'.format(
            p=_num(SOLVER_PRECISION),
            d=_num(model.depth_m),
            a=_num(case.mesh_policy.minimum_angle_deg),
        ),
    ]
    lines.extend(_material_definitions(materials, case.geometry.is_coreless))
    lines.append("-- Circuits: no-load, zero current in every phase")
    for name in model.circuit_names:
        lines.append("mi_addcircprop({0}, 0, 1)".format(_lua_string(name)))
    lines.extend(
        emit_geometry_lua(model, materials, is_coreless=case.geometry.is_coreless)
    )
    lines.extend(
        [
            "-- Solve",
            "mi_saveas({0})".format(_lua_path(fem_path)),
            "mi_analyze(1)",
            "mi_loadsolution()",
        ]
    )
    lines.append('handle = openfile({0}, "w")'.format(_lua_path(output_path)))
    lines.append(
        'write(handle, {0}, "\\n")'.format(_lua_string(AIRGAP_CSV_HEADER))
    )
    # FEMM 4.2 embeds Lua 4.0: numeric for-loops and multiple assignment are
    # available. Emitting a loop rather than thousands of unrolled calls keeps
    # the script small enough for the interpreter to load.
    lines.append("nsamp = {0}".format(sample_count))
    lines.append("span = {0}".format(_num(model.modelled_span_m)))
    for plane in planes_y_m:
        lines.append("yp = {0}".format(_num(plane)))
        lines.append("for i=0,nsamp-1 do")
        lines.append("  xs = span * i / nsamp")
        lines.append(
            "  Az, B1, B2, Sig, Ee, H1, H2, Je, Js, Mu1, Mu2, Pe, Ph = "
            "mo_getpointvalues(xs, yp)"
        )
        lines.append(
            '  write(handle, yp, ",", xs, ",", Az, ",", B1, ",", B2, "\\n")'
        )
        lines.append("end")
    lines.append("closefile(handle)")
    lines.append("mo_close()")
    lines.append("mi_close()")
    lines.append("quit()")
    return "\n".join(lines) + "\n"


def parse_airgap_csv(
    text: str, *, span_m: float, pole_pairs: int, radial_length_m: float
) -> tuple[AirgapScan, ...]:
    """Group the emitted CSV into one :class:`AirgapScan` per sampling plane."""

    rows = [line.strip() for line in text.splitlines() if line.strip()]
    if not rows or not rows[0].startswith("plane_y_m"):
        raise ValueError("air-gap CSV is missing its header")
    grouped: dict[float, list[tuple[float, float, float, float]]] = {}
    for row in rows[1:]:
        parts = row.split(",")
        if len(parts) != 5:
            raise ValueError("malformed air-gap CSV row: {0!r}".format(row))
        plane, x, a, bx, by = (float(p) for p in parts)
        grouped.setdefault(plane, []).append((x, a, bx, by))
    scans = []
    for plane in sorted(grouped):
        samples = sorted(grouped[plane])
        scans.append(
            AirgapScan(
                plane_y_m=plane,
                x_m=tuple(s[0] for s in samples),
                bx_t=tuple(s[2] for s in samples),
                by_t=tuple(s[3] for s in samples),
                span_m=span_m,
                pole_pairs=pole_pairs,
                radial_length_m=radial_length_m,
                a_wb_per_m=tuple(s[1] for s in samples),
            )
        )
    return tuple(scans)


def spatial_harmonics(scan: AirgapScan, *, max_order: int = 25) -> SpatialHarmonics:
    """Decompose the normal field into harmonics of the pole-pair fundamental.

    The sampled span covers the whole modelled circumference, so the harmonic
    with one cycle per *pole pair* sits at FFT bin ``pole_pairs``. Orders are
    stated relative to that fundamental, which is the electrical-machine
    convention: order 3 is the third harmonic of the back-EMF, not the third
    spatial cycle around the machine.
    """

    b = scan.normal_t
    n = b.size
    spectrum = np.fft.rfft(b)
    amplitude = np.abs(spectrum) * 2.0 / n
    p = scan.pole_pairs
    if p >= amplitude.size:
        raise ValueError("too few samples to resolve the pole-pair fundamental")

    fundamental = float(amplitude[p])
    phase = float(np.angle(spectrum[p]))
    amplitudes: dict[int, float] = {}
    for order in range(1, max_order + 1):
        bin_index = p * order
        if bin_index >= amplitude.size:
            break
        amplitudes[order] = float(amplitude[bin_index])

    harmonic_power = sum(v * v for k, v in amplitudes.items() if k >= 2)
    thd = math.sqrt(harmonic_power) / fundamental if fundamental > 0.0 else 0.0
    return SpatialHarmonics(
        fundamental_amplitude_t=fundamental,
        fundamental_phase_rad=phase,
        amplitudes_t=amplitudes,
        total_harmonic_distortion=thd,
        peak_t=float(np.max(np.abs(b))),
    )


def signed_pole_flux_wb(scan: AirgapScan, *, pole_index: int = 0) -> float:
    """Literal signed flux through one pole window.

    The integral of ``B_n`` over one pole pitch, times the radial length. The
    sign follows the field, so alternate poles report opposite signs.
    """

    b = scan.normal_t
    n = b.size
    per_pole = n / (2.0 * scan.pole_pairs)
    start = int(round(pole_index * per_pole))
    stop = int(round((pole_index + 1) * per_pole))
    dx = scan.span_m / n
    return float(np.sum(b[start:stop]) * dx * scan.radial_length_m)


def absolute_pole_flux_wb(scan: AirgapScan) -> float:
    """Mean magnitude flux per pole, independent of window placement."""

    b = scan.normal_t
    dx = scan.span_m / b.size
    return float(
        np.sum(np.abs(b)) * dx * scan.radial_length_m / (2.0 * scan.pole_pairs)
    )


def fundamental_flux_per_pole_wb(
    scan: AirgapScan, harmonics: SpatialHarmonics | None = None
) -> float:
    """Flux per pole carried by the spatial fundamental alone.

    ``(2/pi) * B1_peak * pole_pitch * radial_length``: the integral of a
    half-cycle of the fundamental across one pole pitch. This is the quantity
    the sinusoidal back-EMF convention ``E = 4.44 f N k_w Phi`` requires.
    """

    h = harmonics if harmonics is not None else spatial_harmonics(scan)
    return (
        (2.0 / math.pi)
        * h.fundamental_amplitude_t
        * scan.pole_pitch_m
        * scan.radial_length_m
    )


def vector_potential_fundamental_flux_per_pole_wb(scan: AirgapScan) -> float:
    """Fundamental flux per pole taken from ``A_z`` rather than from ``B_n``.

    In a planar problem the flux linked between two conductors at ``x1`` and
    ``x2`` is ``(A(x1) - A(x2)) * depth``. A circuit flux linkage is therefore a
    *difference of A*, never a line integral of ``B_n`` on a plane the modeller
    picked. For the fundamental, ``A`` and ``B_n`` are related by
    ``A1_peak = B1_peak * tau / pi``, so the fundamental flux per pole is
    ``2 * A1_peak * depth``.

    Computing it this way makes the comparison against a flux-linkage-derived
    flux an identity check rather than an assumption.
    """

    if not scan.a_wb_per_m:
        raise ValueError("this scan carries no vector potential samples")
    a = np.asarray(scan.a_wb_per_m, dtype=float)
    spectrum = np.fft.rfft(a)
    amplitude = np.abs(spectrum) * 2.0 / a.size
    p = scan.pole_pairs
    if p >= amplitude.size:
        raise ValueError("too few samples to resolve the pole-pair fundamental")
    return float(2.0 * amplitude[p] * scan.radial_length_m)


def vector_potential_peak_to_peak_flux_wb(scan: AirgapScan) -> float:
    """Total flux per pole from the extremes of ``A_z``.

    ``(max A - min A) * depth`` is the literal flux between the two points where
    the field reverses, i.e. one full pole's worth of flux including every
    harmonic. Reported alongside the fundamental so the harmonic share of the
    linkage is visible.
    """

    if not scan.a_wb_per_m:
        raise ValueError("this scan carries no vector potential samples")
    a = np.asarray(scan.a_wb_per_m, dtype=float)
    return float((a.max() - a.min()) * scan.radial_length_m)


def rectangular_to_fundamental_form_factor(pole_arc_coefficient: float) -> float:
    """``Phi_fundamental / Phi_flat_top`` for an ideal rectangular pole.

    A flat-top field of amplitude ``B`` spanning ``alpha_p`` of the pole pitch
    carries ``B * alpha_p * tau * L`` in total, but its spatial fundamental
    carries ``(8/pi^2) * B * sin(alpha_p*pi/2) * tau * L``. The ratio is a pure
    geometry identity with no fitted content; it is the conversion the
    ``4.44 f N k_w Phi`` convention silently assumes has already been applied.
    """

    if not 0.0 < pole_arc_coefficient <= 1.0:
        raise ValueError("pole_arc_coefficient must be within (0, 1]")
    return (
        (8.0 / math.pi**2)
        * math.sin(pole_arc_coefficient * math.pi / 2.0)
        / pole_arc_coefficient
    )
