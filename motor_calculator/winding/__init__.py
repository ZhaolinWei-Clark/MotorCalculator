"""Winding engineering: electrical axes, topology, and slot manufacturability.

Phase 10G. This package holds the winding questions a user actually asks --
"what winding factor does my slot/pole combination give", "will this many turns
of this wire fit in the slot", "is that manufacturable" -- alongside the
electrical-axis geometry the validation bridge needs.

It computes; it does not modify. Nothing here writes into
``motor_core/calculations.py`` or changes a production result.
"""

from __future__ import annotations
