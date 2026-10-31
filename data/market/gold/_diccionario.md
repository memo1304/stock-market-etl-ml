# market / gold

94 archivos CSV, uno por símbolo. Se generan con `python productos/precios_fx/capas.py`.

| Columna | Tipo | Descripción |
|---|---|---|
| `ticker` | texto | Símbolo de Yahoo Finance |
| `fecha` | fecha | Día de la sesión, YYYY-MM-DD |
| `open` | decimal | Precio de apertura, en la moneda del símbolo |
| `high` | decimal | Precio máximo del día |
| `low` | decimal | Precio mínimo del día |
| `close` | decimal | Precio de cierre |
| `volume` | entero | Títulos negociados |
| `moneda` | texto | MXN o USD |
| `usdmxn_close` | decimal | Pesos por dólar al cierre de ese día (MXN=X). Si ese día no hubo dato, el último de hasta 5 días antes |
| `close_usd` | decimal | Cierre en dólares: close / usdmxn_close si moneda = MXN; close si moneda = USD. Vacío para MXN=X |
| `ret_1d` | decimal | Rendimiento del día contra el cierre anterior, en porcentaje (1.2 = +1.2 %). Vacío en la primera fila |
| `target_next_day` | decimal | Rendimiento en porcentaje de la siguiente sesión (el ret_1d de mañana). Vacío en la última fila. Es la etiqueta para ML: nunca usarla como variable de entrada |
| `es_valido` | 0/1 | 1 si la fila no tiene precio <= 0, ni OHLC incoherente, ni volumen 0 (MXN=X queda exento del volumen) |

Muestra: WALMEX.MX

| ticker | fecha | open | high | low | close | volume | moneda | usdmxn_close | close_usd | ret_1d | target_next_day | es_valido |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| WALMEX.MX | 2026-10-23 | 50.33 | 50.94 | 50.01 | 50.73 | 8903167 | MXN | 18.7208 | 2.70982 | 0.83482 | -0.8082 | 1 |
| WALMEX.MX | 2026-10-26 | 50.51 | 51.33 | 50.13 | 50.32 | 9184793 | MXN | 18.719 | 2.68818 | -0.8082 | -2.96105 | 1 |
| WALMEX.MX | 2026-10-27 | 50.03 | 50.54 | 48.72 | 48.83 | 14506008 | MXN | 18.5502 | 2.63232 | -2.96105 | -0.839655 | 1 |
| WALMEX.MX | 2026-10-28 | 48.8 | 48.85 | 47.2 | 48.42 | 14004344 | MXN | 18.687 | 2.5911 | -0.839655 | 0.784802 | 1 |
| WALMEX.MX | 2026-10-29 | 48.15 | 49.18 | 48 | 48.8 | 14084306 | MXN | 18.6318 | 2.61918 | 0.784802 |  | 1 |
