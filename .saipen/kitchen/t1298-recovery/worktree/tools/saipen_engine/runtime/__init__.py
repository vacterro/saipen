"""Portable runtime identity and capability projection.

Runtime metadata is session telemetry.  It never owns Work, replaces the
acting ``--agent`` seat, or becomes canonical project state.
"""

from .base import (
    CAPABILITY_NAMES,
    ENV_RUNTIME_INFO,
    RUNTIME_INFO_SCHEMA_VERSION,
    RuntimeInfoError,
    load_runtime_info,
    runtime_projection,
)

__all__ = (
    "CAPABILITY_NAMES",
    "ENV_RUNTIME_INFO",
    "RUNTIME_INFO_SCHEMA_VERSION",
    "RuntimeInfoError",
    "load_runtime_info",
    "runtime_projection",
)
