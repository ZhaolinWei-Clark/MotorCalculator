"""Phase 7C blocker resolution without production input substitution."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from .external_metric_comparison import ComparabilityStatus
from .phase7b1_campaign import build_phase7b1_campaign
from .reconstructed_cases import ReconstructedAFPMCase, load_reconstructed_case


class BlockerCategory(str, Enum):
    MISSING_GEOMETRY = "missing_geometry"
    MISSING_TURNS = "missing_turns"
    MISSING_WINDING_CONNECTION = "missing_winding_connection"
    AMBIGUOUS_PHASE_LINE = "ambiguous_phase_line"
    AMBIGUOUS_PEAK_RMS = "ambiguous_peak_rms"
    NONSINUSOIDAL_WAVEFORM = "nonsinusoidal_waveform"
    CURRENT_BASIS_UNKNOWN = "current_basis_unknown"
    TORQUE_BOUNDARY_UNKNOWN = "torque_boundary_unknown"
    OPERATING_POINT_INCOMPLETE = "operating_point_incomplete"
    TEMPERATURE_UNKNOWN = "temperature_unknown"
    TOPOLOGY_MISMATCH = "topology_mismatch"
    INDUCTANCE_STRUCTURE_MISMATCH = "inductance_structure_mismatch"
    MODEL_INPUT_NOT_SUPPORTED = "model_input_not_supported"
    SOURCE_ACCESS_BLOCKED = "source_access_blocked"


@dataclass(frozen=True)
class BlockerResolution:
    source_id: str
    metric: str
    case_id: str
    categories_before: tuple[BlockerCategory, ...]
    categories_after: tuple[BlockerCategory, ...]
    known_fields: str
    missing_fields: str
    recoverable_from_source: str
    approved_transform: str
    fundamentally_blocked: bool
    resolution_notes: str


@dataclass(frozen=True)
class Phase7CResult:
    cases: tuple[ReconstructedAFPMCase, ...]
    blockers: tuple[BlockerResolution, ...]
    before_counts: dict[str, int]
    after_counts: dict[str, int]
    new_direct_rows: tuple[str, ...] = ()
    new_safe_transform_rows: tuple[str, ...] = ()

    @property
    def blocker_category_counts_before(self) -> dict[str, int]:
        counts = Counter(category.value for row in self.blockers for category in row.categories_before)
        return {category.value: counts.get(category.value, 0) for category in BlockerCategory}

    @property
    def blocker_category_counts_after(self) -> dict[str, int]:
        counts = Counter(category.value for row in self.blockers for category in row.categories_after)
        return {category.value: counts.get(category.value, 0) for category in BlockerCategory}


def _blockers() -> tuple[BlockerResolution, ...]:
    B = BlockerCategory
    return (
        BlockerResolution(
            "abdelli_2026_dssr_afpm", "back_emf_phase_waveform", "abdelli_2026_reconstructed_afpm",
            (B.MISSING_TURNS, B.MISSING_WINDING_CONNECTION, B.TOPOLOGY_MISMATCH, B.MODEL_INPUT_NOT_SUPPORTED),
            (B.MISSING_TURNS, B.MISSING_WINDING_CONNECTION, B.TOPOLOGY_MISMATCH, B.MODEL_INPUT_NOT_SUPPORTED),
            "1000 rpm; 6 pole pairs; 245/140 mm active diameters; 1 mm gap; 10 mm magnet; measured/FEA plots",
            "prototype turns-per-phase, connection, Br, winding factor, production-equivalent leakage and pole-arc semantics, tabulated voltage",
            "Only graph digitization could recover an approximate scalar; it cannot resolve topology or model inputs.",
            "None approved for graph-only harmonic waveform.", True,
            "No plot digitization performed; DSSR/open-slot tooth-coil physics remains outside the default SSDR model.",
        ),
        BlockerResolution(
            "abdelli_2026_dssr_afpm", "torque_nm", "abdelli_2026_reconstructed_afpm",
            (B.OPERATING_POINT_INCOMPLETE, B.TOPOLOGY_MISMATCH, B.MODEL_INPUT_NOT_SUPPORTED),
            (B.OPERATING_POINT_INCOMPLETE, B.TOPOLOGY_MISMATCH, B.MODEL_INPUT_NOT_SUPPORTED),
            "1000 rpm; current sweep 20-400 A; measured and FEA torque curves",
            "authoritative point value, exact current/torque boundary for a selected point, source-compatible production topology",
            "A figure estimate is possible but would remain approximate and topology-blocked.",
            "No safe transform produces a production torque-current prediction.", True,
            "Low-value digitization was rejected while Priority-1 back-EMF remains blocked.",
        ),
        BlockerResolution(
            "price_2009_coreless_afpm_generator", "back_emf_phase_peak_v", "price_2009_reconstructed_afpm",
            (B.MISSING_GEOMETRY, B.MODEL_INPUT_NOT_SUPPORTED),
            (B.MISSING_GEOMETRY, B.MODEL_INPUT_NOT_SUPPORTED),
            "600 rpm; Y; 108 turns/phase; 37 V measured phase peak; sinusoidal waveform; SSDR/coreless class",
            "pole pairs, Br, magnet permeability, physical per-side gap, winding factor, leakage factor, scalar pole arc",
            "Full article resolves turns and native voltage semantics but not the remaining magnetic inputs.",
            "Native phase peak requires no RMS conversion.", True,
            "The production magnetic model cannot be run without inventing material and scalar-factor inputs.",
        ),
        BlockerResolution(
            "price_2009_coreless_afpm_generator", "torque_nm", "price_2009_reconstructed_afpm",
            (B.CURRENT_BASIS_UNKNOWN, B.TORQUE_BOUNDARY_UNKNOWN, B.MODEL_INPUT_NOT_SUPPORTED),
            (B.MODEL_INPUT_NOT_SUPPORTED,),
            "500 rpm; 10 A phase RMS; 12.6 Nm measured average shaft torque; three-phase Y; sinusoidal current",
            "source-compatible electromagnetic torque prediction and quantified shaft mechanical-loss torque",
            "Full article resolves current RMS basis and the shaft torque boundary.",
            "12.6/10 = 1.26 Nm/A is a shaft ratio, not production electromagnetic Kt.", True,
            "Two semantic blockers resolved; the remaining boundary/model gap prevents a comparison or Kt claim.",
        ),
        BlockerResolution(
            "parviainen_2005_afpm_prototype", "back_emf_phase_rms_v", "parviainen_2005_reconstructed_afpm",
            (B.NONSINUSOIDAL_WAVEFORM, B.TOPOLOGY_MISMATCH, B.MODEL_INPUT_NOT_SUPPORTED),
            (B.NONSINUSOIDAL_WAVEFORM, B.TOPOLOGY_MISMATCH, B.MODEL_INPUT_NOT_SUPPORTED),
            "300 rpm; 6 pole pairs; 328/197 mm; 4 mm magnet; Br 1.05 T at 100 C; 840 turns/stator phase; star; 211 V phase RMS",
            "production-equivalent coil height, leakage, winding factor, scalar pole arc and DSSR parallel-stator representation",
            "The full dissertation resolves connection, per-stator turns, temperature, and measured phase RMS semantics.",
            "No sqrt(2) conversion because Figure 3.6 shows flattened non-sinusoidal phase voltage.", True,
            "The remaining blockers are model/schema capability gaps, not merely missing headline metadata.",
        ),
        BlockerResolution(
            "parviainen_2005_afpm_prototype", "phase_resistance_ohm", "parviainen_2005_reconstructed_afpm",
            (B.TEMPERATURE_UNKNOWN, B.TOPOLOGY_MISMATCH, B.MODEL_INPUT_NOT_SUPPORTED),
            (B.TEMPERATURE_UNKNOWN, B.TOPOLOGY_MISMATCH, B.MODEL_INPUT_NOT_SUPPORTED),
            "3.7 ohm measured DC per-stator phase; 840 turns; star stator; stators parallel by default",
            "measurement temperature, exact conductor area/parallel paths, source-compatible end-turn geometry",
            "No measurement temperature or prototype conductor specification was recovered from the validation section.",
            "Copper temperature normalization is approved only after source temperature is known.", True,
            "The reported 3.7 ohm is retained without normalizing or treating two parallel stators as one production phase.",
        ),
        BlockerResolution(
            "parviainen_2005_afpm_prototype", "Ld_h", "parviainen_2005_reconstructed_afpm",
            (B.INDUCTANCE_STRUCTURE_MISMATCH, B.TOPOLOGY_MISMATCH),
            (B.INDUCTANCE_STRUCTURE_MISMATCH, B.TOPOLOGY_MISMATCH),
            "Ld=0.055 H estimated by inverter for the DSSR prototype",
            "approved bridge from per-axis DSSR inductance to production scalar phase inductance",
            "The source quantity is already explicit; more source extraction does not fix model semantics.",
            "No axis-to-scalar conversion approved.", True,
            "This is a model input/output structure mismatch.",
        ),
        BlockerResolution(
            "parviainen_2005_afpm_prototype", "Lq_h", "parviainen_2005_reconstructed_afpm",
            (B.INDUCTANCE_STRUCTURE_MISMATCH, B.TOPOLOGY_MISMATCH),
            (B.INDUCTANCE_STRUCTURE_MISMATCH, B.TOPOLOGY_MISMATCH),
            "Lq=0.060 H estimated by inverter for the DSSR prototype",
            "approved bridge from per-axis DSSR inductance to production scalar phase inductance",
            "The source quantity is already explicit; more source extraction does not fix model semantics.",
            "No axis-to-scalar conversion approved.", True,
            "This is a model input/output structure mismatch.",
        ),
        BlockerResolution(
            "parviainen_2005_afpm_prototype", "efficiency_percent", "parviainen_2005_reconstructed_afpm",
            (B.OPERATING_POINT_INCOMPLETE, B.TOPOLOGY_MISMATCH, B.MODEL_INPUT_NOT_SUPPORTED),
            (B.OPERATING_POINT_INCOMPLETE, B.TOPOLOGY_MISMATCH, B.MODEL_INPUT_NOT_SUPPORTED),
            "89.2% measured steady-state efficiency; natural convection and radiation; rated prototype context",
            "matched electrical/mechanical powers, temperatures and loss decomposition for the exact point",
            "Additional test-curve digitization would not make the frozen production loss model source-equivalent.",
            "No safe efficiency transformation.", True,
            "Loss and cooling boundaries remain incompatible.",
        ),
        BlockerResolution(
            "hosseini_2008_coreless_afpm_generator", "back_emf_no_load_peak_to_peak_v", "hosseini_2008_reconstructed_afpm",
            (B.MISSING_TURNS, B.MISSING_WINDING_CONNECTION, B.AMBIGUOUS_PEAK_RMS, B.NONSINUSOIDAL_WAVEFORM, B.MODEL_INPUT_NOT_SUPPORTED),
            (B.MISSING_TURNS, B.MISSING_WINDING_CONNECTION, B.AMBIGUOUS_PEAK_RMS, B.NONSINUSOIDAL_WAVEFORM, B.MODEL_INPUT_NOT_SUPPORTED),
            "3000 rpm; 12 pole pairs; complete active radii/gap/coil height/magnet Br and permeability; 160 V phase Vpp",
            "turns per phase, series/parallel and terminal connection, winding factor, source-equivalent leakage and pole arc",
            "The source gives 50 conductors/coil but not a defensible phase turns/interconnection mapping.",
            "No harmonic Vpp-to-RMS or Vpp-to-production-peak conversion approved.", True,
            "This is the strongest geometry case, but winding and waveform blockers remain decisive.",
        ),
        BlockerResolution(
            "hosseini_2008_coreless_afpm_generator", "output_voltage_fundamental_peak_to_peak_v", "hosseini_2008_reconstructed_afpm",
            (B.MISSING_TURNS, B.MISSING_WINDING_CONNECTION, B.AMBIGUOUS_PEAK_RMS, B.OPERATING_POINT_INCOMPLETE),
            (B.MISSING_TURNS, B.MISSING_WINDING_CONNECTION, B.AMBIGUOUS_PEAK_RMS, B.OPERATING_POINT_INCOMPLETE),
            "102 V phase Vpp fundamental at 3000 rpm under 10-ohm load",
            "winding mapping and source-equivalent loaded-terminal-voltage model",
            "The full table resolves the column meaning but not the electrical connection.",
            "A sinusoidal fundamental Vpp conversion is mathematically possible, but it would still be loaded terminal voltage, not no-load back-EMF.", True,
            "Quantity-scope mismatch remains even after isolating the fundamental.",
        ),
        BlockerResolution(
            "hosseini_2008_coreless_afpm_generator", "efficiency_percent", "hosseini_2008_reconstructed_afpm",
            (B.CURRENT_BASIS_UNKNOWN, B.OPERATING_POINT_INCOMPLETE, B.MODEL_INPUT_NOT_SUPPORTED),
            (B.CURRENT_BASIS_UNKNOWN, B.OPERATING_POINT_INCOMPLETE, B.MODEL_INPUT_NOT_SUPPORTED),
            "78.1%; 390 W output; 40 V phase; 3.6 A phase; 3000 rpm",
            "current RMS/peak basis, connection, complete input-power/loss boundary",
            "Table 4 provides nominal values but not enough semantics to rebuild the production efficiency chain.",
            "No safe transform for unknown current basis.", True,
            "Efficiency remains lower priority than unresolved back-EMF.",
        ),
        BlockerResolution(
            "hosseini_2008_coreless_afpm_generator", "Xsd_ohm", "hosseini_2008_reconstructed_afpm",
            (B.INDUCTANCE_STRUCTURE_MISMATCH,), (B.INDUCTANCE_STRUCTURE_MISMATCH,),
            "Xsd=2.1 ohm and f=300 Hz; safely derived Ld=0.00111408460164 H",
            "production Ld output or approved bridge to scalar phase inductance",
            "Source and frequency fully support an axis-preserving Xd-to-Ld transform.",
            "Ld = Xsd/(2*pi*f), labelled SAFE_TRANSFORM field only.", True,
            "Unit/semantic reconstruction resolved; comparison remains blocked by production scalar-inductance structure.",
        ),
        BlockerResolution(
            "hosseini_2008_coreless_afpm_generator", "Xsq_ohm", "hosseini_2008_reconstructed_afpm",
            (B.INDUCTANCE_STRUCTURE_MISMATCH,), (B.INDUCTANCE_STRUCTURE_MISMATCH,),
            "Xsq=2.1 ohm and f=300 Hz; safely derived Lq=0.00111408460164 H",
            "production Lq output or approved bridge to scalar phase inductance",
            "Source and frequency fully support an axis-preserving Xq-to-Lq transform.",
            "Lq = Xsq/(2*pi*f), labelled SAFE_TRANSFORM field only.", True,
            "Unit/semantic reconstruction resolved; comparison remains blocked by production scalar-inductance structure.",
        ),
    )


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def build_phase7c_result(repo_root: Path | None = None) -> Phase7CResult:
    root = Path(repo_root) if repo_root is not None else _repo_root()
    case_dir = root / "validation_data" / "reconstructed_cases"
    cases = tuple(load_reconstructed_case(path) for path in sorted(case_dir.glob("*_case.json")))
    phase7b1 = build_phase7b1_campaign()
    blocked_keys = {
        (row.evidence.source_id, row.evidence.metric_name)
        for row in phase7b1.rows
        if row.evidence.comparability_status is ComparabilityStatus.BLOCKED
    }
    blockers = _blockers()
    inventory_keys = {(row.source_id, row.metric) for row in blockers}
    if blocked_keys != inventory_keys:
        missing = blocked_keys - inventory_keys
        extra = inventory_keys - blocked_keys
        raise RuntimeError(f"Phase 7C blocker inventory drifted; missing={missing}, extra={extra}")
    return Phase7CResult(
        cases=cases,
        blockers=blockers,
        before_counts=phase7b1.comparability_counts,
        after_counts=phase7b1.comparability_counts.copy(),
    )


def _counts_text(counts: dict[str, int]) -> str:
    return ", ".join(f"{key}={value}" for key, value in counts.items())


def render_phase7c_report(result: Phase7CResult) -> str:
    lines = [
        "# Phase 7C 重建静态比较报告",
        "",
        "## 冻结边界",
        "",
        "本报告仅加载逐字段来源重建记录并审计可比性。没有向缺失字段写入 production defaults，没有修改公式、参数、GUI、dynamic/controller chain 或 legacy baseline。",
        "",
        "## 状态计数",
        "",
        f"- before: {_counts_text(result.before_counts)}",
        f"- after: {_counts_text(result.after_counts)}",
        f"- new DIRECT rows: {len(result.new_direct_rows)}",
        f"- new SAFE_TRANSFORM comparison rows: {len(result.new_safe_transform_rows)}",
        "",
        "没有新增 model prediction/reference pair。Phase 7C 恢复的是来源语义与模型能力边界，不把安全派生的 source field 冒充 production comparison。",
        "",
        "## 新增 Reconstructed Comparison Rows",
        "",
        "| source | metric | source-native semantics | reconstructed case | predicted | reference | absolute error | percentage error | comparability | provenance | uncertainty | remaining blockers |",
        "|---|---|---|---|---:|---:|---:|---:|---|---|---|---|",
        "| none | none | no source-compatible production prediction | four cases audited | unavailable | unavailable | unavailable | unavailable | BLOCKED | see case-level field provenance | source uncertainty retained | see blocker inventory |",
        "",
        "## 已恢复但仍不可比较的量",
        "",
        "| source | recovered item | result | remaining blocker |",
        "|---|---|---|---|",
        "| Price 2009 | current basis and torque boundary | 10 A phase RMS; 12.6 Nm measured average shaft torque; shaft ratio 1.26 Nm/A | production electromagnetic prediction and mechanical-loss torque are unavailable |",
        "| Hosseini 2008 | Xsd/Xsq to axis inductance | Ld=Lq=0.00111408460164 H at 300 Hz | production predicts scalar phase inductance, not Ld/Lq |",
        "| Parviainen 2005 | winding and voltage semantics | 840 turns per stator phase; star; parallel stators; 211 V phase RMS | DSSR topology, flattened waveform and source-specific magnet/leakage model |",
        "",
        "## Blocker 明细",
        "",
        "| source | metric | categories after | known fields | exact missing fields | approved transform | fundamentally blocked | resolution |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for row in result.blockers:
        categories = ", ".join(category.value for category in row.categories_after)
        lines.append(
            f"| {row.source_id} | {row.metric} | {categories} | {row.known_fields} | "
            f"{row.missing_fields} | {row.approved_transform} | {'yes' if row.fundamentally_blocked else 'no'} | "
            f"{row.resolution_notes} |"
        )
    lines.extend((
        "",
        "## 新增误差与诊断",
        "",
        "无。没有新增 DIRECT/SAFE_TRANSFORM comparison，因此不存在可归因于 magnetic circuit、leakage/fringing 或 winding factor 的新数值误差。把 blocked 行计算成误差会混淆 source-data limitation 与 model-physics limitation。",
        "",
        "## 决策",
        "",
        "当前仍不能评估 production AFPM electromagnetic accuracy。下一步应优先获取一个 SSDR source 的 Br、physical per-side gap、series turns/phase、connection、winding factor/leakage definition 与 tabulated native back-EMF；或者先提出 Phase 7D schema/model capability proposal。没有多点外部 electromagnetic comparison，不建议 calibration。",
        "",
    ))
    return "\n".join(lines)


def run_phase7c_reconstruction(repo_root: Path | None = None) -> Phase7CResult:
    root = Path(repo_root) if repo_root is not None else _repo_root()
    result = build_phase7c_result(root)
    report = root / "validation_data" / "reports" / "phase7c_reconstructed_static_comparison_zh.md"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(render_phase7c_report(result), encoding="utf-8")
    return result
