"""ITBIS calculations for República Dominicana e-CF.

Key difference with GT: in DO prices are **net** (without ITBIS included),
and the tax is calculated on top of the line total.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP, getcontext
from typing import Any

from ...core.money import fmt

getcontext().prec = 28

# IndicadorFacturacion → ITBIS rate (%)
_ITBIS_RATES: dict[str, Decimal] = {
    "1": Decimal("18.00"),  # ITBIS 18%
    "2": Decimal("16.00"),  # ITBIS 16%
    "3": Decimal("0"),      # ITBIS 0% (no ITBIS)
    "4": Decimal("0"),      # Exento
}

# IndicadorFacturacion → tax code in Totals
_ITBIS_CODES: dict[str, str] = {
    "1": "ITBIS1",
    "2": "ITBIS2",
    "3": "ITBIS3",
    "4": "EXENTO",
}

# UnitOfMeasure mapping (DGII standard codes)
UOM_CODES: dict[str, str] = {
    "unidad": "98",
    "UNI": "98",
    "servicio": "98",
    "kg": "01",
    "kilogramo": "01",
    "lb": "02",
    "litro": "03",
    "LTS": "03",
    "galon": "04",
    "m2": "17",
    "metro": "16",
    "m3": "18",
    "caja": "53",
    "docena": "72",
    "pack": "53",
    "par": "75",
    "rollo": "93",
}


def resolve_uom(uom: str) -> str:
    """Map a common UOM name to a DGII standard code.

    Returns an empty string when *uom* is empty, so the caller can omit
    the ``UnitOfMeasure`` field entirely from the payload (the DGII schema
    may reject code-based values like ``"98"`` for certain document types).
    When a non-empty value is given that is not found in the mapping, it
    is passed through as-is.
    """
    if not uom:
        return ""
    return UOM_CODES.get(uom, uom)


class DoLineCalc:
    """Calculation for a single e-CF line item in Dominican Republic.

    Parameters
    ----------
    qty : Decimal
        Quantity.
    unit_price : Decimal
        Unit price **NET** (without ITBIS).
    indicador : str
        IndicadorFacturacion code: ``"1"`` (ITBIS 18%), ``"2"`` (ITBIS 16%),
        ``"3"`` (ITBIS 0%), ``"4"`` (Exento).
    discount : Decimal, optional
        Line-level discount amount.
    charge : Decimal, optional
        Line-level charge (recargo) amount.
    """

    def __init__(
        self,
        qty: Decimal | float | str,
        unit_price: Decimal | float | str,
        indicador: str = "1",
        discount: Decimal | float | str | None = None,
        charge: Decimal | float | str | None = None,
    ) -> None:
        if indicador not in _ITBIS_RATES:
            raise ValueError(f"Invalid indicador_facturacion: {indicador!r}. Must be 1, 2, 3, or 4.")

        self.qty = Decimal(str(qty))
        self.unit_price = Decimal(str(unit_price))
        self.indicador = indicador

        self.gross = (self.qty * self.unit_price).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
        self.discount = (Decimal(str(discount)) if discount is not None else Decimal("0")).quantize(
            Decimal("0.000001"), rounding=ROUND_HALF_UP
        )
        self.charge = (Decimal(str(charge)) if charge is not None else Decimal("0")).quantize(
            Decimal("0.000001"), rounding=ROUND_HALF_UP
        )
        self.line_total = (self.gross - self.discount + self.charge).quantize(
            Decimal("0.000001"), rounding=ROUND_HALF_UP
        )

        # ITBIS calculation
        rate = _ITBIS_RATES[indicador]
        if indicador == "4":  # Exento
            self.taxable_amount = Decimal("0")
            self.itbis_amount = Decimal("0")
        else:
            self.taxable_amount = self.line_total
            self.itbis_amount = (self.line_total * rate / Decimal("100")).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )

    @property
    def itbis_rate(self) -> Decimal:
        return _ITBIS_RATES.get(self.indicador, Decimal("0"))

    @property
    def tax_code(self) -> str:
        return _ITBIS_CODES.get(self.indicador, "EXENTO")

    # ── String formatters ─────────────────────────────────────────────────────

    def f_qty(self) -> str:
        return fmt(self.qty)

    def f_price(self) -> str:
        return fmt(self.unit_price)

    def f_line_total(self) -> str:
        return fmt(self.line_total)

    def f_taxable(self) -> str:
        return fmt(self.taxable_amount)

    def f_itbis(self) -> str:
        return fmt(self.itbis_amount)

    def f_discount(self) -> str:
        return fmt(self.discount, decimals=2)


class DoInvoiceTotals:
    """Aggregate totals for an e-CF in Dominican Republic."""

    def __init__(self, lines: list[DoLineCalc]) -> None:
        self.lines = lines

        # Totals
        self.total_taxable = sum(ln.taxable_amount for ln in lines).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        self.total_itbis = sum(ln.itbis_amount for ln in lines).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        self.total_line = sum(ln.line_total for ln in lines).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        self.grand_total = sum(ln.line_total + ln.itbis_amount for ln in lines).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

    def build_taxes(self) -> list[dict]:
        """Build the ``TotalTaxes.TotalTax[]`` list grouped by tax code.

        Key order is critical for DGII's XSLT-to-XML validation.  The confirmed
        working order is: ``Code`` → ``TaxableAmount`` (number) → ``Rate`` (string) → ``Amount`` (string).

        For EXENTO items, the ``Amount`` field contains the line total
        (as confirmed by working DO API payloads).
        ``TaxableAmount`` and ``Rate`` are **omitted** for EXENTO when they
        are zero, matching the majority of working payload examples.
        """
        groups: dict[str, dict] = {}
        for line in self.lines:
            code = line.tax_code
            rate = line.itbis_rate
            if code not in groups:
                groups[code] = {
                    "Code": code,
                    "TaxableAmount": Decimal("0"),
                    "Rate": rate,
                    "Amount": Decimal("0"),
                }
            if code == "EXENTO":
                # EXENTO: Amount = line_total, TaxableAmount = 0
                groups[code]["Amount"] = (groups[code]["Amount"] + line.line_total).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
            else:
                groups[code]["TaxableAmount"] = (groups[code]["TaxableAmount"] + line.taxable_amount).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
                groups[code]["Amount"] = (groups[code]["Amount"] + line.itbis_amount).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
        result = []
        for g in groups.values():
            # Build entry with EXACT key order: Code → TaxableAmount → Rate → Amount
            # TaxableAmount is a number (float), Rate and Amount are strings.
            entry: dict[str, Any] = {
                "Code": g["Code"],
            }
            if g["Code"] == "EXENTO" and g["TaxableAmount"] == Decimal("0") and g["Rate"] == Decimal("0"):
                # Omit TaxableAmount and Rate for EXENTO when both are zero
                entry["Amount"] = fmt(g["Amount"], decimals=2)
            else:
                entry["TaxableAmount"] = round(float(g["TaxableAmount"]), 2)
                entry["Rate"] = str(g["Rate"])
                entry["Amount"] = fmt(g["Amount"], decimals=2)
            result.append(entry)
        return result

    @property
    def is_all_exento(self) -> bool:
        """True when every line item has indicador_facturacion=4 (Exento)."""
        return all(line.indicador == "4" for line in self.lines)

    def to_totals_block(
        self,
        extra_taxes: list[dict] | None = None,
    ) -> dict:
        """Build the full ``Totals`` JSON block.

        Format per API requirements:
        - ``TotalTaxableAmount`` → **number** (float), **omitted** when all
          items are EXENTO (matching types 43, 44, 45, 47).
        - ``GrandTotal.InvoiceTotal`` → **string** (2 decimales)
        - ``TotalTax[].*`` values → **string**

        Key order matches the working JSON: [TotalTaxableAmount] → TotalTaxes → GrandTotal → AdditionalInfo.

        Parameters
        ----------
        extra_taxes : list[dict], optional
            Additional tax entries to append to ``TotalTax[]``, e.g.
            ``[{"Code": "002", "TaxableAmount": "84.75", "Rate": "2.00", "Amount": "1.69"}]``.
            These represent DGII-specific taxes (Impuesto Adicional 001,
            CDT 002, ISC 004) that are not derived from indicador_facturacion.
        """
        taxes = self.build_taxes()
        if extra_taxes:
            taxes.extend(extra_taxes)

        block: dict[str, Any] = {}

        # Omit TotalTaxableAmount for fully EXENTO documents (types 43, 44, 45, 47)
        if not self.is_all_exento:
            block["TotalTaxableAmount"] = float(self.total_taxable)

        if taxes:
            block["TotalTaxes"] = {"TotalTax": taxes}
        block["GrandTotal"] = {
            "InvoiceTotal": fmt(self.grand_total, decimals=2),
        }
        return block
