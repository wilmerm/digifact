"""Core shared modules — country-agnostic base classes, helpers, and exceptions."""
from .money import fmt, calc_iva
from .exceptions import (
    DigifactError,
    DigifactAuthError,
    DigifactApiError,
    DigifactValidationError,
    DigifactNitNotFoundError,
    classify_error,
)

__all__ = [
    "fmt",
    "calc_iva",
    "DigifactError",
    "DigifactAuthError",
    "DigifactApiError",
    "DigifactValidationError",
    "DigifactNitNotFoundError",
    "classify_error",
]