"""Abstract base provider for country-specific Digifact implementations."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class DteResult:
    """Result of a DTE emission (shared by all countries)."""

    auth_number: str
    series: str
    number: str
    issue_datetime: str
    raw: dict = field(default_factory=dict)

    @property
    def auth_number_upper(self) -> str:
        return self.auth_number.upper()


class BaseProvider(ABC):
    """Abstract interface that every country provider must implement.

    Concrete providers (GtProvider, DoProvider, …) subclass this and
    implement the five core DTE operations plus authentication.
    """

    @abstractmethod
    def authenticate(self) -> str:
        """Authenticate and return a bearer token."""
        ...

    @abstractmethod
    def invoice(
        self,
        buyer: str | dict,
        items: list[dict],
        *,
        doc_type: str = "FACT",
        **kwargs: Any,
    ) -> DteResult:
        """Emit an invoice / DTE."""
        ...

    @abstractmethod
    def credit_note(
        self,
        buyer: str | dict,
        items: list[dict],
        origin: dict,
        reason: str,
        **kwargs: Any,
    ) -> DteResult:
        """Emit a credit note."""
        ...

    @abstractmethod
    def debit_note(
        self,
        buyer: str | dict,
        items: list[dict],
        origin: dict,
        reason: str,
        **kwargs: Any,
    ) -> DteResult:
        """Emit a debit note."""
        ...

    @abstractmethod
    def get_document(self, auth_number: str, fmt: str = "JSON") -> dict:
        """Retrieve a DTE document (XML/HTML/PDF/JSON)."""
        ...

    @abstractmethod
    def cancel(self, auth_number: str, receiver_id: str, issue_datetime: str, reason: str = "Anulación") -> dict:
        """Cancel a DTE."""
        ...