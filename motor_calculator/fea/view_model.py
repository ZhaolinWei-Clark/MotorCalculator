"""Tk-free view model for the FEA validation screen.

All of the decision logic lives here so it can be tested without a display and
so no FEMM logic ends up inside a Tk callback. The dialog in
``gui/fea_validation_dialog.py`` only renders what this object exposes and
forwards user actions back to it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ..motor_core.models import AnalysisResult, MotorAnalysisInput
from .adapter import default_workspace_root
from .availability import FEMMAvailabilityReport, detect_femm
from .case_builder import FEAModellingParameters
from .export import export_bundle
from .models import FEASupportability, FEAValidationTarget
from .report import render_case_review_zh, render_comparison_zh
from .service import (
    SOLVER_UNAVAILABLE_DETAIL_ZH,
    SOLVER_UNAVAILABLE_MESSAGE_ZH,
    FEAValidationRun,
    export_scripts_only,
    preview_case,
    run_validation,
)

#: Shown above the two FEA-only inputs, so the user knows they are not part of
#: the motor design and are not read back into it.
MODELLING_PARAMETER_NOTICE_ZH = (
    "以下为 FEA 专用建模参数：MotorCalculator 的输入模型中不存在这两项，"
    "它们只用于建立有限元几何，不会写回设计，也不会影响任何解析结果。"
)

MODELLING_PROVENANCE_CONFIRMED = (
    "USER_CONFIRMED_IN_FEA_DIALOG: rotor back-iron thickness and coil span were "
    "entered and confirmed by the user in the FEA validation dialog; neither is "
    "part of the MotorCalculator input schema and neither was derived from an "
    "analytical result"
)

NO_DATA_PLOT_MESSAGE_ZH = "尚无 FEA 数据，因此不绘制任何 FEA 曲线。"

TARGET_CHOICES_ZH = (
    (FEAValidationTarget.NO_LOAD_BACK_EMF, "空载反电动势 / Ke"),
    (FEAValidationTarget.AVERAGE_TORQUE, "平均电磁转矩"),
    (FEAValidationTarget.COGGING_TORQUE, "齿槽转矩"),
)

#: Which targets have actually been run against a real solver and compared.
#: Phase 10B validated no-load back-EMF only; the other two can be executed but
#: no campaign has been run for them, and the screen must not imply otherwise.
TARGET_VALIDATION_STATUS_ZH = {
    FEAValidationTarget.NO_LOAD_BACK_EMF: (
        "已在 Phase 10B 中以真实 FEMM 求解并完成对比（FEA_TIER_3，单一参考设计）。"
    ),
    FEAValidationTarget.AVERAGE_TORQUE: (
        "NOT_YET_VALIDATED：尚未运行过真实转矩验证活动。"
        "此外，相 A 轴与转子 d 轴的电角对齐尚未由空载扫描实测，"
        "因此激励不能确认就是解析转矩常数所定义的 id = 0 工况。"
    ),
    FEAValidationTarget.COGGING_TORQUE: (
        "NOT_YET_VALIDATED：尚未运行过真实齿槽验证活动。"
        "当前无铁芯参考设计按构造没有齿槽，对其求解只能得到数值噪声底，"
        "不构成齿槽预测的验证。"
    ),
}


def suggested_modelling_values(inputs: MotorAnalysisInput) -> tuple[float, int]:
    """Editable starting values for the two FEA-only parameters.

    These are *suggestions shown in an editable field*, not silent defaults: the
    dialog cannot build a case until the user has seen and confirmed them.
    """

    back_iron_m = inputs.magnet_thickness_m
    full_pitch = inputs.slot_count / float(2 * inputs.pole_pairs)
    coil_span = max(1, int(round(full_pitch)))
    return back_iron_m, coil_span


@dataclass
class FEAValidationViewModel:
    """State and actions behind the FEA validation screen."""

    inputs: MotorAnalysisInput
    analysis: AnalysisResult
    target: FEAValidationTarget = FEAValidationTarget.NO_LOAD_BACK_EMF
    availability: FEMMAvailabilityReport = field(default_factory=detect_femm)
    modelling: FEAModellingParameters | None = None
    last_run: FEAValidationRun | None = None

    # ------------------------------------------------------------------
    # Availability
    # ------------------------------------------------------------------
    @property
    def solver_available(self) -> bool:
        return self.availability.is_available

    @property
    def solver_message_zh(self) -> str:
        if self.solver_available:
            return f"已检测到 FEMM：{self.availability.executable_path}"
        return SOLVER_UNAVAILABLE_MESSAGE_ZH

    @property
    def solver_detail_zh(self) -> str:
        if self.solver_available:
            return "可执行完整的案例生成、求解与对比流程。"
        return SOLVER_UNAVAILABLE_DETAIL_ZH

    # ------------------------------------------------------------------
    # Modelling parameters
    # ------------------------------------------------------------------
    def suggested_values(self) -> tuple[float, int]:
        return suggested_modelling_values(self.inputs)

    def confirm_modelling_parameters(
        self, *, rotor_back_iron_thickness_m: float, coil_span_slots: int
    ) -> None:
        """Accept the two FEA-only parameters the user confirmed."""

        self.modelling = FEAModellingParameters(
            rotor_back_iron_thickness_m=float(rotor_back_iron_thickness_m),
            coil_span_slots=int(coil_span_slots),
            provenance=MODELLING_PROVENANCE_CONFIRMED,
        )
        self.last_run = None

    def set_target(self, target: FEAValidationTarget) -> None:
        self.target = target
        self.last_run = None

    @property
    def target_validation_status_zh(self) -> str:
        """Whether this target has actually been validated, in plain words."""

        return TARGET_VALIDATION_STATUS_ZH[self.target]

    # ------------------------------------------------------------------
    # Review
    # ------------------------------------------------------------------
    def preview(self):
        return preview_case(
            self.inputs,
            self.analysis,
            target=self.target,
            modelling=self.modelling,
            availability=self.availability,
        )

    def review_text_zh(self) -> str:
        preview = self.preview()
        if preview.case is None:
            state = preview.supportability.state
            header = (
                "当前设计缺少 FEA 建模所需信息。"
                if state is FEASupportability.NOT_ENOUGH_GEOMETRY
                else "当前设计不受 FEA 桥接支持。"
            )
            reasons = "\n".join(f"- {reason}" for reason in preview.supportability.blocking_reasons)
            return f"{header}\n\n{reasons}"
        return render_case_review_zh(preview.case)

    @property
    def can_run_solver(self) -> bool:
        return self.preview().can_execute_solver

    @property
    def can_generate_case(self) -> bool:
        return self.preview().can_generate_case

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def run(
        self, *, allow_mock_solver: bool = False, force_mock_solver: bool = False
    ) -> FEAValidationRun:
        """Run the validation. Only ever called from an explicit user action."""

        if self.modelling is None:
            raise ValueError("the FEA modelling parameters must be confirmed first")
        self.last_run = run_validation(
            self.inputs,
            self.analysis,
            target=self.target,
            modelling=self.modelling,
            availability=self.availability,
            allow_mock_solver=allow_mock_solver,
            force_mock_solver=force_mock_solver,
        )
        return self.last_run

    def export_scripts(self, directory: Path | None = None) -> tuple[Path, ...]:
        """Write the solver scripts. Works with no FEMM installed."""

        preview = self.preview()
        if preview.case is None:
            raise ValueError("no case can be generated for this design")
        root = Path(directory) if directory is not None else default_workspace_root()
        return export_scripts_only(preview.case, root / preview.case.case_id[:16])

    def export_results(self, directory: Path) -> tuple[Path, ...]:
        preview = self.preview()
        if preview.case is None:
            raise ValueError("no case can be generated for this design")
        run = self.last_run
        return export_bundle(
            preview.case,
            Path(directory),
            result=run.outcome.result if run else None,
            report=run.comparison if run else None,
        )

    # ------------------------------------------------------------------
    # Results
    # ------------------------------------------------------------------
    @property
    def has_results(self) -> bool:
        """True only when a solver actually produced data."""

        return self.last_run is not None and self.last_run.comparison is not None

    @property
    def has_real_fea_data(self) -> bool:
        """True only when *non-mock* solver data exists. Plots gate on this."""

        return self.last_run is not None and self.last_run.has_real_fea_data

    def results_text_zh(self) -> str:
        if self.last_run is None:
            return "尚未运行验证。"
        if self.last_run.comparison is None:
            return f"{self.solver_message_zh}\n\n{self.last_run.outcome.detail}\n\n{NO_DATA_PLOT_MESSAGE_ZH}"
        text = render_comparison_zh(self.last_run.comparison)
        if self.last_run.used_mock_solver:
            text = (
                "⚠ 本次使用的是模拟管线数据（MockFEASolver），不是有限元求解结果，"
                "不得作为验证证据。\n\n" + text
            )
        return text
