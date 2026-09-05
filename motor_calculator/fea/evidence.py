"""Integration of FEA comparisons with the project's validation evidence layer.

An FEA result is *independent numerical evidence*. It is not a measurement. The
distinction is enforced here: the classification used is
``EvidenceClassification.NUMERICAL_FEA``, never
``EvidenceClassification.EXPERIMENTAL_MEASUREMENT``, and no code path converts
one into the other.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..validation.fea_reference import EvidenceClassification
from .comparison import FEAComparisonReport
from .models import FEAComparisonStatus

FEA_EVIDENCE_SCHEMA_VERSION = "phase10a.fea.evidence.v1"

#: How many admissible, independent FEA cases would be needed before FEA alone
#: could support more than a single-point confidence statement. One agreeing
#: case is evidence about one design at one operating point, nothing wider.
MINIMUM_CASES_FOR_BROAD_NUMERICAL_CONFIDENCE = 5

CONFIDENCE_POLICY_STATEMENT = (
    "A single agreeing FEA case is evidence about one design, one operating point "
    "and one fidelity tier. It does not raise model confidence to HIGH on its own. "
    "Confidence remains bounded by the number of independent cases, the parameter "
    "range they cover, whether the solved topology matches the design in question, "
    "the solver's own assumptions, and the continued absence of experimental "
    "measurement."
)


@dataclass(frozen=True)
class FEAEvidenceRecord:
    """One admissible FEA comparison, expressed as evidence."""

    schema_version: str
    classification: EvidenceClassification
    case_id: str
    target: str
    fidelity_tier: str
    solver: str
    solver_version: str
    timestamp_utc: str
    admissible: bool
    inadmissible_reasons: tuple[str, ...]
    worst_status: FEAComparisonStatus
    metric_statuses: tuple[tuple[str, str], ...]
    approximation_labels: tuple[str, ...]
    confidence_policy: str
    supports_experimental_claim: bool

    def __post_init__(self) -> None:
        if self.classification is EvidenceClassification.EXPERIMENTAL_MEASUREMENT:
            raise ValueError("an FEA result is never experimental measurement evidence")
        if self.supports_experimental_claim:
            raise ValueError("numerical evidence cannot support an experimental claim")


_STATUS_SEVERITY = {
    FEAComparisonStatus.CLOSE_AGREEMENT: 0,
    FEAComparisonStatus.MODERATE_DEVIATION: 1,
    FEAComparisonStatus.LARGE_DEVIATION: 2,
    FEAComparisonStatus.INSUFFICIENT_DATA: 3,
    FEAComparisonStatus.NOT_COMPARABLE: 4,
}


def worst_status(report: FEAComparisonReport) -> FEAComparisonStatus:
    """The least favourable status across every metric in a report."""

    if not report.metrics:
        return FEAComparisonStatus.INSUFFICIENT_DATA
    return max(
        (metric.status for metric in report.metrics),
        key=lambda status: _STATUS_SEVERITY[status],
    )


def build_evidence_record(
    report: FEAComparisonReport,
    *,
    solver: str,
    solver_version: str,
    timestamp_utc: str,
) -> FEAEvidenceRecord:
    """Turn a comparison into an evidence record, admissible or not."""

    reasons: list[str] = []
    if report.is_mock:
        reasons.append("the result came from the mock pipeline solver, not a field solver")
    reasons.extend(report.stale_reasons)

    return FEAEvidenceRecord(
        schema_version=FEA_EVIDENCE_SCHEMA_VERSION,
        classification=EvidenceClassification.NUMERICAL_FEA,
        case_id=report.case_id,
        target=report.target.value,
        fidelity_tier=report.fidelity_tier,
        solver=solver,
        solver_version=solver_version,
        timestamp_utc=timestamp_utc,
        admissible=report.evidence_admissible,
        inadmissible_reasons=tuple(reasons),
        worst_status=worst_status(report),
        metric_statuses=tuple(
            (metric.quantity, metric.status.value) for metric in report.metrics
        ),
        approximation_labels=report.approximation_labels,
        confidence_policy=CONFIDENCE_POLICY_STATEMENT,
        supports_experimental_claim=False,
    )


def numerical_confidence_statement(admissible_case_count: int) -> str:
    """A confidence sentence sized to how much evidence actually exists."""

    if admissible_case_count <= 0:
        return (
            "没有可采信的 FEA 证据：模型置信度不受本阶段影响。"
            "（No admissible FEA evidence; model confidence is unchanged by this phase.）"
        )
    if admissible_case_count < MINIMUM_CASES_FOR_BROAD_NUMERICAL_CONFIDENCE:
        return (
            f"仅有 {admissible_case_count} 个可采信的 FEA 案例，属于单点数值证据，"
            "不足以支撑对模型整体精度的结论，也不替代实验验证。"
            f"（{admissible_case_count} admissible FEA case(s): single-point numerical "
            "evidence only, not a statement about overall model accuracy and not a "
            "substitute for measurement.）"
        )
    return (
        f"已有 {admissible_case_count} 个可采信的 FEA 案例，可支撑对已覆盖参数范围的"
        "数值一致性结论；该结论仍限于所用求解器的假设与保真度等级，且仍不是实验验证。"
        f"（{admissible_case_count} admissible FEA cases support a numerical-agreement "
        "statement over the covered parameter range only, still bounded by the "
        "solver's assumptions and fidelity tier, and still not experimental.）"
    )
