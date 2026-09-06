"""Phase 10B: real FEMM bring-up.

Two kinds of test live here, deliberately separated.

*Unit tests* run everywhere. They cover script generation, output parsing, the
sanity-check logic and the hardened availability probe, none of which need a
solver.

*Integration tests* are marked ``femm_integration`` and skip when FEMM is
absent. An optional external solver must never make normal regression fail, and
its absence must never be papered over with mock data.
"""

from __future__ import annotations

import math

import pytest

from motor_calculator.fea.availability import (
    FEMM_ASSOCIATED_EXTENSIONS,
    FEMM_AVAILABILITY_PROBE_VERSION,
    FEMM_REGISTRY_APP_PATHS,
    FEMM_UNINSTALL_DISPLAY_NAME_TOKEN,
    FEMMAvailability,
    detect_femm,
)
from motor_calculator.fea.bringup import (
    BRINGUP_DIRECTORY_NAME,
    BRINGUP_MAGNET_HEIGHT_M,
    BRINGUP_MAGNET_REMANENCE_T,
    BRINGUP_PROBE_ABOVE_POLE,
    BRINGUP_TIMEOUT_SECONDS,
    FEMM_BRINGUP_VERSION,
    build_bringup_script,
    evaluate_bringup_checks,
    parse_bringup_output,
    run_bringup,
)

FEMM_REPORT = detect_femm()
FEMM_PRESENT = FEMM_REPORT.is_available

requires_femm = pytest.mark.skipif(
    not FEMM_PRESENT,
    reason=(
        "FEMM is not installed on this machine; real-solver integration tests are "
        "blocked, not failed"
    ),
)


# ---------------------------------------------------------------------------
# Availability probe hardening
# ---------------------------------------------------------------------------


def test_probe_version_records_the_widened_search():
    assert FEMM_AVAILABILITY_PROBE_VERSION == "phase10b.femm.probe.v2"


def test_probe_searches_the_registry_and_every_fixed_drive():
    report = detect_femm()
    searched = report.searched_locations
    assert searched
    # PATH is still probed first.
    assert any(entry.startswith("PATH:") for entry in searched)
    # A relocated install on a non-system drive would previously have been
    # missed entirely.
    drives = {entry[:2] for entry in searched if len(entry) > 2 and entry[1] == ":"}
    assert len(drives) >= 1
    # Per-user installs.
    assert any("Programs" in entry for entry in searched)


def test_probe_never_raises_and_always_returns_one_verdict():
    report = detect_femm()
    assert report.availability in (
        FEMMAvailability.FEMM_AVAILABLE,
        FEMMAvailability.FEMM_NOT_INSTALLED,
    )
    assert report.is_available is not report.execution_blocked


def test_uninstall_token_is_narrow_enough_to_avoid_false_positives():
    """A looser token matches unrelated software and would misdirect the adapter.

    'Autodesk Interoperability Engine Manager' is present on this machine and
    contains 'opera'; it is not an FEA solver.
    """

    assert FEMM_UNINSTALL_DISPLAY_NAME_TOKEN == "femm"
    assert "femm" not in "autodesk interoperability engine manager"


def test_registry_probe_targets_are_the_canonical_windows_locations():
    assert any("App Paths" in entry for entry in FEMM_REGISTRY_APP_PATHS)
    assert FEMM_ASSOCIATED_EXTENSIONS == (".fem",)


def test_an_override_pointing_at_a_real_file_wins(tmp_path):
    fake = tmp_path / "femm.exe"
    fake.write_bytes(b"")
    report = detect_femm(environment_override=str(fake))
    assert report.availability is FEMMAvailability.FEMM_AVAILABLE
    assert report.executable_path == fake.resolve()


# ---------------------------------------------------------------------------
# Bring-up script generation
# ---------------------------------------------------------------------------


def test_bringup_script_defines_solve_and_extracts(tmp_path):
    script = build_bringup_script(
        fem_path=tmp_path / "b.fem", output_path=tmp_path / "b.csv"
    )
    # Problem definition, material, geometry, boundary, solve, extract, close.
    for fragment in (
        "newdocument(0)",
        "mi_probdef",
        '"planar"',
        "mi_addmaterial",
        "mi_addboundprop",
        "mi_analyze(1)",
        "mi_loadsolution()",
        "mo_getb",
        "closefile(handle)",
        "mi_close()",
    ):
        assert fragment in script, fragment
    assert FEMM_BRINGUP_VERSION in script


def test_bringup_script_probes_all_three_points(tmp_path):
    script = build_bringup_script(
        fem_path=tmp_path / "b.fem", output_path=tmp_path / "b.csv"
    )
    assert script.count("mo_getb") == 3
    for name in ("magnet_centre", "above_pole", "far_field"):
        assert name in script


def test_bringup_magnetisation_direction_is_declared_positive_y(tmp_path):
    """90 degrees is +y in FEMM's convention; the polarity check depends on it."""

    script = build_bringup_script(
        fem_path=tmp_path / "b.fem", output_path=tmp_path / "b.csv"
    )
    assert '"bringup_magnet", 0,' in script
    assert ', "", 90, 1, 0)' in script
    assert BRINGUP_PROBE_ABOVE_POLE[1] > BRINGUP_MAGNET_HEIGHT_M / 2.0


def test_bringup_workspace_name_contains_a_space_on_purpose(tmp_path):
    """Quoting a path with a space is one of the things bring-up must prove."""

    assert " " in BRINGUP_DIRECTORY_NAME
    script = build_bringup_script(
        fem_path=tmp_path / "with space" / "b.fem",
        output_path=tmp_path / "with space" / "b.csv",
    )
    assert "with space" in script
    # The path must be a quoted Lua string, not a bare token.
    assert 'mi_saveas("' in script


def test_bringup_script_escapes_windows_separators(tmp_path):
    script = build_bringup_script(
        fem_path=tmp_path / "b.fem", output_path=tmp_path / "b.csv"
    )
    for line in script.splitlines():
        if line.startswith("mi_saveas("):
            # A Windows path must reach Lua with escaped backslashes.
            assert "\\\\" in line or "/" in line


# ---------------------------------------------------------------------------
# Output parsing
# ---------------------------------------------------------------------------


def test_bringup_output_parses():
    probes = parse_bringup_output(
        "probe,bx_t,by_t\nmagnet_centre,0.0,0.9\nabove_pole,0.0,0.35\nfar_field,0.0,0.001\n"
    )
    assert probes["magnet_centre"] == (0.0, 0.9)
    assert probes["far_field"] == (0.0, 0.001)


def test_bringup_output_rejects_non_finite_and_malformed():
    with pytest.raises(ValueError):
        parse_bringup_output("probe,bx_t,by_t\nmagnet_centre,0.0,nan\n")
    with pytest.raises(ValueError):
        parse_bringup_output("probe,bx_t,by_t\nmagnet_centre,0.0\n")
    with pytest.raises(ValueError, match="no probe values"):
        parse_bringup_output("probe,bx_t,by_t\n")


# ---------------------------------------------------------------------------
# Sanity-check logic
# ---------------------------------------------------------------------------


def _probes(centre=(0.0, 0.9), above=(0.0, 0.35), far=(0.0, 0.001)):
    return {"magnet_centre": centre, "above_pole": above, "far_field": far}


def test_a_physically_sensible_field_passes_every_check():
    checks = evaluate_bringup_checks(_probes())
    assert checks
    assert all(check.passed for check in checks), [c.name for c in checks if not c.passed]


def test_a_dead_field_is_caught():
    checks = {c.name: c for c in evaluate_bringup_checks(_probes(centre=(0.0, 0.0)))}
    assert checks["field_is_nonzero"].passed is False


def test_an_inverted_magnet_is_caught():
    checks = {c.name: c for c in evaluate_bringup_checks(_probes(above=(0.0, -0.35)))}
    assert checks["pole_face_polarity"].passed is False


def test_a_units_error_is_caught():
    huge = BRINGUP_MAGNET_REMANENCE_T * 1000.0
    checks = {c.name: c for c in evaluate_bringup_checks(_probes(centre=(0.0, huge)))}
    assert checks["field_below_remanence"].passed is False


def test_a_boundary_loading_the_solution_is_caught():
    checks = {c.name: c for c in evaluate_bringup_checks(_probes(far=(0.0, 5.0)))}
    assert checks["field_decays_with_distance"].passed is False


def test_a_rotated_geometry_is_caught():
    checks = {c.name: c for c in evaluate_bringup_checks(_probes(above=(0.5, 0.05)))}
    assert checks["pole_face_is_dominantly_axial"].passed is False


def test_missing_probes_fail_rather_than_pass_vacuously():
    checks = evaluate_bringup_checks({"magnet_centre": (0.0, 0.9)})
    assert len(checks) == 1
    assert checks[0].passed is False
    assert "missing probe" in checks[0].detail


# ---------------------------------------------------------------------------
# Blocked behaviour without a solver
# ---------------------------------------------------------------------------


@pytest.mark.skipif(FEMM_PRESENT, reason="FEMM is installed on this machine")
def test_bringup_reports_blocked_and_fabricates_nothing():
    outcome = run_bringup()
    assert outcome.status == "BLOCKED_BY_ENVIRONMENT"
    assert outcome.passed is False
    assert outcome.b_magnet_centre_t is None
    assert outcome.b_above_pole_y_t is None
    assert outcome.b_far_field_t is None
    assert outcome.exit_code is None
    assert outcome.checks == ()
    assert "not installed" in outcome.detail


def test_bringup_timeout_is_bounded():
    assert 0.0 < BRINGUP_TIMEOUT_SECONDS <= 600.0


def test_bringup_never_uses_a_shell():
    import inspect

    from motor_calculator.fea import bringup

    source = inspect.getsource(bringup.run_bringup)
    assert "shell=False" in source
    assert "shell=True" not in source
    assert "timeout=" in source


# ---------------------------------------------------------------------------
# Real-solver integration tests. Skipped, never failed, when FEMM is absent.
# ---------------------------------------------------------------------------


@requires_femm
@pytest.mark.femm_integration
def test_real_femm_bringup_solves_and_exits_cleanly():
    outcome = run_bringup()
    assert outcome.status in ("PASS", "FAIL"), outcome.detail
    assert outcome.exit_code == 0, f"FEMM exit {outcome.exit_code}: {outcome.stderr_tail}"
    assert outcome.b_magnet_centre_t is not None
    assert math.isfinite(outcome.b_magnet_centre_t)
    failed = [check.name for check in outcome.checks if not check.passed]
    assert outcome.status == "PASS", f"failed sanity checks: {failed}"


@requires_femm
@pytest.mark.femm_integration
def test_real_femm_bringup_records_full_provenance():
    outcome = run_bringup()
    assert outcome.executable_path
    assert outcome.script_sha256 and len(outcome.script_sha256) == 64
    assert outcome.workspace and BRINGUP_DIRECTORY_NAME in outcome.workspace
    assert outcome.seconds is not None and outcome.seconds > 0.0
