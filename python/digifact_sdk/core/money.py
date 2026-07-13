"""Money formatting, IVA calculations, and time helpers.

Shared by all country providers.  Guatemala-specific helpers (gt_now, pad_taxid)
live in the GT provider module; country-agnostic helpers here.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone, timedelta
from decimal import Decimal, ROUND_HALF_UP, getcontext

getcontext().prec = 28

_IVA_RATE = Decimal("12")
_IVA_DIVISOR = Decimal("112")


def fmt(value: Decimal | float | str, decimals: int = 6) -> str:
    """Format a Decimal (or float/str) as a string with *decimals* decimal places."""
    d = Decimal(str(value))
    quantize_str = Decimal("1." + "0" * decimals)
    return str(d.quantize(quantize_str, rounding=ROUND_HALF_UP))


def calc_iva(line_total: "Decimal | float | str") -> tuple[Decimal, Decimal]:
    """Return (taxable_amount, iva_amount) for an IVA-inclusive line_total.

    taxable_amount = line_total / 1.12
    iva_amount     = line_total - taxable_amount
    """
    line_total = Decimal(str(line_total))
    taxable = (line_total * 100 / _IVA_DIVISOR).quantize(
        Decimal("0.000001"), rounding=ROUND_HALF_UP
    )
    iva = (line_total - taxable).quantize(
        Decimal("0.000001"), rounding=ROUND_HALF_UP
    )
    return taxable, iva


def pad_taxid(taxid: str, length: int = 12) -> str:
    """Strip non-digits and left-pad to *length* characters with zeros.

    Example: '44653948' → '000044653948'
    """
    digits = re.sub(r"\D", "", taxid)
    return digits.rjust(length, "0")


def do_now() -> str:
    """Return ISO 8601 datetime with offset in Dominican Republic time (UTC-4)."""
    _DO_TZ = timezone(timedelta(hours=-4))
    dt = datetime.now(_DO_TZ)
    return dt.strftime("%Y-%m-%dT%H:%M:%S-04:00")