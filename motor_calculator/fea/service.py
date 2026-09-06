"""The FEA validation service: the single entry point GUI code should use.

Keeping the orchestration here is what lets the GUI stay a thin view. No FEMM
logic, no subprocess handling and no file layout decision lives in a Tk
callback.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..motor_core.models import AnalysisResult, MotorAnalysisInput
from .adapter import (
    FEASolveOutcome,
    FEMMSubprocessSolver,
    MockFEASolver,
    generate_case_scripts,
)
from .availability import FEMMAvailabilityReport, detect_femm
from .case_builder import (
    FEAModellingParameters,
    assess_supportability,
    build_validation_case,
)
from .comparison import FEAComparisonReport, build_comparison
from .evidence import FEAEvidenceRecord, build_evidence_record
from .models import (
    FEASupportability,
    FEASupportabilityReport,
    FEAValidationCase,
    FEAValidationTarget,
)

FEA_SERVICE_VERSION = "phase10a.fea.service.v1"

SOLVER_UNAVAILABLE_MESSAGE_ZH = (
    "未检测到 FEMM。当前可生成验证案例，但无法执行求解。"
)

SOLVER_UNAVAILABLE_DETAIL_ZH = (
    "案例定义、几何映射、材料映射、绕组映射、网格策略与求解脚本均可生成并导出；"
    "只有实际场求解被环境阻塞。安装 FEMM 后可直接运行同一案例。"
)


@dataclass(frozen=True)
class FEACasePreview:
    """Everything the review screen needs before anything is executed."""

    supportability: FEASupportabilityReport
    case: FEAValidationCase | None
    availability: FEMMAvailabilityReport
    can_generate_case: bool
    can_execute_solver: bool
    blocked_message_zh: str | None
    approximation_warnings: tuple[str, ...]

    @property
    def solver_status_zh(self) -> str:
        if self.can_execute_solver:
            return "已检测到 FEMM，可执行求解。"
        return SOLVER_UNAVAILABLE_MESSAGE_ZH


@dataclass(frozen=True)
class FEAValidationRun:
    """The outcome of one user-initiated validation run."""

    case: FEAValidationCase
    outcome: FEASolveOutcome
    comparison: FEAComparisonReport | None
    evidence: FEAEvidenceRecord | None
    used_mock_solver: bool

    @property
    def has_real_fea_data(self) -> bool:
        return (
            self.outcome.result is not None
            and not self.outcome.result.is_mock
        )


def preview_case(
    inputs: MotorAnalysisInput,
    analysis: AnalysisResult,
    *,
    target: FEAValidationTarget,
    modelling: FEAModellingParameters | None,
    availability: FEMMAvailabilityReport | None = None,
) -> FEACasePreview:
    """Build the review screen's content without executing anything."""

    report = availability if availability is not None else detect_femm()
    supportability = assess_supportability(inputs, modelling=modelling)
    can_generate = supportability.state in (
        FEASupportability.SUPPORTED,
        FEASupportability.PARTIALLY_SUPPORTED,
    )
    case: FEAValidationCase | None = None
    blocked: str | None = None
    if can_generate:
        case = build_validation_case(
            inputs, analysis, target=target, modelling=modelling
        )
    else:
        blocked = "；".join(supportability.blocking_reasons)
    return FEACasePreview(
        supportability=supportability,
        case=case,
        availability=report,
        can_generate_case=can_generate,
        can_execute_solver=can_generate and report.is_available,
        blocked_message_zh=blocked,
        approximation_warnings=supportability.approximation_labels,
    )


def export_scripts_only(
    case: FEAValidationCase, workspace: Path
) -> tuple[Path, ...]:
    """Generate the solver scripts without running them.

    Useful on a machine with no FEMM: the user can carry the scripts to a
    machine that has it.
    """

    return generate_case_scripts(case, Path(workspace))


def run_validation(
    inputs: MotorAnalysisInput,
    analysis: AnalysisResult,
    *,
    target: FEAValidationTarget,
    modelling: FEAModellingParameters,
    availability: FEMMAvailabilityReport | None = None,
    allow_mock_solver: bool = False,
    force_mock_solver: bool = False,
) -> FEAValidationRun:
    """Run one validation.

    ``allow_mock_solver`` permits the mock pipeline as a *fallback* when no real
    solver is present. ``force_mock_solver`` selects it even when one is, which
    is what a software test wants: a unit test must not launch a multi-minute
    field campaign just because the machine happens to have FEMM installed.
    Either way the resulting comparison is marked inadmissible as evidence.
    """

    report = availability if availability is not None else detect_femm()
    case = build_validation_case(inputs, analysis, target=target, modelling=modelling)

    if force_mock_solver:
        outcome = MockFEASolver().solve(case)
        used_mock = True
    elif report.is_available:
        solver = FEMMSubprocessSolver(availability=report)
        outcome = solver.solve(case)
        used_mock = False
    elif allow_mock_solver:
        outcome = MockFEASolver().solve(case)
        used_mock = True
    else:
        outcome = FEASolveOutcome(
            status="BLOCKED_BY_ENVIRONMENT",
            result=None,
            detail=SOLVER_UNAVAILABLE_DETAIL_ZH,
            workspace=None,
            seconds=None,
        )
        used_mock = False

    comparison = None
    evidence = None
    if outcome.result is not None:
        comparison = build_comparison(case, outcome.result)
        evidence = build_evidence_record(
            comparison,
            solver=outcome.result.provenance.solver,
            solver_version=outcome.result.provenance.solver_version,
            timestamp_utc=outcome.result.provenance.timestamp_utc,
        )
    return FEAValidationRun(
        case=case,
        outcome=outcome,
        comparison=comparison,
        evidence=evidence,
        used_mock_solver=used_mock,
    )
