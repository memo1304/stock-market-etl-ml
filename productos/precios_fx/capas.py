"""Capas bronze → silver → gold del producto Precios & FX (equipo verde).

    python productos/precios_fx/capas.py              # market + intraday + base SQLite
    python productos/precios_fx/capas.py --solo market
    python productos/precios_fx/capas.py --solo intraday

Fuente (no se modifica):
  data/market/*.parquet    OHLCV diario de Yahoo Finance, un archivo por símbolo
  data/intraday/*.parquet  precio cada 5 minutos de DataBursátil, un archivo por emisora

Salida, en texto (CSV) para poder ver campos y datos:
  data/market/{bronze,silver,gold}/<SIMBOLO>.csv
  data/intraday/{bronze,silver,gold}/<EMISORA>.csv, más gold/diario/ (resumen por día)
  _diccionario.md en cada carpeta: columnas, tipo, descripción y una muestra
  data/market/gold/mercado.db: la base SQLite que consulta el agente

Reglas:
  bronze  los campos de la fuente con su nombre original, más el ticker.
  silver  nombres en minúsculas (Date → fecha), tipos fijos y banderas de calidad.
          No se borra ni se corrige ninguna fila: solo se marca.
  gold    lo que consumen el agente y ML. Diario: tipo de cambio, precio en dólares,
          ret_1d y target_next_day (en %) y es_valido. Intradía: ret_5m y
          target_next_5m (en %) por barra, sin barras de relleno, y un resumen por día.
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
MARKET = ROOT / "data" / "market"
INTRADAY = ROOT / "data" / "intraday"
DB_PATH = MARKET / "gold" / "mercado.db"
FX = "MXN=X"
SALTO = 0.25
MAX_DIAS_FX = 5  # si falta el tipo de cambio, se usa el último conocido hasta 5 días atrás
BARRAS_DIA = 79
CSV = {"index": False, "float_format": "%.8g"}  # 8 cifras significativas: suficiente para precios

# ── esquemas: una sola fuente de verdad para CSV, diccionario y SQLite ───────

ESQUEMA = {
    "market/bronze": [
        ("ticker", "texto", "Símbolo de Yahoo Finance: WALMEX.MX (BMV, pesos), AAPL (USA, dólares), MXN=X (tipo de cambio)"),
        ("Date", "fecha", "Día de la sesión, YYYY-MM-DD"),
        ("Open", "decimal", "Precio de apertura"),
        ("High", "decimal", "Precio máximo del día"),
        ("Low", "decimal", "Precio mínimo del día"),
        ("Close", "decimal", "Precio de cierre"),
        ("Volume", "entero", "Títulos negociados. En MXN=X siempre es 0: el tipo de cambio no se negocia en una bolsa"),
    ],
    "market/silver": [
        ("ticker", "texto", "Símbolo de Yahoo Finance"),
        ("fecha", "fecha", "Día de la sesión, YYYY-MM-DD (Date se renombra porque DATE es palabra reservada en SQL)"),
        ("open", "decimal", "Precio de apertura"),
        ("high", "decimal", "Precio máximo del día"),
        ("low", "decimal", "Precio mínimo del día"),
        ("close", "decimal", "Precio de cierre"),
        ("volume", "entero", "Títulos negociados"),
        ("moneda", "texto", "MXN si el símbolo termina en .MX o es MXN=X; USD en otro caso"),
        ("flag_volumen_cero", "0/1", "1 si volume = 0 (normal en MXN=X; en una acción indica que no se negoció)"),
        ("flag_precio_no_positivo", "0/1", "1 si algún precio es <= 0"),
        ("flag_ohlc_incoherente", "0/1", "1 si high < max(open, close) o low > min(open, close)"),
        ("flag_salto_25", "0/1", "1 si el cierre cambió más de 25 % contra el día anterior"),
        ("flag_cierre_repetido", "0/1", "1 si el cierre es idéntico al del día anterior"),
    ],
    "market/gold": [
        ("ticker", "texto", "Símbolo de Yahoo Finance"),
        ("fecha", "fecha", "Día de la sesión, YYYY-MM-DD"),
        ("open", "decimal", "Precio de apertura, en la moneda del símbolo"),
        ("high", "decimal", "Precio máximo del día"),
        ("low", "decimal", "Precio mínimo del día"),
        ("close", "decimal", "Precio de cierre"),
        ("volume", "entero", "Títulos negociados"),
        ("moneda", "texto", "MXN o USD"),
        ("usdmxn_close", "decimal", "Pesos por dólar al cierre de ese día (MXN=X). Si ese día no hubo dato, el último de hasta 5 días antes"),
        ("close_usd", "decimal", "Cierre en dólares: close / usdmxn_close si moneda = MXN; close si moneda = USD. Vacío para MXN=X"),
        ("ret_1d", "decimal", "Rendimiento del día contra el cierre anterior, en porcentaje (1.2 = +1.2 %). Vacío en la primera fila"),
        ("target_next_day", "decimal", "Rendimiento en porcentaje de la siguiente sesión (el ret_1d de mañana). Vacío en la última fila. Es la etiqueta para ML: nunca usarla como variable de entrada"),
        ("es_valido", "0/1", "1 si la fila no tiene precio <= 0, ni OHLC incoherente, ni volumen 0 (MXN=X queda exento del volumen)"),
    ],
    "intraday/bronze": [
        ("ticker", "texto", "Emisora de DataBursátil sin serie: WALMEX, AMXL, FEMSAUBD"),
        ("datetime", "fecha y hora", "Marca de la barra de 5 minutos, tal como la entrega DataBursátil (07:30 a 14:00)"),
        ("price", "decimal", "Último precio negociado en esa marca. No hay open/high/low ni volumen por barra"),
    ],
    "intraday/silver": [
        ("ticker", "texto", "Emisora"),
        ("fecha_hora", "fecha y hora", "Marca de la barra, YYYY-MM-DD HH:MM:SS"),
        ("fecha", "fecha", "Día de la barra"),
        ("precio", "decimal", "Último precio negociado en esa marca"),
        ("flag_festivo", "0/1", "1 si ese día no hubo sesión en el diario de la BMV y todo el día trae el mismo precio (barras de relleno)"),
        ("flag_falla_fuente", "0/1", "1 si ese día casi todas las emisoras traen un solo precio a la vez: la fuente no mandó datos y rellenó"),
        ("flag_dia_plano", "0/1", "1 si la emisora tuvo un solo precio todo el día (en emisoras poco líquidas puede ser real: no hubo operaciones)"),
        ("flag_dia_incompleto", "0/1", "1 si el día tiene menos de 79 barras"),
    ],
    "intraday/gold": [
        ("ticker", "texto", "Emisora"),
        ("fecha_hora", "fecha y hora", "Marca de la barra"),
        ("fecha", "fecha", "Día de la barra"),
        ("hora", "entero", "Hora de la marca (7 a 14)"),
        ("minuto", "entero", "Minuto de la marca (0, 5, ..., 55)"),
        ("precio", "decimal", "Último precio negociado en esa marca"),
        ("ret_5m", "decimal", "Rendimiento contra la barra anterior del MISMO día, en porcentaje. Vacío en la primera barra de cada día"),
        ("target_next_5m", "decimal", "Rendimiento en porcentaje de la siguiente barra del mismo día. Vacío en la última barra. Etiqueta para ML"),
    ],
    "intraday/gold_diario": [
        ("ticker", "texto", "Emisora"),
        ("fecha", "fecha", "Día de la sesión"),
        ("n_barras", "entero", "Barras de 5 minutos ese día (79 = día completo)"),
        ("precio_primero", "decimal", "Precio de la primera barra"),
        ("precio_ultimo", "decimal", "Precio de la última barra"),
        ("precio_max", "decimal", "Precio máximo entre las barras (puede quedarse corto contra el High diario)"),
        ("precio_min", "decimal", "Precio mínimo entre las barras"),
        ("ret_intradia", "decimal", "Rendimiento de la primera a la última barra, en porcentaje"),
        ("volatilidad_5m", "decimal", "Desviación estándar de ret_5m del día, en porcentaje"),
        ("dia_completo", "0/1", "1 si n_barras = 79"),
        ("dia_plano", "0/1", "1 si todo el día hubo un solo precio"),
    ],
}


def columnas(capa: str) -> list[str]:
    return [c for c, _, _ in ESQUEMA[capa]]


# ── lectura de la fuente ─────────────────────────────────────────────────────

def _simbolo(path: Path) -> str:
    return path.stem


def leer_parquet_diario(path: Path) -> pd.DataFrame:
    df = pd.read_parquet(path)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.columns.name = None
    idx = pd.to_datetime(df.index)
    if getattr(idx, "tz", None) is not None:
        idx = idx.tz_localize(None)
    df.index = idx.normalize()
    df.index.name = "Date"
    return df


# ── market ───────────────────────────────────────────────────────────────────

def market_bronze(simbolo: str, raw: pd.DataFrame) -> pd.DataFrame:
    df = raw[["Open", "High", "Low", "Close", "Volume"]].reset_index()
    df.insert(0, "ticker", simbolo)
    df["Date"] = df["Date"].dt.strftime("%Y-%m-%d")
    return df[columnas("market/bronze")]


def market_silver(bronze: pd.DataFrame) -> pd.DataFrame:
    df = bronze.rename(columns={
        "Date": "fecha", "Open": "open", "High": "high",
        "Low": "low", "Close": "close", "Volume": "volume",
    }).copy()
    df["fecha"] = pd.to_datetime(df["fecha"]).dt.strftime("%Y-%m-%d")
    for c in ("open", "high", "low", "close"):
        df[c] = pd.to_numeric(df[c], errors="coerce").astype(float)
    df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0).astype("int64")
    df = df.sort_values("fecha").drop_duplicates("fecha", keep="last").reset_index(drop=True)

    sym = df["ticker"].iloc[0] if len(df) else ""
    df["moneda"] = "MXN" if (sym.endswith(".MX") or sym == FX) else "USD"
    precios = df[["open", "high", "low", "close"]]
    df["flag_volumen_cero"] = (df["volume"] == 0).astype(int)
    df["flag_precio_no_positivo"] = (precios <= 0).any(axis=1).astype(int)
    df["flag_ohlc_incoherente"] = (
        (df["high"] < df[["open", "close"]].max(axis=1) - 1e-9)
        | (df["low"] > df[["open", "close"]].min(axis=1) + 1e-9)
    ).astype(int)
    df["flag_salto_25"] = (df["close"].pct_change().abs() > SALTO).astype(int)
    df["flag_cierre_repetido"] = (df["close"].diff() == 0).astype(int)
    return df[columnas("market/silver")]


def tipo_cambio(silver_fx: pd.DataFrame) -> pd.Series:
    fx = silver_fx[silver_fx["close"] > 0]
    return pd.Series(fx["close"].to_numpy(), index=pd.to_datetime(fx["fecha"]), name="usdmxn_close")


def market_gold(silver: pd.DataFrame, fx: pd.Series) -> pd.DataFrame:
    df = silver.copy()
    fechas = pd.to_datetime(df["fecha"])
    serie_fx = fx.sort_index()
    usd = pd.merge_asof(
        pd.DataFrame({"fecha": fechas}),
        pd.DataFrame({"fecha": serie_fx.index, "usdmxn_close": serie_fx.to_numpy()}),
        on="fecha", direction="backward", tolerance=pd.Timedelta(days=MAX_DIAS_FX),
    )
    df["usdmxn_close"] = usd["usdmxn_close"].to_numpy()

    sym = df["ticker"].iloc[0] if len(df) else ""
    if sym == FX:
        df["close_usd"] = np.nan
    elif (df["moneda"] == "MXN").all():
        df["close_usd"] = df["close"] / df["usdmxn_close"]
    else:
        df["close_usd"] = df["close"]

    prev = df["close"].shift(1)
    df["ret_1d"] = np.where(prev > 0, (df["close"] / prev - 1) * 100, np.nan)
    df["target_next_day"] = df["ret_1d"].shift(-1)

    exento_vol = sym == FX
    malo = (df["flag_precio_no_positivo"] == 1) | (df["flag_ohlc_incoherente"] == 1)
    if not exento_vol:
        malo |= df["flag_volumen_cero"] == 1
    df["es_valido"] = (~malo).astype(int)
    return df[columnas("market/gold")]


def construir_market() -> dict[str, pd.DataFrame]:
    paths = sorted(MARKET.glob("*.parquet"))
    silver: dict[str, pd.DataFrame] = {}
    for capa in ("bronze", "silver", "gold"):
        (MARKET / capa).mkdir(parents=True, exist_ok=True)

    for path in paths:
        raw = leer_parquet_diario(path)
        if raw.empty:
            print(f"  ! {path.name} vacío, se omite")
            continue
        b = market_bronze(_simbolo(path), raw)
        b.to_csv(MARKET / "bronze" / f"{_simbolo(path)}.csv", **CSV)
        s = market_silver(b)
        s.to_csv(MARKET / "silver" / f"{_simbolo(path)}.csv", **CSV)
        silver[_simbolo(path)] = s

    if FX not in silver:
        raise RuntimeError("Falta data/market/MXN=X.parquet: sin tipo de cambio no hay gold")
    fx = tipo_cambio(silver[FX])
    gold: dict[str, pd.DataFrame] = {}
    for sym, s in silver.items():
        g = market_gold(s, fx)
        g.to_csv(MARKET / "gold" / f"{sym}.csv", **CSV)
        gold[sym] = g

    muestra = "WALMEX.MX" if "WALMEX.MX" in silver else next(iter(silver))
    escribir_diccionario("market/bronze", market_bronze(muestra, leer_parquet_diario(MARKET / f"{muestra}.parquet")), len(paths))
    escribir_diccionario("market/silver", silver[muestra], len(silver))
    escribir_diccionario("market/gold", gold[muestra], len(gold))
    print(f"  market: {len(gold)} símbolos en bronze, silver y gold")
    return gold


# ── intraday ─────────────────────────────────────────────────────────────────

def intraday_bronze(ticker: str, raw: pd.DataFrame) -> pd.DataFrame:
    df = raw[["datetime", "price"]].copy()
    df["datetime"] = pd.to_datetime(df["datetime"]).dt.strftime("%Y-%m-%d %H:%M:%S")
    df.insert(0, "ticker", ticker)
    return df[columnas("intraday/bronze")]


def intraday_silver(bronze: pd.DataFrame, dias_bmv: set[str], dias_falla: set[str]) -> pd.DataFrame:
    df = bronze.rename(columns={"datetime": "fecha_hora", "price": "precio"}).copy()
    df["precio"] = pd.to_numeric(df["precio"], errors="coerce").astype(float)
    df = df.sort_values("fecha_hora").drop_duplicates("fecha_hora", keep="last").reset_index(drop=True)
    df["fecha"] = df["fecha_hora"].str[:10]
    por_dia = df.groupby("fecha")["precio"]
    plano = por_dia.transform("nunique") == 1
    df["flag_festivo"] = ((~df["fecha"].isin(dias_bmv)) & plano).astype(int)
    df["flag_falla_fuente"] = (df["fecha"].isin(dias_falla) & plano & (df["flag_festivo"] == 0)).astype(int)
    df["flag_dia_plano"] = plano.astype(int)
    df["flag_dia_incompleto"] = (por_dia.transform("size") < BARRAS_DIA).astype(int)
    return df[columnas("intraday/silver")]


def _utiles(silver: pd.DataFrame) -> pd.DataFrame:
    """Gold no usa barras de relleno: ni festivos ni días en que falló la fuente."""
    return silver[(silver["flag_festivo"] == 0) & (silver["flag_falla_fuente"] == 0)]


def intraday_gold(silver: pd.DataFrame) -> pd.DataFrame:
    df = _utiles(silver).copy()
    ts = pd.to_datetime(df["fecha_hora"])
    df["hora"] = ts.dt.hour
    df["minuto"] = ts.dt.minute
    prev = df.groupby("fecha")["precio"].shift(1)
    df["ret_5m"] = np.where(prev > 0, (df["precio"] / prev - 1) * 100, np.nan)
    df["target_next_5m"] = df.groupby("fecha")["ret_5m"].shift(-1)
    return df[columnas("intraday/gold")].reset_index(drop=True)


def intraday_gold_diario(gold: pd.DataFrame) -> pd.DataFrame:
    filas = []
    for fecha, d in gold.groupby("fecha", sort=True):
        p = d["precio"].to_numpy()
        filas.append({
            "ticker": d["ticker"].iloc[0],
            "fecha": fecha,
            "n_barras": len(p),
            "precio_primero": p[0],
            "precio_ultimo": p[-1],
            "precio_max": p.max(),
            "precio_min": p.min(),
            "ret_intradia": (p[-1] / p[0] - 1) * 100 if p[0] > 0 else np.nan,
            "volatilidad_5m": float(d["ret_5m"].std()) if len(p) > 2 else np.nan,
            "dia_completo": int(len(p) == BARRAS_DIA),
            "dia_plano": int(np.unique(p).size == 1),
        })
    return pd.DataFrame(filas, columns=columnas("intraday/gold_diario"))


def dias_bmv() -> set[str]:
    """Días con sesión según el diario: días en que operó al menos la mitad de las .MX vivas."""
    series = {}
    for path in MARKET.glob("*.MX.parquet"):
        raw = leer_parquet_diario(path)
        if not raw.empty:
            series[path.stem] = pd.Series(1, index=raw.index)
    if not series:
        return set()
    panel = pd.concat(series, axis=1, sort=True)
    vivos = pd.DataFrame(
        {k: (panel.index >= v.index.min()) & (panel.index <= v.index.max()) for k, v in series.items()},
        index=panel.index,
    ).sum(axis=1)
    ratio = panel.notna().sum(axis=1) / vivos.clip(lower=1)
    return set(panel.index[ratio >= 0.5].strftime("%Y-%m-%d"))


def dias_falla_fuente(bronzes: dict[str, pd.DataFrame], umbral: float = 0.8) -> set[str]:
    """Días en que al menos el 80 % de las emisoras traen un solo precio todo el día."""
    planos = []
    for b in bronzes.values():
        n = b.groupby(b["datetime"].str[:10])["price"].nunique()
        planos.append(n == 1)
    panel = pd.concat(planos, axis=1)
    return set(panel.index[panel.mean(axis=1) >= umbral])


def construir_intraday() -> tuple[dict[str, pd.DataFrame], dict[str, pd.DataFrame]]:
    for capa in ("bronze", "silver", "gold", "gold/diario"):
        (INTRADAY / capa).mkdir(parents=True, exist_ok=True)
    dias = dias_bmv()
    ultimo_diario = max(dias) if dias else ""
    bronzes = {p.stem: intraday_bronze(p.stem, pd.read_parquet(p)) for p in sorted(INTRADAY.glob("*.parquet"))}
    falla = dias_falla_fuente(bronzes) if bronzes else set()
    gold: dict[str, pd.DataFrame] = {}
    diario: dict[str, pd.DataFrame] = {}
    muestra = None
    for t, b in bronzes.items():
        b.to_csv(INTRADAY / "bronze" / f"{t}.csv", **CSV)
        # los días posteriores al último diario no se pueden validar: no se marcan como festivos
        validos = dias | {f for f in b["datetime"].str[:10].unique() if f > ultimo_diario}
        s = intraday_silver(b, validos, falla)
        s.to_csv(INTRADAY / "silver" / f"{t}.csv", **CSV)
        g = intraday_gold(s)
        g.to_csv(INTRADAY / "gold" / f"{t}.csv", **CSV)
        gd = intraday_gold_diario(g)
        gd.to_csv(INTRADAY / "gold" / "diario" / f"{t}.csv", **CSV)
        gold[t], diario[t] = g, gd
        if t == "WALMEX" or muestra is None:
            muestra = (b, s, g, gd)
    if muestra:
        b, s, g, gd = muestra
        escribir_diccionario("intraday/bronze", b, len(gold))
        escribir_diccionario("intraday/silver", s, len(gold))
        escribir_diccionario("intraday/gold", g, len(gold), extra=("intraday/gold_diario", gd, "diario/"))
    habiles = sorted(f for f in falla if f in dias or f > ultimo_diario)
    print(f"  intraday: {len(gold)} emisoras; días hábiles con falla de la fuente: {', '.join(habiles) or 'ninguno'}")
    return gold, diario


# ── base SQLite para el agente ───────────────────────────────────────────────

def construir_db(gold_market: dict[str, pd.DataFrame],
                 diario_intraday: dict[str, pd.DataFrame] | None = None,
                 db_path: Path = DB_PATH) -> Path:
    """Base del agente: gold diario, tipo de cambio y resumen intradía por día.

    Las barras de 5 min (gold intradía) no entran: son 1.1 millones de filas y
    el agente no las necesita para responder; ML las lee de los CSV.
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = db_path.with_suffix(".tmp")
    tmp.unlink(missing_ok=True)
    with sqlite3.connect(tmp) as conn:
        conn.executescript("""
            CREATE TABLE precios_historicos (
                ticker TEXT NOT NULL, fecha TEXT NOT NULL,
                open REAL, high REAL, low REAL, close REAL, volume INTEGER,
                moneda TEXT, usdmxn_close REAL, close_usd REAL,
                ret_1d REAL, target_next_day REAL, es_valido INTEGER,
                PRIMARY KEY (ticker, fecha)
            );
            CREATE TABLE tipo_cambio (fecha TEXT PRIMARY KEY, close REAL);
            CREATE TABLE intradia_diario (
                ticker TEXT NOT NULL, fecha TEXT NOT NULL, n_barras INTEGER,
                precio_primero REAL, precio_ultimo REAL, precio_max REAL, precio_min REAL,
                ret_intradia REAL, volatilidad_5m REAL, dia_completo INTEGER, dia_plano INTEGER,
                PRIMARY KEY (ticker, fecha)
            );
        """)
        pd.concat(gold_market.values(), ignore_index=True).to_sql(
            "precios_historicos", conn, if_exists="append", index=False)
        if FX in gold_market:
            fx = gold_market[FX][["fecha", "close"]]
            fx[fx["close"] > 0].to_sql("tipo_cambio", conn, if_exists="append", index=False)
        if diario_intraday:
            pd.concat(diario_intraday.values(), ignore_index=True).to_sql(
                "intradia_diario", conn, if_exists="append", index=False)
        conn.execute("CREATE INDEX idx_precios_fecha ON precios_historicos (fecha)")
    tmp.replace(db_path)
    print(f"  base: {db_path.relative_to(ROOT) if db_path.is_relative_to(ROOT) else db_path}")
    return db_path


# ── diccionario de datos ─────────────────────────────────────────────────────

def _fmt(v) -> str:
    if v is None or v is pd.NA or (isinstance(v, float) and np.isnan(v)):
        return ""
    if isinstance(v, float):
        return f"{v:.6g}"
    return str(v)


def _tabla_md(capa: str, muestra: pd.DataFrame, filas: pd.DataFrame) -> list[str]:
    lineas = ["| Columna | Tipo | Descripción |", "|---|---|---|"]
    lineas += [f"| `{c}` | {t} | {d} |" for c, t, d in ESQUEMA[capa]]
    lineas += ["", f"Muestra: {muestra['ticker'].iloc[0]}", "",
               "| " + " | ".join(muestra.columns) + " |",
               "|" + "---|" * len(muestra.columns)]
    lineas += ["| " + " | ".join(_fmt(v) for v in r) + " |" for _, r in filas.iterrows()]
    return lineas


def escribir_diccionario(capa: str, muestra: pd.DataFrame, n_archivos: int,
                         extra: tuple[str, pd.DataFrame, str] | None = None) -> None:
    dominio, nivel = capa.split("/")
    carpeta = (MARKET if dominio == "market" else INTRADAY) / nivel
    filas = muestra.tail(5) if nivel != "bronze" else muestra.head(5)
    lineas = [
        f"# {dominio} / {nivel}",
        "",
        f"{n_archivos} archivos CSV, uno por {'símbolo' if dominio == 'market' else 'emisora'}. "
        f"Se generan con `python productos/precios_fx/capas.py`.",
        "",
    ] + _tabla_md(capa, muestra, filas)
    if extra:
        capa2, muestra2, sub = extra
        lineas += ["", f"## Subcarpeta `{sub}`: resumen por día", "",
                   f"{n_archivos} archivos CSV más, un día por fila.", ""]
        lineas += _tabla_md(capa2, muestra2, muestra2.tail(5))
    (carpeta / "_diccionario.md").write_text("\n".join(lineas) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--solo", choices=("market", "intraday"))
    args = parser.parse_args(argv)
    gold_m = diario_i = None
    if args.solo in (None, "market"):
        gold_m = construir_market()
    if args.solo in (None, "intraday"):
        _, diario_i = construir_intraday()
    if gold_m is not None:
        construir_db(gold_m, diario_i)
    return 0


if __name__ == "__main__":
    sys.exit(main())
