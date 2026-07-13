# Digifact FEL SDK — Multi-país (Python)

SDK en Python para la API Digifact FEL — facturación electrónica en
**Guatemala** (SAT) y **República Dominicana** (DGII).

[![PyPI](https://img.shields.io/pypi/v/digifact-sdk)](https://pypi.org/p/digifact-sdk)
[![Python](https://img.shields.io/pypi/pyversions/digifact-sdk)](https://pypi.org/p/digifact-sdk)

---

## Índice

- [Instalación](#instalación)
- [Inicio rápido — Guatemala](#inicio-rápido--guatemala)
- [Inicio rápido — República Dominicana](#inicio-rápido--república-dominicana)
- [Parámetros del cliente](#parámetros-del-cliente)
- [Campos del ítem](#campos-del-ítem)
  - [Guatemala](#guatemala)
  - [República Dominicana](#república-dominicana-1)
- [Parámetros específicos de `invoice()` para DO](#parámetros-específicos-de-invoice-para-do)
- [Tipos de documento](#tipos-de-documento)
- [Cálculo de impuestos](#cálculo-de-impuestos)
  - [IVA Guatemala](#iva-guatemala)
  - [ITBIS República Dominicana](#itbis-república-dominicana)
- [Estructura del payload DO](#estructura-del-payload-do)
- [Facturas de combustible (solo GT)](#facturas-de-combustible-solo-gt)
- [Configuración de frases (solo GT)](#configuración-de-frases-solo-gt)
- [Establecimiento / sucursal (solo GT)](#establecimiento--sucursal-solo-gt)
- [Manejo de errores](#manejo-de-errores)
- [Ejecutar las pruebas](#ejecutar-las-pruebas)
- [Variables de entorno](#variables-de-entorno)
- [Referencia de métodos](#referencia-de-métodos)

---

## Instalación

```bash
pip install digifact-sdk
```

O desde el código fuente:

```bash
pip install -e python/
```

---

## Inicio rápido — Guatemala

> `country="GT"` es el valor por defecto. Las integraciones existentes
> **no requieren cambios**.

```python
from digifact_sdk import DigifactClient

client = DigifactClient(
    taxid="12345678",
    username="FELUSER",
    password="secret",
    environment="test",  # o "production"
)

# FACT CF — consumidor final, el IVA se calcula automáticamente
result = client.invoice(
    buyer="CF",
    items=[{"description": "Consultoría", "qty": 1, "price": 100.00}]
)
print(result.auth_number)

# FACT a NIT — el nombre del receptor se consulta automáticamente en SAT
result = client.invoice(
    buyer="12345678",
    items=[
        {"description": "Laptop", "qty": 1, "price": 5000.00, "type": "Bien"},
        {"description": "Soporte anual", "qty": 1, "price": 500.00},
    ]
)

# FCAM (Factura Cambiaria)
result = client.invoice(
    buyer="12345678",
    items=[{"description": "Servicio", "qty": 1, "price": 500.00}],
    doc_type="FCAM",
    payment_terms=[{"date": "2026-04-18", "amount": 500.00}]
)

# Nota de crédito (NCRE)
result = client.credit_note(
    buyer="12345678",
    items=[{"description": "Devolución", "qty": 1, "price": 100.00}],
    origin={
        "auth_number": "XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX",
        "date": "2026-03-18",
        "series": "XXXXXXXX",
        "number": "123456",
    },
    reason="Producto defectuoso"
)

# Consulta de NIT
info = client.lookup_nit("12345678")
print(info["name"])
```

---

## Inicio rápido — República Dominicana

> Usa `country="DO"` para emitir comprobantes fiscales electrónicos (e-CF)
> ante la DGII.

```python
from digifact_sdk import DigifactClient

client = DigifactClient(
    taxid="123456789",         # RNC del emisor (9 dígitos, sin guiones)
    username="TESTUSERUNO",
    password="*****",
    country="DO",               # ← obligatorio
    environment="test",         # "test" o "production"
)

# Factura de Crédito Fiscal Electrónica (e-CF tipo 31)
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
            "description": "Servicio de consultoría",
            "price": 10000.00,
            "indicador_facturacion": "1",  # ITBIS 18%
        },
        {
            "description": "Caja de madera (exento)",
            "price": 5000.00,
            "indicador_facturacion": "4",  # Exento
        },
    ],
    doc_type="31",
    secuencia="0000490963",               # NCF asignado por la DGII
    fecha_vencimiento_secuencia="2028-12-31",
    url_to_send="https://www.unolet.com",  # opcional
)
print(f"NCF: {result.number}")        # "E310000490960"
print(f"Auth: {result.auth_number}")  # UUID

# Factura de Consumo (e-CF tipo 32)
result = client.invoice(
    buyer="40221201896",  # RNC o Cédula
    items=[{"description": "Producto", "price": 500.00, "indicador_facturacion": "1"}],
    doc_type="32",
    secuencia="0000490964",
    fecha_vencimiento_secuencia="2028-12-31",
)

# Nota de Crédito (e-CF tipo 34)
result = client.credit_note(
    buyer="40221201896",
    items=[{"description": "Devolución", "price": 1000.00, "indicador_facturacion": "1"}],
    origin={
        "auth_number": "XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX",
        "date": "2026-06-01",
        "series": "E310",
        "number": "0000490945",
    },
    reason="Devolución total",
    secuencia="0000490947",
    fecha_vencimiento_secuencia="2028-12-31",
)

# Descargar XML
doc = client.get_document(result.auth_number, fmt="XML")
```

> ⚠️ **Importante:**
> - `taxid` es el **RNC** (9 dígitos, sin guiones).
> - Siempre se requiere `secuencia` (NCF) y `fecha_vencimiento_secuencia`.
> - Los precios son **netos** (sin ITBIS). El impuesto se calcula según
>   `indicador_facturacion`.
> - No existe `"CF"` (Consumidor Final). El comprador siempre necesita
>   RNC o Cédula.
> - `Payments` **no se incluye** en el payload por defecto.
> - `cancel()` **no está disponible** para DO.

---

## Parámetros del cliente

### Comunes

| Parámetro | Tipo | Por defecto | Descripción |
|-----------|------|-------------|-------------|
| `taxid` | `str` | **requerido** | GT: NIT. DO: RNC (9 dígitos, sin guiones). |
| `username` | `str` | **requerido** | Usuario Digifact (sin prefijo `GT.` / `DO.`). |
| `password` | `str` | `""` | Contraseña. Requerido si no se provee `token`. |
| `token` | `str` | `""` | Bearer token preobtenido. |
| `country` | `str` | `"GT"` | `"GT"` o `"DO"`. |
| `environment` | `str` | `"test"` | `"test"` o `"production"`. |
| `seller_name` | `str` | `""` | Nombre/Razón Social del emisor. Se auto-consulta si se omite. |
| `seller_address` | `str` | `""` | Dirección del emisor. Se auto-consulta si se omite (GT). |
| `timeout` | `int` | `120` | Timeout HTTP en segundos. |

### Específicos de Guatemala (se ignoran si `country="DO"`)

| Parámetro | Tipo | Por defecto | Descripción |
|-----------|------|-------------|-------------|
| `branch_code` | `str` | `"1"` | Código del establecimiento (RTU). |
| `branch_name` | `str` | `"ESTABLECIMIENTO PRINCIPAL"` | Nombre comercial de la sucursal. |
| `afiliacion_iva` | `str` | `"GEN"` | `"GEN"`, `"PEQ"` o `"EXE"`. |
| `tipo_frase` | `str \| None` | `None` | Override global de `TipoFrase`. |
| `escenario` | `str \| None` | `None` | Override global de `CodigoEscenario`. |
| `frases` | `list[dict] \| None` | `None` | Lista `{"tipo_frase", "escenario"}`. |
| `auto_fuel_subsidy_frases` | `bool \| None` | `None` | Auto-inyección frases 9/18 y 9/19. |
| `petroleo_rates` | `dict[str, float] \| None` | `None` | Tarifas PETROLEO (gasolineras). |
| `tipo_personeria` | `str` | `"1"` | Sólo aplica a RDON. |
| `session` | `requests.Session \| None` | `None` | Sesión HTTP personalizada. |

---

## Campos del ítem

### Guatemala

```python
{
    "description": str,          # requerido
    "price": float | Decimal,    # requerido — incluye IVA
    "qty": float | Decimal,      # opcional, por defecto 1
    "type": str,                  # "Servicio" (default) | "Bien"
    "unit_of_measure": str,       # por defecto "UNI"
    "discount": float | None,     # descuento de línea
}
```

### República Dominicana

```python
{
    "description": str,                     # requerido
    "price": float | Decimal,               # requerido — NETO (sin ITBIS)
    "indicador_facturacion": str,            # "1"=ITBIS 18%, "2"=16%, "3"=0%, "4"=Exento
    "qty": float | Decimal,                 # opcional, por defecto 1
    "type": str,                             # "1" (default) | "2" = Producto
    "unit_of_measure": str,                  # "UNI" (default), "kg", "litro", etc.
    "discount": float | None,               # descuento de línea
    "ean": str,                              # código EAN (opcional)
    "plu": str,                              # código PLU (opcional)
    "charge": float | None,                 # cargo adicional (opcional)
    "descripcion_item": str,                # descripción extendida (opcional)
}
```

> ℹ️ Los valores en el payload se envían como **strings**: `qty="1"`, `price="342604.97"`.

---

## Parámetros específicos de `invoice()` para DO

Estos parámetros se pasan como `**kwargs` al llamar `client.invoice(...)`:

| Parámetro | Default | Descripción |
|-----------|---------|-------------|
| `secuencia` | **requerido** | NCF asignado por la DGII (ej. `"0000490963"`). |
| `fecha_vencimiento_secuencia` | **requerido** | Fecha vencimiento NCF (ej. `"2028-12-31"`). |
| `indicador_monto_gravado` | `"0"` | `"0"` o `"1"`. |
| `tipo_ingresos` | `"01"` | Código catálogo DGII. |
| `tipo_pago` | `"1"` | `"1"` = Contado. |
| `fecha_desde` | `None` | Fecha inicio (opcional). |
| `fecha_hasta` | `None` | Fecha fin (opcional). |
| `numero_factura_interna` | `""` | Número interno (opcional). |
| `seller_additionl_info` | `None` | Lista `[{"Name": ..., "Value": ...}]`. |
| `seller_branch_name` | `"0001"` | Nombre sucursal. |
| `url_to_send` | `None` | URL en `AdditionalDocumentInfo` (opcional). |
| `payments` | `None` | Lista de pagos. **No se incluye** si no se provee. |
| `issue_dt` | `None` | `IssuedDateTime`. Default = hora actual DO sin offset. |

---

## Tipos de documento

### Guatemala

| Tipo | Descripción | IVA |
|------|-------------|:---:|
| `FACT` | Factura estándar | Sí |
| `FCAM` | Factura Cambiaria | Sí |
| `NDEB` | Nota de débito | Sí |
| `NCRE` | Nota de crédito | Sí |
| `NABN` | Nota de abono | No |
| `FESP` | Factura especial | Sí |
| `RDON` | Recibo por donación | No |
| `FPEQ` | Factura pequeño contribuyente | No |
| `RECI` | Recibo universitario | No |
| `CCA` | Cobro por cuenta ajena | Sí |

### República Dominicana

| Tipo | Descripción | ITBIS |
|:----:|-------------|:-----:|
| `31` | Factura de Crédito Fiscal Electrónica | Sí |
| `32` | Factura de Consumo Electrónica | Sí |
| `33` | Nota de Débito Electrónica | Sí |
| `34` | Nota de Crédito Electrónica | Sí |

---

## Cálculo de impuestos

### IVA Guatemala

Los precios **incluyen IVA** (es lo que paga el cliente):

```
total_linea    = qty × price
base_imponible = total_linea / 1.12
monto_iva      = total_linea − base_imponible
```

### ITBIS República Dominicana

Los precios son **netos** (sin ITBIS). El impuesto se calcula por fuera:

```
total_linea    = qty × price                 ← sin ITBIS
base_imponible = total_linea                  ← = total_linea (para ítems gravados)
monto_itbis    = base_imponible × tasa / 100
```

| Indicador | Tasa | Código en `TotalTaxes` |
|:---------:|:----:|:----------------------:|
| `"1"` | 18% | `ITBIS1` |
| `"2"` | 16% | `ITBIS2` |
| `"3"` | 0% | `ITBIS3` |
| `"4"` | Exento | `EXENTO` (Amount = line_total) |

> ℹ️ Para ítems exentos (`"4"`), se incluye un `TotalTax` con `Code: "EXENTO"`
> donde `Amount = line_total` y `TaxableAmount = "0"`. Esto coincide con el
> formato validado por la API de Digifact DO.

---

## Estructura del payload DO

El JSON NUC que se envía a `/v2/transform/nuc_json` tiene esta estructura:

```json
{
  "Version": "1.0",
  "CountryCode": "DO",
  "Header": {
    "DocType": "31",
    "IssuedDateTime": "2026-05-06T00:00:00",
    "AdditionalIssueDocInfo": [
      {"Name": "Secuencia", "Value": "0000490963"},
      {"Name": "FechaVencimientoSecuencia", "Value": "2028-12-31"},
      {"Name": "IndicadorMontoGravado", "Value": "0"},
      {"Name": "TipoIngresos", "Value": "01"},
      {"Name": "TipoPago", "Value": "1"},
      {"Name": "FechaDesde", "Value": "2026-05-01"},
      {"Name": "FechaHasta", "Value": "2027-05-01"}
    ]
  },
  "Seller": {
    "TaxID": "132752155",
    "Name": "EMPRESA DE PRUEBA S.A.",
    "AdditionlInfo": [{"Name": "NumeroFacturaInterna", "Value": "0000490963"}],
    "BranchInfo": {
      "Name": "0001",
      "AddressInfo": {"Address": "...", "District": "", "State": "", "Country": ""}
    }
  },
  "Buyer": {
    "TaxID": "132232798", "TaxIDType": null,
    "Name": "UNOLET SRL",
    "EmailList": {"Email": ["info@unolet.com"]},
    "Website": "https://www.unolet.com",
    "AddressInfo": {"Address": "...", "District": "", "State": "", "Country": "DO"}
  },
  "Items": [{
    "Type": "2", "Description": "CAJA DE MADERA",
    "Qty": "1", "Price": "342604.97",
    "Discounts": null, "Taxes": null, "Charges": null,
    "Totals": {"TotalItem": "342604.97"},
    "AdditionalInfo": [{"Name": "IndicadorFacturacion", "Value": "4"}]
  }],
  "Totals": {
    "TotalTaxableAmount": "0.00",
    "TotalTaxes": {
      "TotalTax": [{
        "Code": "EXENTO",
        "TaxableAmount": "0", "Rate": "0", "Amount": "342604.97"
      }]
    },
    "GrandTotal": {"InvoiceTotal": "342604.97"},
    "AdditionalInfo": [{"Name": "", "Value": ""}]
  },
  "AdditionalDocumentInfo": {
    "AdditionalInfo": [{
      "AditionalInfo": [{"Name": "UrlToSend", "Value": "https://www.unolet.com"}],
      "AditionalData": {
        "Data": [{"Name": "INFORMACION_REFERENCIA", "Id": 0, "Info": [{"Name": "", "Value": ""}]}]
      }
    }]
  }
}
```

> ⚠️ Nota sobre la ortografía: la API de Digifact DO usa `AdditionlInfo` y
> `AditionalInfo` (sin la segunda 'd') — son intencionales, no errores.

---

## Facturas de combustible (solo GT)

Las facturas de combustible emiten IVA **y** un impuesto PETROLEO según la
especificación de SAT.

### Opción A — tarifas fijadas al inicializar el cliente

```python
client = DigifactClient(
    taxid="12345678",
    username="FELUSER",
    password="secret",
    petroleo_rates={"1": 4.70, "2": 4.60, "4": 1.30},
)
result = client.fuel_invoice(
    buyer="CF",
    items=[
        {"description": "GASOLINA SUPER", "qty": 30, "price": 35.00,
         "petroleo_code": "1", "type": "Bien"},
        {"description": "FILTRO DE ACEITE", "qty": 1, "price": 45.00, "type": "Bien"},
    ],
)
```

### Opción B — monto explícito por ítem

```python
result = client.fuel_invoice(
    buyer="CF",
    items=[
        {"description": "GASOLINA SUPER", "qty": 1, "price": 35.00,
         "petroleo_amount": 4.70, "petroleo_code": "1", "type": "Bien"},
    ],
)
```

### Subsidio combustible — frases automáticas

Durante el **periodo de subsidio** (2026-04-27 a 2026-07-27), SAT exige
incluir frases `TipoFrase=9, Escenario=18` y `TipoFrase=9, Escenario=19`.
**El SDK las agrega automáticamente.**

```python
# Deshabilitar por llamada
result = client.fuel_invoice("CF", items, auto_fuel_subsidy_frases=False)

# Deshabilitar globalmente
client = DigifactClient(..., auto_fuel_subsidy_frases=False)

# Deshabilitar vía ENV VAR (sin deploy)
# DIGIFACT_DISABLE_AUTO_FUEL_SUBSIDY_FRASES=1
```

---

## Configuración de frases (solo GT)

Ver la tabla de valores por defecto en el [README principal](../README.md#parámetros-del-cliente).

```python
# API legacy: tipo_frase / escenario
client.invoice("CF", items, tipo_frase="1", escenario="1")

# Nueva API: frases múltiples
client.fuel_invoice("CF", items, frases=[
    {"tipo_frase": "1", "escenario": "1"},
])
```

> `frases` y `tipo_frase`/`escenario` son **mutuamente exclusivos**.

---

## Establecimiento / sucursal (solo GT)

```python
client = DigifactClient(
    taxid="12345678",
    username="FELUSER",
    password="secret",
    branch_code="2",
    branch_name="SUCURSAL ZONA 10",
)
```

---

## Manejo de errores

```python
from digifact_sdk import (
    DigifactError,           # base
    DigifactAuthError,       # fallo de autenticación
    DigifactApiError,        # error HTTP / de API
    DigifactValidationError, # rechazo de SAT/DGII
    DigifactNitNotFoundError, # NIT/RNC no encontrado
)

try:
    result = client.invoice("CF", [...])
except DigifactValidationError as exc:
    print(f"Rechazado: {exc}")
    print(f"Código: {exc.code}")
    print(f"Respuesta: {exc.raw}")
except DigifactError as exc:
    print(f"Error del SDK: {exc}")
```

---

## Ejecutar las pruebas

```bash
# Pruebas unitarias (no requieren credenciales)
python -m pytest tests/ -v

# Pruebas de integración (requieren credenciales reales)
export DIGIFACT_TAXID=132752155
export DIGIFACT_USERNAME=TESTUSERUNO
export DIGIFACT_PASSWORD=tu_contraseña
export DIGIFACT_COUNTRY=DO
python -m pytest tests/ -v
```

---

## Variables de entorno

| Variable | Descripción |
|----------|-------------|
| `DIGIFACT_TAXID` | NIT (GT) o RNC (DO) del emisor |
| `DIGIFACT_USERNAME` | Usuario Digifact |
| `DIGIFACT_PASSWORD` | Contraseña |
| `DIGIFACT_COUNTRY` | `"GT"` (default) o `"DO"` |
| `DIGIFACT_ENVIRONMENT` | `"test"` (default) o `"production"` |
| `DIGIFACT_DISABLE_AUTO_FUEL_SUBSIDY_FRASES` | `"1"` para deshabilitar frases de subsidio (GT) |

---

## Referencia de métodos

Todos los métodos de emisión devuelven `DteResult` con los campos:
`auth_number`, `series`, `number`, `issue_datetime`, `raw`.

### Multi-país

| Método | GT | DO | Descripción |
|--------|:--:|:--:|-------------|
| `invoice(buyer, items, **kwargs)` | ✔ | ✔ | Emitir factura / e-CF |
| `credit_note(buyer, items, origin, reason, **kwargs)` | ✔ | ✔ | Nota de crédito |
| `debit_note(buyer, items, origin, reason, **kwargs)` | ✔ | ✔ | Nota de débito |
| `get_document(auth_number, fmt="XML")` | ✔ | ✔ | Descargar documento (XML/HTML/PDF) |
| `cancel(...)` | ✔ | ❌ | Anular DTE (no disponible en DO) |

### Solo Guatemala

| Método | Descripción |
|--------|-------------|
| `cca_invoice()` | FACT con complemento CCA |
| `fuel_invoice()` | FACT con combustible (IVA + PETROLEO) |
| `credit_note_total()` | Nota de crédito total vía `/cert/ncredtotal` |
| `lookup_nit()` | Consultar NIT en SAT |
| `get_dte_info()` | Metadatos del DTE |
| `get_dte()` | Recuperar DTE (alias) |