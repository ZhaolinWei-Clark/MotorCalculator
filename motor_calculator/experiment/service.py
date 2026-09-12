"""Phase 11A: the session's datasets, and the comparisons they support.

All of the decision-making lives in the modules this one calls. The service
exists so that the GUI holds no logic at all: every gate a user could hit --
whether a dataset is admissible, whether it may validate the design, what the
no-data state says -- is decided here and can be exercised without a Tk display.

The service never *creates* evidence. It holds datasets, asks the analysis
modules what they say, asks the compatibility layer whether it counts, and
assembles the result.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from .analysis import (
    AnalysisError,
    BackEmfResult,
    Connection,
    EfficiencyResult,
    ResistanceResult,
    SpeedBasis,
    TorqueCurrentResult,
    analyze_back_emf,
    analyze_efficiency,
    analyze_phase_resistance,
    analyze_torque_current,
)
from .columns import VoltageBasis
from .comparison import (
    QuantityComparison,
    ValidationOverview,
    analytical_entry,
    build_overview,
    build_quantity_comparison,
    fea_entry,
    measurement_entry,
)
from .compatibility import (
    CompatibilityAssessment,
    assess_compatibility,
    project_machine_identity,
)
from .csv_import import ImportedDataset, MeasurementRow, import_csv_file, rows_from_records
from .fixtures import require_production_admissible
from .persistence import (
    DatasetAvailability,
    DatasetReference,
    DatasetStore,
    USABLE_AVAILABILITY,
    from_preferences,
    to_preferences,
)
from .schema import DatasetMetadata, MachineIdentity, TestType, file_sha256

EXPERIMENT_SERVICE_SCHEMA_VERSION = "phase11a.experiment.service.v1"


@dataclass(frozen=True)
class LoadedDataset:
    """One dataset held in the session, with its rows if they are available."""

    reference: DatasetReference
    rows: tuple[MeasurementRow, ...]
    availability: DatasetAvailability
    import_errors: tuple[str, ...] = ()

    @property
    def metadata(self) -> DatasetMetadata:
        return self.reference.metadata

    @property
    def dataset_id(self) -> str:
        return self.reference.dataset_id

    @property
    def is_usable(self) -> bool:
        return self.availability in USABLE_AVAILABILITY and bool(self.rows)


@dataclass
class ValidationDataService:
    """Holds the session's datasets and produces the validation view."""

    store: DatasetStore
    datasets: list[LoadedDataset] = field(default_factory=list)
    #: Non-fatal problems encountered restoring a project, kept for display.
    load_warnings: tuple[str, ...] = ()

    # -- dataset lifecycle ------------------------------------------------

    def add_from_csv(
        self,
        path: str | Path,
        *,
        metadata: DatasetMetadata,
        column_mapping: Mapping[str, str] | None = None,
        column_units: Mapping[str, str] | None = None,
        comparison_config: Mapping[str, Any] | None = None,
    ) -> LoadedDataset:
        """Import a file, copy it into the store, and hold the result.

        A file with any import error is still *held*, with its errors, so the
        user can see what is wrong. It is not usable until re-imported clean.
        """

        require_production_admissible(metadata)
        source = Path(path)
        imported = import_csv_file(
            source,
            test_type=metadata.test_type,
            column_mapping=column_mapping,
            column_units=column_units,
        )
        digest = imported.raw_sha256 or file_sha256(source)
        stored = self.store.store(source, digest)
        enriched = replace(
            metadata,
            raw_file_hash=digest,
            raw_file_name=source.name,
            import_timestamp_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            data_provenance=metadata.data_provenance
            if metadata.data_provenance != "UNSPECIFIED"
            else "CSV_IMPORT",
        )
        reference = DatasetReference(
            dataset_id=enriched.dataset_id,
            metadata=enriched,
            stored_relative_path=stored,
            expected_sha256=digest,
            column_mapping=dict(column_mapping or {}),
            column_units=dict(column_units or {}),
            comparison_config=dict(comparison_config or {}),
        )
        loaded = LoadedDataset(
            reference=reference,
            rows=imported.rows if imported.ok else (),
            availability=DatasetAvailability.AVAILABLE,
            import_errors=tuple(str(error) for error in imported.errors),
        )
        self.datasets.append(loaded)
        return loaded

    def add_manual(
        self,
        records: Sequence[Mapping[str, float]],
        *,
        metadata: DatasetMetadata,
        comparison_config: Mapping[str, Any] | None = None,
    ) -> LoadedDataset:
        """Hold a manually entered dataset. Stored inline, not as a file."""

        require_production_admissible(metadata)
        rows = rows_from_records(records)
        enriched = replace(
            metadata,
            import_timestamp_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            data_provenance="MANUAL_ENTRY",
        )
        reference = DatasetReference(
            dataset_id=enriched.dataset_id,
            metadata=enriched,
            stored_relative_path=None,
            expected_sha256=None,
            column_mapping={},
            column_units={},
            comparison_config=dict(comparison_config or {}),
            inline_rows=tuple(dict(record) for record in records),
        )
        loaded = LoadedDataset(
            reference=reference, rows=rows, availability=DatasetAvailability.INLINE
        )
        self.datasets.append(loaded)
        return loaded

    def remove(self, dataset_id: str) -> bool:
        before = len(self.datasets)
        self.datasets = [item for item in self.datasets if item.dataset_id != dataset_id]
        return len(self.datasets) != before

    def get(self, dataset_id: str) -> LoadedDataset | None:
        for item in self.datasets:
            if item.dataset_id == dataset_id:
                return item
        return None

    def datasets_for(self, test_type: TestType) -> tuple[LoadedDataset, ...]:
        return tuple(
            item for item in self.datasets if item.metadata.test_type is TestType(test_type)
        )

    # -- persistence ------------------------------------------------------

    def to_preferences(self) -> dict[str, Any]:
        return to_preferences([item.reference for item in self.datasets])

    def restore(self, preferences: Mapping[str, Any] | None) -> tuple[str, ...]:
        """Rebuild the session's datasets from a loaded project.

        A referenced file that is gone, or whose bytes changed, produces a held
        dataset in that state rather than an exception: the metadata is what
        tells the user what was lost, so it must survive the loss.
        """

        references, problems = from_preferences(preferences)
        self.datasets = []
        warnings = list(problems)
        for reference in references:
            availability = self.store.availability(reference)
            rows: tuple[MeasurementRow, ...] = ()
            errors: tuple[str, ...] = ()
            if availability is DatasetAvailability.INLINE:
                rows = rows_from_records(reference.inline_rows)
            elif availability is DatasetAvailability.AVAILABLE:
                path = self.store.resolve(reference.stored_relative_path)
                imported = import_csv_file(
                    path,
                    test_type=reference.metadata.test_type,
                    column_mapping=reference.column_mapping,
                    column_units=reference.column_units,
                )
                rows = imported.rows if imported.ok else ()
                errors = tuple(str(error) for error in imported.errors)
            else:
                warnings.append(
                    f"数据集「{reference.metadata.title}」"
                    f"（{reference.dataset_id}）：{availability.value}"
                )
            self.datasets.append(
                LoadedDataset(
                    reference=reference,
                    rows=rows,
                    availability=availability,
                    import_errors=errors,
                )
            )
        self.load_warnings = tuple(warnings)
        return self.load_warnings

    # -- analysis ---------------------------------------------------------

    def analyze(self, dataset: LoadedDataset, **overrides: Any):
        """Run the analysis a dataset's test type calls for.

        Returns ``None`` when the test type has no implementation yet, which is
        a stated state rather than an error: the dataset is stored and shown, it
        simply has nothing computed from it.
        """

        if not dataset.is_usable:
            return None
        config = {**dataset.reference.comparison_config, **overrides}
        test_type = dataset.metadata.test_type
        if test_type is TestType.NO_LOAD_BACK_EMF:
            return analyze_back_emf(
                dataset.rows,
                target_voltage_basis=VoltageBasis(
                    config.get("voltage_basis", VoltageBasis.PHASE_RMS)
                ),
                speed_basis=SpeedBasis(
                    config.get("speed_basis", SpeedBasis.MECHANICAL_RAD_PER_S)
                ),
                pole_pairs=config.get("pole_pairs"),
                connection=Connection(config.get("connection", Connection.UNKNOWN)),
                force_zero_intercept=bool(config.get("force_zero_intercept", False)),
                force_reason_zh=str(config.get("force_reason_zh", "")),
            )
        if test_type is TestType.PHASE_RESISTANCE:
            return analyze_phase_resistance(
                dataset.rows,
                connection=Connection(config.get("connection", Connection.UNKNOWN)),
                normalize_to_temperature_c=config.get("normalize_to_temperature_c"),
            )
        if test_type is TestType.TORQUE_CURRENT:
            return analyze_torque_current(
                dataset.rows,
                current_semantics_known=bool(config.get("current_semantics_known", False)),
                operating_point_known=bool(config.get("operating_point_known", False)),
            )
        if test_type is TestType.EFFICIENCY:
            return analyze_efficiency(dataset.rows)
        return None

    # -- comparison -------------------------------------------------------

    def compatibility_for(
        self, dataset: LoadedDataset, project_parameters: Mapping[str, Any], **kwargs: Any
    ) -> CompatibilityAssessment:
        return assess_compatibility(
            dataset.metadata.machine,
            project_machine_identity(project_parameters, **kwargs),
        )

    def build_back_emf_comparison(
        self,
        dataset: LoadedDataset,
        *,
        project_parameters: Mapping[str, Any],
        analytical_ke_v_per_rad_s: float | None,
        fea_ke_v_per_rad_s: float | None = None,
        connection: Connection = Connection.UNKNOWN,
        project_connection: Any = None,
    ) -> QuantityComparison | None:
        """The Ke comparison: analytical, FEMM and measurement on one basis."""

        try:
            result = self.analyze(dataset, connection=connection)
        except AnalysisError:
            return None
        if not isinstance(result, BackEmfResult):
            return None

        compatibility = self.compatibility_for(
            dataset,
            project_parameters,
            connection=project_connection if project_connection is not None else connection.value,
        )
        limitations = list(result.warnings_zh)
        if result.excluded_rows:
            limitations.append(
                "以下行未参与拟合："
                + "、".join(f"第 {line} 行（{reason}）" for line, reason in result.excluded_rows)
            )
        for conversion in result.conversions:
            limitations.append(f"电压基准换算：{conversion.assumption_zh}")

        return build_quantity_comparison(
            quantity="ke_phase_rms_v_per_rad_s",
            quantity_label_zh="反电动势常数 Ke",
            unit="V/(rad/s)",
            basis_zh=(
                f"{result.voltage_basis.value} / {result.speed_basis.value}"
                "（三方使用同一基准）"
            ),
            analytical=analytical_entry(analytical_ke_v_per_rad_s, "V/(rad/s)"),
            fea=fea_entry(fea_ke_v_per_rad_s, "V/(rad/s)") if fea_ke_v_per_rad_s else None,
            measured=measurement_entry(
                result.ke_v_per_rad_s,
                "V/(rad/s)",
                metadata=dataset.metadata,
                sample_count=result.used_sample_count,
                note_zh=(
                    f"由 {result.used_sample_count} 个转速点回归得到，"
                    f"R² = {'不适用' if result.r_squared is None else f'{result.r_squared:.6f}'}，"
                    f"截距 = {result.intercept_v:.4g} V"
                ),
            ),
            dataset=dataset.metadata,
            compatibility=compatibility,
            limitations_zh=tuple(limitations),
        )

    def build_resistance_comparison(
        self,
        dataset: LoadedDataset,
        *,
        project_parameters: Mapping[str, Any],
        analytical_phase_resistance_ohm: float | None,
        connection: Connection = Connection.UNKNOWN,
    ) -> QuantityComparison | None:
        try:
            result = self.analyze(dataset, connection=connection)
        except AnalysisError:
            return None
        if not isinstance(result, ResistanceResult) or result.phase_resistance_ohm is None:
            return None
        compatibility = self.compatibility_for(
            dataset, project_parameters, connection=connection.value
        )
        return build_quantity_comparison(
            quantity="phase_resistance_ohm",
            quantity_label_zh="相电阻",
            unit="Ohm",
            basis_zh=f"每相直流电阻，{result.connection.value} 接法折算",
            analytical=analytical_entry(analytical_phase_resistance_ohm, "Ohm"),
            measured=measurement_entry(
                result.phase_resistance_ohm,
                "Ohm",
                metadata=dataset.metadata,
                sample_count=result.sample_count,
                note_zh=result.derivation_zh,
            ),
            dataset=dataset.metadata,
            compatibility=compatibility,
            limitations_zh=(
                *result.warnings_zh,
                (
                    f"测量温度 {result.measurement_temperature_c:.1f} °C"
                    if result.measurement_temperature_c is not None
                    else "数据中没有测量温度，任何温度归一化都不会被执行。"
                ),
                f"温度归一化：{result.normalization_provenance}",
            ),
        )

    def build_torque_comparison(
        self,
        dataset: LoadedDataset,
        *,
        project_parameters: Mapping[str, Any],
        analytical_kt_nm_per_a: float | None,
        **overrides: Any,
    ) -> QuantityComparison | None:
        try:
            result = self.analyze(dataset, **overrides)
        except AnalysisError:
            return None
        if not isinstance(result, TorqueCurrentResult):
            return None
        compatibility = self.compatibility_for(dataset, project_parameters)
        limitations = list(result.limitations_zh)
        if not result.supports_kt_claim:
            limitations.insert(
                0,
                "该斜率**不是**独立验证的 Kt：在电流语义与工作点被明确声明之前，"
                "它只是这批测点上的转矩-电流比。",
            )
        return build_quantity_comparison(
            quantity="torque_per_amp_nm_per_a",
            quantity_label_zh="转矩-电流斜率",
            unit="Nm/A",
            basis_zh=f"来源电流列：{result.current_column}",
            analytical=analytical_entry(analytical_kt_nm_per_a, "Nm/A"),
            measured=measurement_entry(
                result.slope_nm_per_a,
                "Nm/A",
                metadata=dataset.metadata,
                sample_count=result.used_sample_count,
            ),
            dataset=dataset.metadata,
            compatibility=compatibility,
            limitations_zh=tuple(limitations),
        )

    def build_efficiency_comparison(
        self,
        dataset: LoadedDataset,
        *,
        project_parameters: Mapping[str, Any],
        analytical_efficiency: float | None,
    ) -> QuantityComparison | None:
        try:
            result = self.analyze(dataset)
        except AnalysisError:
            return None
        if not isinstance(result, EfficiencyResult) or result.peak_efficiency is None:
            return None
        compatibility = self.compatibility_for(dataset, project_parameters)
        return build_quantity_comparison(
            quantity="efficiency",
            quantity_label_zh="效率（峰值点）",
            unit="1",
            basis_zh=(
                "逆变器 + 电机整体"
                if result.includes_inverter_losses
                else "按数据源给出的功率边界"
            ),
            analytical=analytical_entry(analytical_efficiency, "1"),
            measured=measurement_entry(
                result.peak_efficiency,
                "1",
                metadata=dataset.metadata,
                sample_count=len(result.points),
                note_zh=f"峰值点在第 {result.peak_efficiency_line} 行",
            ),
            dataset=dataset.metadata,
            compatibility=compatibility,
            limitations_zh=(result.boundary_zh, *result.warnings_zh),
        )

    # -- the whole picture ------------------------------------------------

    def build_overview(
        self, comparisons: Sequence[QuantityComparison] = ()
    ) -> ValidationOverview:
        """The validation view, including the empty state."""

        return build_overview(
            tuple(comparisons),
            tuple(item.metadata for item in self.datasets),
        )

    def production_datasets(self) -> tuple[LoadedDataset, ...]:
        """Datasets admissible in the production UI: fixtures excluded."""

        return tuple(
            item for item in self.datasets if not item.metadata.test_fixture_only
        )
