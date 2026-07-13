#!/usr/bin/env python3
"""Basic usage example for the Digifact FEL SDK — República Dominicana.

Sin credenciales → muestra el JSON que se enviaría a la API (preview).
Con credenciales → emite real contra el ambiente Digifact DO.

Configuración:
    export DIGIFACT_TAXID=123456789
    export DIGIFACT_USERNAME=TESTUSERUNO
    export DIGIFACT_PASSWORD=*****
    export DIGIFACT_ENVIRONMENT=test      # opcional, default "test"

Luego:
    python examples/do_basic.py
"""
import json
import os
import sys

# Allow running from the sdk/python directory without installing
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from digifact_sdk import DigifactClient, DigifactError
from digifact_sdk.providers.do.do_builder import build_ecf

TAXID = os.environ.get("DIGIFACT_TAXID", "")
USERNAME = os.environ.get("DIGIFACT_USERNAME", "")
PASSWORD = os.environ.get("DIGIFACT_PASSWORD", "")
ENV = os.environ.get("DIGIFACT_ENVIRONMENT", "test")

# ── Datos del ejemplo ─────────────────────────────────────────────────────
BUYER_DATA = {
    "taxid": "132232798",
    "name": "UNOLET SRL",
    "email": "info@unolet.com",
    "website": "https://www.unolet.com",
    "address": "Dirección de prueba",
    "country": "DO",
}

ITEMS_DATA = [
    {
        "description": "SERVICIO DE CONSULTORÍA",
        "price": 10000.00,
        "indicador_facturacion": "1",  # ITBIS 18%
        "qty": 1,
        "type": "1",
    },
    {
        "description": "CAJA DE MADERA DE PRUEBA",
        "price": 5000.00,
        "indicador_facturacion": "4",  # Exento
        "qty": 1,
        "type": "2",
    },
]

SECUENCIA="0000490967"  # Aumente aquí para evitar rechazo de `El documento electrónico ya ha sido certificado en fecha...`

KWARGS = dict(
    doc_type="31",
    secuencia=SECUENCIA,
    fecha_vencimiento_secuencia="2028-12-31",
    indicador_monto_gravado="0",
    tipo_ingresos="01",
    tipo_pago="1",
    fecha_desde="2026-05-01",
    fecha_hasta="2027-05-01",
    numero_factura_interna=SECUENCIA,
    url_to_send="https://www.unolet.com",
    seller_name="EMPRESA DE PRUEBA S.A.",
    seller_address="Dirección de Prueba",
)

# ── Modo preview (sin credenciales) ───────────────────────────────────────
if not (TAXID and USERNAME and PASSWORD):
    print("╔═══════════════════════════════════════════════════════════╗")
    print("║  MODO PREVIEW — Sin credenciales                        ║")
    print("║  Se muestra el JSON que se enviaría a la API de Digifact ║")
    print("╚═══════════════════════════════════════════════════════════╝")
    print()
    payload = build_ecf(
        taxid="132752155",
        buyer=BUYER_DATA,
        items=ITEMS_DATA,
        **KWARGS,
    )
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    print()
    print("Para emitir real, configurá las variables de entorno:")
    print("  export DIGIFACT_TAXID=123456789")
    print("  export DIGIFACT_USERNAME=TESTUSERUNO")
    print("  export DIGIFACT_PASSWORD=*****")
    sys.exit(0)

# ── Modo real (con credenciales) ──────────────────────────────────────────
client = DigifactClient(
    taxid=TAXID,
    username=USERNAME,
    password=PASSWORD,
    country="DO",
    environment=ENV,
)

print("=== Emitiendo e-CF tipo 31 (Crédito Fiscal) ===")
try:
    result = client.invoice(
        buyer=BUYER_DATA,
        items=ITEMS_DATA,
        **KWARGS,
    )
    print(f"  ✅ NCF          : {result.number}")
    print(f"  ✅ Auth Number  : {result.auth_number}")
    print(f"  ✅ Serie        : {result.series}")
    print(f"  ✅ Fecha Emisión: {result.issue_datetime}")
except DigifactError as exc:
    print(f"  ❌ ERROR: {exc}")
    print(f"     Código: {exc.code}")
    print(f"     Raw: {json.dumps(exc.raw, indent=2, ensure_ascii=False)}")
    sys.exit(1)

print("\n=== Descargando XML ===")
try:
    doc = client.get_document(result.auth_number, fmt="xml")
    xml_b64 = doc.get("responseData1") or ""
    print(f"  ✅ XML descargado ({len(xml_b64)} chars base64)")
except DigifactError as exc:
    print(f"  ❌ ERROR al descargar: {exc}")

print("\n=== Emitiendo e-CF tipo 32 (Consumo) ===")
try:
    result2 = client.invoice(
        buyer="40221201896",
        items=[{
            "description": "PRODUCTO DE CONSUMO",
            "price": 500.00,
            "indicador_facturacion": "1",
            "qty": 2,
        }],
        doc_type="32",
        secuencia=SECUENCIA,
        seller_name="EMPRESA DE PRUEBA S.A.",
        seller_address="Dirección de Prueba",
    )
    print(f"  ✅ NCF: {result2.number}")
except DigifactError as exc:
    print(f"  ❌ ERROR: {exc}")

print("\n=== Todos los ejemplos completados exitosamente ===")
