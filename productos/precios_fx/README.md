# Producto Precios & FX (equipo verde)

OHLCV diario, tipo de cambio USD/MXN e intradía de 5 minutos, en capas bronze → silver → gold con PySpark, más la herramienta `consultar_mercado_sql` para que el agente consulte el gold.

## Cómo correrlo

Requisitos: Java 17 o 21 (`sudo dnf install java-21-openjdk-headless` en Fedora) y `uv pip install pyspark pyarrow pandas sqlglot pyyaml`.

```bash
python productos/precios_fx/actualizar_fuente.py   # opcional: baja de Yahoo los días nuevos a data/market
python -m src.etl.bronze.verde.etl_bronze          # parquet → bronze
python -m src.etl.silver.verde.etl_silver          # bronze → silver
python -m src.etl.gold.verde.etl_gold              # silver → gold y data/market/gold/mercado.db
python productos/precios_fx/calidad_datos.py       # gráficas y CSV de calidad en salida/
python productos/precios_fx/demo_herramienta_sql.py   # simula lo que haría Claude, sin gastar tokens
```

Cada capa acepta `--solo market` o `--solo intraday`. Las tres juntas tardan unos 3 minutos.

## Capas

El código está en `src/etl/{bronze,silver,gold}/verde/`; lo común (rutas, esquemas, sesión de Spark) en `src/etl/shared/precios_fx.py`. La fuente (`data/market/*.parquet`, `data/intraday/*.parquet`) no se toca. Cada capa lee la anterior y escribe un CSV por símbolo para que se puedan abrir y leer. El `_diccionario.md` de cada carpeta lista columnas, tipos, descripción y una muestra de datos.

| Capa | market (diario) | intraday (5 min) |
|---|---|---|
| bronze | `ticker, Date, Open, High, Low, Close, Volume` | `ticker, datetime, price` |
| silver | minúsculas, `Date → fecha`, `moneda` y banderas `flag_*` de calidad | `fecha_hora, fecha, precio` y banderas `flag_festivo`, `flag_falla_fuente`, `flag_dia_plano`, `flag_dia_incompleto` |
| gold | `+ usdmxn_close, close_usd, ret_1d, target_next_day, es_valido` | por barra: `hora, minuto, ret_5m, target_next_5m`; y en `gold/diario/` un resumen por día |

`ret_1d`, `target_next_day`, `ret_5m` y `target_next_5m` están en **porcentaje** (1.2 = +1.2 %). Los targets son el rendimiento del periodo siguiente y no se calculan entre días distintos: la primera barra de cada día no tiene `ret_5m` y la última no tiene `target_next_5m`.

Silver no borra ni corrige filas: las marca. Gold diario calcula sobre todas y deja `es_valido` para filtrar. Gold intradía deja fuera las barras de relleno: días festivos y días en que la fuente mandó un solo precio para casi todas las emisoras (2025-02-12, 2025-04-16, 2026-06-29 y 2026-06-30).

`data/market/gold/mercado.db` (SQLite) tiene tres tablas: `precios_historicos` (gold diario de todos los símbolos), `tipo_cambio` e `intradia_diario`. Las barras de 5 minutos no entran a la base (1.1 millones de filas que el agente no necesita); ML las lee de `data/intraday/gold/`. La describe `semantic_layer_mercado.yaml`, en la raíz del repo.

Los CSV y la base se regeneran con el ETL y están en `.gitignore`; solo se suben los `_diccionario.md`.

## Archivos

| Archivo | Qué es |
|---|---|
| `../../src/etl/bronze/verde/etl_bronze.py` | Parquet → bronze: campos de la fuente más el ticker. |
| `../../src/etl/silver/verde/etl_silver.py` | Bronze → silver: minúsculas, tipos y banderas de calidad. |
| `../../src/etl/gold/verde/etl_gold.py` | Silver → gold y base SQLite del agente. |
| `../../src/etl/shared/precios_fx.py` | Rutas, esquemas de cada capa, sesión de Spark y escritura de CSV. |
| `actualizar_fuente.py` | Refresca `data/market/*.parquet` desde Yahoo (`src/data/store.update_all`). |
| `calidad_datos.py` | Auditoría de completitud y calidad con 8 gráficas. |
| `demo_herramienta_sql.py` | Lo que vería y haría Claude con la herramienta. |
| `../../semantic_layer_mercado.yaml` | Capa semántica que lee la herramienta. |
| `../../src/agent/tools.py` | `AgenteMercadoSQL` (`consultar_mercado_sql`). |
