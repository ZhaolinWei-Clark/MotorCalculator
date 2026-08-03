"""Markdown report generation for Phase 6A sensitivity summaries."""

from __future__ import annotations

from pathlib import Path

from .sensitivity import SensitivityOutputChange, SensitivityRunResult, SensitivitySummary


def generate_sensitivity_markdown_report(summary: SensitivitySummary) -> str:
    lines: list[str] = [
        "# Phase 6A 参数敏感性沙盒预览报告",
        "",
        "更新时间：2026-07-10",
        "",
        "## 1. Sandbox boundary statement",
        "",
        "本报告由 Phase 6A read-only sensitivity sandbox 生成，只回答：如果某个输入参数临时变化，现有模型输出会怎样变化。",
        "",
        "本报告不执行 calibration，不拟合参数，不生成 calibrated model，也不允许把任何结果写回 production defaults。",
        "",
        "## 2. Tested parameters",
        "",
        "| parameter | internal field | unit | status | notes |",
        "|---|---|---|---|---|",
    ]
    for target in summary.tested_parameters:
        status = "available" if target.available else "unavailable"
        lines.append(
            f"| `{target.parameter_name}` | `{target.internal_field_name or 'N/A'}` | "
            f"{target.unit or 'N/A'} | {status} | {target.notes} |"
        )

    lines.extend(
        [
            "",
            "## 3. Perturbation table",
            "",
            "| parameter | perturbation | baseline | temporary | status |",
            "|---|---:|---:|---:|---|",
        ]
    )
    for result in summary.run_results:
        spec = result.perturbation
        lines.append(
            f"| `{spec.parameter_name}` | {spec.perturbation_percent:+.1f}% | "
            f"{_format_value(spec.baseline_value)} | {_format_value(spec.temporary_value)} | {result.status} |"
        )

    lines.extend(
        [
            "",
            "## 4. Output sensitivity table",
            "",
            "| parameter | perturbation | output | baseline | temporary | relative change | status |",
            "|---|---:|---|---:|---:|---:|---|",
        ]
    )
    for result in summary.run_results:
        for change in result.affected_outputs:
            lines.append(_format_output_change_row(result, change))

    lines.extend(
        [
            "",
            "## 5. Most sensitive parameters",
            "",
            "| output | most sensitive parameter in this sweep |",
            "|---|---|",
        ]
    )
    for output_name, parameter_name in summary.most_sensitive_parameters.items():
        lines.append(f"| `{output_name}` | `{parameter_name or 'N/A'}` |")

    lines.extend(
        [
            "",
            "## 6. Nonlinear / unstable behavior notes",
            "",
        ]
    )
    if summary.nonlinear_or_unstable_notes:
        for note in summary.nonlinear_or_unstable_notes:
            lines.append(f"- {note}")
    else:
        lines.append("- 本轮 sweep 没有检测到运行错误；integer 输入仍需注意 rounding 对小扰动的影响。")

    lines.extend(
        [
            "",
            "## 7. Warnings",
            "",
        ]
    )
    for warning in summary.boundary_warnings:
        lines.append(f"- {warning}")
    lines.append("- 本报告中的敏感性排名只描述当前 baseline 附近的局部响应，不代表推荐校准方向。")
    lines.append("")
    return "\n".join(lines)


def write_sensitivity_markdown_report(summary: SensitivitySummary, report_path: str | Path) -> Path:
    path = Path(report_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(generate_sensitivity_markdown_report(summary), encoding="utf-8")
    return path


def _format_output_change_row(result: SensitivityRunResult, change: SensitivityOutputChange) -> str:
    return (
        f"| `{result.perturbation.parameter_name}` | {result.perturbation.perturbation_percent:+.1f}% | "
        f"`{change.output_name}` | {_format_value(change.baseline_value)} | {_format_value(change.temporary_value)} | "
        f"{_format_percent(change.relative_change_percent)} | {change.status} |"
    )


def _format_value(value: float | int | None) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, int):
        return str(value)
    return f"{value:.6g}"


def _format_percent(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{value:+.4g}%"
