"""Guatemala-specific configuration."""
from __future__ import annotations

from dataclasses import dataclass, field


_BASE_URLS = {
    "test": "https://testnucgt.digifact.com/api",
    "production": "https://nucgt.digifact.com/gt.com.apinuc/api",
}


@dataclass
class GtConfig:
    """Configuration for the Guatemala Digifact API."""

    taxid: str
    username: str
    password: str = ""
    environment: str = "test"
    token: str = ""
    timeout: int = 120
    afiliacion_iva: str = "GEN"
    tipo_personeria: str = "1"
    tipo_frase: str | None = None
    escenario: str | None = None
    frases: list[dict] | None = None
    auto_fuel_subsidy_frases: bool | None = None
    branch_code: str = "1"
    branch_name: str = "ESTABLECIMIENTO PRINCIPAL"
    petroleo_rates: dict[str, float] | None = None
    seller_name: str = ""
    seller_address: str = ""

    @property
    def base_url(self) -> str:
        urls = _BASE_URLS.get(self.environment)
        if urls is None:
            raise ValueError(f"environment must be 'test' or 'production', got {self.environment!r}")
        return urls

    @property
    def full_username(self) -> str:
        from ...core.money import pad_taxid
        return f"GT.{pad_taxid(self.taxid, 12)}.{self.username}"