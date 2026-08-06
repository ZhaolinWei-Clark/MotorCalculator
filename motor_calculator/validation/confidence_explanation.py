"""User-readable reasons for an engineering confidence classification."""

from __future__ import annotations

from .feedback_models import ExternalValidationCoverage, ValidationSummary
from .uncertainty_models import AccuracyEnvelopeResult, ModelFormUncertaintyStatus, ResultConfidence


def build_confidence_reasons(
    envelope: AccuracyEnvelopeResult,
    validation_summary: ValidationSummary | None = None,
) -> tuple[str, ...]:
    """Explain confidence dimensions without converting them into a score."""

    coverage = (
        validation_summary.validation_coverage
        if validation_summary is not None
        else ExternalValidationCoverage.NONE
    )
    reasons: list[str] = []
    if envelope.confidence_level is ResultConfidence.INSUFFICIENT:
        reasons.append("Required prediction or uncertainty information is incomplete.")
    elif envelope.confidence_level is ResultConfidence.LOW:
        reasons.append("Overall engineering confidence is low because important evidence gaps remain.")
    elif envelope.confidence_level is ResultConfidence.MEDIUM:
        reasons.append("Several uncertainty dimensions are characterized, but important limitations remain.")
    else:
        reasons.append("The declared uncertainty and evidence dimensions meet the current project criteria.")

    if coverage in {ExternalValidationCoverage.NONE, ExternalValidationCoverage.VERY_LIMITED}:
        reasons.append(f"External validation coverage is {coverage.value.lower().replace('_', ' ')}.")
    else:
        reasons.append(f"External validation coverage is {coverage.value.lower()} under project governance rules.")

    if envelope.model_form_uncertainty_status is ModelFormUncertaintyStatus.UNQUANTIFIED:
        reasons.append("Model-form uncertainty is not quantified.")
    else:
        reasons.append("Model-form uncertainty has an evidence-bounded estimate.")

    if envelope.dominant_uncertainty_parameters:
        drivers = ", ".join(envelope.dominant_uncertainty_parameters[:2])
        reasons.append(f"The strongest declared parameter drivers include {drivers}.")
    if envelope.numerical_uncertainty is None:
        reasons.append("Numerical convergence evidence is unavailable.")
    elif envelope.numerical_uncertainty <= 1.0:
        reasons.append("The monitored radial integration is well converged numerically.")
    else:
        reasons.append("Numerical convergence contributes a visible uncertainty warning.")
    return tuple(reasons)
