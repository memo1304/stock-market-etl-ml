# intraday / gold

36 archivos CSV, uno por emisora. Se generan con `python productos/precios_fx/capas.py`.

| Columna | Tipo | Descripción |
|---|---|---|
| `ticker` | texto | Emisora |
| `fecha_hora` | fecha y hora | Marca de la barra |
| `fecha` | fecha | Día de la barra |
| `hora` | entero | Hora de la marca (7 a 14) |
| `minuto` | entero | Minuto de la marca (0, 5, ..., 55) |
| `precio` | decimal | Último precio negociado en esa marca |
| `ret_5m` | decimal | Rendimiento contra la barra anterior del MISMO día, en porcentaje. Vacío en la primera barra de cada día |
| `target_next_5m` | decimal | Rendimiento en porcentaje de la siguiente barra del mismo día. Vacío en la última barra. Etiqueta para ML |

Muestra: WALMEX

| ticker | fecha_hora | fecha | hora | minuto | precio | ret_5m | target_next_5m |
|---|---|---|---|---|---|---|---|
| WALMEX | 2026-06-26 13:40:00 | 2026-06-26 | 13 | 40 | 50.73 | 0 | 0.157698 |
| WALMEX | 2026-06-26 13:45:00 | 2026-06-26 | 13 | 45 | 50.81 | 0.157698 | -0.0393623 |
| WALMEX | 2026-06-26 13:50:00 | 2026-06-26 | 13 | 50 | 50.79 | -0.0393623 | 0 |
| WALMEX | 2026-06-26 13:55:00 | 2026-06-26 | 13 | 55 | 50.79 | 0 | 0.137822 |
| WALMEX | 2026-06-26 14:00:00 | 2026-06-26 | 14 | 0 | 50.86 | 0.137822 |  |

## Subcarpeta `diario/`: resumen por día

36 archivos CSV más, un día por fila.

| Columna | Tipo | Descripción |
|---|---|---|
| `ticker` | texto | Emisora |
| `fecha` | fecha | Día de la sesión |
| `n_barras` | entero | Barras de 5 minutos ese día (79 = día completo) |
| `precio_primero` | decimal | Precio de la primera barra |
| `precio_ultimo` | decimal | Precio de la última barra |
| `precio_max` | decimal | Precio máximo entre las barras (puede quedarse corto contra el High diario) |
| `precio_min` | decimal | Precio mínimo entre las barras |
| `ret_intradia` | decimal | Rendimiento de la primera a la última barra, en porcentaje |
| `volatilidad_5m` | decimal | Desviación estándar de ret_5m del día, en porcentaje |
| `dia_completo` | 0/1 | 1 si n_barras = 79 |
| `dia_plano` | 0/1 | 1 si todo el día hubo un solo precio |

Muestra: WALMEX

| ticker | fecha | n_barras | precio_primero | precio_ultimo | precio_max | precio_min | ret_intradia | volatilidad_5m | dia_completo | dia_plano |
|---|---|---|---|---|---|---|---|---|---|---|
| WALMEX | 2026-06-22 | 79 | 50.36 | 50.46 | 51.38 | 50.36 | 0.19857 | 0.276841 | 1 | 0 |
| WALMEX | 2026-06-23 | 79 | 50.46 | 50.68 | 50.85 | 49.9 | 0.435989 | 0.155923 | 1 | 0 |
| WALMEX | 2026-06-24 | 79 | 50.68 | 51.48 | 51.75 | 50.68 | 1.57853 | 0.262582 | 1 | 0 |
| WALMEX | 2026-06-25 | 79 | 51.11 | 51.12 | 51.51 | 50.82 | 0.0195656 | 0.170968 | 1 | 0 |
| WALMEX | 2026-06-26 | 79 | 50.92 | 50.86 | 51.13 | 50.56 | -0.117832 | 0.0933271 | 1 | 0 |
