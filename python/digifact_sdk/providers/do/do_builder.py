"""JSON NUC payload builder for República Dominicana e-CF (electronic tax documents).

Builds the JSON payload that is sent to ``/v2/transform/nuc_json`` for certification
by Digifact DO.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from ...core.money import do_now
from .do_tax import DoLineCalc, DoInvoiceTotals, resolve_uom


def _resolve_buyer_do(buyer: str | dict) -> dict:
    """Resolve a buyer specification to a DO buyer dict.

    In DO there is no "CF" (Consumidor Final) special ID. Buyer always needs
    a TaxID (RNC or Cédula).
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
        "Name": buyer["name"],
        "Contact": {
            "PhoneList": {"Phone": [buyer.get("phone", "")]},
            "EmailList": {"Email": [buyer.get("email", "")]},
            "Website": buyer.get("website", ""),
        },
        "AdditionlInfo": [
            {"Name": "FechaEntrega", "Value": buyer.get("delivery_date", "")},
            {"Name": "ContactoEntrega", "Value": buyer.get("delivery_contact", "")},
        ],
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
    currency: str,
    secuencia: str,
    fecha_vencimiento_secuencia: str,
    indicador_monto_gravado: str = "1",
    tipo_ingresos: str = "01",
    tipo_pago: str = "1",
    exchange_rate: float | None = None,
    fecha_desde: str | None = None,
    fecha_hasta: str | None = None,
    indicador_envio_diferido: str | None = None,
) -> dict:
    """Build the ``Header`` block for an e-CF."""
    header: dict[str, Any] = {
        "DocType": doc_type,
        "IssuedDateTime": issue_dt,
        "AdditionalIssueType": None,
        "Currency": currency,
        "AdditionalIssueDocInfo": [
            {"Name": "Secuencia", "Value": secuencia},
            {"Name": "FechaVencimientoSecuencia", "Value": fecha_vencimiento_secuencia},
            {"Name": "IndicadorMontoGravado", "Value": indicador_monto_gravado},
            {"Name": "TipoIngresos", "Value": tipo_ingresos},
            {"Name": "TipoPago", "Value": tipo_pago},
        ],
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
    nombre_comercial: str = "",
    actividad_economica: str = "",
    numero_factura_interna: str = "",
    branch_code: str = "1",
    branch_name: str = "ESTABLECIMIENTO PRINCIPAL",
    district: str = "",
    state: str = "",
) -> dict:
    """Build the ``Seller`` block for an e-CF."""
    seller: dict[str, Any] = {
        "TaxID": taxid,
        "Name": name,
        "AdditionlInfo": [
            {"Name": "NombreComercial", "Value": nombre_comercial or name},
            {"Name": "ActividadEconomica", "Value": actividad_economica or ""},
            {"Name": "NumeroFacturaInterna", "Value": numero_factura_interna or ""},
        ],
        "BranchInfo": {
            "Code": branch_code,
            "Name": branch_name,
            "AddressInfo": {
                "Address": address,
                "District": district,
                "State": state,
                "Country": "DO",
            },
        },
    }
    return seller


def _build_items_do(items: list[dict]) -> tuple[list[dict], DoInvoiceTotals]:
    """Build the ``Items`` list and totals from item dicts.

    Each item dict supports:
        description: str
        qty: float | Decimal   (default 1)
        price: float | Decimal  (NET price, without ITBIS)
        indicador_facturacion: str  "1"=ITBIS 18%, "2"=16%, "3"=0%, "4"=Exento
        type: str               (default "1")
        unit_of_measure: str    (default "UNI")
        discount: float | None
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

        built: dict[str, Any] = {
            "Codes": [
                {"Name": "EAN", "Value": item.get("ean", "")},
                {"Name": "PLU", "Value": item.get("plu", "")},
            ],
            "Type": item_type,
            "Description": desc,
            "Qty": lc.f_qty(),
            "UnitOfMeasure": uom,
            "Price": lc.f_price(),
            "Taxes": None,  # DO: taxes at Totals level, not per-item
            "Totals": {"TotalItem": lc.f_line_total()},
            "AdditionalInfo": [
                {"Name": "IndicadorFacturacion", "Value": indicador},
            ],
        }

        # Optional description item detail
        desc_item = item.get("descripcion_item", "")
        if desc_item:
            built["AdditionalInfo"].append(
                {"Name": "DescripcionItem", "Value": desc_item}
            )

        # Discounts
        if discount is not None and discount > 0:
            built["Discounts"] = {
                "Discount": [{"Code": "$", "Amount": float(discount)}]
            }
        else:
            built["Discounts"] = None

        # Charges (optional)
        charge_val = item.get("charge")
        if charge_val is not None:
            built["Charges"] = {
                "Charge": [{"Code": "$", "Amount": float(charge_val)}]
            }

        line_items.append(built)

    totals = DoInvoiceTotals(lines)
    return line_items, totals


def build_ecf(
    taxid: str,
    seller_name: str,
    seller_address: str,
    buyer: str | dict,
    items: list[dict],
    *,
    doc_type: str = "31",
    currency: str = "DOP",
    secuencia: str,
    fecha_vencimiento_secuencia: str,
    indicador_monto_gravado: str = "1",
    tipo_ingresos: str = "01",
    tipo_pago: str = "1",
    exchange_rate: float | None = None,
    fecha_desde: str | None = None,
    fecha_hasta: str | None = None,
    indicador_envio_diferido: str | None = None,
    nombre_comercial: str = "",
    actividad_economica: str = "",
    numero_factura_interna: str = "",
    forma_pago_codigo: str = "1",
    additional_info: list[dict] | None = None,
    issue_dt: str | None = None,
    # Origin document for NC/ND (33=NDeb, 34=NCre, etc.)
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
        Tipo de documento: ``"31"`` (Factura Crédito Fiscal), ``"32"`` (Consumo),
        ``"33"`` (Nota Débito), ``"34"`` (Nota Crédito).
    secuencia : str
        NCF (Número de Comprobante Fiscal) asignado por la DGII, ej. ``"0000490945"``.
    fecha_vencimiento_secuencia : str
        Fecha de vencimiento del NCF, ej. ``"2028-12-31"``.
    """
    effective_issue_dt = issue_dt or do_now()
    buyer_dict = _resolve_buyer_do(buyer)

    header = _build_header_do(
        doc_type=doc_type,
        issue_dt=effective_issue_dt,
        currency=currency,
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
        nombre_comercial=nombre_comercial,
        actividad_economica=actividad_economica,
        numero_factura_interna=numero_factura_interna,
    )

    line_items, totals = _build_items_do(items)

    totals_block = totals.to_totals_block()

    # Payments
    payments = [
        {
            "Type": "FormaPago",
            "Code": forma_pago_codigo,
            "Amount": float(totals.grand_total),
        }
    ]

    payload: dict[str, Any] = {
        "Version": "1.0",
        "CountryCode": "DO",
        "Header": header,
        "Seller": seller,
        "Buyer": buyer_dict,
        "Items": line_items,
        "Totals": totals_block,
        "Payments": payments,
        "AdditionalDocumentInfo": {
            "AdditionalInfo": additional_info or [],
        },
    }

    # ── Origin document (ND, NC) ───────────────────────────────────────────
    if origin is not None:
        comp_code = "NDEB" if doc_type in ("33", "33") else "NCRE"
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