#!/usr/bin/env python3
"""Basic usage example for the Digifact FEL SDK — República Dominicana.

Set environment variables before running:
    export DIGIFACT_TAXID=132752155
    export DIGIFACT_USERNAME=TESTUSERUNO
    export DIGIFACT_PASSWORD=Digifact25*
    export DIGIFACT_COUNTRY=DO

Then:
    python examples/do_basic.py
"""
import json
import os
import sys

# Allow running from the sdk/python directory without installing
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from digifact_sdk import DigifactClient, DigifactError

TAXID = os.environ.get("DIGIFACT_TAXID", "")
USERNAME = os.environ.get("DIGIFACT_USERNAME", "")
PASSWORD = os.environ.get("DIGIFACT_PASSWORD", "")
ENV = os.environ.get("DIGIFACT_ENVIRONMENT", "test")

if not (TAXID and USERNAME and PASSWORD):
    print("Skipping example: set DIGIFACT_TAXID, DIGIFACT_USERNAME, DIGIFACT_PASSWORD")
    sys.exit(0)

client = DigifactClient(
    taxid=TAXID,
    username=USERNAME,
    password=PASSWORD,
    country="DO",
    environment=ENV,
)

# ── Factura de Crédito Fiscal (e-CF tipo 31) ──────────────────────────────
print("=== Emitiendo e-CF tipo 31 (Crédito Fiscal) ===")
try:
    result = client.invoice(
        buyer={
            "taxid": "132232798",
            "name": "UNOLET SRL",
            "email": "info@unolet.com",
            "website": "https://www.unolet.com",
            "address": "Dirección de prueba",
            "country": "DO",
        },
        items=[
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
        ],
        doc_type="31",
        secuencia="0000490963",                 # NCF asignado por DGII
        fecha_vencimiento_secuencia="2028-12-31",
        indicador_monto_gravado="0",
        tipo_ingresos="01",
        tipo_pago="1",
        fecha_desde="2026-05-01",
        fecha_hasta="2027-05-01",
        numero_factura_interna="0000490963",
        url_to_send="https://www.unolet.com",
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

# ── Descargar XML ─────────────────────────────────────────────────────────
print("\n=== Descargando XML ===")
try:
    doc = client.get_document(result.auth_number, fmt="XML")
    xml_b64 = doc.get("responseData1") or ""
    print(f"  ✅ XML descargado ({len(xml_b64)} chars base64)")
except DigifactError as exc:
    print(f"  ❌ ERROR al descargar: {exc}")

# ── Factura de Consumo (e-CF tipo 32) ─────────────────────────────────────
print("\n=== Emitiendo e-CF tipo 32 (Consumo) ===")
try:
    result2 = client.invoice(
        buyer="40221201896",  # RNC o Cédula del comprador
        items=[
            {
                "description": "PRODUCTO DE CONSUMO",
                "price": 500.00,
                "indicador_facturacion": "1",  # ITBIS 18%
                "qty": 2,
            },
        ],
        doc_type="32",
        secuencia="0000490964",
        fecha_vencimiento_secuencia="2028-12-31",
    )
    print(f"  ✅ NCF: {result2.number}")
except DigifactError as exc:
    print(f"  ❌ ERROR: {exc}")

print("\n=== Todos los ejemplos completados exitosamente ===")