# market / silver

94 archivos CSV, uno por símbolo. Se generan con `python productos/precios_fx/capas.py`.

| Columna | Tipo | Descripción |
|---|---|---|
| `ticker` | texto | Símbolo de Yahoo Finance |
| `fecha` | fecha | Día de la sesión, YYYY-MM-DD (Date se renombra porque DATE es palabra reservada en SQL) |
| `open` | decimal | Precio de apertura |
| `high` | decimal | Precio máximo del día |
| `low` | decimal | Precio mínimo del día |
| `close` | decimal | Precio de cierre |
| `volume` | entero | Títulos negociados |
| `moneda` | texto | MXN si el símbolo termina en .MX o es MXN=X; USD en otro caso |
| `flag_volumen_cero` | 0/1 | 1 si volume = 0 (normal en MXN=X; en una acción indica que no se negoció) |
| `flag_precio_no_positivo` | 0/1 | 1 si algún precio es <= 0 |
| `flag_ohlc_incoherente` | 0/1 | 1 si high < max(open, close) o low > min(open, close) |
| `flag_salto_25` | 0/1 | 1 si el cierre cambió más de 25 % contra el día anterior |
| `flag_cierre_repetido` | 0/1 | 1 si el cierre es idéntico al del día anterior |

Muestra: WALMEX.MX

| ticker | fecha | open | high | low | close | volume | moneda | flag_volumen_cero | flag_precio_no_positivo | flag_ohlc_incoherente | flag_salto_25 | flag_cierre_repetido |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| WALMEX.MX | 2026-10-23 | 50.33 | 50.94 | 50.01 | 50.73 | 8903167 | MXN | 0 | 0 | 0 | 0 | 0 |
| WALMEX.MX | 2026-10-26 | 50.51 | 51.33 | 50.13 | 50.32 | 9184793 | MXN | 0 | 0 | 0 | 0 | 0 |
| WALMEX.MX | 2026-10-27 | 50.03 | 50.54 | 48.72 | 48.83 | 14506008 | MXN | 0 | 0 | 0 | 0 | 0 |
| WALMEX.MX | 2026-10-28 | 48.8 | 48.85 | 47.2 | 48.42 | 14004344 | MXN | 0 | 0 | 0 | 0 | 0 |
| WALMEX.MX | 2026-10-29 | 48.15 | 49.18 | 48 | 48.8 | 14084306 | MXN | 0 | 0 | 0 | 0 | 0 |
