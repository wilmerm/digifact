"""República Dominicana-specific configuration."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DoConfig:
    """Configuration for the República Dominicana Digifact API.

    Parameters
    ----------
    taxid : str
        RNC del emisor (9 dígitos, sin guiones).
    username : str
        Nombre corto de usuario Digifact DO (sin el prefijo ``DO.``).
    password : str
        Contraseña de la cuenta.
    environment : {"test", "production"}, default "test"
        Entorno objetivo.
    token : str, optional
        Token JWT pre-obtenido. Si se proporciona, no se necesita password.
    timeout : int, default 120
        Timeout HTTP en segundos.
    seller_name : str, optional
        Razón Social del emisor. Si se omite se puede resolver vía lookup RNC.
    seller_address : str, optional
        Dirección del emisor.
    """

    taxid: str
    username: str
    password: str = ""
    environment: str = "test"
    token: str = ""
    timeout: int = 120
    seller_name: str = ""
    seller_address: str = ""

    @property
    def base_url(self) -> str:
        urls = {
            "test": "https://testnucdo.digifact.com/api",
            "production": "https://nucdo.digifact.com/do.com.apinuc/api",
        }
        url = urls.get(self.environment)
        if url is None:
            raise ValueError(
                f"environment must be 'test' or 'production', got {self.environment!r}"
            )
        return url

    @property
    def full_username(self) -> str:
        """Username with DO prefix: ``DO.{RNC}.{user}``."""
        return f"DO.{self.taxid}.{self.username}"