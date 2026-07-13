"""Digifact FEL SDK — multi-country (Guatemala + República Dominicana)."""
from .client import DigifactClient, DteResult
from .core.exceptions import (
    DigifactApiError,
    DigifactAuthError,
    DigifactError,
    DigifactNitNotFoundError,
    DigifactValidationError,
)
from .providers.gt import GtProvider, GtConfig
from .providers.do import DoProvider, DoConfig

__version__ = "2.1.0"
__all__ = [
    "DigifactClient",
    "DteResult",
    "DigifactError",
    "DigifactAuthError",
    "DigifactApiError",
    "DigifactValidationError",
    "DigifactNitNotFoundError",
    "GtProvider",
    "GtConfig",
    "DoProvider",
    "DoConfig",
]
