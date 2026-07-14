"""JSON NUC payload builder for República Dominicana e-CF (electronic tax documents).

Builds the JSON payload that is sent to ``/v2/transform/nuc_json`` for certification
by Digifact DO.

Matches the exact JSON structure confirmed working with the Digifact DO API across
document types 31, 32, 33, 34, 41, 43, 44, 45, 46, 47.
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

    Contact info (PhoneList, EmailList, Website) is nested inside a ``Contact``
    block, matching the working JSON payloads.

    ``TaxIDType`` is only included when the buyer dict explicitly provides
    ``taxid_type`` (e.g. ``"EXTRANJERO"`` for type 47).

    ``AdditionlInfo`` is included when the buyer dict provides ``additional_info``
    (e.g. FechaEntrega, ContactoEntrega, DireccionEntrega, etc.).
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

    # Build Contact block (omit entirely if no contact data provided)
    has_email = bool(buyer.get("email"))
    has_phone = bool(buyer.get("phone"))
    has_website = bool(buyer.get("website"))

    buyer_dict: dict[str, Any] = {
        "TaxID": buyer["taxid"],
        "Name": buyer["name"],
    }

    # TaxIDType — only if explicitly provided (e.g. "EXTRANJERO" for type 47)
    if "taxid_type" in buyer:
        buyer_dict["TaxIDType"] = buyer["taxid_type"]

    # Contact block — nested structure matching working JSON
    if has_email or has_phone or has_website:
        contact: dict[str, Any] = {}
        if has_phone:
            contact["PhoneList"] = {"Phone": [buyer["phone"]]}
        if has_email:
            contact["EmailList"] = {"Email": [buyer["email"]]}
        if has_website:
            contact["Website"] = buyer["website"]
        if contact:
            buyer_dict["Contact"] = contact

    # AdditionlInfo — optional buyer extra fields
    buyer_additional = buyer.get("additional_info")
    if buyer_additional:
        buyer_dict["AdditionlInfo"] = buyer_additional

    # AddressInfo
    has_address = any(
        buyer.get(k)
        for k in ("address", "district", "state")
    )
    if has_address or "country" in buyer:
        buyer_dict["AddressInfo"] = {
            "Address": buyer.get("address", ""),
            "District": buyer.get("district", ""),
            "State": buyer.get("state", ""),
            "Country": buyer.get("country", "DO"),
        }

    return buyer_dict


def _build_header_do(
    doc_type: str,
    issue_dt: str,
    secuencia: str,
    fecha_vencimiento_secuencia: str = "",
    indicador_monto_gravado: str = "0",
    tipo_ingresos: str = "01",
    tipo_pago: str = "1",
    exchange_rate: float | None = None,
    currency: str | None = None,
    fecha_desde: str | None = None,
    fecha_hasta: str | None = None,
    indicador_envio_diferido: str | None = None,
    fecha_limite_pago: str | None = None,
    termino_pago: str | None = None,
    numero_cuenta_pago: str | None = None,
    banco_pago: str | None = None,
) -> dict:
    """Build the ``Header`` block for an e-CF.

    ``FechaVencimientoSecuencia`` is only included when provided (optional for
    doc types like 32 that do not support it).

    ``IndicadorEnvioDiferido`` is placed before ``IndicadorMontoGravado``
    matching the working JSON payload order.
    """
    # Step 1 — Secuencia always first
    info_list: list[dict[str, str]] = [
        {"Name": "Secuencia", "Value": secuencia},
    ]

    # Step 2 — FechaVencimientoSecuencia (if provided)
    if fecha_vencimiento_secuencia:
        info_list.append(
            {"Name": "FechaVencimientoSecuencia", "Value": fecha_vencimiento_secuencia}
        )

    # Step 3 — IndicadorEnvioDiferido before IndicadorMontoGravado
    if indicador_envio_diferido:
        info_list.append(
            {"Name": "IndicadorEnvioDiferido", "Value": indicador_envio_diferido}
        )

    # Step 4 — IndicadorMontoGravado, TipoIngresos, TipoPago
    info_list.append(
        {"Name": "IndicadorMontoGravado", "Value": indicador_monto_gravado}
    )
    info_list.append({"Name": "TipoIngresos", "Value": tipo_ingresos})
    info_list.append({"Name": "TipoPago", "Value": tipo_pago})

    # Step 5 — Optional fields in working JSON order
    if fecha_desde:
        info_list.append({"Name": "FechaDesde", "Value": fecha_desde})
    if fecha_hasta:
        info_list.append({"Name": "FechaHasta", "Value": fecha_hasta})
    if fecha_limite_pago:
        info_list.append({"Name": "FechaLimitePago", "Value": fecha_limite_pago})
    if termino_pago:
        info_list.append({"Name": "TerminoPago", "Value": termino_pago})
    if numero_cuenta_pago:
        info_list.append({"Name": "NumeroCuentaPago", "Value": numero_cuenta_pago})
    if banco_pago:
        info_list.append({"Name": "BancoPago", "Value": banco_pago})

    header: dict[str, Any] = {
        "DocType": doc_type,
        "IssuedDateTime": issue_dt,
        "AdditionalIssueDocInfo": info_list,
    }

    # Currency + ExchangeRate (for foreign currency invoices)
    if currency:
        header["Currency"] = currency
    if exchange_rate is not None:
        header["ExchangeRate"] = exchange_rate

    return header


def _build_seller_do(
    taxid: str,
    name: str,
    address: str,
    *,
    numero_factura_interna: str = "",
    seller_additionl_info: list[dict] | None = None,
    branch_name: str = "0001",
    branch_code: str = "",
    district: str = "",
    state: str = "",
    country: str = "",
    seller_phone: str = "",
    seller_email: str = "",
    seller_website: str = "",
) -> dict:
    """Build the ``Seller`` block for an e-CF.

    The ``Contact`` block is only included when at least one contact field
    (phone, email, website) is provided, matching working JSON patterns.

    ``BranchInfo.Code`` is included only when provided (used in type 47).
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
    # TaxID → Name → [Contact] → [AdditionlInfo] → BranchInfo
    seller: dict[str, Any] = {
        "TaxID": taxid,
        "Name": name,
    }

    # Contact block — only if at least one field is provided
    has_contact = any([seller_phone, seller_email, seller_website])
    if has_contact:
        contact: dict[str, Any] = {}
        if seller_phone:
            contact["PhoneList"] = {"Phone": [seller_phone]}
        else:
            contact["PhoneList"] = {"Phone": [""]}
        if seller_email:
            contact["EmailList"] = {"Email": [seller_email]}
        else:
            contact["EmailList"] = {"Email": [""]}
        if seller_website:
            contact["Website"] = seller_website
        else:
            contact["Website"] = ""
        seller["Contact"] = contact
    else:
        # Contact with minimal required fields (matching payloads that include it)
        seller["Contact"] = {
            "PhoneList": {"Phone": [""]},
            "EmailList": {"Email": [""]},
            "Website": "",
        }

    if additionl_info:
        seller["AdditionlInfo"] = additionl_info

    branch_info: dict[str, Any] = {
        "Name": branch_name,
        "AddressInfo": {
            "Address": address,
            "District": district,
            "State": state,
            "Country": country,
        },
    }
    if branch_code:
        branch_info["Code"] = branch_code
    seller["BranchInfo"] = branch_info

    return seller


def _build_items_do(
    items: list[dict],
    extra_taxes: list[dict] | None = None,
) -> tuple[list[dict], DoInvoiceTotals]:
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
        discount_type: str      (default "$" for fixed amount, "%" for percentage)
        discount_rate: float | None  (rate for percentage discounts)
        charge: float | None
        ean: str                (optional)
        plu: str                (optional)
        codes: list[dict]       (optional custom codes, e.g. Interna, TipoCodigo/CodigoItem)
        descripcion_item: str   (optional extended description)
        taxes: list[dict]       (optional inline taxes, e.g. 001/002/004)
        additional_info: list[dict] (optional extra AdditionalInfo entries)
        indicador_agente_retencion: str (optional, "1" for types 41/47)
        monto_itbis_retenido: str (optional, for type 41)
        monto_isr_retenido: str  (optional, for types 41/47)

    Parameters
    ----------
    extra_taxes : list[dict], optional
        Additional tax entries at invoice level (e.g. 002 CDT, 004 ISC).
        Passed through to ``DoInvoiceTotals.to_totals_block()``.
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
        charge_val = item.get("charge")
        charge = Decimal(str(charge_val)) if charge_val is not None else None

        lc = DoLineCalc(qty, price, indicador=indicador, discount=discount, charge=charge)
        lines.append(lc)

        # Qty and Price — use number when input is numeric (int/float), string
        # otherwise.  Matching the mixed format in working JSON payloads where
        # some use native numbers and others use strings.
        raw_qty = item.get("qty", 1)
        raw_price = item["price"]
        use_num_qty = isinstance(raw_qty, (int, float)) and not isinstance(raw_qty, bool)
        use_num_price = isinstance(raw_price, (int, float)) and not isinstance(raw_price, bool)

        built: dict[str, Any] = {
            "Type": item_type,
            "Description": desc,
            "Qty": raw_qty if use_num_qty else str(qty),
            "UnitOfMeasure": uom,
            "Price": raw_price if use_num_price else str(price),
            "Totals": {"TotalItem": fmt(lc.line_total, decimals=2)},
            "AdditionalInfo": [
                {"Name": "IndicadorFacturacion", "Value": indicador},
            ],
        }

        # Optional codes — unified handling for EAN, PLU, and custom codes
        ean = item.get("ean")
        plu = item.get("plu")
        custom_codes = item.get("codes")
        if ean or plu or custom_codes:
            codes: list[dict] = []
            if ean:
                codes.append({"Name": "EAN", "Value": ean})
            if plu:
                codes.append({"Name": "PLU", "Value": plu})
            if custom_codes:
                codes.extend(custom_codes)
            built["Codes"] = codes

        # Optional extended description
        desc_item = item.get("descripcion_item", "")
        if desc_item:
            built["AdditionalInfo"].append(
                {"Name": "DescripcionItem", "Value": desc_item}
            )

        # Optional inline taxes (e.g. 001 Impuesto Adicional, 002 CDT, 004 ISC)
        item_taxes = item.get("taxes")
        if item_taxes:
            built["Taxes"] = {"Tax": item_taxes}

        # Optional retenciones (IndicadorAgenteRetencionPercepcion, MontoITBISRetenido, MontoISRRetenido)
        indicador_retencion = item.get("indicador_agente_retencion")
        if indicador_retencion:
            built["AdditionalInfo"].append(
                {"Name": "IndicadorAgenteRetencionPercepcion", "Value": indicador_retencion}
            )
        monto_itbis_ret = item.get("monto_itbis_retenido")
        if monto_itbis_ret is not None:
            built["AdditionalInfo"].append(
                {"Name": "MontoITBISRetenido", "Value": str(monto_itbis_ret)}
            )
        monto_isr_ret = item.get("monto_isr_retenido")
        if monto_isr_ret is not None:
            built["AdditionalInfo"].append(
                {"Name": "MontoISRRetenido", "Value": str(monto_isr_ret)}
            )

        # Optional extra AdditionalInfo from item (FechaElaboracion, FechaVencimientoItem,
        # ItemDescription, etc.)
        item_extra_info = item.get("additional_info")
        if item_extra_info:
            built["AdditionalInfo"].extend(item_extra_info)

        # Discounts — support both fixed ($) and percentage (%) — omit if absent
        if discount is not None and discount > 0:
            discount_type = item.get("discount_type", "$")
            discount_entry: dict[str, Any] = {
                "Code": discount_type,
                "Amount": float(discount),
            }
            discount_rate = item.get("discount_rate")
            if discount_type == "%" and discount_rate is not None:
                discount_entry["Rate"] = float(discount_rate)
            built["Discounts"] = {"Discount": [discount_entry]}

        # Charges — only include when present (omit matching working JSON)
        if charge is not None and charge > 0:
            built["Charges"] = {
                "Charge": [{"Code": "$", "Amount": float(charge)}]
            }

        line_items.append(built)

    totals = DoInvoiceTotals(lines)
    return line_items, totals


def _build_totals_additional_info(
    additional_info: list[dict] | None = None,
) -> list[dict]:
    """Build ``Totals.AdditionalInfo`` block.

    Returns the caller-provided list as-is, or an empty list by default.
    Working payloads use semantic fields such as ``TotalITBISRetenido``,
    ``MontoNoFacturable``, or ``TotalISRRetencion``.
    """
    if additional_info:
        return additional_info
    return []


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
    currency: str | None = None,
    fecha_desde: str | None = None,
    fecha_hasta: str | None = None,
    indicador_envio_diferido: str | None = None,
    fecha_limite_pago: str | None = None,
    termino_pago: str | None = None,
    numero_cuenta_pago: str | None = None,
    banco_pago: str | None = None,
    numero_factura_interna: str = "",
    seller_additionl_info: list[dict] | None = None,
    seller_branch_name: str = "0001",
    seller_branch_code: str = "",
    seller_branch_district: str = "",
    seller_branch_state: str = "",
    seller_branch_country: str = "",
    seller_phone: str = "",
    seller_email: str = "",
    seller_website: str = "",
    payments: list[dict] | None = None,
    additional_info: list[dict] | None = None,
    totals_extra_info: list[dict] | None = None,
    url_to_send: str | None = None,
    issue_dt: str | None = None,
    extra_taxes: list[dict] | None = None,
    # Origin document for ND (33) / NC (34) — DGII structure
    origin: dict | None = None,
    reason: str = "",
    codigo_modificacion: str = "",
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
        Use ``taxid_type`` key for explicit ``Buyer.TaxIDType`` (optional).
        Use ``additional_info`` key for ``Buyer.AdditionlInfo`` entries
        (e.g. FechaEntrega, ContactoEntrega, DireccionEntrega, etc.).
    items : list[dict]
        List of item dicts. Each must have ``description`` and ``price``.
        ``indicador_facturacion`` controls ITBIS: ``"1"`` (18%), ``"2"`` (16%),
        ``"3"`` (0%), ``"4"`` (Exento).
        Optional keys: ``taxes`` (inline item taxes), ``additional_info``
        (extra AdditionalInfo entries per item), ``indicador_agente_retencion``,
        ``monto_itbis_retenido``, ``monto_isr_retenido`` (for types 41/47),
        ``codes`` (custom Codes entries like Interna, TipoCodigo/CodigoItem).
    doc_type : str
        ``"31"`` (Factura Crédito Fiscal, default), ``"32"`` (Consumo),
        ``"33"`` (Nota Débito), ``"34"`` (Nota Crédito),
        ``"41"`` (Comprobante de Compras), ``"43"`` (Comprobante de Gastos
        Menores), ``"44"`` (Comprobante de Regímenes Especiales),
        ``"45"`` (Comprobante Gubernamental), ``"46"`` (Comprobante de
        Exportación), ``"47"`` (Comprobante de Pagos al Exterior).
    secuencia : str
        NCF asignado por la DGII, ej. ``"0000490963"``.
    fecha_vencimiento_secuencia : str
        Fecha de vencimiento del NCF, ej. ``"2028-12-31"``.
    currency : str, optional
        Currency code for foreign currency invoices (e.g. ``"EUR"``).
        When set, ``exchange_rate`` should also be provided.
    origin : dict, optional
        Origin document info for ND/NC (types 33/34). Keys:
        ``auth_number`` (NCFModificado), ``date`` (FechaNCFModificado),
        ``number`` (not used directly in DGII structure — NCFModificado
        serves as the identifier).
    reason : str, optional
        Reason for modification (RazonModificacion).
    codigo_modificacion : str, optional
        DGII modification code: ``"1"`` (anulación), ``"2"`` (corrección),
        ``"3"`` (devolución). Required for types 33/34.
    payments : list[dict], optional
        Payment entries. If omitted, **no** ``Payments`` field is added.
    totals_extra_info : list[dict], optional
        Extra entries for ``Totals.AdditionalInfo``. Use semantic names like
        ``TotalITBISRetenido``, ``MontoNoFacturable``, ``TotalISRRetencion``.
    extra_taxes : list[dict], optional
        Additional tax entries at invoice level appended to ``TotalTax[]``,
        e.g. ``[{"Code": "002", "TaxableAmount": "84.75", "Rate": "2.00",
        "Amount": "1.69"}]``.
    """
    effective_issue_dt = issue_dt or do_now(with_offset=True)
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
        currency=currency,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        indicador_envio_diferido=indicador_envio_diferido,
        fecha_limite_pago=fecha_limite_pago,
        termino_pago=termino_pago,
        numero_cuenta_pago=numero_cuenta_pago,
        banco_pago=banco_pago,
    )

    seller = _build_seller_do(
        taxid,
        seller_name,
        seller_address,
        numero_factura_interna=numero_factura_interna,
        seller_additionl_info=seller_additionl_info,
        branch_name=seller_branch_name,
        branch_code=seller_branch_code,
        district=seller_branch_district,
        state=seller_branch_state,
        country=seller_branch_country,
        seller_phone=seller_phone,
        seller_email=seller_email,
        seller_website=seller_website,
    )

    line_items, totals = _build_items_do(items, extra_taxes=extra_taxes)

    totals_block = totals.to_totals_block(extra_taxes=extra_taxes)
    # QtyItems — item counter (present in 12/14 working payloads)
    totals_block["QtyItems"] = len(line_items)
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

    # ── Origin document (ND: 33, NC: 34) — DGII INFORMACION_REFERENCIA structure ──
    if origin is not None:
        ref_info = [
            {"Name": "NCFModificado", "Data": None, "Value": origin.get("auth_number", "")},
            {"Name": "FechaNCFModificado", "Data": None, "Value": origin.get("date", "")},
            {"Name": "CodigoModificacion", "Data": None, "Value": codigo_modificacion or "1"},
            {"Name": "RazonModificacion", "Data": None, "Value": reason},
        ]
        payload["AdditionalDocumentInfo"]["AdditionalInfo"].append(
            {
                "AditionalData": {
                    "Data": [
                        {
                            "Info": ref_info,
                            "Name": "INFORMACION_REFERENCIA",
                        }
                    ]
                },
                "AditionalInfo": None,
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
    codigo_modificacion: str = "1",
    **kwargs: Any,
) -> dict:
    """Build an e-CF tipo 33 (Nota de Débito Electrónica).

    Parameters
    ----------
    codigo_modificacion : str
        DGII modification code: ``"1"`` (anulación), ``"2"`` (corrección),
        ``"3"`` (devolución).
    """
    return build_ecf(
        taxid, seller_name, seller_address, buyer, items,
        doc_type="33",
        secuencia=secuencia,
        fecha_vencimiento_secuencia=fecha_vencimiento_secuencia,
        origin=origin,
        reason=reason,
        codigo_modificacion=codigo_modificacion,
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
    codigo_modificacion: str = "1",
    **kwargs: Any,
) -> dict:
    """Build an e-CF tipo 34 (Nota de Crédito Electrónica).

    Parameters
    ----------
    codigo_modificacion : str
        DGII modification code: ``"1"`` (anulación), ``"2"`` (corrección),
        ``"3"`` (devolución).
    """
    return build_ecf(
        taxid, seller_name, seller_address, buyer, items,
        doc_type="34",
        secuencia=secuencia,
        fecha_vencimiento_secuencia=fecha_vencimiento_secuencia,
        origin=origin,
        reason=reason,
        codigo_modificacion=codigo_modificacion,
        **kwargs,
    )
