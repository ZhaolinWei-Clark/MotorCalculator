"""Explicit real-window GUI smoke procedure for source and packaged builds."""

from __future__ import annotations

import json
import math
import sys
import time
import traceback
from pathlib import Path
from typing import Any


def _window_fits_screen(window) -> bool:
    window.update_idletasks()
    return (
        window.winfo_reqwidth() <= window.winfo_screenwidth()
        and window.winfo_reqheight() <= window.winfo_screenheight()
    )


def _calculation_snapshot(result) -> dict[str, float]:
    return {
        "back_emf_phase_rms_v": float(result.electrical.E_phase_rms),
        "back_emf_line_rms_v": float(result.electrical.E_line_rms),
        "phase_resistance_ohm": float(result.electrical.R_phase),
        "phase_inductance_h": float(result.electrical.L_phase),
        "rated_current_rms_a": float(result.performance.I_phase_rms),
        "efficiency_percent": float(result.performance.Efficiency),
        "required_voltage_v": float(result.performance.V_required),
    }


def _install_nonblocking_messages(main_window_module, legacy_module) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []

    def recorder(kind: str):
        def record(title: str, message: str, **_kwargs: Any) -> None:
            messages.append({"kind": kind, "title": str(title), "message": str(message)})

        return record

    for module in (main_window_module.messagebox, legacy_module.messagebox):
        module.showinfo = recorder("info")
        module.showwarning = recorder("warning")
        module.showerror = recorder("error")
    return messages


def _submit_smoke_feedback(app, main_window_module) -> tuple[int, int]:
    from motor_calculator.gui.feedback_dialog import FeedbackDialogValues
    from motor_calculator.validation.feedback_models import ValidationEvidenceType
    from motor_calculator.validation.feedback_service import load_feedback_records

    before = len(load_feedback_records(app._feedback_store))
    options = app._feedback_metric_options()
    option = options["phase_resistance_ohm"]
    values = FeedbackDialogValues(
        metric_name=option.metric_name,
        reference_value=option.predicted_value,
        reference_unit=option.unit,
        evidence_type=ValidationEvidenceType.ANALYTICAL_REFERENCE,
        speed_rpm=float(app._get_params()["n_rated"]),
        current_a=None,
        voltage_v=None,
        temperature_c=None,
        source_name="Phase 8A.2 packaged smoke",
        source_reference="local runtime smoke record",
        notes="Runtime persistence verification only; not calibration evidence.",
        reference_semantics=option.semantics,
    )
    original_dialog = main_window_module.ValidationFeedbackDialog

    class SmokeFeedbackDialog:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def show(self):
            return values

    main_window_module.ValidationFeedbackDialog = SmokeFeedbackDialog
    try:
        app._add_validation_feedback()
    finally:
        main_window_module.ValidationFeedbackDialog = original_dialog
    after = len(load_feedback_records(app._feedback_store))
    if after != before + 1:
        raise RuntimeError("feedback record was not appended exactly once")
    return before, after


def _exercise_dialogs(root, app, screenshot_base: Path) -> dict[str, Any]:
    from motor_calculator.gui.feedback_dialog import ValidationFeedbackDialog
    from motor_calculator.gui.uncertainty_dialog import UncertaintyAssumptionDialog
    from motor_calculator.validation.uncertainty_models import load_uncertainty_specification

    feedback = ValidationFeedbackDialog(
        root,
        app._feedback_metric_options(),
        default_speed=float(app._get_params()["n_rated"]),
    )
    feedback.window.update()
    feedback_fits = _window_fits_screen(feedback.window)
    feedback_screenshot = screenshot_base.with_name(screenshot_base.stem + "-feedback.png")
    feedback_screenshot_error = _capture_window(feedback.window, feedback_screenshot)
    feedback.window.destroy()

    specification = load_uncertainty_specification(
        app._runtime_paths.resource(
            "validation_data",
            "uncertainty",
            "phase7i_afpm_back_emf_uncertainty.json",
        )
    )
    uncertainty = UncertaintyAssumptionDialog(root, specification.parameters)
    uncertainty.window.update()
    uncertainty_fits = _window_fits_screen(uncertainty.window)
    uncertainty_screenshot = screenshot_base.with_name(screenshot_base.stem + "-uncertainty.png")
    uncertainty_screenshot_error = _capture_window(uncertainty.window, uncertainty_screenshot)
    uncertainty.window.destroy()
    root.update()
    return {
        "feedback_dialog_opened": True,
        "feedback_dialog_fits_screen": feedback_fits,
        "feedback_dialog_screenshot": str(feedback_screenshot),
        "feedback_dialog_screenshot_error": feedback_screenshot_error,
        "uncertainty_dialog_opened": True,
        "uncertainty_dialog_fits_screen": uncertainty_fits,
        "uncertainty_dialog_screenshot": str(uncertainty_screenshot),
        "uncertainty_dialog_screenshot_error": uncertainty_screenshot_error,
    }


def _capture_window(root, destination: Path) -> str | None:
    try:
        from PIL import ImageGrab

        root.update()
        destination.parent.mkdir(parents=True, exist_ok=True)
        if sys.platform == "win32":
            image = ImageGrab.grab(
                window=root.winfo_id(),
                include_layered_windows=True,
                all_screens=True,
            )
        else:
            left = root.winfo_rootx()
            top = root.winfo_rooty()
            right = left + root.winfo_width()
            bottom = top + root.winfo_height()
            image = ImageGrab.grab(bbox=(left, top, right, bottom), all_screens=True)
        image.save(destination)
    except Exception:
        return traceback.format_exc()
    return None


def run_real_gui_smoke(root, app, output_path: Path) -> None:
    """Exercise the real GUI, persist evidence/export, write JSON, then exit."""

    from motor_calculator.gui import main_window as main_window_module
    from motor_calculator.validation.confidence_summary import export_confidence_summary
    from motor_calculator.validation.feedback_service import load_feedback_records
    from motor_calculator.runtime.display import windows_work_area

    output = Path(output_path).resolve()
    screenshot = output.with_suffix(".png")
    payload: dict[str, Any] = {
        "status": "FAILED",
        "mode": app._runtime_paths.mode,
        "user_data_dir": str(app._runtime_paths.user_data_dir),
        "feedback_store": str(app._feedback_store),
        "log_file": str(app._runtime_paths.log_file),
        "screenshot": str(screenshot),
    }
    try:
        legacy_module = main_window_module._get_legacy_module()
        messages = _install_nonblocking_messages(main_window_module, legacy_module)
        root.deiconify()
        root.update()
        tab_names = tuple(
            str(app.notebook.tab(index, "text")) for index in range(app.notebook.index("end"))
        )
        if "Confidence & Validation" not in tab_names:
            raise RuntimeError("Confidence & Validation tab is missing")
        app.run_analysis()
        root.update()
        if not getattr(app, "calc_results", None):
            raise RuntimeError("GUI calculation did not produce results")
        calculation = _calculation_snapshot(app.calc_results)
        if not all(math.isfinite(value) for value in calculation.values()):
            raise RuntimeError("GUI calculation produced non-finite output")
        dialog_results = _exercise_dialogs(root, app, screenshot)
        records_before, records_after = _submit_smoke_feedback(app, main_window_module)
        confidence_export = app._runtime_paths.export_dir / "phase8a2_smoke_confidence.json"
        export_confidence_summary(
            app._engineering_confidence_summary,
            confidence_export,
            format_name="json",
        )
        if not confidence_export.is_file():
            raise RuntimeError("confidence export was not created")
        app.notebook.select(app.confidence_tab)
        root.deiconify()
        root.lift()
        root.update_idletasks()
        root.update()
        time.sleep(0.2)
        root.update()
        screenshot_error = _capture_window(root, screenshot)
        payload.update(
            {
                "status": "PASS",
                "tabs": tab_names,
                "calculation": calculation,
                "root_size": [root.winfo_width(), root.winfo_height()],
                "screen_size": [root.winfo_screenwidth(), root.winfo_screenheight()],
                "work_area": list(
                    windows_work_area(root.winfo_screenwidth(), root.winfo_screenheight())
                ),
                "screen_dpi": float(root.winfo_fpixels("1i")),
                "tk_scaling": float(root.tk.call("tk", "scaling")),
                "root_fits_screen": _window_fits_screen(root),
                "matplotlib_available": bool(legacy_module.MATPLOTLIB_AVAILABLE),
                "messages": messages,
                "feedback_records_before": records_before,
                "feedback_records_after": records_after,
                "feedback_records_reloaded": len(load_feedback_records(app._feedback_store)),
                "confidence_export": str(confidence_export),
                "confidence_export_exists": confidence_export.is_file(),
                "screenshot_error": screenshot_error,
                **dialog_results,
            }
        )
    except Exception as exc:
        payload["error"] = str(exc)
        payload["traceback"] = traceback.format_exc()
    finally:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        root.after_idle(root.destroy)
