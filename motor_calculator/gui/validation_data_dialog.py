"""Phase 11A: the validation data manager.

Its own window, kept away from the FEA validation dialog on purpose. Importing a
bench measurement and driving a finite-element solver are different activities
done by different people at different times, and putting a CSV import button
next to a mesh control invites the exact conflation this project spends its
effort avoiding.

The dialog holds no engineering logic. Every decision -- what a dataset is,
whether it may validate the design, what the empty state says -- comes from
:mod:`motor_calculator.experiment`. The ``build_*`` methods are separated from
the widgets so the whole surface can be exercised headlessly.
"""

from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any, Callable, Mapping

from ..experiment.analysis import Connection
from ..experiment.comparison import NO_DATA_MESSAGE_ZH, NO_EXPERIMENTAL_DATA
from ..experiment.compatibility import COMPATIBILITY_LABELS_ZH
from ..experiment.persistence import AVAILABILITY_MESSAGES_ZH, DatasetStore
from ..experiment.schema import (
    TEST_TYPE_LABELS_ZH,
    Citation,
    DatasetMetadata,
    MachineIdentity,
    RedistributionStatus,
    TestType,
    UNKNOWN,
)
from ..experiment.service import LoadedDataset, ValidationDataService
from ..experiment.sources import (
    SOURCE_TYPE_CAVEATS_ZH,
    SOURCE_TYPE_LABELS_ZH,
    DatasetSourceType,
)
from ..experiment.templates import TEMPLATES, export_template

VALIDATION_DATA_DIALOG_VERSION = "phase11a.gui.validation_data.v1"

#: Shown above the dataset list whenever nothing experimental is loaded. The
#: state string is included verbatim so it is greppable and testable.
EMPTY_STATE_TEXT_ZH = NO_DATA_MESSAGE_ZH

INTRO_ZH = (
    "导入实验或公开参考测量数据，并与解析模型、有限元结果作同基比较。\n"
    "数据来源类别与机器一致性决定结论的强度；残差大小不会改变证据类别。"
)


@dataclass(frozen=True)
class DatasetRow:
    """One line in the dataset list, already rendered."""

    dataset_id: str
    title: str
    source_type: str
    source_label_zh: str
    test_type: str
    test_label_zh: str
    sample_count: int
    availability: str
    is_experimental: bool
    has_errors: bool


class ValidationDataDialog:
    """Import, enter, inspect and compare measurement datasets."""

    def __init__(
        self,
        master: tk.Misc,
        *,
        service: ValidationDataService,
        parameters_provider: Callable[[], Mapping[str, Any]],
        analytical_provider: Callable[[], Mapping[str, float | None]] | None = None,
        export_dir: Path | None = None,
        on_changed: Callable[[], None] | None = None,
        creator_dataset_root: str | Path | None = None,
    ) -> None:
        self.service = service
        self._parameters_provider = parameters_provider
        self._analytical_provider = analytical_provider
        self._export_dir = Path(export_dir) if export_dir else Path.cwd()
        self._on_changed = on_changed
        self._last_overview = None
        # Phase 11B. The raw public dataset is never shipped, so this is empty
        # until a user points it at their own copy.
        self._creator_root = creator_dataset_root
        self._creator_report = None

        self.window = tk.Toplevel(master)
        self.window.title("验证数据管理")
        self.window.geometry("960x740")

        ttk.Label(
            self.window, text=INTRO_ZH, wraplength=920, justify=tk.LEFT
        ).pack(anchor=tk.W, padx=10, pady=(10, 6))

        self.state_var = tk.StringVar(value=NO_EXPERIMENTAL_DATA)
        self.state_label = ttk.Label(
            self.window, textvariable=self.state_var, wraplength=920,
            justify=tk.LEFT, foreground="#8a6d1f",
        )
        self.state_label.pack(anchor=tk.W, padx=10, pady=(0, 6))

        self.tabs = ttk.Notebook(self.window)
        self.tabs.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 8))
        self._build_datasets_tab()
        self._build_manual_tab()
        self._build_metadata_tab()
        self._build_results_tab()
        self._build_public_reference_tab()

        ttk.Button(self.window, text="关闭", command=self.window.destroy).pack(
            side=tk.RIGHT, padx=10, pady=(0, 10)
        )
        self.refresh()

    # ------------------------------------------------------------------
    # Widgets
    # ------------------------------------------------------------------

    def _build_datasets_tab(self) -> None:
        frame = ttk.Frame(self.tabs, padding=8)
        self.tabs.add(frame, text="数据集")

        actions = ttk.Frame(frame)
        actions.pack(fill=tk.X, pady=(0, 6))
        self.import_button = ttk.Button(
            actions, text="导入 CSV 数据集...", command=self.import_dataset
        )
        self.import_button.pack(side=tk.LEFT)
        self.template_button = ttk.Button(
            actions, text="导出测量模板...", command=self.export_measurement_template
        )
        self.template_button.pack(side=tk.LEFT, padx=(6, 0))
        self.remove_button = ttk.Button(
            actions, text="移除所选", command=self.remove_selected
        )
        self.remove_button.pack(side=tk.LEFT, padx=(6, 0))

        ttk.Label(actions, text="测试类型").pack(side=tk.LEFT, padx=(16, 4))
        self.test_type_var = tk.StringVar(value=TEST_TYPE_LABELS_ZH[TestType.NO_LOAD_BACK_EMF])
        self.test_type_combo = ttk.Combobox(
            actions,
            textvariable=self.test_type_var,
            values=[TEST_TYPE_LABELS_ZH[test_type] for test_type in TEMPLATES],
            state="readonly",
            width=22,
        )
        self.test_type_combo.pack(side=tk.LEFT)

        columns = ("source", "test", "samples", "availability")
        self.tree = ttk.Treeview(frame, columns=columns, show="tree headings", height=9)
        self.tree.heading("#0", text="数据集")
        self.tree.heading("source", text="来源类别")
        self.tree.heading("test", text="测试类型")
        self.tree.heading("samples", text="样本数")
        self.tree.heading("availability", text="可用性")
        self.tree.column("#0", width=280)
        self.tree.column("samples", width=70, anchor=tk.E)
        self.tree.pack(fill=tk.BOTH, expand=True)
        self.tree.bind("<<TreeviewSelect>>", lambda _event: self._refresh_metadata_text())

        self.empty_var = tk.StringVar(value=EMPTY_STATE_TEXT_ZH)
        self.empty_label = ttk.Label(
            frame, textvariable=self.empty_var, wraplength=900,
            justify=tk.LEFT, foreground="#666666",
        )
        self.empty_label.pack(anchor=tk.W, pady=(6, 0))

    def _build_manual_tab(self) -> None:
        frame = ttk.Frame(self.tabs, padding=8)
        self.tabs.add(frame, text="手工录入")
        ttk.Label(
            frame,
            text=(
                "逐点录入测量值。每行一个测点，列之间用逗号分隔，"
                "顺序与下方提示一致。留空表示缺失，**不要填 0**。"
            ),
            wraplength=900, justify=tk.LEFT,
        ).pack(anchor=tk.W)

        self.manual_hint_var = tk.StringVar(value="speed_rpm, line_voltage_rms_v")
        ttk.Label(frame, textvariable=self.manual_hint_var, foreground="#444444").pack(
            anchor=tk.W, pady=(4, 2)
        )
        self.manual_text = tk.Text(frame, height=10, wrap=tk.NONE)
        self.manual_text.pack(fill=tk.BOTH, expand=True)

        row = ttk.Frame(frame)
        row.pack(fill=tk.X, pady=(6, 0))
        ttk.Label(row, text="数据集标题").pack(side=tk.LEFT)
        self.manual_title_var = tk.StringVar(value="手工录入测量")
        ttk.Entry(row, textvariable=self.manual_title_var, width=28).pack(side=tk.LEFT, padx=(4, 12))
        ttk.Label(row, text="来源类别").pack(side=tk.LEFT)
        self.manual_source_var = tk.StringVar(
            value=SOURCE_TYPE_LABELS_ZH[DatasetSourceType.USER_EXPERIMENT]
        )
        ttk.Combobox(
            row, textvariable=self.manual_source_var,
            values=[SOURCE_TYPE_LABELS_ZH[item] for item in DatasetSourceType],
            state="readonly", width=28,
        ).pack(side=tk.LEFT, padx=(4, 12))
        self.manual_add_button = ttk.Button(row, text="加入数据集", command=self.add_manual_entry)
        self.manual_add_button.pack(side=tk.LEFT)

        self.manual_status_var = tk.StringVar(value="")
        ttk.Label(frame, textvariable=self.manual_status_var, wraplength=900,
                  justify=tk.LEFT).pack(anchor=tk.W, pady=(4, 0))

    def _build_metadata_tab(self) -> None:
        frame = ttk.Frame(self.tabs, padding=8)
        self.tabs.add(frame, text="数据集元数据")
        self.metadata_text = tk.Text(frame, wrap=tk.WORD, height=24)
        self.metadata_text.pack(fill=tk.BOTH, expand=True)
        self.metadata_text.configure(state=tk.DISABLED)

    def _build_results_tab(self) -> None:
        frame = ttk.Frame(self.tabs, padding=8)
        self.tabs.add(frame, text="验证结果")
        actions = ttk.Frame(frame)
        actions.pack(fill=tk.X, pady=(0, 6))
        self.compare_button = ttk.Button(actions, text="重新比较", command=self.refresh)
        self.compare_button.pack(side=tk.LEFT)
        self.export_report_button = ttk.Button(
            actions, text="导出验证报告...", command=self.export_report
        )
        self.export_report_button.pack(side=tk.LEFT, padx=(6, 0))
        self.results_text = tk.Text(frame, wrap=tk.WORD)
        self.results_text.pack(fill=tk.BOTH, expand=True)
        self.results_text.configure(state=tk.DISABLED)

    def _build_public_reference_tab(self) -> None:
        """Phase 11B: the registered public reference sources.

        Kept separate from the imported-dataset tabs because a registered source
        is metadata that exists whether or not any data is present locally. The
        repository ships no raw measurements, so "registered but not configured"
        is the normal state and has to read as information, not as an error.
        """

        frame = ttk.Frame(self.tabs, padding=8)
        self.tabs.add(frame, text="公开参考源")

        row = ttk.Frame(frame)
        row.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(row, text="数据集目录").pack(side=tk.LEFT)
        self.creator_root_var = tk.StringVar(value=str(self._creator_root or ""))
        self.creator_root_entry = ttk.Entry(row, textvariable=self.creator_root_var, width=54)
        self.creator_root_entry.pack(side=tk.LEFT, padx=(4, 6))
        self.creator_browse_button = ttk.Button(
            row, text="浏览...", command=self.browse_creator_root
        )
        self.creator_browse_button.pack(side=tk.LEFT)
        self.creator_load_button = ttk.Button(
            row, text="读取", command=self.refresh_public_reference
        )
        self.creator_load_button.pack(side=tk.LEFT, padx=(6, 0))
        # Phase 11B Step 19: a live consumer of the topology firewall. The button
        # exists so the refusal is a production path a user can actually reach,
        # rather than a library function nothing calls.
        self.creator_project_button = ttk.Button(
            row, text="据此建立项目", command=self.create_project_from_public_source
        )
        self.creator_project_button.pack(side=tk.LEFT, padx=(12, 0))

        self.creator_state_var = tk.StringVar(value="")
        ttk.Label(
            frame, textvariable=self.creator_state_var, wraplength=900,
            justify=tk.LEFT, foreground="#8a6d1f",
        ).pack(anchor=tk.W, pady=(0, 6))

        self.creator_tabs = ttk.Notebook(frame)
        self.creator_tabs.pack(fill=tk.BOTH, expand=True)
        self.creator_views: dict[str, tk.Text] = {}
        for key, label in (
            ("source", "来源与机器"),
            ("back_emf", "反电动势波形"),
            ("cogging", "齿槽转矩"),
            ("no_load", "空载损耗"),
            ("parameters", "等效电路参数"),
            ("drive_cycle", "行驶工况"),
        ):
            tab = ttk.Frame(self.creator_tabs, padding=6)
            self.creator_tabs.add(tab, text=label)
            widget = tk.Text(tab, wrap=tk.NONE, height=22)
            scroll = ttk.Scrollbar(tab, orient=tk.VERTICAL, command=widget.yview)
            widget.configure(yscrollcommand=scroll.set, state=tk.DISABLED)
            scroll.pack(side=tk.RIGHT, fill=tk.Y)
            widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            self.creator_views[key] = widget

    # ------------------------------------------------------------------
    # Public reference (Phase 11B)
    # ------------------------------------------------------------------

    def browse_creator_root(self, path: str | Path | None = None):
        if path is None:
            path = filedialog.askdirectory(
                parent=self.window, title="选择 CREATOR PMSM 数据集目录"
            )
            if not path:
                return None
        self.creator_root_var.set(str(path))
        return self.refresh_public_reference()

    def build_public_reference_report(self):
        """The CREATOR evidence report, present or absent. Headless."""

        from ..experiment.creator_evidence import build_report

        root = str(self.creator_root_var.get()).strip() if hasattr(self, "creator_root_var") else ""
        try:
            parameters = dict(self._parameters_provider())
        except Exception:  # noqa: BLE001 - the view must render regardless
            parameters = {}
        return build_report(root or None, parameters)

    def render_public_reference(self, report) -> dict:
        """Every public-reference view's text, keyed by tab."""

        from ..experiment import creator_evidence as evidence

        return {
            "source": evidence.render_header_zh(report),
            "back_emf": evidence.render_back_emf_zh(report),
            "cogging": evidence.render_cogging_zh(report),
            "no_load": evidence.render_no_load_zh(report),
            "parameters": evidence.render_parameters_zh(report),
            "drive_cycle": evidence.render_drive_cycle_zh(report),
        }

    def refresh_public_reference(self):
        report = self.build_public_reference_report()
        self._creator_report = report
        self.creator_state_var.set(
            f"{report.state}　|　机器一致性：{report.compatibility.status.value}"
            f"　|　{report.afpm_claim}"
        )
        for key, text in self.render_public_reference(report).items():
            widget = self.creator_views[key]
            widget.configure(state=tk.NORMAL)
            widget.delete("1.0", "end")
            widget.insert("1.0", text)
            widget.configure(state=tk.DISABLED)
        return report

    def create_project_from_public_source(self):
        """Refuse to build an AFPM project from a radial-flux source.

        Phase 11B-A established that the production kernel is axial-flux only,
        so there is no assignment of CREATOR's radial geometry to the AFPM
        fields that preserves the physics. The refusal is explicit and names the
        reason; silently producing a project would be far worse, because the
        numbers would look valid.
        """

        from ..experiment.topology import (
            TopologyMismatchError,
            reject_afpm_project_construction,
        )

        report = getattr(self, "_creator_report", None) or self.build_public_reference_report()
        try:
            reject_afpm_project_construction(
                report.summary.topology, context="AFPM project construction"
            )
        except TopologyMismatchError as error:
            messagebox.showerror("拓扑不匹配", str(error), parent=self.window)
            return str(error)
        return None

    # ------------------------------------------------------------------
    # Headless-testable content
    # ------------------------------------------------------------------

    def selected_test_type(self) -> TestType:
        label = str(self.test_type_var.get()).strip()
        for test_type, text in TEST_TYPE_LABELS_ZH.items():
            if text == label:
                return test_type
        return TestType.NO_LOAD_BACK_EMF

    def selected_manual_source(self) -> DatasetSourceType:
        label = str(self.manual_source_var.get()).strip()
        for source_type, text in SOURCE_TYPE_LABELS_ZH.items():
            if text == label:
                return source_type
        return DatasetSourceType.USER_EXPERIMENT

    def dataset_rows(self) -> tuple[DatasetRow, ...]:
        """The dataset list. Test fixtures are excluded from the production UI."""

        rows = []
        for item in self.service.production_datasets():
            metadata = item.metadata
            rows.append(
                DatasetRow(
                    dataset_id=item.dataset_id,
                    title=str(metadata.title),
                    source_type=metadata.source_type.value,
                    source_label_zh=SOURCE_TYPE_LABELS_ZH[metadata.source_type],
                    test_type=metadata.test_type.value,
                    test_label_zh=TEST_TYPE_LABELS_ZH[metadata.test_type],
                    sample_count=len(item.rows),
                    availability=item.availability.value,
                    is_experimental=metadata.is_experimental,
                    has_errors=bool(item.import_errors),
                )
            )
        return tuple(rows)

    def build_comparisons(self):
        """Every comparison the loaded datasets currently support."""

        parameters = dict(self._parameters_provider())
        analytical = dict(self._analytical_provider() or {}) if self._analytical_provider else {}
        comparisons = []
        for item in self.service.production_datasets():
            if not item.is_usable:
                continue
            config = item.reference.comparison_config
            connection = Connection(config.get("connection", Connection.UNKNOWN))
            test_type = item.metadata.test_type
            comparison = None
            if test_type is TestType.NO_LOAD_BACK_EMF:
                comparison = self.service.build_back_emf_comparison(
                    item,
                    project_parameters=parameters,
                    analytical_ke_v_per_rad_s=analytical.get("ke_phase_rms_v_per_rad_s"),
                    fea_ke_v_per_rad_s=analytical.get("fea_ke_phase_rms_v_per_rad_s"),
                    connection=connection,
                )
            elif test_type is TestType.PHASE_RESISTANCE:
                comparison = self.service.build_resistance_comparison(
                    item,
                    project_parameters=parameters,
                    analytical_phase_resistance_ohm=analytical.get("phase_resistance_ohm"),
                    connection=connection,
                )
            elif test_type is TestType.TORQUE_CURRENT:
                comparison = self.service.build_torque_comparison(
                    item,
                    project_parameters=parameters,
                    analytical_kt_nm_per_a=analytical.get("kt_nm_per_a"),
                )
            elif test_type is TestType.EFFICIENCY:
                comparison = self.service.build_efficiency_comparison(
                    item,
                    project_parameters=parameters,
                    analytical_efficiency=analytical.get("efficiency"),
                )
            if comparison is not None:
                comparisons.append(comparison)
        return tuple(comparisons)

    def build_overview(self):
        return self.service.build_overview(self.build_comparisons())

    def render_results_zh(self, overview) -> str:
        """The comparison view's text. Says NO_EXPERIMENTAL_DATA when true."""

        if not overview.comparisons:
            return overview.message_zh
        lines = [overview.message_zh, ""]
        for comparison in overview.comparisons:
            compatibility = comparison.compatibility
            lines.extend(
                [
                    "=" * 58,
                    f"{comparison.quantity_label_zh}（{comparison.unit}）",
                    f"  比较基准：{comparison.basis_zh}",
                    f"  结论：{comparison.claim_label_zh}",
                    f"  理由：{comparison.claim_reason_zh}",
                    "",
                    f"  解析模型        {_value(comparison.analytical)}",
                    f"  数值有限元      {_value(comparison.fea)}",
                    f"  实验/参考       {_value(comparison.measured)}"
                    + (
                        f"   [{comparison.measured.evidence_label}]"
                        if comparison.measured is not None
                        else ""
                    ),
                ]
            )
            if comparison.measured is not None and comparison.measured.sample_count:
                lines.append(f"  样本数          {comparison.measured.sample_count}")
            if comparison.measured is not None and comparison.measured.note_zh:
                lines.append(f"  拟合质量        {comparison.measured.note_zh}")
            for residual in comparison.residuals:
                relative = (
                    "不适用"
                    if residual.relative_percent is None
                    else f"{residual.relative_percent:+.3f} %"
                )
                lines.append(
                    f"  残差 {residual.subject} vs {residual.reference}："
                    f"{residual.absolute:+.6g}（{relative}）"
                )
            if compatibility is not None:
                lines.extend(
                    [
                        "",
                        f"  机器一致性：{COMPATIBILITY_LABELS_ZH[compatibility.status]}",
                        f"    {compatibility.reason_zh}",
                        f"    {compatibility.permitted_use_zh}",
                    ]
                )
            if comparison.dataset is not None:
                lines.append(
                    f"  数据来源：{SOURCE_TYPE_LABELS_ZH[comparison.dataset.source_type]}"
                )
                lines.append(f"    {SOURCE_TYPE_CAVEATS_ZH[comparison.dataset.source_type]}")
            if comparison.limitations_zh:
                lines.append("  局限：")
                lines.extend(f"    · {item}" for item in comparison.limitations_zh)
            lines.append(f"  标定状态：{comparison.calibration_status}")
            lines.append("")
        return "\n".join(lines)

    def render_metadata_zh(self, dataset: LoadedDataset | None) -> str:
        if dataset is None:
            return "请选择一个数据集以查看其元数据。"
        metadata = dataset.metadata
        machine = metadata.machine
        citation = metadata.citation
        lines = [
            f"数据集 ID：{metadata.dataset_id}",
            f"标题：{metadata.title}",
            f"来源类别：{metadata.source_type.value} —— {SOURCE_TYPE_LABELS_ZH[metadata.source_type]}",
            f"  {SOURCE_TYPE_CAVEATS_ZH[metadata.source_type]}",
            f"测试类型：{metadata.test_type.value} —— {TEST_TYPE_LABELS_ZH[metadata.test_type]}",
            f"数据来路：{metadata.data_provenance}",
            f"样本数：{len(dataset.rows)}",
            f"可用性：{dataset.availability.value} —— "
            f"{AVAILABILITY_MESSAGES_ZH[dataset.availability]}",
            f"文件哈希：{metadata.raw_file_hash}",
            f"文件名：{metadata.raw_file_name}",
            f"导入时间（UTC）：{metadata.import_timestamp_utc}",
            f"测量日期：{metadata.measurement_date}",
            f"操作者：{metadata.operator}",
            f"仪器：{metadata.instrument}",
            f"备注：{metadata.notes}",
            "",
            "机器识别信息（缺失项保持 UNKNOWN，不作猜测）：",
            f"  描述：{machine.description}",
            f"  编号：{machine.machine_id}",
            f"  拓扑：{machine.topology}",
            f"  极数：{machine.pole_count}    槽数：{machine.slot_count}    相数：{machine.phases}",
            f"  接法：{machine.connection}    每相匝数：{machine.turns_per_phase}",
            f"  额定转速：{machine.rated_speed_rpm}    额定功率：{machine.rated_power_w}",
            f"  已知字段数：{machine.known_field_count}",
            "",
            "引用与许可：",
            f"  标题：{citation.title}",
            f"  作者：{citation.authors}",
            f"  出处：{citation.publication}（{citation.year}）",
            f"  DOI：{citation.doi}",
            f"  URL：{citation.url}",
            f"  位置：{citation.page} / {citation.table_or_figure}",
            f"  许可：{citation.license}",
            f"  再分发：{citation.redistribution.value}",
        ]
        if dataset.import_errors:
            lines.extend(["", "导入错误："])
            lines.extend(f"  · {error}" for error in dataset.import_errors)
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def import_dataset(self, path: str | Path | None = None, **kwargs: Any):
        """Import a CSV. ``path`` is supplied directly by the smoke harness."""

        if path is None:
            selected = filedialog.askopenfilename(
                parent=self.window,
                title="选择测量数据 CSV",
                filetypes=(("CSV", "*.csv"), ("所有文件", "*.*")),
            )
            if not selected:
                return None
            path = selected
        test_type = kwargs.pop("test_type", None) or self.selected_test_type()
        metadata = kwargs.pop("metadata", None) or DatasetMetadata(
            dataset_id=kwargs.pop("dataset_id", Path(path).stem),
            title=kwargs.pop("title", Path(path).name),
            source_type=kwargs.pop("source_type", DatasetSourceType.USER_EXPERIMENT),
            test_type=test_type,
            machine=kwargs.pop("machine", MachineIdentity()),
            citation=kwargs.pop("citation", Citation()),
        )
        try:
            loaded = self.service.add_from_csv(path, metadata=metadata, **kwargs)
        except (OSError, ValueError) as error:
            messagebox.showerror("导入失败", str(error), parent=self.window)
            return None
        if loaded.import_errors:
            messagebox.showwarning(
                "导入存在问题",
                "该文件已登记，但存在以下问题，在修正之前不会参与比较：\n\n"
                + "\n".join(loaded.import_errors[:10]),
                parent=self.window,
            )
        self.refresh()
        if self._on_changed is not None:
            self._on_changed()
        return loaded

    def add_manual_entry(self, text: str | None = None):
        """Parse the manual-entry box into a dataset."""

        raw = self.manual_text.get("1.0", "end") if text is None else text
        test_type = self.selected_test_type()
        template = TEMPLATES.get(test_type)
        names = [column.name for column in template.columns] if template else []
        records: list[dict[str, float]] = []
        problems: list[str] = []
        for index, line in enumerate(raw.splitlines(), 1):
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            cells = [cell.strip() for cell in line.split(",")]
            record: dict[str, float] = {}
            for name, cell in zip(names, cells):
                if not cell or cell.lower() in {"na", "n/a", "-"}:
                    continue
                try:
                    record[name] = float(cell)
                except ValueError:
                    problems.append(f"第 {index} 行，{name}：无法解析 {cell!r}")
            if record:
                records.append(record)
        if problems:
            self.manual_status_var.set("；".join(problems[:5]))
            return None
        if not records:
            self.manual_status_var.set("没有可用的录入行。")
            return None
        metadata = DatasetMetadata(
            dataset_id=f"manual.{test_type.value.lower()}.{len(self.service.datasets) + 1}",
            title=str(self.manual_title_var.get()).strip() or "手工录入测量",
            source_type=self.selected_manual_source(),
            test_type=test_type,
        )
        loaded = self.service.add_manual(records, metadata=metadata)
        self.manual_status_var.set(f"已加入 {len(records)} 个测点。")
        self.refresh()
        if self._on_changed is not None:
            self._on_changed()
        return loaded

    def export_measurement_template(self, destination: str | Path | None = None):
        test_type = self.selected_test_type()
        if destination is None:
            destination = filedialog.asksaveasfilename(
                parent=self.window,
                title="导出测量模板",
                defaultextension=".csv",
                initialfile=f"template_{test_type.value.lower()}.csv",
                initialdir=str(self._export_dir),
            )
            if not destination:
                return None
        return export_template(test_type, destination)

    def remove_selected(self) -> bool:
        selection = self.tree.selection()
        if not selection:
            return False
        removed = any(self.service.remove(item) for item in selection)
        self.refresh()
        if removed and self._on_changed is not None:
            self._on_changed()
        return removed

    def export_report(self, destination: str | Path | None = None):
        from ..experiment.report import export_validation_report
        from ..version import APPLICATION_VERSION
        from datetime import datetime, timezone

        overview = self._last_overview or self.build_overview()
        return export_validation_report(
            overview,
            destination or self._export_dir,
            application_version=APPLICATION_VERSION,
            generated_at_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        )

    # ------------------------------------------------------------------

    def selected_dataset(self) -> LoadedDataset | None:
        selection = self.tree.selection()
        if not selection:
            return None
        return self.service.get(selection[0])

    def _refresh_metadata_text(self) -> None:
        self.metadata_text.configure(state=tk.NORMAL)
        self.metadata_text.delete("1.0", "end")
        self.metadata_text.insert("1.0", self.render_metadata_zh(self.selected_dataset()))
        self.metadata_text.configure(state=tk.DISABLED)

    def refresh(self) -> None:
        rows = self.dataset_rows()
        self.tree.delete(*self.tree.get_children())
        for row in rows:
            self.tree.insert(
                "", "end", iid=row.dataset_id, text=row.title,
                values=(
                    row.source_label_zh,
                    row.test_label_zh,
                    row.sample_count,
                    row.availability + ("（有导入错误）" if row.has_errors else ""),
                ),
            )

        overview = self.build_overview()
        self._last_overview = overview
        self.state_var.set(
            f"{overview.state}：{overview.message_zh.splitlines()[0]}"
        )
        self.state_label.configure(
            foreground="#2f6f4f" if overview.has_experimental_data else "#8a6d1f"
        )
        self.empty_var.set("" if rows else EMPTY_STATE_TEXT_ZH)

        template = TEMPLATES.get(self.selected_test_type())
        if template is not None:
            self.manual_hint_var.set(
                "列顺序：" + ", ".join(column.name for column in template.columns)
            )

        self.results_text.configure(state=tk.NORMAL)
        self.results_text.delete("1.0", "end")
        self.results_text.insert("1.0", self.render_results_zh(overview))
        self.results_text.configure(state=tk.DISABLED)
        self._refresh_metadata_text()
        self.refresh_public_reference()


def _value(entry) -> str:
    if entry is None or entry.value is None:
        return "不可用"
    return f"{entry.value:.6g} {entry.unit}"
