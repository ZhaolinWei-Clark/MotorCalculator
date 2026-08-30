"""Generate the deterministic Phase 8G warning-frequency audit sample."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
for path in (REPOSITORY_ROOT, REPOSITORY_ROOT / "motor_calculator"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from motor_calculator.input_ux import APPLICATION_DEFAULTS
from motor_calculator.motor_core import LegacyGuiMotorModelBridge, parse_legacy_gui_params
from motor_calculator.presets import apply_preset, default_preset_registry
from motor_calculator.validation.design_feasibility import evaluate_design_feasibility


def _samples(seed: Mapping[str, Any]) -> tuple[dict[str, Any], ...]:
    variants = [dict(seed)]
    for name, factors in {
        "V_dc": (0.9, 1.1),
        "P_rated": (0.8, 1.2),
        "n_rated": (0.9, 1.1),
        "d_wire": (0.8, 1.2),
        "N_ph_turns": (0.9, 1.1),
    }.items():
        for factor in factors:
            item = dict(seed)
            value = float(seed[name]) * factor
            item[name] = int(round(value)) if name == "N_ph_turns" else value
            variants.append(item)
    return tuple(variants)


def _legacy_codes(result) -> tuple[str, ...]:
    performance = result.performance
    codes: list[str] = []
    if performance.current_density_a_per_mm2 > 10.0:
        codes.append("CURRENT_DENSITY_SEVERE")
    elif performance.current_density_a_per_mm2 > 6.0:
        codes.append("CURRENT_DENSITY_HIGH")
    if performance.voltage_margin_percent < 5.0:
        codes.append("VOLTAGE_MARGIN_LOW")
    elif performance.voltage_margin_percent > 40.0:
        codes.append("VOLTAGE_MARGIN_HIGH_INFO")
    if performance.fill_factor > 0.8:
        codes.append("LEGACY_FILL_SEVERE")
    elif performance.fill_factor > 0.6:
        codes.append("LEGACY_FILL_HIGH")
    return tuple(codes)


def run_frequency_audit() -> dict[str, Any]:
    registry = default_preset_registry()
    seeds = {
        "application_defaults": dict(APPLICATION_DEFAULTS),
        "pmsm_starting_template": apply_preset(
            APPLICATION_DEFAULTS, registry.get("template.pmsm.v1")
        ),
        "bldc_starting_template": apply_preset(
            APPLICATION_DEFAULTS, registry.get("template.bldc.v1")
        ),
        "ssdr_starting_template": apply_preset(
            APPLICATION_DEFAULTS, registry.get("template.afpm_ssdr.v1")
        ),
    }
    groups: dict[str, Any] = {}
    for group_name, seed in seeds.items():
        legacy_counts: Counter[str] = Counter()
        audited_counts: Counter[str] = Counter()
        severe_samples = 0
        warning_samples = 0
        for parameters in _samples(seed):
            result = LegacyGuiMotorModelBridge(
                parse_legacy_gui_params(parameters)
            ).run_full_analysis()
            assessment = evaluate_design_feasibility(parameters, result)
            legacy_counts.update(_legacy_codes(result))
            audited_counts.update(issue.code for issue in assessment.issues)
            if assessment.has_severe_design_risk:
                severe_samples += 1
            if any(issue.severity.value == "WARNING" for issue in assessment.issues):
                warning_samples += 1
        groups[group_name] = {
            "sample_count": 11,
            "legacy_rule_counts": dict(sorted(legacy_counts.items())),
            "audited_rule_counts": dict(sorted(audited_counts.items())),
            "audited_samples_with_severe_risk": severe_samples,
            "audited_samples_with_warning": warning_samples,
        }
    return {
        "method": "one-at-a-time deterministic perturbations; not population statistics",
        "groups": groups,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    text = json.dumps(run_frequency_audit(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if arguments.output is None:
        print(text, end="")
    else:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
