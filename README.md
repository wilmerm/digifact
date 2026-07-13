# Digifact FEL SDK — Multi-país

SDKs para la API Digifact FEL — facturación electrónica en **Guatemala** (SAT)
y **República Dominicana** (DGII).

| SDK | Paquete | Versión mínima |
|-----|---------|---------------|
| [Python](./python/) | [`digifact-sdk`](https://pypi.org/p/digifact-sdk) (PyPI) | Python 3.10+ |
| [JavaScript](./javascript/) | [`digifact-sdk`](https://www.npmjs.com/package/digifact-sdk) (npm) | Node 18+ |
| [PHP](./php/) | [`aalonzolu/digifact`](https://packagist.org/packages/aalonzolu/digifact) (Packagist) | PHP 8.1+ |
| [C# / .NET](./dotnet/) | [`Digifact.Fel`](https://www.nuget.org/packages/Digifact.Fel) (NuGet) | .NET 8+ |

---

## Índice

- [Instalación rápida](#instalación-rápida)
- [Uso básico — Guatemala](#uso-básico--guatemala)
- [Uso básico — República Dominicana](#uso-básico--república-dominicana)
- [Tipos de DTE soportados](#tipos-de-dte-soportados)
- [Parámetros del cliente](#parámetros-del-cliente)
- [Variables de entorno](#variables-de-entorno)
- [Estructura del repositorio](#estructura-del-repositorio)
- [Documentación adicional](#documentación-adicional)

---

## Instalación rápida

```bash
# Python
pip install digifact-sdk

# JavaScript
npm install digifact-sdk

# PHP
composer require aalonzolu/digifact

# C# / .NET
dotnet add package Digifact.Fel
```

---

## Uso básico — Guatemala

> `country="GT"` es el valor por defecto. Las integraciones existentes siguen
> funcionando **sin ningún cambio**.

```python
# Python
from digifact_sdk import DigifactClient

client = DigifactClient(
    taxid="12345678",
    username="FELUSER",
    password="...",
    environment="test",   # o "production"
)
result = client.invoice("CF", [
    {"description": "Servicio", "qty": 1, "price": 100},
])
print(result.auth_number)
```

```js
// JavaScript
import { DigifactClient } from 'digifact-sdk';

const client = new DigifactClient({
  taxid: '12345678', username: 'FELUSER', password: '...', environment: 'test',
});
const result = await client.invoice('CF', [
  { description: 'Servicio', qty: 1, price: 100 },
]);
console.log(result.authNumber);
```

```php
// PHP
use Digifact\Fel\DigifactClient;

$client = new DigifactClient([
  'taxid' => '12345678', 'username' => 'FELUSER',
  'password' => '...', 'environment' => 'test',
]);
$result = $client->invoice('CF', [
  ['description' => 'Servicio', 'qty' => 1, 'price' => 100],
]);
echo $result->authNumber;
```

```csharp
// C# / .NET
using Digifact.Fel;

using var client = new DigifactClient(new DigifactOptions {
  Taxid = "12345678", Username = "FELUSER",
  Password = "...", Environment = "test",
});
var result = await client.InvoiceAsync("CF", new[] {
  new LineItem { Description = "Servicio", Qty = 1, Price = 100 },
});
Console.WriteLine(result.AuthNumber);
```

---

## Uso básico — República Dominicana

> Usa `country="DO"` para emitir comprobantes fiscales electrónicos (e-CF)
> ante la DGII de República Dominicana.

```python
# Python
from digifact_sdk import DigifactClient

client = DigifactClient(
    taxid="132752155",         # RNC del emisor (9 dígitos)
    username="TESTUSERUNO",
    password="Digifact25*",
    country="DO",               # ← obligatorio para DO
    environment="test",         # "test" o "production"
)

# Factura de Crédito Fiscal Electrónica (e-CF tipo 31)
result = client.invoice(
    buyer="40221201896",                   # RNC o Cédula del comprador
    items=[
        {"description": "Consultoría", "price": 10000.00, "indicador_facturacion": "1"},
        {"description": "Servicio exento", "price": 5000.00, "indicador_facturacion": "4"},
    ],
    doc_type="31",
    secuencia="0000490945",                # NCF asignado por la DGII
    fecha_vencimiento_secuencia="2028-12-31",
)
print(f"NCF: {result.number}")       # "E310000490960"
print(f"Auth: {result.auth_number}") # UUID
```

> ⚠️ **Importante para DO:**
> - `taxid` es el **RNC** (9 dígitos, sin guiones ni ceros a la izquierda).
> - El comprobante requiere `secuencia` (NCF) emitido por la DGII y su
>   `fecha_vencimiento_secuencia`.
> - Los precios de los ítems son **netos** (sin ITBIS). El impuesto se calcula
>   automáticamente según `indicador_facturacion`.
> - No existe "CF" (Consumidor Final) como en Guatemala — el comprador siempre
>   requiere un RNC o Cédula.
> - La cancelación (`cancel()`) **aún no está disponible** para DO.

---

## Tipos de DTE soportados

### Guatemala (SAT FEL)

| Método | DTE | Descripción |
|--------|-----|-------------|
| `invoice()` | FACT | Factura de consumidor final o NIT |
| `invoice()` | FCAM | Factura cambiaria con cuotas |
| `invoice()` | NABN | Nota de abono |
| `invoice()` | FESP | Factura especial (retención) |
| `invoice()` | RDON | Recibo por donación |
| `invoice()` | RECI | Recibo de colegiatura |
| `invoice()` | FPEQ | Factura pequeño contribuyente |
| `debitNote()` | NDEB | Nota de débito |
| `creditNote()` | NCRE | Nota de crédito parcial |
| `creditNoteTotal()` | — | Nota de crédito total (anulación) |
| `cancel()` | — | Anulación de DTE |
| `fuelInvoice()` | FACT+Combustible | Factura con IVA + impuesto PETROLEO |
| `ccaInvoice()` | FACT+CCA | Cobro por cuenta ajena |
| `lookupNit()` | — | Consulta nombre/dirección de un NIT en SAT |
| `getDte()` | — | Descarga un DTE ya emitido |

### República Dominicana (DGII e-CF)

| Método | Tipo | Descripción |
|--------|:----:|-------------|
| `invoice(doc_type="31")` | **31** | Factura de Crédito Fiscal Electrónica |
| `invoice(doc_type="32")` | **32** | Factura de Consumo Electrónica |
| `debitNote(doc_type="33")` | **33** | Nota de Débito Electrónica |
| `creditNote(doc_type="34")` | **34** | Nota de Crédito Electrónica |
| `getDocument(fmt="XML")` | — | Descarga un e-CF (XML/HTML/PDF) |

> Los tipos 41 (Compras), 43 (Gastos Menores), 45 (Regímenes Especiales)
> se planean para una versión futura.

---

## Parámetros del cliente

### Comunes a todos los países

| Parámetro | Requerido | Descripción |
|-----------|:---------:|-------------|
| `taxid` / `Taxid` | ✔ | GT: NIT. DO: RNC (9 dígitos). |
| `username` / `Username` | ✔ | Usuario Digifact (sin prefijo `GT.` ni `DO.`). |
| `password` / `Password` | ✔\* | Contraseña. \*O bien `token`. |
| `token` / `Token` | ✔\* | Bearer token preobtenido. \*O bien `password`. |
| `country` / `Country` | | `"GT"` (default) o `"DO"`. |
| `environment` / `Environment` | | `"test"` (default) o `"production"`. |
| `seller_name` / `SellerName` | | Nombre del emisor. Se auto-consulta si se omite. |
| `seller_address` / `SellerAddress` | | Dirección del emisor. Se auto-consulta si se omite. |
| `timeout` / `Timeout` | | Timeout HTTP. Default 120s (JS: 120000 ms). |

### Específicos de Guatemala (se ignoran si `country="DO"`)

| Parámetro | Default | Descripción |
|-----------|---------|-------------|
| `afiliacion_iva` / `AfiliacionIva` | `"GEN"` | `"GEN"`, `"PEQ"` o `"EXE"`. |
| `branch_code` / `BranchCode` | `"1"` | Código del establecimiento (RTU). |
| `branch_name` / `BranchName` | `"ESTABLECIMIENTO PRINCIPAL"` | Nombre comercial de la sucursal. |
| `tipo_frase` / `TipoFrase` | `None` | Override global de `TipoFrase` (legacy). |
| `escenario` / `Escenario` | `None` | Override global de `CodigoEscenario` (legacy). |
| `frases` / `Frases` | `None` | Lista `{"tipo_frase", "escenario"}`. |
| `auto_fuel_subsidy_frases` | `None` | Auto-inyección frases 9/18 y 9/19. |
| `petroleo_rates` / `PetroleoRates` | `None` | Tarifas PETROLEO (gasolineras). |
| `tipo_personeria` / `TipoPersoneria` | `"1"` | Sólo aplica a RDON. |

### Específicos de República Dominicana (se ignoran si `country="GT"`)

| Parámetro | Default | Descripción |
|-----------|---------|-------------|
| `seller_name` / `SellerName` | `""` | Razón Social del emisor. |
| `seller_address` / `SellerAddress` | `""` | Dirección del emisor. |

> Para más detalles y ejemplos por lenguaje, ver los READMEs respectivos:
> [Python](./python/README.md), [JavaScript](./javascript/README.md),
> [PHP](./php/README.md), [C# / .NET](./dotnet/README.md).

---

## Diferencias clave: Guatemala vs República Dominicana

| Característica | Guatemala (GT) | República Dominicana (DO) |
|---|---|---|
| Código de país | `"GT"` | `"DO"` |
| ID fiscal | NIT (12 dígitos con padding) | RNC (9 dígitos, sin padding) |
| Prefijo username | `GT.{NIT}.{user}` | `DO.{RNC}.{user}` |
| Moneda | `GTQ` | `DOP` |
| Precios | **IVA incluido** | **Netos** (sin ITBIS) |
| Impuesto | IVA 12% | ITBIS 18%/16%/0%/Exento |
| Impuesto por ítem | En `Items[].Taxes` | A nivel de `Totals` |
| Consumidor Final | `"CF"` | No existe |
| NCF | No aplica | `secuencia` obligatoria |
| Cancelación | Soportada | Pendiente de documentar |

---

## Variables de entorno

```bash
# Globales (todos los países)
DIGIFACT_TAXID=132752155
DIGIFACT_USERNAME=TESTUSERUNO
DIGIFACT_PASSWORD=...
DIGIFACT_COUNTRY=DO                 # "GT" (default) o "DO"
DIGIFACT_ENVIRONMENT=test           # "test" o "production"

# Específicas de Guatemala (solo si DIGIFACT_COUNTRY=GT o no definida)
# DIGIFACT_DISABLE_AUTO_FUEL_SUBSIDY_FRASES=1

# Específicas de República Dominicana (solo si DIGIFACT_COUNTRY=DO)
# (ninguna adicional por ahora — RNC, usuario y contraseña se pasan
#  directamente en TAXID, USERNAME y PASSWORD)
```

---

## Estructura del repositorio

```
digifact-sdk/
├── python/               SDK Python — pyproject.toml, digifact_sdk/
│   └── digifact_sdk/
│       ├── core/         Código compartido entre países
│       └── providers/
│           ├── gt/       Provider para Guatemala (SAT FEL)
│           └── do/       Provider para República Dominicana (DGII e-CF)
├── javascript/           SDK JavaScript — package.json, src/
├── php/                  SDK PHP — composer.json, src/
├── dotnet/               SDK C#/.NET — Digifact.Fel.csproj, *.cs
├── docs/                 Documentación y colección Postman
│   ├── postman/          Colección y ambiente para Postman
│   ├── documentacion_sat.md       Documentación SAT Guatemala
│   └── documentacion_dgii.md      Documentación DGII Rep. Dominicana
├── scripts/              Herramientas de validación y smoke tests
└── .github/
    └── workflows/
        ├── ci.yml        Tests en cada push/PR
        └── publish.yml   Publicación a PyPI/npm/Packagist/NuGet al hacer tag
```

---

## Documentación adicional

- [Python SDK](./python/README.md)
- [JavaScript SDK](./javascript/README.md)
- [PHP SDK](./php/README.md)
- [C# / .NET SDK](./dotnet/README.md)
- [Documentación SAT Guatemala](./docs/documentacion_sat.md)
- [Documentación DGII Rep. Dominicana](./docs/documentacion_dgii.md)
- [Especificación técnica e-CF DO](./certificar-documentos.md)
- [Colección Postman](./docs/postman/)

---

## Publicar una release

```bash
# Actualizar versiones en pyproject.toml y package.json, luego:
git tag v2.1.0
git push origin v2.1.0
```

El workflow `publish.yml` se activa automáticamente y publica los cuatro paquetes.
