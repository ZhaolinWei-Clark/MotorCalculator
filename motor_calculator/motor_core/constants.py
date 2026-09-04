"""Shared constants and legacy compatibility factors for the motor calculator."""

from __future__ import annotations

import math

PI = math.pi
MU0 = 4 * PI * 1e-7

RHO_CU_20 = 1.72e-8
RHO_CU_TEMP_COEFF = 0.00393
ALPHA_CU = 0.00393

AIR_DENSITY = 1.225

# Legacy compatibility factors preserved from the single-file calculator.
LEGACY_POWER_SPEED_TO_TORQUE_FACTOR = 9.55
LEGACY_SINE_EMF_FACTOR = 4.44
LEGACY_TRAPEZOIDAL_EMF_FACTOR = 4.0
END_WINDING_LENGTH_FACTOR = 1.3
END_WINDING_INDUCTANCE_RATIO = 0.15
BALANCED_THREE_PHASE_MUTUAL_RATIO = -0.5
AFPM_MUTUAL_REDUCTION_FACTOR = 0.3
CORE_LOSS_RATED_POWER_RATIO = 0.01
WINDAGE_COEFFICIENT = 0.005
BEARING_LOSS_RATED_POWER_RATIO = 0.005
BEARING_LOSS_REFERENCE_SPEED_RPM = 3000.0
VOLTAGE_REQUIREMENT_MARGIN_FACTOR = 1.05

# Validation and optimization defaults.
DEFAULT_FILL_LIMIT = 0.65
DEFAULT_SLOT_COUNT_PER_POLE_PAIR = 6
DEFAULT_COGGING_FACTOR = 0.02

# Phase 9B B2: deterministic adaptive cogging sampling.
#
# The cogging shape is  sin(N*theta) + 0.3*sin(2N*theta) + 0.1*sin(3N*theta)
# with N = LCM(pole_count, slot_count) cycles per MECHANICAL revolution, so the
# highest represented spatial order is
#     H = COGGING_HIGHEST_HARMONIC_MULTIPLE * N
# `np.linspace(0, 2*pi, n)` duplicates the endpoint, so the effective sample
# rate is (n - 1) samples per revolution. Strict Nyquist therefore needs
#     n - 1 > 2*H
# and faithful peak/plot rendering needs S samples per cycle of the highest
# component:
#     n - 1 >= COGGING_SAMPLES_PER_HIGHEST_CYCLE * H
# S = 8 was chosen from a measured sweep: worst RMS error 0.043% against a
# dense reference, against 0.087% at S = 4 and 0.029% at S = 12.
COGGING_HIGHEST_HARMONIC_MULTIPLE = 3
COGGING_SAMPLES_PER_HIGHEST_CYCLE = 8
# Keeps the previous plot density for small LCM. The old fixed grid was
# linspace(0, 2*pi, 360), i.e. 359 intervals.
COGGING_MINIMUM_INTERVALS = 359
# Stability/memory ceiling for pathological slot/pole combinations.
COGGING_MAXIMUM_SAMPLES = 200_001
# Exact maximum of |sin(x) + 0.3*sin(2x) + 0.1*sin(3x)|, Newton-refined and
# cross-checked against a 2e7-point scan. Independent of N, so the reported
# cogging peak can be taken analytically instead of from the sampled trace.
COGGING_SHAPE_PEAK_FACTOR = 1.1283820906416413
DEFAULT_RIPPLE_6TH = 0.05
DEFAULT_RIPPLE_12TH = 0.02

MAGNET_LIBRARY = {
    "N35": {"Br": 1.17, "Hc": 868, "BHmax": 263, "Tmax": 80, "description": "Standard NdFeB"},
    "N38": {"Br": 1.22, "Hc": 899, "BHmax": 287, "Tmax": 80, "description": "Standard NdFeB"},
    "N40": {"Br": 1.25, "Hc": 923, "BHmax": 302, "Tmax": 80, "description": "Standard NdFeB"},
    "N42": {"Br": 1.28, "Hc": 955, "BHmax": 318, "Tmax": 80, "description": "High-performance NdFeB"},
    "N45": {"Br": 1.32, "Hc": 995, "BHmax": 342, "Tmax": 80, "description": "High-performance NdFeB"},
    "N48": {"Br": 1.38, "Hc": 1027, "BHmax": 366, "Tmax": 80, "description": "Very high-performance NdFeB"},
    "N50": {"Br": 1.40, "Hc": 1043, "BHmax": 382, "Tmax": 80, "description": "Very high-performance NdFeB"},
    "N52": {"Br": 1.43, "Hc": 1059, "BHmax": 398, "Tmax": 80, "description": "Top-grade NdFeB"},
    "N35SH": {"Br": 1.17, "Hc": 876, "BHmax": 263, "Tmax": 150, "description": "High-temperature NdFeB"},
    "N38SH": {"Br": 1.22, "Hc": 907, "BHmax": 287, "Tmax": 150, "description": "High-temperature NdFeB"},
    "N42SH": {"Br": 1.28, "Hc": 955, "BHmax": 318, "Tmax": 150, "description": "High-temperature NdFeB"},
    "SmCo28": {"Br": 1.05, "Hc": 796, "BHmax": 210, "Tmax": 300, "description": "SmCo permanent magnet"},
    "SmCo32": {"Br": 1.13, "Hc": 860, "BHmax": 255, "Tmax": 300, "description": "SmCo permanent magnet"},
}

WIRE_AWG_TABLE = {
    "AWG10": {"diameter_mm": 2.588, "area_mm2": 5.26},
    "AWG12": {"diameter_mm": 2.053, "area_mm2": 3.31},
    "AWG14": {"diameter_mm": 1.628, "area_mm2": 2.08},
    "AWG16": {"diameter_mm": 1.291, "area_mm2": 1.31},
    "AWG18": {"diameter_mm": 1.024, "area_mm2": 0.823},
    "AWG20": {"diameter_mm": 0.812, "area_mm2": 0.518},
    "AWG22": {"diameter_mm": 0.644, "area_mm2": 0.326},
    "AWG24": {"diameter_mm": 0.511, "area_mm2": 0.205},
    "AWG26": {"diameter_mm": 0.405, "area_mm2": 0.129},
    "AWG28": {"diameter_mm": 0.321, "area_mm2": 0.081},
    "AWG30": {"diameter_mm": 0.255, "area_mm2": 0.051},
    "AWG32": {"diameter_mm": 0.202, "area_mm2": 0.032},
}

SLOT_TYPES = {
    "开口槽": {"description": "Open rectangular slot", "carter_factor": 1.2},
    "半开口槽": {"description": "Semi-open slot", "carter_factor": 1.1},
    "半闭口槽": {"description": "Semi-closed slot", "carter_factor": 1.05},
    "闭口槽": {"description": "Closed slot", "carter_factor": 1.02},
    "无槽": {"description": "Slotless / coreless design", "carter_factor": 1.0},
}

OPERATING_MODE_PMSM = "pmsm"
OPERATING_MODE_BLDC = "bldc"

LEGACY_WAVEFORM_TO_MODE = {
    "正弦波": OPERATING_MODE_PMSM,
    "PMSM": OPERATING_MODE_PMSM,
    "pmsm": OPERATING_MODE_PMSM,
    "梯形波": OPERATING_MODE_BLDC,
    "BLDC": OPERATING_MODE_BLDC,
    "bldc": OPERATING_MODE_BLDC,
}

MODE_TO_LEGACY_WAVEFORM = {
    OPERATING_MODE_PMSM: "正弦波",
    OPERATING_MODE_BLDC: "梯形波",
}
