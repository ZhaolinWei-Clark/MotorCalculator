"""Sandbox-only perturbation data structures for Phase 6A."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PerturbationSpec:
    """One temporary input change applied only to a copied baseline input."""

    parameter_name: str
    baseline_value: float | int | None
    perturbation_percent: float
    temporary_value: float | int | None
    internal_field_name: str | None = None
    unit: str | None = None
    status: str = "ready"
    notes: str | None = None


@dataclass(frozen=True)
class SensitivityTarget:
    """A user-facing input parameter that may be explored by the sandbox."""

    parameter_name: str
    internal_field_name: str | None
    unit: str | None
    available: bool
    notes: str
