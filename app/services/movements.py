import os
from typing import List, Tuple
from datetime import date
import pandas as pd
import numpy as np
from dateutil import parser as dateparser

# -------- utilidades de parseo --------
def parse_date_safe(x) -> date | None:
    if pd.isna(x) or x == "": return None
    try:
        return pd.to_datetime(x, dayfirst=True, errors="coerce").date()
    except Exception:
        try:
            return dateparser.parse(str(x), dayfirst=True).date()
        except Exception:
            return None

def normalize_importe_series(s: pd.Series) -> pd.Series:
    s = s.astype(str).str.strip()
    s = s.str.replace(r"[^\d,\-\.]", "", regex=True)
    mask_coma = s.str.contains(",", na=False)
    s[mask_coma] = s[mask_coma].str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
    s[~mask_coma] = s[~mask_coma].str.replace(r"(?<=\d)\.(?=\d{3}(\D|$))", "", regex=True)
    return pd.to_numeric(s, errors="coerce").fillna(0.0)

def pick_fecha_column(cols: List[str]) -> str | None:
    low = {c: c.lower() for c in cols}
    for c,l in low.items():
        if "fecha" in l and ("val" in l or "valor" in l): return c
    for c,l in low.items():
        if "fecha" in l and ("contab" in l or "contable" in l): return c
    for c,l in low.items():
        if "fecha" in l: return c
    return None

# -------- lector de xls/xlsx --------
def read_movements_excel(filepath: str) -> pd.DataFrame:
    df = pd.read_excel(filepath)  # xlrd abre .xls; openpyxl abre .xlsx
    fecha_col = pick_fecha_column(df.columns)
    rename = {}
    if fecha_col: rename[fecha_col] = "Fecha"
    for c in df.columns:
        cl = c.lower()
        if c == fecha_col: continue
        if "descrip" in cl: rename[c] = "Concepto"
        elif "import" in cl: rename[c] = "Importe"
        elif "saldo" in cl: rename[c] = "Saldo"
    df = df.rename(columns=rename)
    req = {"Fecha","Concepto","Importe"}
    missing = req - set(df.columns)
    if missing:
        raise ValueError(f"Faltan columnas: {missing}")
    df["Fecha"] = pd.to_datetime(df["Fecha"], errors="coerce", dayfirst=True)
    df = df.dropna(subset=["Fecha"])
    df["Concepto"] = df["Concepto"].astype(str)
    df["Importe"] = normalize_importe_series(df["Importe"])
    if "Saldo" in df.columns:
        df["Saldo"] = normalize_importe_series(df["Saldo"])
    else:
        df["Saldo"] = np.nan
    return df[["Fecha","Concepto","Importe","Saldo"]]

# -------- clasificación por reglas --------
def classify(df: pd.DataFrame, reglas: list[dict], property_id: int) -> pd.DataFrame:
    if df.empty: return pd.DataFrame(columns=["Fecha","Concepto","Importe","categoria","subcuenta","inquilino"])
    out = []
    for _, row in df.iterrows():
        concepto = str(row["Concepto"])
        cat = None; sub = None; inq = None
        for r in reglas:
            pal = (r.get("palabra") or "").strip()
            if pal and pal.lower() in concepto.lower():
                tipo = r.get("tipo")
                cat = "Renta" if tipo=="renta" else ("Hipoteca" if tipo=="hipoteca" else "Gasto")
                sub = r.get("subcuenta")
                inq = r.get("inquilino")
                break
        if cat:
            out.append({
                "Fecha": row["Fecha"].date() if hasattr(row["Fecha"], "date") else row["Fecha"],
                "Concepto": concepto,
                "Importe": float(row["Importe"]),
                "categoria": cat,
                "subcuenta": sub,
                "inquilino": inq,
                "property_id": property_id,
            })
    return pd.DataFrame(out)
