"""Phase 11A: the experimental / public-reference data framework.

The application can now ingest measurement-shaped data. It still has no
measurements, and this package is built so that those two facts stay separable:
nothing here produces an experimental claim without an experimental source, and
nothing produces a claim about *this* machine without a machine-identity match.

Read :mod:`.sources` first. Everything else depends on the taxonomy it defines.
"""

from __future__ import annotations

from .sources import (
    DatasetSourceType,
    EXPERIMENTAL_SOURCE_TYPES,
    ReclassificationError,
    is_experimental,
    may_reclassify,
)
from .schema import (
    UNKNOWN,
    Citation,
    DatasetMetadata,
    MachineIdentity,
    RedistributionStatus,
    TestType,
)

EXPERIMENT_FRAMEWORK_VERSION = "phase11a.experiment.v1"

__all__ = [
    "EXPERIMENT_FRAMEWORK_VERSION",
    "DatasetSourceType",
    "EXPERIMENTAL_SOURCE_TYPES",
    "ReclassificationError",
    "is_experimental",
    "may_reclassify",
    "UNKNOWN",
    "Citation",
    "DatasetMetadata",
    "MachineIdentity",
    "RedistributionStatus",
    "TestType",
]
