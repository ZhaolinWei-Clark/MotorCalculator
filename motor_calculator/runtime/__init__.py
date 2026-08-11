"""Windows-oriented runtime reliability helpers for source and packaged modes."""

from .display import (
    bounded_window_size,
    dpi_scaled_window_size,
    enable_windows_dpi_awareness,
    windows_work_area,
)
from .health import (
    HealthCheck,
    HealthStatus,
    RuntimeHealthReport,
    check_runtime_health,
    format_startup_failure,
    probe_tk_runtime,
)
from .logging_config import initialize_local_logging
from .paths import (
    RuntimePaths,
    check_packaged_resources,
    create_runtime_directories,
    resolve_runtime_paths,
)

__all__ = [
    "HealthCheck",
    "HealthStatus",
    "RuntimeHealthReport",
    "RuntimePaths",
    "bounded_window_size",
    "check_packaged_resources",
    "check_runtime_health",
    "create_runtime_directories",
    "dpi_scaled_window_size",
    "enable_windows_dpi_awareness",
    "format_startup_failure",
    "initialize_local_logging",
    "probe_tk_runtime",
    "resolve_runtime_paths",
    "windows_work_area",
]
