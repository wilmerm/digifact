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
- [Tipos de documento](#tipos-de-documento)
- [Cálculo de impuestos](#cálculo-de-impuestos)
  - [IVA Guatemala](#iva-guatemala)
  - [ITBIS República Dominicana](#itbis-república-dominicana)
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
    taxid="132752155",         # RNC del emisor (9 dígitos, sin guiones)
    username="TESTUSERUNO",
    password="Digifact25*",
    country="DO",               # ← obligatorio
    environment="test",         # "test" o "production"
)

# Factura de Crédito Fiscal Electrónica (e-CF tipo 31)
result = client.invoice(
    buyer="40221201896",       # RNC o Cédula del comprador
    items=[
        {
            "description": "Consultoría",
            "price": 10000.00,
            "indicador_facturacion": "1",  # ITBIS 18%
        },
        {
            "description": "Servicio exento",
            "price": 5000.00,
            "indicador_facturacion": "4",  # Exento
        },
    ],
    doc_type="31",
    secuencia="0000490945",               # NCF asignado por la DGII
    fecha_vencimiento_secuencia="2028-12-31",
)
print(f"NCF: {result.number}")        # "E310000490960"
print(f"Auth: {result.auth_number}")  # UUID

# Factura de Consumo (e-CF tipo 32)
result = client.invoice(
    buyer="40221201896",
    items=[{"description": "Producto", "price": 500.00, "indicador_facturacion": "1"}],
    doc_type="32",
    secuencia="0000490946",
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
> - `cancel()` **no está disponible** para DO.

---

## Parámetros del cliente

### Comunes

| Parámetro | Tipo | Por defecto | Descripción |
|-----------|------|-------------|-------------|
| `taxid` | `str` | **requerido** | GT: NIT (dígitos o con separadores). DO: RNC (9 dígitos, sin guiones). |
| `username` | `str` | **requerido** | Usuario Digifact (sin prefijo `GT.` / `DO.`). |
| `password` | `str` | `""` | Contraseña. Requerido si no se provee `token`. |
| `token` | `str` | `""` | Bearer token preobtenido. |
| `country` | `str` | `"GT"` | `"GT"` o `"DO"`. |
| `environment` | `str` | `"test"` | `"test"` o `"production"`. |
| `seller_name` | `str` | `""` | Nombre del emisor. Auto-consulta si se omite. |
| `seller_address` | `str` | `""` | Dirección del emisor. Auto-consulta si se omite. |
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

### Específicos de República Dominicana (se ignoran si `country="GT"`)

| Parámetro | Tipo | Por defecto | Descripción |
|-----------|------|-------------|-------------|
| `seller_name` | `str` | `""` | Razón Social del emisor. |
| `seller_address` | `str` | `""` | Dirección del emisor. |

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
    "description": str,                    # requerido
    "price": float | Decimal,              # requerido — NETO (sin ITBIS)
    "indicador_facturacion": str,           # "1"=ITBIS 18%, "2"=16%, "3"=0%, "4"=Exento
    "qty": float | Decimal,                # opcional, por defecto 1
    "type": str,                            # "1" (default) | otros códigos DGII
    "unit_of_measure": str,                 # "UNI" (default), "kg", "litro", etc.
    "discount": float | None,              # descuento de línea
    "ean": str,                             # código EAN (opcional)
    "plu": str,                             # código PLU (opcional)
    "charge": float | None,                # cargo adicional (opcional)
    "descripcion_item": str,               # descripción extendida (opcional)
}
```

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

| Indicador | Tasa | Código |
|:---------:|:----:|:------:|
| `"1"` | 18% | `ITBIS1` |
| `"2"` | 16% | `ITBIS2` |
| `"3"` | 0% | `ITBIS3` |
| `"4"` | Exento | — |

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
    {"tipo_frase": "9", "escenario": "18"},
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
| `DIGIFACT_DISABLE_AUTO_FUEL_SUBSIDY_FRASES` | `"1"` para deshabilitar frases de subsidio |

---

## Referencia de métodos

Todos los métodos de emisión devuelven `DteResult` con los campos:
`auth_number`, `series`, `number`, `issue_datetime`, `raw`.

### Multi-país

| Método | GT | DO | Descripción |
|--------|:--:|:--:|-------------|
| `invoice()` | ✔ | ✔ | Emitir factura / e-CF |
| `credit_note()` | ✔ | ✔ | Nota de crédito |
| `debit_note()` | ✔ | ✔ | Nota de débito |
| `get_document()` | ✔ | ✔ | Descargar documento (XML/HTML/PDF) |
| `cancel()` | ✔ | ❌ | Anular DTE (no disponible en DO) |

### Solo Guatemala

| Método | Descripción |
|--------|-------------|
| `cca_invoice()` | FACT con complemento CCA |
| `fuel_invoice()` | FACT con combustible (IVA + PETROLEO) |
| `credit_note_total()` | Nota de crédito total vía `/cert/ncredtotal` |
| `lookup_nit()` | Consultar NIT en SAT |
| `get_dte_info()` | Metadatos del DTE |
| `get_dte()` | Recuperar DTE (alias) |