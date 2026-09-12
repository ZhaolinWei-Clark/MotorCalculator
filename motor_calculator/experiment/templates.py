"""Phase 11A: the CSV a user takes to the bench.

A template is the cheapest possible way to stop the ambiguity problem before it
starts: if the file the user fills in already says ``line_voltage_rms_v``, the
importer never has to refuse a column called ``Voltage``.

Two things each template does deliberately.

**Optional columns are offered, not required.** The Ke template lists both line
and phase voltage. Filling in either is enough; the parser reads whichever is
present and says which it used. Demanding both would force a user to compute one
from the other by hand, which is exactly the sqrt(3) mistake the template exists
to avoid.

**The header comments travel with the file.** A template carries its units, its
test conditions and the meaning of each column as ``#`` comments, which the
importer skips. A file that comes back six months later still explains itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .schema import TestType

TEMPLATE_SCHEMA_VERSION = "phase11a.experiment.template.v1"


@dataclass(frozen=True)
class TemplateColumn:
    name: str
    unit: str
    required: bool
    note_zh: str


@dataclass(frozen=True)
class MeasurementTemplate:
    test_type: TestType
    title_zh: str
    columns: tuple[TemplateColumn, ...]
    procedure_zh: tuple[str, ...]
    example_rows: tuple[tuple[str, ...], ...] = ()

    @property
    def header_line(self) -> str:
        return ",".join(f"{column.name} ({column.unit})" for column in self.columns)


TEMPLATES: dict[TestType, MeasurementTemplate] = {
    TestType.NO_LOAD_BACK_EMF: MeasurementTemplate(
        test_type=TestType.NO_LOAD_BACK_EMF,
        title_zh="Ke / 反电动势测试",
        columns=(
            TemplateColumn("speed_rpm", "rpm", True, "机械转速，由外部原动机拖动"),
            TemplateColumn("line_voltage_rms_v", "V", False,
                           "线电压有效值。与相电压二选一即可，不需要两者都填"),
            TemplateColumn("phase_voltage_rms_v", "V", False,
                           "相电压有效值。与线电压二选一即可"),
            TemplateColumn("temperature_c", "degC", False, "绕组或环境温度"),
        ),
        procedure_zh=(
            "电机不接负载、不接驱动器，由外部原动机拖动至各转速。",
            "至少测 4 个转速点，覆盖尽可能宽的转速范围：单点无法判断线性度。",
            "记录线电压或相电压之一即可，但必须明确是哪一个，且是有效值还是峰值。",
            "填写绕组接法（Y 或角接）到数据集元数据中：线/相换算需要它。",
            "若使用示波器，注意区分峰值与有效值；本软件不会按数值大小猜测。",
        ),
    ),
    TestType.PHASE_RESISTANCE: MeasurementTemplate(
        test_type=TestType.PHASE_RESISTANCE,
        title_zh="相电阻测试",
        columns=(
            TemplateColumn("measured_resistance_ohm", "Ohm", False,
                           "端子间实测电阻。与施加电压/电流二选一"),
            TemplateColumn("applied_voltage_v", "V", False, "四线法施加的直流电压"),
            TemplateColumn("applied_current_a", "A", False, "四线法施加的直流电流"),
            TemplateColumn("temperature_c", "degC", False,
                           "测量时的绕组温度。没有它就无法做任何温度归一化"),
        ),
        procedure_zh=(
            "使用四线（开尔文）法，避免引线与接触电阻进入读数。",
            "记录的是**端子间**电阻；相电阻由接法折算（Y 接 /2，角接 ×3/2）。",
            "务必填写绕组接法：未知接法时本软件不会给出相电阻。",
            "记录温度。铜电阻随温度变化明显，缺温度时不会做任何修正。",
            "可测量多对端子并多次记录，本软件取平均并在离散度较大时提示。",
        ),
    ),
    TestType.TORQUE_CURRENT: MeasurementTemplate(
        test_type=TestType.TORQUE_CURRENT,
        title_zh="转矩-电流测试",
        columns=(
            TemplateColumn("speed_rpm", "rpm", False, "测试转速，尽量保持恒定"),
            TemplateColumn("torque_nm", "Nm", True, "测功机读取的轴端转矩"),
            TemplateColumn("phase_current_rms_a", "A", False, "相电流有效值"),
            TemplateColumn("id_a", "A", False, "d 轴电流（若为 FOC 驱动）"),
            TemplateColumn("iq_a", "A", False, "q 轴电流（若为 FOC 驱动）"),
            TemplateColumn("temperature_c", "degC", False, "磁体或绕组温度"),
        ),
        procedure_zh=(
            "尽量在同一转速下改变电流，跨转速的斜率是综合结果而非常数。",
            "明确电流的定义：相有效值、峰值、还是 q 轴分量，三者互不相同。",
            "若为 FOC 驱动，同时记录 id：id ≠ 0 时转矩不只由 iq 决定。",
            "记录温度：磁体温度变化会改变磁链，进而改变转矩常数。",
            "本软件不会在电流语义未声明时把该斜率称作 Kt。",
        ),
    ),
    TestType.EFFICIENCY: MeasurementTemplate(
        test_type=TestType.EFFICIENCY,
        title_zh="效率测试",
        columns=(
            TemplateColumn("speed_rpm", "rpm", True, "机械转速"),
            TemplateColumn("torque_nm", "Nm", True, "轴端转矩"),
            TemplateColumn("dc_bus_voltage_v", "V", False, "直流母线电压"),
            TemplateColumn("dc_bus_current_a", "A", False, "直流母线电流"),
            TemplateColumn("input_power_w", "W", False,
                           "若有功率分析仪实测输入功率，请填此列；本软件不会覆盖它"),
            TemplateColumn("output_power_w", "W", False, "若直接实测输出功率，请填此列"),
            TemplateColumn("efficiency", "1", False, "若数据源直接给出效率，请填此列"),
            TemplateColumn("temperature_c", "degC", False, "温度"),
        ),
        procedure_zh=(
            "注意测量边界：用母线功率算出的是**逆变器+电机**整体效率。",
            "若要得到电机本身的效率，需用功率分析仪测电机端三相输入功率。",
            "实测值与推导值分别保留：本软件不会用推导值覆盖实测值。",
            "效率以比值给出（0.92），若填百分数请在表头标注单位 (%)。",
        ),
    ),
}


def build_template_csv(test_type: TestType | str) -> str:
    """The template file's text, comments included."""

    template = TEMPLATES[TestType(test_type)]
    lines = [
        f"# {template.title_zh} —— 测量数据模板",
        f"# 模板版本：{TEMPLATE_SCHEMA_VERSION}",
        f"# 测试类型：{template.test_type.value}",
        "#",
        "# 以 # 开头的行会被导入器忽略，可以保留。空行也会被忽略。",
        "# 缺失值请留空，或填 NA / n/a。**不要填 0**：0 是一个测量值。",
        "#",
        "# 列说明：",
    ]
    lines.extend(
        f"#   {column.name} [{column.unit}] "
        f"{'（必填）' if column.required else '（可选）'} —— {column.note_zh}"
        for column in template.columns
    )
    lines.extend(["#", "# 测试步骤与注意事项："])
    lines.extend(f"#   {index}. {step}" for index, step in enumerate(template.procedure_zh, 1))
    lines.extend(
        [
            "#",
            "# 请同时在软件的「数据集元数据」中填写：机器识别信息（极数/槽数/相数/",
            "# 接法/匝数）、数据来源类别、测试日期与操作者。缺失项保持 UNKNOWN，",
            "# 不要猜测填写。",
            "#",
            template.header_line,
        ]
    )
    lines.extend(",".join(row) for row in template.example_rows)
    return "\n".join(lines) + "\n"


def export_template(test_type: TestType | str, destination: str | Path) -> Path:
    """Write a template next to wherever the user wants it."""

    path = Path(destination)
    if path.is_dir():
        path = path / f"template_{TestType(test_type).value.lower()}.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_template_csv(test_type), encoding="utf-8")
    return path


def available_templates() -> tuple[MeasurementTemplate, ...]:
    return tuple(TEMPLATES[test_type] for test_type in TEMPLATES)
