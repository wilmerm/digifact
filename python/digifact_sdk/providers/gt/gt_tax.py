"""IVA calculations and Guatemala time helpers — migrated from digifact_sdk.tax."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from decimal import Decimal, ROUND_HALF_UP

from ...core.money import fmt, calc_iva as core_calc_iva

_GT_TZ = timezone(timedelta(hours=-6))


def gt_now() -> tuple[str, str, str]:
    """Return (iso_with_offset, space_datetime, date_only) in Guatemala time (UTC-6)."""
    gt = datetime.now(_GT_TZ)
    dt_offset = gt.strftime("%Y-%m-%dT%H:%M:%S-06:00")
    dt_space = gt.strftime("%Y-%m-%d %H:%M:%S")
    date_only = gt.strftime("%Y-%m-%d")
    return dt_offset, dt_space, date_only


def gt_now_dt() -> datetime:
    """Return current datetime in Guatemala timezone."""
    return datetime.now(_GT_TZ)


def pad_taxid(taxid: str) -> str:
    """Strip non-digits and left-pad to 12 characters with zeros."""
    from ...core.money import pad_taxid as _pad
    return _pad(taxid, 12)


class LineCalc:
    """Holds calculated values for a single invoice line (GT: IVA-inclusive pricing)."""

    def __init__(
        self,
        qty: Decimal,
        unit_price: Decimal,
        *,
        taxable: bool = True,
        discount: Decimal | None = None,
    ) -> None:
        self.qty = qty
        self.unit_price = unit_price
        self.gross = (qty * unit_price).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
        self.discount = (discount or Decimal("0")).quantize(
            Decimal("0.000001"), rounding=ROUND_HALF_UP
        )
        self.line_total = (self.gross - self.discount).quantize(
            Decimal("0.000001"), rounding=ROUND_HALF_UP
        )
        if taxable:
            self.taxable_amount, self.iva_amount = core_calc_iva(self.line_total)
        else:
            self.taxable_amount = Decimal("0")
            self.iva_amount = Decimal("0")

    def f_qty(self) -> str: return fmt(self.qty)
    def f_price(self) -> str: return fmt(self.unit_price)
    def f_line_total(self) -> str: return fmt(self.line_total)
    def f_taxable(self) -> str: return fmt(self.taxable_amount)
    def f_iva(self) -> str: return fmt(self.iva_amount)
    def f_discount(self) -> str: return fmt(self.discount, decimals=2)


class FuelLineCalc:
    """Holds calculated values for fuel (combustible) line item (GT)."""

    def __init__(
        self,
        qty: Decimal,
        unit_price: Decimal,
        petrol_amount_per_unit: Decimal,
    ) -> None:
        self.qty = qty
        self.unit_price = unit_price
        net_per_unit = unit_price - petrol_amount_per_unit
        self.gross = (qty * net_per_unit).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
        self.petrol_total = (qty * petrol_amount_per_unit).quantize(
            Decimal("0.000001"), rounding=ROUND_HALF_UP
        )
        self.line_total = (qty * unit_price).quantize(
            Decimal("0.000001"), rounding=ROUND_HALF_UP
        )
        self.taxable_amount, self.iva_amount = core_calc_iva(self.gross)

    def f_qty(self) -> str: return fmt(self.qty)
    def f_price(self) -> str: return fmt(self.unit_price)
    def f_line_total(self) -> str: return fmt(self.line_total)
    def f_taxable(self) -> str: return fmt(self.taxable_amount)
    def f_iva(self) -> str: return fmt(self.iva_amount)
    def f_petrol(self) -> str: return fmt(self.petrol_total)


class InvoiceTotals:
    """Aggregate totals for a full invoice (GT)."""

    def __init__(self, lines: list[LineCalc]) -> None:
        self.lines = lines
        self.grand_total = sum(ln.line_total for ln in lines).quantize(
            Decimal("0.000001"), rounding=ROUND_HALF_UP
        )
        self.total_iva = sum(ln.iva_amount for ln in lines).quantize(
            Decimal("0.000001"), rounding=ROUND_HALF_UP
        )
        self.total_taxable = sum(ln.taxable_amount for ln in lines).quantize(
            Decimal("0.000001"), rounding=ROUND_HALF_UP
        )

    def f_grand_total(self) -> str: return fmt(self.grand_total)
    def f_total_iva(self) -> str: return fmt(self.total_iva)


class FuelInvoiceTotals:
    """Aggregate totals for a fuel invoice (GT)."""

    def __init__(self, lines: list[FuelLineCalc]) -> None:
        self.lines = lines
        self.grand_total = sum(ln.line_total for ln in lines).quantize(
            Decimal("0.000001"), rounding=ROUND_HALF_UP
        )
        self.total_iva = sum(ln.iva_amount for ln in lines).quantize(
            Decimal("0.000001"), rounding=ROUND_HALF_UP
        )
        self.total_taxable = sum(ln.taxable_amount for ln in lines).quantize(
            Decimal("0.000001"), rounding=ROUND_HALF_UP
        )
        self.total_petrol = sum(ln.petrol_total for ln in lines).quantize(
            Decimal("0.000001"), rounding=ROUND_HALF_UP
        )

    def f_grand_total(self) -> str: return fmt(self.grand_total)
    def f_total_iva(self) -> str: return fmt(self.total_iva)