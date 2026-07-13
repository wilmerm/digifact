"""República Dominicana e-CF provider — implements BaseProvider for DGII."""
from __future__ import annotations

from typing import Any

import requests

from ...core.base_provider import BaseProvider, DteResult
from ...core.http_client import _try_json, _check_response
from ...core.exceptions import (
    DigifactApiError,
    DigifactAuthError,
    DigifactValidationError,
)
from .do_config import DoConfig
from .do_builder import build_ecf, build_ecf_31, build_ecf_32, build_ecf_33, build_ecf_34


class DoProvider(BaseProvider):
    """Provider for República Dominicana DGII e-CF (Facturación Electrónica).

    Uses the Digifact DO API to certify and manage electronic tax documents
    (comprobantes fiscales electrónicos / e-CF).
    """

    def __init__(self, config: DoConfig) -> None:
        self.config = config
        self._token: str = config.token
        self._session = requests.Session()

    # ── Authentication ────────────────────────────────────────────────────────

    def authenticate(self) -> str:
        """Authenticate against Digifact DO and return a JWT token."""
        if self._token:
            return self._token
        if not self.config.password:
            raise DigifactAuthError("password is required for DO authentication")

        resp = self._session.post(
            f"{self.config.base_url}/login/get_token",
            json={
                "Username": self.config.full_username,
                "Password": self.config.password,
            },
            timeout=self.config.timeout,
        )
        try:
            resp.raise_for_status()
        except requests.HTTPError as exc:
            raise DigifactAuthError(f"DO Login HTTP error: {exc}", raw=_try_json(resp)) from exc

        data = resp.json()
        tok = data.get("Token") or data.get("token") or data.get("otorgado_a") or ""
        if not tok:
            raise DigifactAuthError(
                "DO login succeeded but response contained no token", raw=data
            )
        self._token = tok
        return self._token

    def _headers(self) -> dict:
        return {
            "Authorization": self.authenticate(),
            "Content-Type": "application/json",
        }

    # ── Low-level API calls ───────────────────────────────────────────────────

    def _certify(self, payload: dict) -> dict:
        """POST to /v2/transform/nuc_json to certify an e-CF."""
        resp = self._session.post(
            f"{self.config.base_url}/v2/transform/nuc_json",
            params={
                "TAXID": self.config.taxid,
                "FORMAT": "XML",
                "USERNAME": self.config.username,
            },
            headers=self._headers(),
            json=payload,
            timeout=self.config.timeout,
        )
        try:
            resp.raise_for_status()
        except requests.HTTPError as exc:
            raise DigifactApiError(
                f"DO Certify HTTP error: {exc}", raw=_try_json(resp)
            ) from exc
        return _check_response(resp.json())

    def _parse_result(self, data: dict) -> DteResult:
        """Parse a DO certification response into a DteResult.

        For DO, the NCF is contained in ``suggestedFileName``
        (e.g. ``"E310000490960"``).
        """
        auth = data.get("authNumber") or data.get("Autorizacion") or ""
        series = data.get("serial") or data.get("batch") or data.get("Serie") or ""
        number = str(data.get("suggestedFileName") or data.get("Numero") or "")
        ts_raw = data.get("issuedTimeStamp") or data.get("FechaEmision") or ""
        issue_dt = ts_raw.replace("T", " ") if "T" in ts_raw else ts_raw
        return DteResult(
            auth_number=auth,
            series=series,
            number=number,
            issue_datetime=issue_dt,
            raw=data,
        )

    # ── Public DTE methods ────────────────────────────────────────────────────

    def invoice(
        self,
        buyer: str | dict,
        items: list[dict],
        *,
        doc_type: str = "31",
        secuencia: str = "",
        fecha_vencimiento_secuencia: str = "",
        **kwargs: Any,
    ) -> DteResult:
        """Emit an e-CF invoice (31 = Crédito Fiscal, 32 = Consumo, etc.).

        Parameters
        ----------
        buyer : str | dict
            RNC/Cédula string or buyer dict with ``taxid``, ``name``, etc.
        items : list[dict]
            List of item dicts. Each must have ``description``, ``price``.
            ``indicador_facturacion`` controls ITBIS: ``"1"`` (18%), ``"2"`` (16%),
            ``"3"`` (0%), ``"4"`` (Exento).
        doc_type : str
            ``"31"`` (Factura Crédito Fiscal, default), ``"32"`` (Consumo).
        secuencia : str
            NCF (Número de Comprobante Fiscal) asignado por la DGII.
        fecha_vencimiento_secuencia : str
            Fecha de vencimiento del NCF (ej. ``"2028-12-31"``).
        """
        if not secuencia or not fecha_vencimiento_secuencia:
            raise DigifactValidationError(
                "secuencia and fecha_vencimiento_secuencia are required for DO invoices"
            )

        seller_name = kwargs.pop("seller_name", self.config.seller_name or "")
        seller_address = kwargs.pop("seller_address", self.config.seller_address or "")

        payload = build_ecf(
            self.config.taxid,
            seller_name,
            seller_address,
            buyer,
            items,
            doc_type=doc_type,
            secuencia=secuencia,
            fecha_vencimiento_secuencia=fecha_vencimiento_secuencia,
            **kwargs,
        )
        data = self._certify(payload)
        return self._parse_result(data)

    def credit_note(
        self,
        buyer: str | dict,
        items: list[dict],
        origin: dict,
        reason: str,
        *,
        secuencia: str = "",
        fecha_vencimiento_secuencia: str = "",
        **kwargs: Any,
    ) -> DteResult:
        """Emit an e-CF Nota de Crédito (tipo 34)."""
        if not secuencia or not fecha_vencimiento_secuencia:
            raise DigifactValidationError(
                "secuencia and fecha_vencimiento_secuencia are required for DO credit notes"
            )

        seller_name = kwargs.pop("seller_name", self.config.seller_name or "")
        seller_address = kwargs.pop("seller_address", self.config.seller_address or "")

        payload = build_ecf_34(
            self.config.taxid,
            seller_name,
            seller_address,
            buyer,
            items,
            origin=origin,
            reason=reason,
            secuencia=secuencia,
            fecha_vencimiento_secuencia=fecha_vencimiento_secuencia,
            **kwargs,
        )
        data = self._certify(payload)
        return self._parse_result(data)

    def debit_note(
        self,
        buyer: str | dict,
        items: list[dict],
        origin: dict,
        reason: str,
        *,
        secuencia: str = "",
        fecha_vencimiento_secuencia: str = "",
        **kwargs: Any,
    ) -> DteResult:
        """Emit an e-CF Nota de Débito (tipo 33)."""
        if not secuencia or not fecha_vencimiento_secuencia:
            raise DigifactValidationError(
                "secuencia and fecha_vencimiento_secuencia are required for DO debit notes"
            )

        seller_name = kwargs.pop("seller_name", self.config.seller_name or "")
        seller_address = kwargs.pop("seller_address", self.config.seller_address or "")

        payload = build_ecf_33(
            self.config.taxid,
            seller_name,
            seller_address,
            buyer,
            items,
            origin=origin,
            reason=reason,
            secuencia=secuencia,
            fecha_vencimiento_secuencia=fecha_vencimiento_secuencia,
            **kwargs,
        )
        data = self._certify(payload)
        return self._parse_result(data)

    def get_document(self, auth_number: str, fmt: str = "XML") -> dict:
        """Retrieve a certified e-CF document via GET /getDocument (lowercase)."""
        resp = self._session.get(
            f"{self.config.base_url}/getDocument",
            params={
                "TAXID": self.config.taxid,
                "AUTHNUMBER": auth_number,
                "FORMAT": fmt,
                "USERNAME": self.config.username,
            },
            headers={"Authorization": self.authenticate()},
            timeout=self.config.timeout,
        )
        try:
            resp.raise_for_status()
        except requests.HTTPError as exc:
            raise DigifactApiError(
                f"DO GetDocument HTTP error: {exc}", raw=_try_json(resp)
            ) from exc
        return resp.json()

    def cancel(self, auth_number: str, receiver_id: str, issue_datetime: str, reason: str = "Anulación") -> dict:
        """Cancel an e-CF (not yet fully confirmed for DO API — may raise).

        Note: The cancel endpoint for DO may differ from GT. This is a placeholder
        implementation.
        """
        raise NotImplementedError(
            "Cancel (anulación) is not yet implemented for República Dominicana. "
            "The DGII API endpoint for cancellation has not been documented. "
            "Contact Digifact DO support for the correct endpoint."
        )