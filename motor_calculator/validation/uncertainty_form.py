"""GUI-neutral form conversion for explicit uncertainty assumptions."""

from __future__ import annotations

from dataclasses import dataclass

from .uncertainty_models import ParameterUncertainty, UncertaintyKind


def _optional_float(value: str) -> float | None:
    return None if not value.strip() else float(value)


@dataclass(frozen=True)
class UncertaintyInputRow:
    parameter_name: str
    unit: str
    nominal_value: str
    uncertainty_kind: str
    lower_bound: str = ""
    upper_bound: str = ""
    mean: str = ""
    standard_deviation: str = ""
    provenance: str = "user-entered local assumption"
    confidence: str = "user_declared"

    def to_parameter_uncertainty(self) -> ParameterUncertainty:
        if not self.parameter_name.strip():
            raise ValueError("parameter_name must not be empty")
        try:
            nominal = float(self.nominal_value)
        except ValueError as exc:
            raise ValueError(f"{self.parameter_name}: nominal value must be numeric") from exc
        try:
            kind = UncertaintyKind(self.uncertainty_kind)
            lower = _optional_float(self.lower_bound)
            upper = _optional_float(self.upper_bound)
            mean = _optional_float(self.mean)
            deviation = _optional_float(self.standard_deviation)
        except ValueError as exc:
            raise ValueError(f"{self.parameter_name}: invalid uncertainty declaration") from exc
        try:
            return ParameterUncertainty(
                parameter_name=self.parameter_name,
                nominal_value=nominal,
                unit=self.unit,
                uncertainty_kind=kind,
                lower_bound=lower,
                upper_bound=upper,
                mean=mean,
                standard_deviation=deviation,
                provenance=self.provenance,
                confidence=self.confidence,
                notes=("Explicit local Phase 7K input; not written to production.",),
            )
        except ValueError as exc:
            raise ValueError(
                f"{self.parameter_name}: invalid uncertainty declaration: {exc}"
            ) from exc


def rows_from_parameters(
    parameters: tuple[ParameterUncertainty, ...],
) -> tuple[UncertaintyInputRow, ...]:
    return tuple(UncertaintyInputRow(
        parameter_name=parameter.parameter_name,
        unit=parameter.unit,
        nominal_value=f"{parameter.nominal_value:g}",
        uncertainty_kind=parameter.uncertainty_kind.value,
        lower_bound="" if parameter.lower_bound is None else f"{parameter.lower_bound:g}",
        upper_bound="" if parameter.upper_bound is None else f"{parameter.upper_bound:g}",
        mean="" if parameter.mean is None else f"{parameter.mean:g}",
        standard_deviation=(
            "" if parameter.standard_deviation is None else f"{parameter.standard_deviation:g}"
        ),
        provenance=parameter.provenance,
        confidence=parameter.confidence,
    ) for parameter in parameters)
