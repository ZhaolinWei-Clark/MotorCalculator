"""Mathematical verification for the Phase 6H FOC transform foundation."""

from __future__ import annotations

import math

import pytest

from dynamics import (
    ABCPhaseValues,
    AlphaBetaValues,
    clarke_transform,
    electrical_angle,
    inverse_clarke_transform,
    inverse_park_transform,
    park_transform,
    wrap_electrical_angle,
)


def _assert_abc_close(actual: ABCPhaseValues, expected: ABCPhaseValues) -> None:
    assert actual.a == pytest.approx(expected.a, abs=1.0e-12)
    assert actual.b == pytest.approx(expected.b, abs=1.0e-12)
    assert actual.c == pytest.approx(expected.c, abs=1.0e-12)


def _assert_alpha_beta_close(
    actual: AlphaBetaValues,
    expected: AlphaBetaValues,
) -> None:
    assert actual.alpha == pytest.approx(expected.alpha, abs=1.0e-12)
    assert actual.beta == pytest.approx(expected.beta, abs=1.0e-12)


def test_clarke_transform_maps_balanced_abc_example():
    result = clarke_transform(ABCPhaseValues(a=1.0, b=-0.5, c=-0.5))

    assert result.alpha == pytest.approx(1.0)
    assert result.beta == pytest.approx(0.0, abs=1.0e-12)


@pytest.mark.parametrize(
    "abc",
    [
        ABCPhaseValues(a=1.0, b=-0.5, c=-0.5),
        ABCPhaseValues(a=0.0, b=math.sqrt(3.0) / 2.0, c=-math.sqrt(3.0) / 2.0),
        ABCPhaseValues(a=2.0, b=-3.0, c=1.0),
    ],
)
def test_inverse_clarke_round_trip_for_balanced_inputs(abc: ABCPhaseValues):
    rebuilt = inverse_clarke_transform(clarke_transform(abc))

    _assert_abc_close(rebuilt, abc)


def test_park_transform_at_zero_angle_preserves_axes():
    alpha_beta = AlphaBetaValues(alpha=1.25, beta=-0.75)

    result = park_transform(alpha_beta, theta_e_rad=0.0)

    assert result.d == pytest.approx(alpha_beta.alpha)
    assert result.q == pytest.approx(alpha_beta.beta)


@pytest.mark.parametrize(
    "theta_e_rad",
    [0.0, math.pi / 6.0, math.pi / 2.0, math.pi, math.tau],
)
def test_park_inverse_round_trip_for_multiple_angles(theta_e_rad: float):
    original = AlphaBetaValues(alpha=1.75, beta=-0.4)

    rebuilt = inverse_park_transform(
        park_transform(original, theta_e_rad),
        theta_e_rad,
    )

    _assert_alpha_beta_close(rebuilt, original)


@pytest.mark.parametrize(
    ("abc", "theta_e_rad"),
    [
        (ABCPhaseValues(a=1.0, b=-0.5, c=-0.5), 0.0),
        (ABCPhaseValues(a=0.25, b=0.75, c=-1.0), math.pi / 3.0),
        (ABCPhaseValues(a=-2.0, b=0.5, c=1.5), -math.pi / 4.0),
    ],
)
def test_full_abc_alpha_beta_dq_round_trip(
    abc: ABCPhaseValues,
    theta_e_rad: float,
):
    alpha_beta = clarke_transform(abc)
    dq = park_transform(alpha_beta, theta_e_rad)
    rebuilt_alpha_beta = inverse_park_transform(dq, theta_e_rad)
    rebuilt_abc = inverse_clarke_transform(rebuilt_alpha_beta)

    _assert_abc_close(rebuilt_abc, abc)


def test_electrical_angle_is_pole_pairs_times_mechanical_angle():
    assert electrical_angle(theta_m_rad=0.75, pole_pairs=4) == pytest.approx(3.0)
    assert electrical_angle(theta_m_rad=-math.pi, pole_pairs=3) == pytest.approx(-3.0 * math.pi)


@pytest.mark.parametrize(
    ("angle", "expected"),
    [
        (0.0, 0.0),
        (math.tau, 0.0),
        (-math.pi / 2.0, 3.0 * math.pi / 2.0),
        (5.0 * math.tau + 0.25, 0.25),
        (-2.0 * math.tau, 0.0),
    ],
)
def test_electrical_angle_wrapping_stays_in_half_open_interval(
    angle: float,
    expected: float,
):
    wrapped = wrap_electrical_angle(angle)

    assert 0.0 <= wrapped < math.tau
    assert wrapped == pytest.approx(expected, abs=1.0e-12)


def test_inverse_clarke_output_is_always_balanced():
    abc = inverse_clarke_transform(AlphaBetaValues(alpha=2.5, beta=-1.25))

    assert abc.a + abc.b + abc.c == pytest.approx(0.0, abs=1.0e-12)


@pytest.mark.parametrize("pole_pairs", [0, -1, 1.5, True])
def test_electrical_angle_rejects_invalid_pole_pair_counts(pole_pairs):
    with pytest.raises(ValueError, match="positive integer"):
        electrical_angle(theta_m_rad=1.0, pole_pairs=pole_pairs)
