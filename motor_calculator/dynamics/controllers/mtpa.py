"""Sandbox-only PMSM maximum-torque-per-ampere reference generation."""

from __future__ import annotations

from dataclasses import dataclass
import math


def _require_finite(name: str, value: float) -> None:
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite, got {value!r}")


@dataclass(frozen=True)
class MTPACurrentReference:
    """Bounded dq current reference and traceable strategy metadata."""

    id_reference: float
    iq_reference: float
    method: str
    notes: tuple[str, ...] = ()
    current_limited: bool = False
    requested_torque_nm: float = 0.0
    estimated_torque_nm: float = 0.0

    def __post_init__(self) -> None:
        for name, value in (
            ("id_reference", self.id_reference),
            ("iq_reference", self.iq_reference),
            ("requested_torque_nm", self.requested_torque_nm),
            ("estimated_torque_nm", self.estimated_torque_nm),
        ):
            _require_finite(name, value)
        if not self.method:
            raise ValueError("method must not be empty")
        if not isinstance(self.current_limited, bool):
            raise TypeError("current_limited must be a bool")
        object.__setattr__(self, "notes", tuple(self.notes))

    @property
    def current_magnitude_a(self) -> float:
        return math.hypot(self.id_reference, self.iq_reference)


class MTPAController:
    """Generate bounded current references without changing the PMSM plant.

    The IPMSM path performs a deterministic one-dimensional search over ``id``.
    For every candidate, ``iq`` is derived from the existing PMSM torque
    equation. This is a transparent sandbox approximation, not an efficiency
    map, calibrated lookup table, or industrial online optimizer.
    """

    def __init__(
        self,
        current_limit_a: float,
        saliency_tolerance_h: float = 1.0e-9,
        search_points: int = 2001,
    ) -> None:
        _require_finite("current_limit_a", current_limit_a)
        _require_finite("saliency_tolerance_h", saliency_tolerance_h)
        if current_limit_a <= 0.0:
            raise ValueError("current_limit_a must be greater than zero")
        if saliency_tolerance_h < 0.0:
            raise ValueError("saliency_tolerance_h must be non-negative")
        if (
            isinstance(search_points, bool)
            or not isinstance(search_points, int)
            or search_points < 101
        ):
            raise ValueError("search_points must be an integer of at least 101")
        self.current_limit_a = current_limit_a
        self.saliency_tolerance_h = saliency_tolerance_h
        self.search_points = search_points

    def compute_current_reference(
        self,
        torque_reference_nm: float,
        motor_parameters,
    ) -> MTPACurrentReference:
        """Return an SPMSM or salient-PMSM current reference under a current limit."""

        _require_finite("torque_reference_nm", torque_reference_nm)
        pole_pairs = getattr(motor_parameters, "pole_pairs", None)
        psi_f = getattr(motor_parameters, "psi_f", math.nan)
        if (
            isinstance(pole_pairs, bool)
            or not isinstance(pole_pairs, int)
            or pole_pairs <= 0
        ):
            raise ValueError("motor_parameters.pole_pairs must be a positive integer")
        _require_finite("motor_parameters.psi_f", psi_f)
        if psi_f <= 0.0:
            raise ValueError("motor_parameters.psi_f must be greater than zero")

        ld = getattr(motor_parameters, "Ld", math.nan)
        lq = getattr(motor_parameters, "Lq", math.nan)
        if not _valid_inductance(ld) or not _valid_inductance(lq):
            return self._id_zero_reference(
                torque_reference_nm,
                pole_pairs,
                psi_f,
                method="fallback_id_zero_invalid_inductance",
                notes=(
                    "Ld/Lq was invalid; the sandbox safely fell back to id=0.",
                ),
            )

        if abs(ld - lq) <= self.saliency_tolerance_h:
            return self._id_zero_reference(
                torque_reference_nm,
                pole_pairs,
                psi_f,
                method="spmsm_id_zero",
                notes=(
                    "Ld approximately equals Lq, so reluctance torque is ignored.",
                ),
            )

        return self._salient_reference(
            torque_reference_nm,
            pole_pairs,
            psi_f,
            ld,
            lq,
        )

    def _id_zero_reference(
        self,
        torque_reference_nm: float,
        pole_pairs: int,
        psi_f: float,
        *,
        method: str,
        notes: tuple[str, ...],
    ) -> MTPACurrentReference:
        torque_factor = 1.5 * pole_pairs
        raw_iq = torque_reference_nm / (torque_factor * psi_f)
        iq_reference = min(max(raw_iq, -self.current_limit_a), self.current_limit_a)
        limited = iq_reference != raw_iq
        result_notes = notes
        if limited:
            result_notes += (
                "Requested torque exceeded the id=0 current limit and was clipped.",
            )
        return MTPACurrentReference(
            id_reference=0.0,
            iq_reference=iq_reference,
            method=method,
            notes=result_notes,
            current_limited=limited,
            requested_torque_nm=torque_reference_nm,
            estimated_torque_nm=torque_factor * psi_f * iq_reference,
        )

    def _salient_reference(
        self,
        torque_reference_nm: float,
        pole_pairs: int,
        psi_f: float,
        ld: float,
        lq: float,
    ) -> MTPACurrentReference:
        if torque_reference_nm == 0.0:
            return MTPACurrentReference(
                id_reference=0.0,
                iq_reference=0.0,
                method="ipmsm_discrete_mtpa",
                notes=("Zero torque requires zero current in this ideal model.",),
            )

        torque_factor = 1.5 * pole_pairs
        saliency = ld - lq
        torque_per_factor = torque_reference_nm / torque_factor
        best: tuple[float, float, float] | None = None
        denominator_floor = max(abs(psi_f) * 1.0e-12, 1.0e-15)

        for index in range(self.search_points):
            fraction = index / (self.search_points - 1)
            id_candidate = -self.current_limit_a + 2.0 * self.current_limit_a * fraction
            effective_flux = psi_f + saliency * id_candidate
            if abs(effective_flux) <= denominator_floor:
                continue
            iq_candidate = torque_per_factor / effective_flux
            magnitude = math.hypot(id_candidate, iq_candidate)
            if magnitude > self.current_limit_a + 1.0e-12:
                continue
            if best is None or magnitude < best[0]:
                best = (magnitude, id_candidate, iq_candidate)

        if best is not None:
            _, id_reference, iq_reference = best
            estimated_torque = _torque(
                id_reference,
                iq_reference,
                pole_pairs,
                psi_f,
                ld,
                lq,
            )
            return MTPACurrentReference(
                id_reference=id_reference,
                iq_reference=iq_reference,
                method="ipmsm_discrete_mtpa",
                notes=(
                    "Reluctance torque is included using the explicit Ld-Lq term.",
                    "A bounded deterministic search minimizes dq current magnitude.",
                ),
                requested_torque_nm=torque_reference_nm,
                estimated_torque_nm=estimated_torque,
            )

        id_reference, iq_reference, estimated_torque = self._maximum_torque_on_limit(
            torque_reference_nm,
            pole_pairs,
            psi_f,
            ld,
            lq,
        )
        return MTPACurrentReference(
            id_reference=id_reference,
            iq_reference=iq_reference,
            method="ipmsm_current_limit_boundary",
            notes=(
                "Requested torque was not feasible inside the current circle.",
                "The returned point maximizes torque in the requested direction on the limit.",
            ),
            current_limited=True,
            requested_torque_nm=torque_reference_nm,
            estimated_torque_nm=estimated_torque,
        )

    def _maximum_torque_on_limit(
        self,
        torque_reference_nm: float,
        pole_pairs: int,
        psi_f: float,
        ld: float,
        lq: float,
    ) -> tuple[float, float, float]:
        requested_sign = 1.0 if torque_reference_nm >= 0.0 else -1.0
        best_score = -math.inf
        best = (0.0, 0.0, 0.0)
        for index in range(self.search_points):
            angle = -math.pi + 2.0 * math.pi * index / (self.search_points - 1)
            id_candidate = self.current_limit_a * math.cos(angle)
            iq_candidate = self.current_limit_a * math.sin(angle)
            torque = _torque(
                id_candidate,
                iq_candidate,
                pole_pairs,
                psi_f,
                ld,
                lq,
            )
            score = requested_sign * torque
            if score > best_score:
                best_score = score
                best = (id_candidate, iq_candidate, torque)
        return best


def _valid_inductance(value: float) -> bool:
    return (
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and math.isfinite(value)
        and value > 0.0
    )


def _torque(
    id_a: float,
    iq_a: float,
    pole_pairs: int,
    psi_f: float,
    ld: float,
    lq: float,
) -> float:
    return 1.5 * pole_pairs * (psi_f * iq_a + (ld - lq) * id_a * iq_a)
