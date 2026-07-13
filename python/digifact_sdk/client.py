"""DigifactClient — main entry point for the multi-country Digifact SDK.

Use ``country="GT"`` (default) for Guatemala SAT FEL or ``country="DO"``
for República Dominicana DGII e-CF.
"""
from __future__ import annotations

from typing import Any

from .core.base_provider import BaseProvider, DteResult
from .core.exceptions import (
    DigifactApiError,
    DigifactAuthError,
    DigifactError,
    DigifactNitNotFoundError,
    DigifactValidationError,
)
from .providers.gt.gt_config import GtConfig
from .providers.gt.gt_provider import GtProvider
from .providers.do.do_config import DoConfig
from .providers.do.do_provider import DoProvider


class DigifactClient:
    """High-level multi-country client for Digifact APIs.

    Parameters
    ----------
    taxid : str
        Fiscal ID of the issuer.
        - GT: NIT (digits only or with separators, padded to 12 chars internally).
        - DO: RNC (9 digits, no hyphens).
    username : str
        Short Digifact username (the part after the ``GT.`` or ``DO.`` prefix).
    password : str, optional
        Account password. Required unless ``token`` is supplied.
    country : {"GT", "DO"}, default "GT"
        Country code:

        - ``"GT"`` → Guatemala SAT FEL (default, preserves full backward
          compatibility).
        - ``"DO"`` → República Dominicana DGII e-CF.
    environment : {"test", "production"}, default "test"
        Target environment.
    token : str, optional
        Pre-obtained bearer token. If provided, login is skipped.
    timeout : int, default 120
        HTTP request timeout in seconds.
    **kwargs
        Additional country-specific parameters forwarded to the provider.
        For GT: ``afiliacion_iva``, ``tipo_frase``, ``escenario``,
        ``frases``, ``auto_fuel_subsidy_frases``, ``branch_code``,
        ``branch_name``, ``seller_name``, ``seller_address``,
        ``tipo_personeria``, ``petroleo_rates``.
        For DO: ``seller_name``, ``seller_address``.
    """

    def __init__(
        self,
        taxid: str,
        username: str,
        password: str = "",
        *,
        country: str = "GT",
        environment: str = "test",
        token: str = "",
        timeout: int = 120,
        **kwargs: Any,
    ) -> None:
        self.country = country.upper()
        self._provider: BaseProvider

        if self.country == "GT":
            config = GtConfig(
                taxid=taxid,
                username=username,
                password=password,
                environment=environment,
                token=token,
                timeout=timeout,
                seller_name=kwargs.pop("seller_name", ""),
                seller_address=kwargs.pop("seller_address", ""),
                afiliacion_iva=kwargs.pop("afiliacion_iva", "GEN"),
                tipo_personeria=kwargs.pop("tipo_personeria", "1"),
                tipo_frase=kwargs.pop("tipo_frase", None),
                escenario=kwargs.pop("escenario", None),
                frases=kwargs.pop("frases", None),
                auto_fuel_subsidy_frases=kwargs.pop("auto_fuel_subsidy_frases", None),
                branch_code=kwargs.pop("branch_code", "1"),
                branch_name=kwargs.pop("branch_name", "ESTABLECIMIENTO PRINCIPAL"),
                petroleo_rates=kwargs.pop("petroleo_rates", None),
            )
            self._provider = GtProvider(config)

        elif self.country == "DO":
            config = DoConfig(
                taxid=taxid,
                username=username,
                password=password,
                environment=environment,
                token=token,
                timeout=timeout,
                seller_name=kwargs.pop("seller_name", ""),
                seller_address=kwargs.pop("seller_address", ""),
            )
            self._provider = DoProvider(config)

        else:
            raise ValueError(
                f"Unsupported country: {country!r}. Must be 'GT' or 'DO'."
            )

        if kwargs:
            raise ValueError(
                f"Unexpected keyword arguments for country={self.country}: {list(kwargs.keys())}"
            )

    def __repr__(self) -> str:
        return (
            f"DigifactClient(country={self.country!r}, "
            f"taxid={self._provider.config.taxid!r}, "
            f"username={self._provider.config.username!r}, "
            f"environment={self._provider.config.environment!r})"
        )

    # ── DO-specific kwargs that must NOT be passed to GT provider ───────────────
    _DO_INVOICE_KWARGS = frozenset({
        "secuencia", "fecha_vencimiento_secuencia", "indicador_monto_gravado",
        "tipo_ingresos", "tipo_pago", "fecha_desde", "fecha_hasta",
        "numero_factura_interna", "seller_additionl_info", "seller_branch_name",
        "seller_branch_district", "seller_branch_state", "seller_branch_country",
        "url_to_send", "payments", "issue_dt", "totals_extra_info",
    })

    # ── Public API — delegates to the active provider ─────────────────────────

    def _check_kwargs(self, method_name: str, kwargs: dict[str, Any]) -> None:
        """Validate kwargs for the current country. Raises ``ValueError`` with
        a helpful message if DO-specific kwargs are passed when country=GT
        (or vice versa).
        """
        if self.country == "GT":
            do_kwargs = self._DO_INVOICE_KWARGS & kwargs.keys()
            if do_kwargs:
                raise ValueError(
                    f"{method_name}() received DO-specific kwargs {sorted(do_kwargs)} "
                    f"but client is configured for country='GT'. "
                    f"Did you forget to pass country='DO' when creating the "
                    f"DigifactClient?"
                )

    def invoice(
        self,
        buyer: str | dict,
        items: list[dict],
        *,
        doc_type: str = "FACT",
        **kwargs: Any,
    ) -> DteResult:
        """Emit an invoice / DTE / e-CF.

        For GT the default ``doc_type`` is ``"FACT"``.
        For DO the default ``doc_type`` is ``"31"`` (Factura Crédito Fiscal).
        """
        self._check_kwargs("invoice", kwargs)
        # Dynamic default: GT → "FACT", DO → "31"
        if doc_type == "FACT" and self.country == "DO":
            doc_type = "31"
        return self._provider.invoice(buyer, items, doc_type=doc_type, **kwargs)

    def credit_note(
        self,
        buyer: str | dict,
        items: list[dict],
        origin: dict,
        reason: str,
        **kwargs: Any,
    ) -> DteResult:
        """Emit a credit note (GT: NCRE, DO: tipo 34)."""
        self._check_kwargs("credit_note", kwargs)
        return self._provider.credit_note(buyer, items, origin, reason, **kwargs)

    def debit_note(
        self,
        buyer: str | dict,
        items: list[dict],
        origin: dict,
        reason: str,
        **kwargs: Any,
    ) -> DteResult:
        """Emit a debit note (GT: NDEB, DO: tipo 33)."""
        self._check_kwargs("debit_note", kwargs)
        return self._provider.debit_note(buyer, items, origin, reason, **kwargs)

    def get_document(self, auth_number: str, fmt: str = "JSON") -> dict:
        """Retrieve a certified document (XML/HTML/PDF/JSON)."""
        return self._provider.get_document(auth_number, fmt=fmt)

    def cancel(
        self,
        auth_number: str,
        receiver_id: str,
        issue_datetime: str,
        reason: str = "Anulación",
    ) -> dict:
        """Cancel a DTE/e-CF."""
        return self._provider.cancel(auth_number, receiver_id, issue_datetime, reason=reason)

    # ── Backward-compatible GT-specific methods ───────────────────────────────

    def _gt_provider(self) -> GtProvider:
        if self.country != "GT":
            raise NotImplementedError(
                f"{self.country} provider does not support this GT-specific method"
            )
        return self._provider  # type: ignore[return-value]

    def cca_invoice(self, *args, **kwargs) -> DteResult:
        """GT-only: emit a CCA (Cobro por Cuenta Ajena) FACT+CCA complemento."""
        return self._gt_provider().cca_invoice(*args, **kwargs)

    def fuel_invoice(self, *args, **kwargs) -> DteResult:
        """GT-only: emit a combustible (fuel) FACT invoice."""
        return self._gt_provider().fuel_invoice(*args, **kwargs)

    def credit_note_total(self, *args, **kwargs) -> dict:
        """GT-only: create a total credit note via /cert/ncredtotal."""
        return self._gt_provider().credit_note_total(*args, **kwargs)

    def lookup_nit(self, nit: str) -> dict:
        """GT-only: look up a NIT via SHARED_GETINFONITcom."""
        return self._gt_provider().lookup_nit(nit)

    def get_dte_info(self, auth_number: str) -> dict:
        """GT-only: get DTE info via SHARED_GETDTEINFO."""
        return self._gt_provider().get_dte_info(auth_number)


# ── Re-export core exceptions and DteResult for backward compatibility ──────

__all__ = [
    "DigifactClient",
    "DteResult",
    "DigifactError",
    "DigifactAuthError",
    "DigifactApiError",
    "DigifactValidationError",
    "DigifactNitNotFoundError",
]