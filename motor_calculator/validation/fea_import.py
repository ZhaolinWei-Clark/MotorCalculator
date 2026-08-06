"""Deterministic import and waveform analysis for externally solved FEA data."""

from __future__ import annotations

import csv
import hashlib
import math
from dataclasses import dataclass
from pathlib import Path

from .fea_reference import EvidenceClassification, FEAReferenceDefinition, FEASolverMetadata


@dataclass(frozen=True)
class FEAWaveformSample:
    rotor_angle_deg: float
    time_s: float
    flux_linkage_phase_a_wb_turn: float | None
    back_emf_phase_a_v: float | None
    torque_nm: float | None


@dataclass(frozen=True)
class FEAWaveformMetrics:
    phase_rms_v: float
    phase_peak_v: float
    phase_fundamental_rms_v: float
    sample_count: int
    dc_component_v: float
    method_notes: tuple[str, ...]


@dataclass(frozen=True)
class FEAImportedMeshMetadata:
    mesh_name: str
    element_count: int
    node_count: int
    minimum_element_quality: float | None
    solver_mesh_notes: str

    def __post_init__(self) -> None:
        if not self.mesh_name.strip() or not self.solver_mesh_notes.strip():
            raise ValueError("mesh name and solver mesh notes must be explicit")
        if self.element_count <= 0 or self.node_count <= 0:
            raise ValueError("mesh element and node counts must be positive")
        quality = self.minimum_element_quality
        if quality is not None and (not math.isfinite(quality) or not 0.0 <= quality <= 1.0):
            raise ValueError("minimum element quality must be within [0, 1]")


@dataclass(frozen=True)
class ImportedFEAReference:
    reference_id: str
    solver_metadata: FEASolverMetadata
    mesh_metadata: FEAImportedMeshMetadata
    evidence_classification: EvidenceClassification
    source_file: Path
    source_file_sha256: str
    samples: tuple[FEAWaveformSample, ...]
    waveform_metrics: FEAWaveformMetrics | None


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def analyze_periodic_waveform(values: tuple[float, ...]) -> FEAWaveformMetrics:
    if len(values) < 8:
        raise ValueError("at least eight endpoint-excluded samples are required")
    if any(not math.isfinite(value) for value in values):
        raise ValueError("waveform samples must be finite")
    count = len(values)
    rms = math.sqrt(sum(value * value for value in values) / count)
    peak = max(abs(value) for value in values)
    dc = sum(values) / count
    cosine = 2.0 / count * sum(
        value * math.cos(2.0 * math.pi * index / count)
        for index, value in enumerate(values)
    )
    sine = 2.0 / count * sum(
        value * math.sin(2.0 * math.pi * index / count)
        for index, value in enumerate(values)
    )
    fundamental_rms = math.hypot(cosine, sine) / math.sqrt(2.0)
    return FEAWaveformMetrics(
        phase_rms_v=rms,
        phase_peak_v=peak,
        phase_fundamental_rms_v=fundamental_rms,
        sample_count=count,
        dc_component_v=dc,
        method_notes=(
            "Total RMS is computed directly from samples; no peak/RMS sinusoidal assumption is used.",
            "Fundamental RMS uses the first discrete Fourier coefficient over one endpoint-excluded period.",
        ),
    )


def _optional_float(row: dict[str, str], name: str) -> float | None:
    value = row.get(name, "").strip()
    return None if value == "" else float(value)


def _require_uniform_spacing(values: tuple[float, ...], name: str) -> None:
    steps = tuple(right - left for left, right in zip(values, values[1:]))
    reference = steps[0]
    tolerance = max(abs(reference) * 1e-9, 1e-12)
    if any(abs(step - reference) > tolerance for step in steps[1:]):
        raise ValueError(f"{name} samples must be uniformly spaced for waveform DFT")


def _validate_reference_sampling(
    samples: tuple[FEAWaveformSample, ...],
    reference: FEAReferenceDefinition,
    solver_metadata: FEASolverMetadata,
) -> None:
    if solver_metadata.model_version != reference.planned_solver.model_version:
        raise ValueError("solver model version does not match the controlled reference")
    operating_point = reference.operating_point
    expected_count = round(
        (operating_point.rotor_angle_end_deg - operating_point.rotor_angle_start_deg)
        / operating_point.rotor_angle_step_deg
    )
    if len(samples) != expected_count:
        raise ValueError("sample count does not match the endpoint-excluded controlled angle sweep")
    if not math.isclose(samples[0].rotor_angle_deg, operating_point.rotor_angle_start_deg, abs_tol=1e-12):
        raise ValueError("first rotor angle does not match the controlled reference")
    expected_last = operating_point.rotor_angle_end_deg - operating_point.rotor_angle_step_deg
    if not math.isclose(samples[-1].rotor_angle_deg, expected_last, abs_tol=1e-12):
        raise ValueError("last rotor angle must exclude the duplicate electrical-period endpoint")


class ExternalFEAImportAdapter:
    REQUIRED_COLUMNS = ("rotor_angle_deg", "time_s")
    SIGNAL_COLUMNS = ("flux_linkage_phase_a_wb_turn", "back_emf_phase_a_v", "torque_nm")

    def import_csv(
        self,
        path: Path,
        solver_metadata: FEASolverMetadata,
        mesh_metadata: FEAImportedMeshMetadata,
        reference: FEAReferenceDefinition,
        *,
        evidence_classification: EvidenceClassification = EvidenceClassification.INDEPENDENT_FEA_REFERENCE,
    ) -> ImportedFEAReference:
        source = Path(path)
        with source.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            columns = tuple(reader.fieldnames or ())
            missing = tuple(name for name in self.REQUIRED_COLUMNS if name not in columns)
            if missing:
                raise ValueError(f"missing required FEA CSV columns: {', '.join(missing)}")
            if not any(name in columns for name in self.SIGNAL_COLUMNS):
                raise ValueError("FEA CSV must contain flux linkage, back-EMF, or torque")
            samples = tuple(
                FEAWaveformSample(
                    rotor_angle_deg=float(row["rotor_angle_deg"]),
                    time_s=float(row["time_s"]),
                    flux_linkage_phase_a_wb_turn=_optional_float(row, "flux_linkage_phase_a_wb_turn"),
                    back_emf_phase_a_v=_optional_float(row, "back_emf_phase_a_v"),
                    torque_nm=_optional_float(row, "torque_nm"),
                )
                for row in reader
            )
        if len(samples) < 2:
            raise ValueError("FEA CSV must contain at least two samples")
        if any(right.time_s <= left.time_s for left, right in zip(samples, samples[1:])):
            raise ValueError("FEA sample times must be strictly increasing")
        _require_uniform_spacing(tuple(sample.time_s for sample in samples), "time")
        _require_uniform_spacing(tuple(sample.rotor_angle_deg for sample in samples), "rotor angle")
        _validate_reference_sampling(samples, reference, solver_metadata)
        if any(
            not math.isfinite(value)
            for sample in samples
            for value in (
                sample.rotor_angle_deg,
                sample.time_s,
                *(
                    optional
                    for optional in (
                        sample.flux_linkage_phase_a_wb_turn,
                        sample.back_emf_phase_a_v,
                        sample.torque_nm,
                    )
                    if optional is not None
                ),
            )
        ):
            raise ValueError("FEA CSV contains non-finite values")
        voltage_values = tuple(sample.back_emf_phase_a_v for sample in samples)
        waveform_metrics = None
        if all(value is not None for value in voltage_values):
            waveform_metrics = analyze_periodic_waveform(tuple(float(value) for value in voltage_values))
        elif any(value is not None for value in voltage_values):
            raise ValueError("back-EMF must be present for every sample or omitted entirely")
        return ImportedFEAReference(
            reference_id=reference.reference_id,
            solver_metadata=solver_metadata,
            mesh_metadata=mesh_metadata,
            evidence_classification=evidence_classification,
            source_file=source.resolve(),
            source_file_sha256=sha256_file(source),
            samples=samples,
            waveform_metrics=waveform_metrics,
        )
