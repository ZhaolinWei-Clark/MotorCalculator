"""The Phase 10A reference validation case.

One deterministic, fully declared case that can be rebuilt from source at any
time. It carries *no* expected FEA numbers: the file records what will be asked
of the solver, not what the solver is supposed to answer. Expected numerical FEA
values may only be added after a real solver run.

Why this design was chosen as the first reference
-------------------------------------------------
MotorCalculator models exactly one machine family, the axial-flux single-stator
dual-rotor PM machine; there is no radial-flux topology in the input schema at
all, so a radial-flux reference would validate a machine the application cannot
compute. Within that family the *coreless* variant is the one whose analytical
magnetic circuit maps onto exactly one physical geometry:

* the analytical effective gap ``h_coil + 2g`` is literally the space between
  the two magnet faces, because the stator really is coils in air;
* the analytical MMF ``2 * H_c * h_m`` against ``2 * h_m`` of magnet reluctance
  is exactly two magnets in series across that gap;
* there is no stator iron, so no B-H curve has to be invented and no saturation
  is introduced that the analytical model never claimed to model;
* the problem is linear, which makes a single-mesh solve reproducible.

The cored variant is only ``PARTIALLY_SUPPORTED``: its magnet arrangement (N-N
with yoke return versus N-S through-flux) is not declared anywhere in the
schema, and the analytical gap keeps the coil height even when a core is
present. Choosing it first would have meant guessing the machine.
"""

from __future__ import annotations

from typing import Any, Mapping

from .case_builder import FEAModellingParameters
from .models import FEAValidationTarget

PHASE10A_REFERENCE_ID = "phase10a_coreless_ssdr_reference_v1"

#: The reference design, in legacy GUI parameter form so it can be typed into
#: the application and reproduced by hand.
PHASE10A_REFERENCE_PARAMETERS: Mapping[str, Any] = {
    "V_dc": 48.0,
    "P_rated": 800.0,
    "n_rated": 2500.0,
    "Temp_coil": 80.0,
    "D_out": 140.0,
    "D_in": 70.0,
    "g_side": 1.0,
    "D_stator_out": 138.0,
    "D_stator_in": 72.0,
    "h_stator": 20.0,
    "h_coil": 5.0,
    "h_yoke": 5.0,
    "slots": 24,
    "slot_type": "无槽",
    "h_slot": 15.0,
    "w_slot_top": 8.0,
    "w_slot_bottom": 6.0,
    "h_slot_opening": 1.0,
    "w_slot_opening": 3.0,
    "h_wedge": 2.0,
    "h_mag": 5.0,
    "w_magnet": 20.0,
    "L_magnet": 30.0,
    "magnet_type": "表贴式",
    "magnetization": "径向充磁",
    "p": 8,
    "magnet_grade": "N42",
    "Br": 1.28,
    "alpha_p": 0.70,
    "sigma_m": 1.15,
    "mu_r_mag": 1.05,
    "N_ph_turns": 50,
    "d_wire": 0.9,
    "n_parallel": 2,
    "k_w": 0.93,
    "fill_limit": 0.65,
    "waveform": "正弦波",
    "k_cogging": 0.02,
    "k_ripple_6": 0.05,
    "k_ripple_12": 0.02,
    "coreless": True,
}

#: The two values the FEA needs and the MotorCalculator schema does not carry.
#: Both are declared, not derived, and their provenance says so.
PHASE10A_REFERENCE_MODELLING = FEAModellingParameters(
    rotor_back_iron_thickness_m=0.006,
    # Q = 24, 2p = 16 gives a full pitch of 1.5 slots, so the physical winding is
    # a concentrated one-slot-span winding. The MotorCalculator schema does not
    # record a coil span, so it is declared here.
    coil_span_slots=1,
    provenance=(
        "rotor back-iron thickness (6 mm) and coil span (1 slot) are declared "
        "FEA-only modelling parameters for reference case "
        f"{PHASE10A_REFERENCE_ID}; neither exists in the MotorCalculator input "
        "schema and neither was derived from an analytical result"
    ),
)

#: The three targets the reference case covers.
PHASE10A_REFERENCE_TARGETS = (
    FEAValidationTarget.NO_LOAD_BACK_EMF,
    FEAValidationTarget.AVERAGE_TORQUE,
    FEAValidationTarget.COGGING_TORQUE,
)

REFERENCE_SELECTION_RATIONALE = (
    "MotorCalculator has no radial-flux topology in its input schema, so the first "
    "reference must come from the axial-flux family it actually models. Within that "
    "family the coreless single-stator dual-rotor machine is the only variant whose "
    "analytical magnetic circuit corresponds to exactly one physical geometry, needs "
    "no invented B-H curve, and stays linear."
)

NO_EXPECTED_FEA_VALUES_STATEMENT = (
    "This reference records the case definition only. It contains no expected FEA "
    "numbers, because no solver has produced any. Expected values may be added only "
    "after a real solver run, together with that run's provenance."
)


def build_reference_case(target: FEAValidationTarget):
    """Rebuild the reference case for one target, from source, deterministically."""

    from ..motor_core.calculations import LegacyGuiMotorModelBridge
    from ..motor_core.validation import parse_legacy_gui_params
    from .case_builder import build_validation_case

    bridge = LegacyGuiMotorModelBridge(
        parse_legacy_gui_params(dict(PHASE10A_REFERENCE_PARAMETERS))
    )
    analysis = bridge.run_full_analysis()
    return build_validation_case(
        bridge.input_data,
        analysis,
        target=target,
        modelling=PHASE10A_REFERENCE_MODELLING,
        winding_factor_provenance="manual_user_input_reference_design",
    )
