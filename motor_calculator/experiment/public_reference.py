"""Phase 11A: preparing for literature data without ingesting any yet.

No web scraping happens here, and no example literature measurements are
fabricated. This module is the shape of the door, not anything that has walked
through it.

Two problems have to be solved before a paper's table can be used, and both are
easier to solve now than retroactively.

**The copyright problem.** A table of measurements in a published paper is
somebody's copyrighted content. Committing it to a public repository because it
is convenient is a real legal exposure, and "the licence was unclear" is not a
defence. So :func:`may_commit_raw_data` treats ``UNKNOWN`` as no, and the
preferred artefact is an *importer plus metadata*: the citation, the page, the
table number and the column mapping are committed, and the numbers are supplied
by whoever has legitimate access to the source.

**The provenance problem.** A number transcribed from a figure by eye is not the
same evidence as a number from a table, which is not the same as a number from
the authors' own dataset. :class:`ExtractionMethod` keeps them distinct, because
a digitised curve can easily carry several percent of reading error -- which is
the same size as the residuals this project is trying to interpret.

What Phase 11B has to add is listed in :data:`PHASE_11B_REQUIREMENTS`.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .schema import UNKNOWN, Citation, DatasetMetadata, MachineIdentity, RedistributionStatus, TestType
from .sources import DatasetSourceType

PUBLIC_REFERENCE_SCHEMA_VERSION = "phase11a.experiment.public_reference.v1"


class ExtractionMethod(str, Enum):
    """How the numbers left the source and arrived here."""

    #: Typed from a numeric table. Exact to the digits the source printed.
    TABLE_TRANSCRIPTION = "TABLE_TRANSCRIPTION"
    #: Read off a plotted curve. Carries reading error, often several percent.
    FIGURE_DIGITISATION = "FIGURE_DIGITISATION"
    #: A machine-readable dataset published alongside the source.
    AUTHOR_SUPPLIED_DATASET = "AUTHOR_SUPPLIED_DATASET"
    #: Stated in prose: "the measured Ke was 0.083 V/(rad/s)".
    TEXT_STATEMENT = "TEXT_STATEMENT"
    UNKNOWN = "UNKNOWN"


EXTRACTION_UNCERTAINTY_ZH = {
    ExtractionMethod.TABLE_TRANSCRIPTION: (
        "来自数值表格，精度为原文所印位数；转录错误是主要风险。"
    ),
    ExtractionMethod.FIGURE_DIGITISATION: (
        "由曲线图读取，通常带有百分级的读图误差。"
        "该误差与本项目试图解释的残差量级相当，因此不能忽略。"
    ),
    ExtractionMethod.AUTHOR_SUPPLIED_DATASET: (
        "来自作者随文发布的机器可读数据集，是公开参考数据中最可靠的一种。"
    ),
    ExtractionMethod.TEXT_STATEMENT: (
        "来自正文中的单个陈述值，通常没有测点、没有温度、没有基准说明。"
    ),
    ExtractionMethod.UNKNOWN: "提取方式未知，无法评估其附加误差。",
}


@dataclass(frozen=True)
class PublicSourceRecord:
    """Everything needed to cite a source and to re-obtain its numbers.

    This record can be committed to the repository even when the measurements
    cannot: it contains no measured values at all.
    """

    schema_version: str
    source_id: str
    citation: Citation
    machine: MachineIdentity
    test_type: TestType
    extraction_method: ExtractionMethod
    #: Which page, table or figure the numbers come from.
    location_note: str
    #: Source header -> canonical field, so an importer needs no guessing.
    column_mapping: dict[str, str]
    column_units: dict[str, str]
    #: Anything the source says about its own test conditions.
    test_conditions_zh: str = ""
    notes_zh: str = ""

    @property
    def may_commit_raw_data(self) -> bool:
        return self.citation.may_commit_raw_data

    @property
    def redistribution_status(self) -> RedistributionStatus:
        return self.citation.redistribution

    def to_metadata(self, dataset_id: str, title: str) -> DatasetMetadata:
        """The dataset record this source would produce once data arrives.

        Always ``PUBLIC_REFERENCE_EXPERIMENT``: these are real measurements, of
        somebody else's machine. The compatibility layer, not this one, decides
        what they may be used for.
        """

        return DatasetMetadata(
            dataset_id=dataset_id,
            title=title,
            source_type=DatasetSourceType.PUBLIC_REFERENCE_EXPERIMENT,
            test_type=self.test_type,
            machine=self.machine,
            citation=self.citation,
            data_provenance=f"PUBLIC_REFERENCE/{self.extraction_method.value}",
            notes=self.notes_zh or UNKNOWN,
        )


def may_commit_raw_data(citation: Citation) -> bool:
    """Whether a source's raw numbers may go into this repository.

    ``UNKNOWN`` is no. An unclear licence is not permission.
    """

    return citation.redistribution is RedistributionStatus.ALLOWED


def redistribution_guidance_zh(citation: Citation) -> str:
    """What to do with a source, given what is known about its licence."""

    if citation.redistribution is RedistributionStatus.ALLOWED:
        return (
            "该来源明确允许再分发：原始数值可以随仓库提交，"
            "但仍须保留完整引用信息。"
        )
    if citation.redistribution is RedistributionStatus.NOT_ALLOWED:
        return (
            "该来源不允许再分发：**不要**提交原始数值。"
            "只提交引用信息与列映射，由具备合法访问权限的使用者自行提供数据文件。"
        )
    return (
        "再分发许可未知：按**不允许**处理。"
        "只提交引用信息与列映射；许可不明确不等于获得许可。"
    )


#: What Phase 11B must add before public literature can actually be ingested.
#: Written here rather than only in the documentation, so the requirement list
#: sits next to the code that will have to satisfy it.
PHASE_11B_REQUIREMENTS: tuple[str, ...] = (
    "一份可提交的来源清单：每条含 DOI/URL、页码、表号或图号、许可状态，"
    "且不含任何原始测量值。",
    "一个「元数据先行」的导入流程：先登记 PublicSourceRecord，"
    "再由使用者提供数据文件，导入时用已登记的列映射，不做任何猜测。",
    "读图数字化的不确定度模型：FIGURE_DIGITISATION 必须携带可量化的读数误差，"
    "否则其残差无法与本项目 7 % 级别的模型残差相区分。",
    "机器识别信息的最低门槛：公开来源常常缺少槽数或接法，"
    "需要明确在缺多少项时判定为 INSUFFICIENT_METADATA 而非 COMPATIBLE_REFERENCE。",
    "针对同一台公开机器的多来源交叉核对：同一机器的两篇独立测量若彼此矛盾，"
    "软件必须显示矛盾，而不是取平均。",
    "术语归一化：不同文献对 Ke 的定义（线/相、有效值/峰值、机械/电气角速度）"
    "差异巨大，需要在导入时强制声明，而不是在比较时假设。",
    "一份明确的政策文档：说明哪些来源已被检视、哪些被排除及原因，"
    "使「没有引用某篇文献」是一个可审计的决定而不是遗漏。",
)
