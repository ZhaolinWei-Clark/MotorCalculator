"""Phase 11B: the CREATOR PMSM as a registered public reference source.

Metadata only. This module contains no measured value copied out of the dataset:
it describes where the data is, how its columns are laid out, what its licence
permits, and which published scalars carry which origin. The numbers themselves
stay in the user's own copy of the source, referenced by SHA-256.

That split is deliberate. The dataset is CC BY-NC 4.0, which does permit
redistribution with attribution for non-commercial use -- but committing tens of
megabytes of someone else's measurements into a calculator's repository is a
choice that should be made deliberately and not by default. Metadata plus hashes
plus an adapter gives the same reproducibility at none of the cost.

Source
------
Dhakal, P. K. (2024). *CREATOR Case: Permanent Magnet Synchronous Motor Data.*
Graz University of Technology. https://doi.org/10.3217/sns1d-77m43

The companion paper is Dhakal, Heidarikani and Muetze, *"CREATOR Case: PMSM and
IM Electric Machine Data for Validation and Benchmarking of Simulation and
Modeling Approaches"*, which is the authority for how each parameter was
obtained.
"""

from __future__ import annotations

from dataclasses import dataclass

from .origins import (
    PARAMETER_ORIGIN_SCHEMA_VERSION,
    PROVENANCE_UNRESOLVED,
    ParameterOrigin,
    ParameterSet,
    PublicParameter,
)
from .public_reference import ExtractionMethod, PublicSourceRecord
from .schema import (
    UNKNOWN,
    Citation,
    DatasetMetadata,
    MachineIdentity,
    RedistributionStatus,
    TestType,
)
from .sources import DatasetSourceType
from .topology import MachineTopology

CREATOR_SOURCE_SCHEMA_VERSION = "phase11b.creator_source.v1"

SOURCE_ID = "creator.pmsm.a01"
DATASET_DOI = "10.3217/sns1d-77m43"
PAPER_TITLE = (
    "CREATOR Case: PMSM and IM Electric Machine Data for Validation and "
    "Benchmarking of Simulation and Modeling Approaches"
)
LICENSE_NAME = "CC BY-NC 4.0"
LICENSE_URL = "https://creativecommons.org/licenses/by-nc/4.0/"

#: The machine's measured operating point for the back-EMF record. From the
#: source's own README, not inferred from the data.
BACK_EMF_SPEED_RPM = 2000.0
#: Quasi-static rotation speed for the cogging record, from the README.
COGGING_SPEED_RPM = 0.25
POLE_PAIRS = 2
SLOTS = 6
PHASES = 3

#: Published scalars, quoted here only so an import can be cross-checked against
#: them. They are targets, never substitutes for the raw data.
PUBLISHED_BACK_EMF_FUNDAMENTAL_PEAK_V = 47.37
PUBLISHED_COGGING_SCALAR_NM = 0.0357
PUBLISHED_RS_OHM = 8.9462
PUBLISHED_LD_H = 0.2055
PUBLISHED_LQ_H = 0.3320
PUBLISHED_LAMBDA_PM_WB = 0.1144

#: Relative paths inside the user's copy of the dataset. The adapter resolves
#: these against a root the user supplies; nothing here assumes a location.
RELATIVE_PATHS = {
    "back_emf": "Measurement_results/No_load_tests/Back_emf.csv",
    "cogging": "Measurement_results/No_load_tests/Cogging_torque.csv",
    "no_load_rotor_out_1": "Measurement_results/No_load_tests/M20231005.csv",
    "no_load_rotor_out_2": "Measurement_results/No_load_tests/M20231017.csv",
    "no_load_rotor_in": "Measurement_results/No_load_tests/M20231018.csv",
    "iron_losses": "Measurement_results/No_load_tests/No_load_iron_losses.csv",
    "equivalent_circuit": (
        "Measurement_results/Equivalent_circuit_parameters/"
        "Equivalent_circuit_parameters_PMSM.csv"
    ),
    "geometry": "Design_parameters/Motor_geometry/Geometry_parameters_PMSM.csv",
    "winding": "Design_parameters/Winding_scheme/Winding_properties_of_PMSM.csv",
}

#: SHA-256 of each referenced file, recorded at audit time. A file that no longer
#: hashes to this is a different file, and the adapter says so rather than
#: quietly analysing something else.
FILE_HASHES = {
    "back_emf": "f5bc193a9413dc6806fe4191cfcae3a676811b80e1ebc33d89969b05aa6c8d29",
    "cogging": "44ba8de50b326225dbba91f0a4123782656872b2a336232b0f83f499446df0bd",
    "no_load_rotor_out_1": "bf50c7068654ee0e1f066be297843ea2ec797227890cbc5bb5aa9f5695de0a8b",
    "no_load_rotor_out_2": "5cb5ae3f5c0c392c370e31c22ddf926a356cd2f93056fbd30c302e9be39c0cd3",
    "no_load_rotor_in": "4b30f6ad7f850b361d1b9106e345ef021d212a631ddf512e9dd567dc86fcef8c",
    "iron_losses": "7b6a3a238c857731696d50ba4037d6032e69eba0fab503387670152f12a9ab47",
    "equivalent_circuit": "de90e95729ef7113bbe4a2674ea88e2310d1d43d240c71bfdb9b2ec9b977248e",
    "geometry": "45d8b9aed4256bcd55dce089a173002c48677cd70792b8a8f39ddbfe336a322a",
    "winding": "f2d28fa5aad56b490cb72559ca1b0d978894956f1c7cb8f2ffceb28beb04e40f",
}

#: Column layouts, declared per file. The CREATOR measurement CSVs declare no
#: units in their headers, so the units live here rather than being guessed at
#: import time -- and two of the drive-cycle folders have no header row at all.
COLUMN_LAYOUTS = {
    "back_emf": {
        "has_header": True,
        "columns": ("rotor_angle_mech_deg", "phase_u_v", "phase_v_v", "phase_w_v"),
        "units": ("deg", "V", "V", "V"),
        "note": "瞬时相电压（相对中性点），角度为机械度。",
    },
    "cogging": {
        "has_header": True,
        "columns": ("rotor_angle_mech_deg", "torque_nm"),
        "units": ("deg", "Nm"),
        "note": "准静态齿槽转矩，零电流。",
    },
    "no_load": {
        "has_header": True,
        "columns": ("speed_rpm", "torque_nm"),
        "units": ("rpm", "Nm"),
        "note": "空载拖曳转矩。",
    },
    "iron_losses": {
        "has_header": True,
        "columns": ("frequency_hz", "loss_w"),
        "units": ("Hz", "W"),
        "note": "由转子内外两组空载转矩之差推导。",
    },
    # Phase 11B-A found that Small_sized_vehicle files carry headers while
    # Mid_sized_vehicle files do not. The difference is per folder, so it is
    # declared per folder rather than sniffed.
    "drive_cycle_small": {
        "has_header": True,
        "columns": ("time_s", "value"),
        "units": ("s", None),
        "note": "带表头。",
    },
    "drive_cycle_mid": {
        "has_header": False,
        "columns": ("time_s", "value"),
        "units": ("s", None),
        "note": "**无表头**：首行即数据。绝不按表头猜测。",
    },
}

CREATOR_MACHINE = MachineIdentity(
    description="CREATOR Project A01 PMSM (EALS, TU Graz)",
    machine_id="CREATOR-A01-PMSM",
    topology=MachineTopology.RADIAL_FLUX_INSET_PMSM.value,
    pole_count=2 * POLE_PAIRS,
    slot_count=SLOTS,
    phases=PHASES,
    connection="WYE",
    turns_per_phase=UNKNOWN,  # see the reconstruction note below
    rated_speed_rpm=2000.0,
    rated_power_w=70.0,
    winding_description="Tooth-wound / concentrated, single layer, q = 0.5, 328 turns per slot",
    geometry_note=(
        "Radial-flux inset PMSM: stator OD 113 mm, bore 47.8 mm, rotor OD 47 mm, "
        "radial air gap 0.4 mm, stack 30.1 mm, sintered ferrite magnets (Br 0.41 T)."
    ),
)

CREATOR_CITATION = Citation(
    title="CREATOR Case: Permanent Magnet Synchronous Motor Data",
    authors="Dhakal, P. K.",
    publication="Graz University of Technology",
    year=2024,
    doi=DATASET_DOI,
    url=f"https://doi.org/{DATASET_DOI}",
    page=UNKNOWN,
    table_or_figure="Tab. 10 (equivalent circuit parameters); Fig. 13-14 (no-load tests)",
    license=LICENSE_NAME,
    # CC BY-NC does permit redistribution with attribution for non-commercial
    # use. It is recorded as ALLOWED because the licence says so; whether this
    # project should exercise that right is a separate, deliberate decision, and
    # COMMIT_POLICY below says it does not.
    redistribution=RedistributionStatus.ALLOWED,
    notes=(
        "CC BY-NC 4.0: attribution required, non-commercial use only. "
        "This project stores metadata, hashes and adapters, not the raw data."
    ),
)

#: What this repository actually stores, regardless of what the licence permits.
COMMIT_POLICY = "METADATA_HASH_AND_ADAPTER_ONLY"
COMMIT_POLICY_NOTE_ZH = (
    "尽管 CC BY-NC 4.0 允许署名、非商业前提下的再分发，本仓库仍**不提交任何原始测量文件**。"
    "仓库只保存：引用信息、DOI、许可名称、文件 SHA-256、列布局与适配器。"
    "原始数据保留在使用者自己的副本中，通过哈希校验其同一性。"
)

CREATOR_SOURCE_RECORD = PublicSourceRecord(
    schema_version=CREATOR_SOURCE_SCHEMA_VERSION,
    source_id=SOURCE_ID,
    citation=CREATOR_CITATION,
    machine=CREATOR_MACHINE,
    test_type=TestType.BACK_EMF_WAVEFORM,
    extraction_method=ExtractionMethod.AUTHOR_SUPPLIED_DATASET,
    location_note=(
        "Machine-readable dataset published by the authors; this record points "
        "at the files by relative path and SHA-256."
    ),
    column_mapping={},  # adapters declare layouts explicitly; see COLUMN_LAYOUTS
    column_units={},
    test_conditions_zh=(
        "反电动势：转子由外部拖动至 2000 rpm，空载。"
        "齿槽转矩：转子以 0.25 rpm 准静态旋转，零电流，转矩传感器测量。"
        "空载损耗：自由惰行，分别在转子位于定子外部与内部两种状态下测量。"
    ),
    notes_zh=(
        "本记录仅含元数据。原始测量值不随仓库分发。"
    ),
)


def dataset_metadata(test_type: TestType, dataset_id: str, title: str) -> DatasetMetadata:
    """A dataset record for one CREATOR file.

    Always ``PUBLIC_REFERENCE_EXPERIMENT``: these are real measurements of a
    real machine, and of a machine that is not the one in this project. The
    compatibility layer decides what that permits; this function does not.
    """

    return DatasetMetadata(
        dataset_id=dataset_id,
        title=title,
        source_type=DatasetSourceType.PUBLIC_REFERENCE_EXPERIMENT,
        test_type=test_type,
        machine=CREATOR_MACHINE,
        citation=CREATOR_CITATION,
        data_provenance=f"PUBLIC_REFERENCE/{ExtractionMethod.AUTHOR_SUPPLIED_DATASET.value}",
        notes=(
            "CREATOR Project A01 PMSM (TU Graz)。径向磁通嵌入式永磁同步电机，"
            "与本项目的 AFPM 设计**不是同一台机器**。"
        ),
    )


# ---------------------------------------------------------------------------
# Published scalars, each with the origin its own source states (Steps 13-15)
# ---------------------------------------------------------------------------

#: E0 / omega_e, using the published fundamental and the machine's own speed and
#: pole-pair count. Computed here so the discrepancy below is reproducible.
_OMEGA_ELECTRICAL = BACK_EMF_SPEED_RPM / 60.0 * 2.0 * 3.141592653589793 * POLE_PAIRS
LAMBDA_FROM_BACK_EMF_WB = PUBLISHED_BACK_EMF_FUNDAMENTAL_PEAK_V / _OMEGA_ELECTRICAL
LAMBDA_DISCREPANCY_RATIO = PUBLISHED_LAMBDA_PM_WB / LAMBDA_FROM_BACK_EMF_WB - 1.0

LAMBDA_PM_NOTE_ZH = (
    f"公开值 {PUBLISHED_LAMBDA_PM_WB} Wb 与由实测基波反推的 "
    f"E0/ω_e = {LAMBDA_FROM_BACK_EMF_WB:.6f} Wb 相差 "
    f"{LAMBDA_DISCREPANCY_RATIO * 100.0:+.2f} %。"
    "来源文献未说明该磁链值如何得到：它既不等于实测基波的直接换算，"
    "也未被声明为有限元结果。在来源澄清之前，其来源标记为 UNKNOWN。"
    "本软件**不修改任何一侧的数值**，也不选择其中之一作为「正确」值。"
)


def published_parameters() -> ParameterSet:
    """The CREATOR equivalent-circuit table, with origins attached.

    The origins are not this project's opinion. They are what the source's own
    documentation states: the README for the equivalent-circuit folder says the
    stator resistance is measured with an LCR meter and that the d- and q-axis
    inductances are obtained by finite-element analysis in JMAG.
    """

    return ParameterSet(
        schema_version=PARAMETER_ORIGIN_SCHEMA_VERSION,
        source_id=SOURCE_ID,
        parameters=(
            PublicParameter(
                name="phase_resistance_ohm",
                label_zh="定子相电阻 Rs",
                value=PUBLISHED_RS_OHM,
                unit="Ohm",
                origin=ParameterOrigin.DIRECT_MEASUREMENT,
                source_note=(
                    "Equivalent_circuit_parameters README: measured directly "
                    "using an LCR meter, at room temperature."
                ),
            ),
            PublicParameter(
                name="back_emf_fundamental_peak_v",
                label_zh="基波反电动势 E0 @2000 rpm",
                value=PUBLISHED_BACK_EMF_FUNDAMENTAL_PEAK_V,
                unit="V peak (phase)",
                origin=ParameterOrigin.MEASUREMENT_DERIVED,
                source_note=(
                    "Discrete Fourier transform of the measured no-load waveform "
                    "at 2000 rpm. Reproduced from the raw file by this project."
                ),
            ),
            PublicParameter(
                name="cogging_torque_peak_nm",
                label_zh="齿槽转矩（公开标量）",
                value=PUBLISHED_COGGING_SCALAR_NM,
                unit="Nm peak",
                origin=ParameterOrigin.DIRECT_MEASUREMENT,
                source_note="Torque transducer at 0.25 rpm.",
                consistency_flag="PUBLISHED_SCALAR_DEFINITION_AMBIGUOUS",
                consistency_note_zh=(
                    "该公开标量与原始记录的 max|T| 不一致，而与 |负峰| 接近。"
                    "见齿槽转矩适配器的说明。"
                ),
            ),
            PublicParameter(
                name="d_axis_inductance_h",
                label_zh="d 轴电感 Ld",
                value=PUBLISHED_LD_H,
                unit="H",
                origin=ParameterOrigin.FEA_DERIVED,
                source_note=(
                    "Equivalent_circuit_parameters README: obtained through "
                    "finite element analysis using JMAG's inductance calculator. "
                    "NOT a measurement, despite appearing in a table of "
                    "'parameters derived from experimental tests'."
                ),
            ),
            PublicParameter(
                name="q_axis_inductance_h",
                label_zh="q 轴电感 Lq",
                value=PUBLISHED_LQ_H,
                unit="H",
                origin=ParameterOrigin.FEA_DERIVED,
                source_note=(
                    "Same JMAG finite-element calculation as Ld. NOT a measurement."
                ),
            ),
            PublicParameter(
                name="magnet_flux_linkage_wb",
                label_zh="永磁磁链 λ_pm",
                value=PUBLISHED_LAMBDA_PM_WB,
                unit="Wb",
                origin=ParameterOrigin.UNKNOWN,
                source_note=(
                    "Listed in Tab. 10 with no stated method. Does not equal "
                    "E0 / omega_e from the same table."
                ),
                consistency_flag=PROVENANCE_UNRESOLVED,
                consistency_note_zh=LAMBDA_PM_NOTE_ZH,
            ),
        ),
    )


@dataclass(frozen=True)
class SourceSummary:
    """What the GUI needs to describe this source without opening any file."""

    source_id: str
    title: str
    doi: str
    license_name: str
    license_url: str
    evidence_class: str
    topology: str
    topology_label_zh: str
    commit_policy: str
    available_evidence_zh: tuple[str, ...]


def source_summary() -> SourceSummary:
    from .topology import TOPOLOGY_LABELS_ZH

    return SourceSummary(
        source_id=SOURCE_ID,
        title="CREATOR Case — PMSM (TU Graz)",
        doi=DATASET_DOI,
        license_name=LICENSE_NAME,
        license_url=LICENSE_URL,
        evidence_class=DatasetSourceType.PUBLIC_REFERENCE_EXPERIMENT.value,
        topology=MachineTopology.RADIAL_FLUX_INSET_PMSM.value,
        topology_label_zh=TOPOLOGY_LABELS_ZH[MachineTopology.RADIAL_FLUX_INSET_PMSM],
        commit_policy=COMMIT_POLICY,
        available_evidence_zh=(
            "反电动势波形（2000 rpm，角度域，7681 点）",
            "齿槽转矩（0.25 rpm，240001 点）",
            "空载损耗（转子在定子内/外，各 16 个转速点）",
            "等效电路参数（Rs / Ld / Lq / λ_pm / E0，逐项标注来源）",
            "行驶工况测量（2 种车型 × 3 种工况，输入/输出功率）",
        ),
    )
