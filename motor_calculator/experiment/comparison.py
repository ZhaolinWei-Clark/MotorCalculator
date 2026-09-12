"""Phase 11A: analytical vs FEA vs measurement, on one explicit basis.

The three layers this project can produce a number from are not
interchangeable, and the whole point of the previous eight phases was learning
exactly how they differ. This module puts them side by side without letting any
of them borrow the others' standing.

The rules, all enforced by construction in :class:`EvidenceEntry` and
:class:`QuantityComparison`:

* A layer's evidence label is fixed by which layer it is. An analytical value is
  ``ANALYTICAL_MODEL`` and cannot be constructed as anything else; the same for
  FEA. Only the measurement layer's label varies, and it varies with the
  dataset's source class, not with anything the caller wants.
* A ``SIMULATED_REFERENCE`` dataset produces a ``SIMULATED_REFERENCE`` entry. It
  is rendered in the third column because that is where imported data goes, and
  it is never called experimental.
* ``overall_claim`` is ``EXPERIMENTALLY_SUPPORTED`` only when
  :func:`may_validate_current_design` says so. Every other combination produces
  a weaker claim with the reason attached.
* Residuals are computed against whichever reference exists, and a residual is
  never promoted into a verdict: a 0.5 % agreement with a different machine's
  data is reported as 0.5 % *and* as not validating anything.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from ..fea.diagnostics import CALIBRATION_STATUS, EvidenceLabel
from .compatibility import (
    CompatibilityAssessment,
    MachineCompatibility,
    may_validate_current_design,
)
from .schema import DatasetMetadata, TestType
from .sources import DatasetSourceType, is_experimental

COMPARISON_SCHEMA_VERSION = "phase11a.experiment.comparison.v1"


class EvidenceLayer(str, Enum):
    """Where a value came from. Three layers, never merged."""

    ANALYTICAL_MODEL = "ANALYTICAL_MODEL"
    NUMERICAL_FEA = "NUMERICAL_FEA"
    EXPERIMENTAL_MEASUREMENT = "EXPERIMENTAL_MEASUREMENT"


LAYER_LABELS_ZH = {
    EvidenceLayer.ANALYTICAL_MODEL: "解析模型",
    EvidenceLayer.NUMERICAL_FEA: "数值有限元",
    EvidenceLayer.EXPERIMENTAL_MEASUREMENT: "实验 / 参考测量",
}


class OverallClaim(str, Enum):
    """What the comparison as a whole is entitled to say."""

    EXPERIMENTALLY_SUPPORTED = "EXPERIMENTALLY_SUPPORTED"
    METHODOLOGY_REFERENCE_ONLY = "METHODOLOGY_REFERENCE_ONLY"
    SIMULATION_CROSS_CHECK_ONLY = "SIMULATION_CROSS_CHECK_ONLY"
    NO_EXPERIMENTAL_DATA = "NO_EXPERIMENTAL_DATA"
    INSUFFICIENT_METADATA = "INSUFFICIENT_METADATA"


CLAIM_LABELS_ZH = {
    OverallClaim.EXPERIMENTALLY_SUPPORTED: "已有实验支持（同一台机器的实测数据）",
    OverallClaim.METHODOLOGY_REFERENCE_ONLY: "仅方法学参考（非当前机器）",
    OverallClaim.SIMULATION_CROSS_CHECK_ONLY: "仅数值交叉核对（数据源为仿真）",
    OverallClaim.NO_EXPERIMENTAL_DATA: "没有实验数据",
    OverallClaim.INSUFFICIENT_METADATA: "机器识别信息不足，无法给出结论",
}

#: The only claim that may be rendered affirmatively.
AFFIRMATIVE_CLAIMS = frozenset({OverallClaim.EXPERIMENTALLY_SUPPORTED})


@dataclass(frozen=True)
class EvidenceEntry:
    """One layer's value for one quantity."""

    layer: EvidenceLayer
    value: float | None
    unit: str
    label_zh: str
    evidence_label: str
    #: For the measurement layer: which class of source this actually is.
    source_type: DatasetSourceType | None = None
    provenance: str = ""
    sample_count: int | None = None
    note_zh: str = ""

    def __post_init__(self) -> None:
        # The label is a property of the layer, not a caller's choice.
        if self.layer is EvidenceLayer.ANALYTICAL_MODEL:
            expected = EvidenceLabel.NOT_YET_VALIDATED
        elif self.layer is EvidenceLayer.NUMERICAL_FEA:
            expected = EvidenceLabel.NUMERICAL_FEA
        else:
            expected = None
        if expected is not None and self.evidence_label != expected:
            raise ValueError(
                f"a {self.layer.value} value must carry the {expected} label; "
                f"{self.evidence_label!r} was requested"
            )
        if (
            self.layer is EvidenceLayer.EXPERIMENTAL_MEASUREMENT
            and self.evidence_label == EvidenceLabel.EXPERIMENTAL_MEASUREMENT
            and not is_experimental(self.source_type or DatasetSourceType.SIMULATED_REFERENCE)
        ):
            raise ValueError(
                "a non-experimental dataset may not carry the "
                "EXPERIMENTAL_MEASUREMENT label; this is the firewall that keeps "
                "a simulation from being read as a measurement"
            )

    @property
    def is_affirmative(self) -> bool:
        return self.evidence_label in EvidenceLabel.AFFIRMATIVE


def analytical_entry(value: float | None, unit: str, *, note_zh: str = "") -> EvidenceEntry:
    return EvidenceEntry(
        layer=EvidenceLayer.ANALYTICAL_MODEL,
        value=value,
        unit=unit,
        label_zh=LAYER_LABELS_ZH[EvidenceLayer.ANALYTICAL_MODEL],
        evidence_label=EvidenceLabel.NOT_YET_VALIDATED,
        provenance="motor_core.calculations",
        note_zh=note_zh,
    )


def fea_entry(
    value: float | None, unit: str, *, provenance: str = "FEMM", note_zh: str = ""
) -> EvidenceEntry:
    return EvidenceEntry(
        layer=EvidenceLayer.NUMERICAL_FEA,
        value=value,
        unit=unit,
        label_zh=LAYER_LABELS_ZH[EvidenceLayer.NUMERICAL_FEA],
        evidence_label=EvidenceLabel.NUMERICAL_FEA,
        provenance=provenance,
        note_zh=note_zh,
    )


def measurement_entry(
    value: float | None,
    unit: str,
    *,
    metadata: DatasetMetadata,
    sample_count: int | None = None,
    note_zh: str = "",
) -> EvidenceEntry:
    """The imported layer. Its label follows the dataset's class, always."""

    if metadata.source_type is DatasetSourceType.SIMULATED_REFERENCE:
        label = EvidenceLabel.NUMERICAL_FEA
    elif metadata.source_type is DatasetSourceType.METHODOLOGY_ONLY:
        label = EvidenceLabel.NO_ANALYTICAL_MODEL
    else:
        label = EvidenceLabel.EXPERIMENTAL_MEASUREMENT
    return EvidenceEntry(
        layer=EvidenceLayer.EXPERIMENTAL_MEASUREMENT,
        value=value,
        unit=unit,
        label_zh=LAYER_LABELS_ZH[EvidenceLayer.EXPERIMENTAL_MEASUREMENT],
        evidence_label=label,
        source_type=metadata.source_type,
        provenance=metadata.data_provenance,
        sample_count=sample_count,
        note_zh=note_zh,
    )


@dataclass(frozen=True)
class Residual:
    """One model-vs-reference difference, with both sides named."""

    subject: str
    reference: str
    absolute: float
    relative_percent: float | None


@dataclass(frozen=True)
class QuantityComparison:
    """One physical quantity across all three layers."""

    schema_version: str
    quantity: str
    quantity_label_zh: str
    unit: str
    #: The basis every entry is expressed on. Stated once, for all three.
    basis_zh: str
    analytical: EvidenceEntry | None
    fea: EvidenceEntry | None
    measured: EvidenceEntry | None
    dataset: DatasetMetadata | None
    compatibility: CompatibilityAssessment | None
    residuals: tuple[Residual, ...]
    overall_claim: OverallClaim
    claim_label_zh: str
    claim_reason_zh: str
    limitations_zh: tuple[str, ...] = ()
    calibration_status: str = CALIBRATION_STATUS

    def __post_init__(self) -> None:
        if self.calibration_status != "NONE":
            raise ValueError("this project does not calibrate; the status is NONE")
        if self.overall_claim is OverallClaim.EXPERIMENTALLY_SUPPORTED:
            if self.dataset is None or self.compatibility is None:
                raise ValueError("an experimental claim needs a dataset and a verdict")
            if not may_validate_current_design(
                self.dataset.source_type, self.compatibility.status
            ):
                raise ValueError(
                    "EXPERIMENTALLY_SUPPORTED requires an experimental source "
                    "measured on the same machine"
                )

    @property
    def is_affirmative(self) -> bool:
        return self.overall_claim in AFFIRMATIVE_CLAIMS


def _residual(subject: str, subject_value, reference: str, reference_value) -> Residual | None:
    if subject_value is None or reference_value is None:
        return None
    absolute = float(subject_value) - float(reference_value)
    relative = (
        None if reference_value == 0 else absolute / float(reference_value) * 100.0
    )
    return Residual(subject, reference, absolute, relative)


def _claim(
    dataset: DatasetMetadata | None,
    compatibility: CompatibilityAssessment | None,
    measured: EvidenceEntry | None,
) -> tuple[OverallClaim, str]:
    if dataset is None or measured is None or measured.value is None:
        return (
            OverallClaim.NO_EXPERIMENTAL_DATA,
            "当前没有可用于该量的实验或参考数据集。",
        )
    if dataset.source_type is DatasetSourceType.SIMULATED_REFERENCE:
        return (
            OverallClaim.SIMULATION_CROSS_CHECK_ONLY,
            "数据源为仿真参考数据，不构成实验证据；"
            "它只能作为第二个数值来源进行交叉核对。",
        )
    if dataset.source_type is DatasetSourceType.METHODOLOGY_ONLY:
        return (
            OverallClaim.NO_EXPERIMENTAL_DATA,
            "该数据源只描述试验方法，不含可用测量值。",
        )
    if compatibility is None:
        return (
            OverallClaim.INSUFFICIENT_METADATA,
            "尚未评估机器一致性，因此不能判断这些测量是否与当前设计有关。",
        )
    if compatibility.status is MachineCompatibility.INSUFFICIENT_METADATA:
        return (OverallClaim.INSUFFICIENT_METADATA, compatibility.reason_zh)
    if may_validate_current_design(dataset.source_type, compatibility.status):
        return (
            OverallClaim.EXPERIMENTALLY_SUPPORTED,
            "数据源为实测，且机器识别信息与当前设计一致。",
        )
    return (
        OverallClaim.METHODOLOGY_REFERENCE_ONLY,
        f"{compatibility.reason_zh} 因此这些实测数据可以检验建模方法，"
        "但不能作为当前设计已被实验验证的依据。",
    )


def build_quantity_comparison(
    *,
    quantity: str,
    quantity_label_zh: str,
    unit: str,
    basis_zh: str,
    analytical: EvidenceEntry | None = None,
    fea: EvidenceEntry | None = None,
    measured: EvidenceEntry | None = None,
    dataset: DatasetMetadata | None = None,
    compatibility: CompatibilityAssessment | None = None,
    limitations_zh: tuple[str, ...] = (),
) -> QuantityComparison:
    """Assemble one quantity's three-layer comparison and its claim."""

    residuals = [
        residual
        for residual in (
            _residual(
                "ANALYTICAL_MODEL", analytical.value if analytical else None,
                "MEASURED", measured.value if measured else None,
            ),
            _residual(
                "NUMERICAL_FEA", fea.value if fea else None,
                "MEASURED", measured.value if measured else None,
            ),
            _residual(
                "ANALYTICAL_MODEL", analytical.value if analytical else None,
                "NUMERICAL_FEA", fea.value if fea else None,
            ),
        )
        if residual is not None
    ]

    claim, reason = _claim(dataset, compatibility, measured)

    limitations = list(limitations_zh)
    if claim is not OverallClaim.EXPERIMENTALLY_SUPPORTED and residuals:
        limitations.append(
            "下方残差是真实的数值差异，但它**不构成**对当前设计的验证结论；"
            "残差小并不改变证据类别。"
        )
    if dataset is not None and dataset.test_fixture_only:
        limitations.append(
            "该数据集被标记为 TEST_FIXTURE_ONLY，仅供自动化测试使用，"
            "不应出现在生产界面中。"
        )

    return QuantityComparison(
        schema_version=COMPARISON_SCHEMA_VERSION,
        quantity=quantity,
        quantity_label_zh=quantity_label_zh,
        unit=unit,
        basis_zh=basis_zh,
        analytical=analytical,
        fea=fea,
        measured=measured,
        dataset=dataset,
        compatibility=compatibility,
        residuals=tuple(residuals),
        overall_claim=claim,
        claim_label_zh=CLAIM_LABELS_ZH[claim],
        claim_reason_zh=reason,
        limitations_zh=tuple(limitations),
    )


#: The comparison a test type feeds, when one exists.
TEST_TYPE_QUANTITY = {
    TestType.NO_LOAD_BACK_EMF: ("ke_phase_rms_v_per_rad_s", "反电动势常数 Ke", "V/(rad/s)"),
    TestType.PHASE_RESISTANCE: ("phase_resistance_ohm", "相电阻", "Ohm"),
    TestType.TORQUE_CURRENT: ("torque_per_amp_nm_per_a", "转矩-电流斜率", "Nm/A"),
    TestType.EFFICIENCY: ("efficiency", "效率", "1"),
}


# ---------------------------------------------------------------------------
# The no-data state (Step 19)
# ---------------------------------------------------------------------------

NO_EXPERIMENTAL_DATA = "NO_EXPERIMENTAL_DATA"

NO_DATA_MESSAGE_ZH = (
    "NO_EXPERIMENTAL_DATA —— 当前项目没有任何实验数据集。\n"
    "此处不显示 0，也不显示占位测量值，更不会给出「验证通过」。\n"
    "本项目迄今为止的全部证据仍然是解析模型与数值有限元；"
    "要把任何量提升为「已验证」，必须先导入实测数据。"
)


@dataclass(frozen=True)
class ValidationOverview:
    """What the validation view shows, including when it shows nothing."""

    schema_version: str
    comparisons: tuple[QuantityComparison, ...]
    dataset_count: int
    experimental_dataset_count: int
    state: str
    message_zh: str

    @property
    def has_experimental_data(self) -> bool:
        return self.experimental_dataset_count > 0

    @property
    def has_any_affirmative_claim(self) -> bool:
        return any(comparison.is_affirmative for comparison in self.comparisons)


def build_overview(
    comparisons: tuple[QuantityComparison, ...], datasets: tuple[DatasetMetadata, ...]
) -> ValidationOverview:
    """The whole validation picture, with the empty case handled first."""

    experimental = tuple(
        dataset
        for dataset in datasets
        if is_experimental(dataset.source_type) and not dataset.test_fixture_only
    )
    if not datasets:
        return ValidationOverview(
            schema_version=COMPARISON_SCHEMA_VERSION,
            comparisons=(),
            dataset_count=0,
            experimental_dataset_count=0,
            state=NO_EXPERIMENTAL_DATA,
            message_zh=NO_DATA_MESSAGE_ZH,
        )
    if not experimental:
        return ValidationOverview(
            schema_version=COMPARISON_SCHEMA_VERSION,
            comparisons=comparisons,
            dataset_count=len(datasets),
            experimental_dataset_count=0,
            state=NO_EXPERIMENTAL_DATA,
            message_zh=(
                f"NO_EXPERIMENTAL_DATA —— 已载入 {len(datasets)} 个数据集，"
                "但其中没有任何一个是实验测量。\n" + NO_DATA_MESSAGE_ZH.split("\n", 1)[1]
            ),
        )
    return ValidationOverview(
        schema_version=COMPARISON_SCHEMA_VERSION,
        comparisons=comparisons,
        dataset_count=len(datasets),
        experimental_dataset_count=len(experimental),
        state="EXPERIMENTAL_DATA_PRESENT",
        message_zh=(
            f"已载入 {len(datasets)} 个数据集，其中 {len(experimental)} 个为实验测量。"
            "每个量的结论仍取决于机器一致性判定。"
        ),
    )
