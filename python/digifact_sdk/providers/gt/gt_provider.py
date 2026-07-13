"""Guatemala DTE provider — implements BaseProvider for SAT FEL."""
from __future__ import annotations

import os
import re
from decimal import Decimal
from typing import Any

import requests

from ...core.base_provider import BaseProvider, DteResult
from ...core.http_client import BaseHttpClient, _try_json, _check_response
from ...core.exceptions import (
    DigifactApiError,
    DigifactAuthError,
    DigifactError,
    DigifactNitNotFoundError,
    DigifactValidationError,
)
from ...builder import (
    build_fact,
    build_fcam,
    build_fact_combustible,
    build_fesp,
    build_fpeq,
    build_nabn,
    build_ncre,
    build_ndeb,
    build_rdon,
    build_reci,
    build_cca,
    default_frase,
    _build_buyer_cf,
    _build_buyer_nit,
    _build_buyer_cui,
    resolve_fuel_frases,
)
from ...tax import gt_now, pad_taxid
from .gt_config import GtConfig


class GtProvider(BaseProvider):
    """Provider for Guatemala SAT FEL (Facturación Electrónica en Línea).

    Wraps the original ``DigifactClient`` logic in the new multi-country
    architecture.  Backward-compatible with the existing client API.
    """

    def __init__(self, config: GtConfig) -> None:
        self.config = config
        self._token: str = config.token
        self._session = requests.Session()
        self._seller_name: str = config.seller_name
        self._seller_address: str = config.seller_address
        self._nit_cache: dict[str, dict] = {}

    # ── Authentication ────────────────────────────────────────────────────────

    def authenticate(self) -> str:
        if self._token:
            return self._token
        if not self.config.password:
            raise DigifactAuthError("password is required")
        resp = self._session.post(
            f"{self.config.base_url}/login/get_token",
            json={"Username": self.config.full_username, "Password": self.config.password},
            timeout=self.config.timeout,
        )
        try:
            resp.raise_for_status()
        except requests.HTTPError as exc:
            raise DigifactAuthError(f"Login HTTP error: {exc}", raw=_try_json(resp)) from exc
        data = resp.json()
        tok = data.get("Token") or data.get("token")
        if not tok:
            raise DigifactAuthError("Login succeeded but response contained no token", raw=data)
        self._token = tok
        return self._token

    def _headers(self) -> dict:
        return {"Authorization": self.authenticate(), "Content-Type": "application/json"}

    # ── Seller info ───────────────────────────────────────────────────────────

    def _get_seller_info(self) -> tuple[str, str]:
        if self._seller_name and self._seller_address:
            return self._seller_name, self._seller_address
        try:
            info = self.lookup_nit(self.config.taxid)
            name = info.get("name") or info.get("NOMBRE") or "EMISOR"
            address = info.get("address") or info.get("Direccion") or "CIUDAD"
            if not self._seller_name:
                self._seller_name = name
            if not self._seller_address:
                self._seller_address = address
        except (DigifactError, requests.RequestException):
            if not self._seller_name:
                self._seller_name = f"EMISOR {self.config.taxid}"
            if not self._seller_address:
                self._seller_address = "CIUDAD"
        return self._seller_name, self._seller_address

    # ── Buyer resolution ──────────────────────────────────────────────────────

    def _resolve_buyer(self, buyer: str | dict) -> dict:
        if isinstance(buyer, str):
            if buyer.upper() == "CF":
                return _build_buyer_cf()
            digits = re.sub(r"\D", "", buyer)
            if digits:
                info = self.lookup_nit(digits)
                return _build_buyer_nit(
                    nit=digits,
                    name=info.get("name") or info.get("NOMBRE") or digits,
                    address=info.get("address") or info.get("Direccion") or "CIUDAD",
                    city=info.get("city") or "01010",
                    district=info.get("district") or "GUATEMALA",
                    state=info.get("state") or "GUATEMALA",
                    country="GT",
                )
            raise DigifactError(f"Cannot resolve buyer: {buyer!r}")
        if isinstance(buyer, dict):
            buyer_type = buyer.get("type", "").upper()
            if buyer_type == "CUI":
                return _build_buyer_cui(taxid=str(buyer["taxid"]), name=buyer["name"])
            return _build_buyer_nit(
                nit=str(buyer["taxid"]),
                name=buyer["name"],
                address=buyer.get("address", "CIUDAD"),
                city=buyer.get("city", "01010"),
                district=buyer.get("district", "GUATEMALA"),
                state=buyer.get("state", "GUATEMALA"),
                country=buyer.get("country", "GT"),
                email=buyer.get("email"),
            )
        raise DigifactError(f"buyer must be a string or dict, got {type(buyer)}")

    # ── Low-level API ─────────────────────────────────────────────────────────

    def _certify(self, payload: dict) -> dict:
        resp = self._session.post(
            f"{self.config.base_url}/v2/transform/nuc_json",
            params={
                "TAXID": pad_taxid(self.config.taxid),
                "FORMAT": "XML|HTML|PDF",
                "USERNAME": self.config.username,
            },
            headers=self._headers(),
            json=payload,
            timeout=self.config.timeout,
        )
        try:
            resp.raise_for_status()
        except requests.HTTPError as exc:
            raise DigifactApiError(f"Certify HTTP error: {exc}", raw=_try_json(resp)) from exc
        return _check_response(resp.json())

    def _parse_result(self, data: dict) -> DteResult:
        auth = data.get("authNumber") or data.get("Autorizacion") or ""
        series = data.get("batch") or data.get("Serie") or ""
        number = str(data.get("serial") or data.get("Numero") or "")
        ts_raw = data.get("issuedTimeStamp") or data.get("FechaEmision") or ""
        issue_dt = ts_raw.replace("T", " ") if "T" in ts_raw else ts_raw
        return DteResult(auth_number=auth, series=series, number=number, issue_datetime=issue_dt, raw=data)

    def _apply_branch_info(self, payload: dict) -> dict:
        branch = payload.get("Seller", {}).get("BranchInfo")
        if isinstance(branch, dict):
            branch["Code"] = self.config.branch_code
            branch["Name"] = self.config.branch_name
        return payload

    def _resolve_frase(self, doc_type: str, tipo_frase: str | None, escenario: str | None) -> tuple[str | None, str | None]:
        defaults = default_frase(doc_type, self.config.afiliacion_iva)
        def_tf, def_es = defaults if defaults else (None, None)
        tf = tipo_frase if tipo_frase is not None else (self.config.tipo_frase if self.config.tipo_frase is not None else def_tf)
        es = escenario if escenario is not None else (self.config.escenario if self.config.escenario is not None else def_es)
        return tf, es

    # ── Public DTE methods ────────────────────────────────────────────────────

    def invoice(
        self,
        buyer: str | dict,
        items: list[dict],
        *,
        doc_type: str = "FACT",
        payment_terms: list[dict] | None = None,
        amount_str: str = "",
        observaciones: str = "-",
        tipo_personeria: str | None = None,
        tipo_frase: str | None = None,
        escenario: str | None = None,
    ) -> DteResult:
        seller_name, seller_address = self._get_seller_info()
        buyer_dict = self._resolve_buyer(buyer)

        if self.config.frases is not None and tipo_frase is None and escenario is None:
            eff_frases = self.config.frases
            tf = es = None
        else:
            eff_frases = None
            tf, es = self._resolve_frase(doc_type, tipo_frase, escenario)

        builder_kwargs: dict[str, Any] = dict(
            taxid=self.config.taxid,
            seller_name=seller_name,
            seller_address=seller_address,
            buyer=buyer_dict,
            items=items,
        )

        if doc_type == "FCAM":
            if not payment_terms:
                raise DigifactValidationError("payment_terms is required for FCAM")
            payload = build_fcam(
                **builder_kwargs,
                payment_terms=payment_terms,
                afiliacion=self.config.afiliacion_iva,
                amount_str=amount_str,
                observaciones=observaciones,
                tipo_frase=tf,
                escenario=es,
                frases=eff_frases,
            )
        elif doc_type == "FESP":
            payload = build_fesp(**builder_kwargs, afiliacion=self.config.afiliacion_iva)
        elif doc_type == "NABN":
            payload = build_nabn(**builder_kwargs, afiliacion=self.config.afiliacion_iva, amount_str=amount_str, observaciones=observaciones, frases=eff_frases)
        elif doc_type == "RDON":
            tp = tipo_personeria or self.config.tipo_personeria
            payload = build_rdon(**builder_kwargs, tipo_personeria=tp, afiliacion=self.config.afiliacion_iva, amount_str=amount_str, observaciones=observaciones, frases=eff_frases)
        elif doc_type == "FPEQ":
            payload = build_fpeq(**builder_kwargs, amount_str=amount_str, observaciones=observaciones, tipo_frase=tf, escenario=es, frases=eff_frases)
        elif doc_type == "RECI":
            payload = build_reci(**builder_kwargs, afiliacion=self.config.afiliacion_iva, amount_str=amount_str, observaciones=observaciones, frases=eff_frases)
        else:
            payload = build_fact(**builder_kwargs, doc_type=doc_type, afiliacion=self.config.afiliacion_iva, tipo_frase=tf, escenario=es, frases=eff_frases, amount_str=amount_str, observaciones=observaciones)

        payload = self._apply_branch_info(payload)
        data = self._certify(payload)
        return self._parse_result(data)

    def credit_note(
        self,
        buyer: str | dict,
        items: list[dict],
        origin: dict,
        reason: str,
        *,
        tipo_frase: str | None = None,
        escenario: str | None = None,
    ) -> DteResult:
        seller_name, seller_address = self._get_seller_info()
        buyer_dict = self._resolve_buyer(buyer)
        if self.config.frases is not None and tipo_frase is None and escenario is None:
            eff_frases = self.config.frases
            tf = es = None
        else:
            eff_frases = None
            tf, es = self._resolve_frase("NCRE", tipo_frase, escenario)
        payload = build_ncre(self.config.taxid, seller_name, seller_address, buyer_dict, items, origin, reason,
                             afiliacion=self.config.afiliacion_iva, tipo_frase=tf, escenario=es, frases=eff_frases)
        payload = self._apply_branch_info(payload)
        data = self._certify(payload)
        return self._parse_result(data)

    def debit_note(
        self,
        buyer: str | dict,
        items: list[dict],
        origin: dict,
        reason: str,
        *,
        tipo_frase: str | None = None,
        escenario: str | None = None,
    ) -> DteResult:
        seller_name, seller_address = self._get_seller_info()
        buyer_dict = self._resolve_buyer(buyer)
        if self.config.frases is not None and tipo_frase is None and escenario is None:
            eff_frases = self.config.frases
            tf = es = None
        else:
            eff_frases = None
            tf, es = self._resolve_frase("NDEB", tipo_frase, escenario)
        payload = build_ndeb(self.config.taxid, seller_name, seller_address, buyer_dict, items, origin, reason,
                             afiliacion=self.config.afiliacion_iva, tipo_frase=tf, escenario=es, frases=eff_frases)
        payload = self._apply_branch_info(payload)
        data = self._certify(payload)
        return self._parse_result(data)

    def get_document(self, auth_number: str, fmt: str = "JSON") -> dict:
        resp = self._session.get(
            f"{self.config.base_url}/GetDocument",
            params={
                "AUTHNUMBER": auth_number,
                "TAXID": pad_taxid(self.config.taxid),
                "FORMAT": fmt,
                "USERNAME": self.config.username,
            },
            headers=self._headers(),
            timeout=self.config.timeout,
        )
        try:
            resp.raise_for_status()
        except requests.HTTPError as exc:
            raise DigifactApiError(f"GetDocument HTTP error: {exc}", raw=_try_json(resp)) from exc
        return resp.json()

    def cancel(self, auth_number: str, receiver_id: str, issue_datetime: str, reason: str = "Anulación") -> dict:
        resp = self._session.post(
            f"{self.config.base_url}/CancelFelGT",
            headers=self._headers(),
            json={
                "Taxid": self.config.taxid,
                "Autorizacion": auth_number,
                "IdReceptor": receiver_id,
                "FechaEmisionDocumentoAnular": issue_datetime,
                "MotivoAnulacion": reason,
                "Username": self.config.username,
            },
            timeout=self.config.timeout,
        )
        try:
            resp.raise_for_status()
        except requests.HTTPError as exc:
            raise DigifactApiError(f"Cancel HTTP error: {exc}", raw=_try_json(resp)) from exc
        return resp.json()

    # ── GT-specific helpers ───────────────────────────────────────────────────

    def lookup_nit(self, nit: str) -> dict:
        digits = re.sub(r"\D", "", nit)
        if digits in self._nit_cache:
            return self._nit_cache[digits]
        resp = self._session.get(
            f"{self.config.base_url}/Shared",
            params={
                "COUNTRY": "GT",
                "TAXID": pad_taxid(self.config.taxid),
                "DATA1": "SHARED_GETINFONITcom",
                "DATA2": f"NIT|{digits}",
                "USERNAME": self.config.username,
            },
            headers={"Authorization": self.authenticate()},
            timeout=self.config.timeout,
        )
        try:
            resp.raise_for_status()
        except requests.HTTPError as exc:
            raise DigifactApiError(f"NIT lookup HTTP error: {exc}", raw=_try_json(resp)) from exc
        from ...client import _parse_nit_response
        data = resp.json()
        normalized = _parse_nit_response(digits, data)
        if not normalized.get("name"):
            raise DigifactNitNotFoundError(f"NIT {nit!r} not found or returned empty name")
        self._nit_cache[digits] = normalized
        return normalized

    def cca_invoice(self, buyer, items, cobros, *, tipo_frase=None, escenario=None):
        seller_name, seller_address = self._get_seller_info()
        buyer_dict = self._resolve_buyer(buyer)
        if self.config.frases is not None and tipo_frase is None and escenario is None:
            eff_frases = self.config.frases
            tf = es = None
        else:
            eff_frases = None
            tf, es = self._resolve_frase("FACT", tipo_frase, escenario)
        payload = build_cca(self.config.taxid, seller_name, seller_address, buyer_dict, items, cobros,
                            afiliacion=self.config.afiliacion_iva, tipo_frase=tf, escenario=es, frases=eff_frases)
        payload = self._apply_branch_info(payload)
        data = self._certify(payload)
        return self._parse_result(data)

    def fuel_invoice(self, buyer, items, *, tipo_frase=None, escenario=None, frases=None, auto_fuel_subsidy_frases=None):
        from ...exceptions import DigifactValidationError
        if frases is not None and (tipo_frase is not None or escenario is not None):
            raise DigifactValidationError("frases and tipo_frase/escenario are mutually exclusive")
        eff_frases: list[dict] | None
        eff_tf: str | None
        eff_es: str | None
        if frases is not None:
            eff_frases, eff_tf, eff_es = frases, None, None
        elif self.config.frases is not None:
            eff_frases, eff_tf, eff_es = self.config.frases, None, None
        else:
            eff_frases = None
            eff_tf, eff_es = self._resolve_frase("FACT", tipo_frase, escenario)
        if auto_fuel_subsidy_frases is not None:
            auto_enabled = auto_fuel_subsidy_frases
        elif self.config.auto_fuel_subsidy_frases is not None:
            auto_enabled = self.config.auto_fuel_subsidy_frases
        else:
            auto_enabled = True
        if os.environ.get("DIGIFACT_DISABLE_AUTO_FUEL_SUBSIDY_FRASES", "") == "1":
            auto_enabled = False
        seller_name, seller_address = self._get_seller_info()
        buyer_dict = self._resolve_buyer(buyer)
        from ...builder import build_fact_combustible
        payload = build_fact_combustible(
            self.config.taxid, seller_name, seller_address, buyer_dict, items,
            afiliacion=self.config.afiliacion_iva,
            tipo_frase=eff_tf, escenario=eff_es, frases=eff_frases,
            auto_fuel_subsidy_frases=auto_enabled,
        )
        payload = self._apply_branch_info(payload)
        data = self._certify(payload)
        return self._parse_result(data)

    def credit_note_total(self, auth_number, issue_datetime, reason="Nota de crédito total", reference=""):
        resp = self._session.post(
            f"{self.config.base_url}/cert/ncredtotal",
            headers=self._headers(),
            json={
                "Staxid": self.config.taxid,
                "Authnumber": auth_number,
                "FechaEmision": issue_datetime,
                "MotivoAjuste": reason,
                "ReferenciaInterna": reference,
                "Formatos": "xml|html|pdf",
                "Username": self.config.username,
            },
            timeout=self.config.timeout,
        )
        try:
            resp.raise_for_status()
        except requests.HTTPError as exc:
            raise DigifactApiError(f"NcredTotal HTTP error: {exc}", raw=_try_json(resp)) from exc
        return resp.json()

    def get_dte_info(self, auth_number: str) -> dict:
        resp = self._session.get(
            f"{self.config.base_url}/Shared",
            params={
                "COUNTRY": "GT",
                "TAXID": pad_taxid(self.config.taxid),
                "DATA1": "SHARED_GETDTEINFO",
                "DATA2": f"AUTHNUMBER|{auth_number}",
                "USERNAME": self.config.username,
            },
            headers={"Authorization": self.authenticate()},
            timeout=self.config.timeout,
        )
        try:
            resp.raise_for_status()
        except requests.HTTPError as exc:
            raise DigifactApiError(f"GetDteInfo HTTP error: {exc}", raw=_try_json(resp)) from exc
        return resp.json()