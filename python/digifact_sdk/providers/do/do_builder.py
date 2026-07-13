"""JSON NUC payload builder for República Dominicana e-CF (electronic tax documents).

Builds the JSON payload that is sent to ``/v2/transform/nuc_json`` for certification
by Digifact DO.

Updated to match the exact JSON structure confirmed working with the Digifact DO API.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from ...core.money import do_now, fmt
from .do_tax import DoLineCalc, DoInvoiceTotals, resolve_uom


def _resolve_buyer_do(buyer: str | dict) -> dict:
    """Resolve a buyer specification to a DO buyer dict.

    In DO there is no "CF" (Consumidor Final). Buyer always needs
    a TaxID (RNC or Cédula).

    Working JSON structure uses flat EmailList/Website (not nested inside Contact).
    """
    if isinstance(buyer, str):
        return {
            "TaxID": buyer,
            "Name": buyer,
            "AddressInfo": {
                "Address": "",
                "District": "",
                "State": "",
                "Country": "DO",
            },
        }
    return {
        "TaxID": buyer["taxid"],
        "TaxIDType": None,
        "Name": buyer["name"],
        "EmailList": {"Email": [buyer.get("email", "")]},
        "Website": buyer.get("website", ""),
        "AddressInfo": {
            "Address": buyer.get("address", ""),
            "District": buyer.get("district", ""),
            "State": buyer.get("state", ""),
            "Country": buyer.get("country", "DO"),
        },
    }


def _build_header_do(
    doc_type: str,
    issue_dt: str,
    secuencia: str,
    fecha_vencimiento_secuencia: str = "",
    indicador_monto_gravado: str = "0",
    tipo_ingresos: str = "01",
    tipo_pago: str = "1",
    exchange_rate: float | None = None,
    fecha_desde: str | None = None,
    fecha_hasta: str | None = None,
    indicador_envio_diferido: str | None = None,
) -> dict:
    """Build the ``Header`` block for an e-CF.

    ``FechaVencimientoSecuencia`` is only included when provided (optional for
    doc types like 32 that do not support it).

    Note: ``Currency`` and ``AdditionalIssueType`` are OMITTED when not needed,
    matching the working JSON payload (the API may reject extra fields).
    """
    info_list: list[dict[str, str]] = [
        {"Name": "Secuencia", "Value": secuencia},
        {"Name": "IndicadorMontoGravado", "Value": indicador_monto_gravado},
        {"Name": "TipoIngresos", "Value": tipo_ingresos},
        {"Name": "TipoPago", "Value": tipo_pago},
    ]
    if fecha_vencimiento_secuencia:
        info_list.insert(1, {"Name": "FechaVencimientoSecuencia", "Value": fecha_vencimiento_secuencia})

    header: dict[str, Any] = {
        "DocType": doc_type,
        "IssuedDateTime": issue_dt,
        "AdditionalIssueDocInfo": info_list,
    }
    if exchange_rate is not None:
        header["ExchangeRate"] = exchange_rate
    if fecha_desde:
        header["AdditionalIssueDocInfo"].append(
            {"Name": "FechaDesde", "Value": fecha_desde}
        )
    if fecha_hasta:
        header["AdditionalIssueDocInfo"].append(
            {"Name": "FechaHasta", "Value": fecha_hasta}
        )
    if indicador_envio_diferido:
        header["AdditionalIssueDocInfo"].append(
            {"Name": "IndicadorEnvioDiferido", "Value": indicador_envio_diferido}
        )
    return header


def _build_seller_do(
    taxid: str,
    name: str,
    address: str,
    *,
    numero_factura_interna: str = "",
    seller_additionl_info: list[dict] | None = None,
    branch_name: str = "0001",
    district: str = "",
    state: str = "",
    country: str = "",
) -> dict:
    """Build the ``Seller`` block for an e-CF.

    The working JSON confirms:
    - ``AdditionlInfo`` is flexible (not hardcoded fields)
    - ``BranchInfo.Code`` is optional
    - ``Contact`` block is optional
    """
    if not name:
        raise ValueError(
            "seller_name (Razón Social del Emisor) es obligatorio para e-CF DO. "
            "Pásalo como kwarg en client.invoice() o configúralo en DigifactClient(seller_name=...)."
        )

    additionl_info = list(seller_additionl_info or [])
    if numero_factura_interna and not any(
        entry.get("Name") == "NumeroFacturaInterna" for entry in additionl_info
    ):
        additionl_info.append(
            {"Name": "NumeroFacturaInterna", "Value": numero_factura_interna}
        )

    # Build seller dict with key order matching the working JSON:
    # TaxID → Name → Contact → AdditionlInfo → BranchInfo
    seller: dict[str, Any] = {
        "TaxID": taxid,
        "Name": name,
        "Contact": {
            "PhoneList": {"Phone": [""]},
            "EmailList": {"Email": [""]},
            "Website": "",
        },
    }
    if additionl_info:
        seller["AdditionlInfo"] = additionl_info
    seller["BranchInfo"] = {
        "Name": branch_name,
        "AddressInfo": {
            "Address": address,
            "District": district,
            "State": state,
            "Country": country,
        },
    }
    return seller


def _build_items_do(items: list[dict]) -> tuple[list[dict], DoInvoiceTotals]:
    """Build the ``Items`` list and totals from item dicts.

    Uses string values for Qty, Price, TotalItem (matching working JSON format).

    Each item dict supports:
        description: str
        price: float | Decimal  (NET price, without ITBIS)
        indicador_facturacion: str  "1"=ITBIS 18%, "2"=16%, "3"=0%, "4"=Exento
        qty: float | Decimal   (default 1)
        type: str               (default "1")
        unit_of_measure: str    (default "98")
        discount: float | None
        charge: float | None
        ean: str                (optional)
        plu: str                (optional)
        descripcion_item: str   (optional extended description)
    """
    line_items = []
    lines: list[DoLineCalc] = []

    for i, item in enumerate(items, start=1):
        qty = Decimal(str(item.get("qty", 1)))
        price = Decimal(str(item["price"]))
        indicador = str(item.get("indicador_facturacion", "1"))
        item_type = str(item.get("type", "1"))
        uom = resolve_uom(item.get("unit_of_measure", "UNI"))
        desc = item["description"]
        discount_val = item.get("discount")
        discount = Decimal(str(discount_val)) if discount_val is not None else None

        lc = DoLineCalc(qty, price, indicador=indicador, discount=discount)
        lines.append(lc)

        # Qty and Price as strings (matching working JSON format)
        built: dict[str, Any] = {
            "Type": item_type,
            "Description": desc,
            "Qty": str(qty),
            "Price": str(price),
            "Discounts": None,
            "Taxes": None,
            "Charges": None,
            "Totals": {"TotalItem": fmt(lc.line_total, decimals=2)},
            "AdditionalInfo": [
                {"Name": "IndicadorFacturacion", "Value": indicador},
            ],
        }

        # Optional codes (EAN/PLU) — only if provided
        ean = item.get("ean")
        plu = item.get("plu")
        if ean or plu:
            codes = []
            if ean:
                codes.append({"Name": "EAN", "Value": ean})
            if plu:
                codes.append({"Name": "PLU", "Value": plu})
            built["Codes"] = codes

        # Optional extended description
        desc_item = item.get("descripcion_item", "")
        if desc_item:
            built["AdditionalInfo"].append(
                {"Name": "DescripcionItem", "Value": desc_item}
            )

        # Discounts (only if > 0, otherwise null)
        if discount is not None and discount > 0:
            built["Discounts"] = {
                "Discount": [{"Code": "$", "Amount": float(discount)}]
            }

        # Charges (only if present, otherwise null)
        charge_val = item.get("charge")
        if charge_val is not None:
            built["Charges"] = {
                "Charge": [{"Code": "$", "Amount": float(charge_val)}]
            }

        line_items.append(built)

    totals = DoInvoiceTotals(lines)
    return line_items, totals


def _build_totals_additional_info(
    additional_info: list[dict] | None = None,
) -> list[dict]:
    """Build ``Totals.AdditionalInfo`` block.

    Working JSON shows: ``[{"Name": "", "Value": ""}]`` when present.
    """
    if additional_info:
        return additional_info
    return [{"Name": "", "Value": ""}]


def _build_additional_document_info(
    additional_info: list[dict] | None = None,
    url_to_send: str | None = None,
) -> dict:
    """Build the ``AdditionalDocumentInfo`` block.

    Working JSON structure includes ``AditionalInfo`` and ``AditionalData``
    sections (yes, the typos are intentional — matching the API).
    """
    info_entries = list(additional_info or [])

    if url_to_send and not any(
        isinstance(e, dict) and any(
            isinstance(sub, dict) and sub.get("Name") == "UrlToSend"
            for sub in e.get("AditionalInfo", [])
        )
        for e in info_entries
    ):
        info_entries.append({
            "AditionalInfo": [
                {"Name": "UrlToSend", "Value": url_to_send},
            ],
            "AditionalData": {
                "Data": [
                    {
                        "Name": "INFORMACION_REFERENCIA",
                        "Id": 0,
                        "Info": [{"Name": "", "Value": ""}],
                    }
                ],
            },
        })

    return {"AdditionalInfo": info_entries}


def build_ecf(
    taxid: str,
    seller_name: str,
    seller_address: str,
    buyer: str | dict,
    items: list[dict],
    *,
    doc_type: str = "31",
    secuencia: str,
    fecha_vencimiento_secuencia: str = "",
    indicador_monto_gravado: str = "0",
    tipo_ingresos: str = "01",
    tipo_pago: str = "1",
    exchange_rate: float | None = None,
    fecha_desde: str | None = None,
    fecha_hasta: str | None = None,
    indicador_envio_diferido: str | None = None,
    numero_factura_interna: str = "",
    seller_additionl_info: list[dict] | None = None,
    seller_branch_name: str = "0001",
    seller_branch_district: str = "",
    seller_branch_state: str = "",
    seller_branch_country: str = "",
    payments: list[dict] | None = None,
    additional_info: list[dict] | None = None,
    totals_extra_info: list[dict] | None = None,
    url_to_send: str | None = None,
    issue_dt: str | None = None,
    # Origin document for ND (33) / NC (34)
    origin: dict | None = None,
    reason: str = "",
) -> dict:
    """Build a complete JSON NUC payload for a Dominican Republic e-CF.

    Parameters
    ----------
    taxid : str
        RNC del emisor.
    seller_name : str
        Razón Social del emisor.
    seller_address : str
        Dirección del emisor.
    buyer : str | dict
        RNC/Cédula string or buyer dict with ``taxid``, ``name``, etc.
    items : list[dict]
        List of item dicts. Each must have ``description`` and ``price``.
        ``indicador_facturacion`` controls ITBIS: ``"1"`` (18%), ``"2"`` (16%),
        ``"3"`` (0%), ``"4"`` (Exento).
    doc_type : str
        ``"31"`` (Factura Crédito Fiscal, default), ``"32"`` (Consumo),
        ``"33"`` (Nota Débito), ``"34"`` (Nota Crédito).
    secuencia : str
        NCF asignado por la DGII, ej. ``"0000490963"``.
    fecha_vencimiento_secuencia : str
        Fecha de vencimiento del NCF, ej. ``"2028-12-31"``.
    payments : list[dict], optional
        Payment entries. If omitted, **no** ``Payments`` field is added.
        Working JSON proved it works without Payments.
    """
    effective_issue_dt = issue_dt or do_now(with_offset=False)
    buyer_dict = _resolve_buyer_do(buyer)

    header = _build_header_do(
        doc_type=doc_type,
        issue_dt=effective_issue_dt,
        secuencia=secuencia,
        fecha_vencimiento_secuencia=fecha_vencimiento_secuencia,
        indicador_monto_gravado=indicador_monto_gravado,
        tipo_ingresos=tipo_ingresos,
        tipo_pago=tipo_pago,
        exchange_rate=exchange_rate,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        indicador_envio_diferido=indicador_envio_diferido,
    )

    seller = _build_seller_do(
        taxid,
        seller_name,
        seller_address,
        numero_factura_interna=numero_factura_interna,
        seller_additionl_info=seller_additionl_info,
        branch_name=seller_branch_name,
        district=seller_branch_district,
        state=seller_branch_state,
        country=seller_branch_country,
    )

    line_items, totals = _build_items_do(items)

    totals_block = totals.to_totals_block()
    totals_block["AdditionalInfo"] = _build_totals_additional_info(totals_extra_info)

    payload: dict[str, Any] = {
        "Version": "1.0",
        "CountryCode": "DO",
        "Header": header,
        "Seller": seller,
        "Buyer": buyer_dict,
        "Items": line_items,
        "Totals": totals_block,
        "AdditionalDocumentInfo": _build_additional_document_info(
            additional_info=additional_info,
            url_to_send=url_to_send,
        ),
    }

    # Payments — only if provided (confirmed optional by working JSON)
    if payments:
        payload["Payments"] = payments

    # ── Origin document (ND: 33, NC: 34) ────────────────────────────────────
    if origin is not None:
        comp_code = "NDEB" if doc_type in ("33",) else "NCRE"
        comp_info = [
            {"Name": "NumeroAutorizacionDocumentoOrigen", "Data": None, "Value": origin.get("auth_number", "")},
            {"Name": "FechaEmisionDocumentoOrigen", "Data": None, "Value": origin.get("date", "")},
            {"Name": "MotivoAjuste", "Data": None, "Value": reason},
            {"Name": "SerieDocumentoOrigen", "Data": None, "Value": origin.get("series", "")},
            {"Name": "NumeroDocumentoOrigen", "Data": None, "Value": str(origin.get("number", ""))},
        ]
        payload["AdditionalDocumentInfo"]["AdditionalInfo"].append(
            {
                "AditionalInfo": comp_info,
            }
        )

    return payload


# ── Convenience builders ──────────────────────────────────────────────────────


def build_ecf_31(
    taxid: str,
    seller_name: str,
    seller_address: str,
    buyer: str | dict,
    items: list[dict],
    *,
    secuencia: str,
    fecha_vencimiento_secuencia: str,
    **kwargs: Any,
) -> dict:
    """Build an e-CF tipo 31 (Factura de Crédito Fiscal Electrónica)."""
    return build_ecf(
        taxid, seller_name, seller_address, buyer, items,
        doc_type="31",
        secuencia=secuencia,
        fecha_vencimiento_secuencia=fecha_vencimiento_secuencia,
        **kwargs,
    )


def build_ecf_32(
    taxid: str,
    seller_name: str,
    seller_address: str,
    buyer: str | dict,
    items: list[dict],
    *,
    secuencia: str,
    fecha_vencimiento_secuencia: str,
    **kwargs: Any,
) -> dict:
    """Build an e-CF tipo 32 (Factura de Consumo Electrónica)."""
    return build_ecf(
        taxid, seller_name, seller_address, buyer, items,
        doc_type="32",
        secuencia=secuencia,
        fecha_vencimiento_secuencia=fecha_vencimiento_secuencia,
        **kwargs,
    )


def build_ecf_33(
    taxid: str,
    seller_name: str,
    seller_address: str,
    buyer: str | dict,
    items: list[dict],
    origin: dict,
    reason: str,
    *,
    secuencia: str,
    fecha_vencimiento_secuencia: str,
    **kwargs: Any,
) -> dict:
    """Build an e-CF tipo 33 (Nota de Débito Electrónica)."""
    return build_ecf(
        taxid, seller_name, seller_address, buyer, items,
        doc_type="33",
        secuencia=secuencia,
        fecha_vencimiento_secuencia=fecha_vencimiento_secuencia,
        origin=origin,
        reason=reason,
        **kwargs,
    )


def build_ecf_34(
    taxid: str,
    seller_name: str,
    seller_address: str,
    buyer: str | dict,
    items: list[dict],
    origin: dict,
    reason: str,
    *,
    secuencia: str,
    fecha_vencimiento_secuencia: str,
    **kwargs: Any,
) -> dict:
    """Build an e-CF tipo 34 (Nota de Crédito Electrónica)."""
    return build_ecf(
        taxid, seller_name, seller_address, buyer, items,
        doc_type="34",
        secuencia=secuencia,
        fecha_vencimiento_secuencia=fecha_vencimiento_secuencia,
        origin=origin,
        reason=reason,
        **kwargs,
    )