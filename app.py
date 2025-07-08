import streamlit as st
import requests
import pandas as pd

# --- Dein FRED-Key als Secret in Streamlit hinterlegen ---
API_KEY = st.secrets["FRED_API_KEY"]

# --- FRED-Serien für US-Kennzahlen ---
SERIES = {
    "Interest Rate":         "FEDFUNDS",
    "Unemployment Rate":     "UNRATE",
    "CPI MoM":               "CPIAUCSL",
    "CPI YoY":               "CPIAUCSL",
    "Nonfarm Payrolls":      "PAYEMS",
    "PPI (All Commodities)": "PPIACO",
    "New Home Sales":        "HSN1F",
    "GDP (Real, Quarterly)": "GDPC1",
    "Consumer Confidence":   "UMCSENT",
    "Retail Sales MoM":      "RSAFS",
    "Balance of Trade":      "BOPGSTB"
}

@st.cache_data(ttl=3600)
def fetch_fred(series_id: str) -> pd.Series:
    """Holt eine monatliche Zeitreihe aus FRED."""
    url = "https://api.stlouisfed.org/fred/series/observations"
    params = dict(
        series_id=series_id,
        api_key=API_KEY,
        file_type="json"
    )
    data = requests.get(url, params=params).json().get("observations", [])
    if not data:
        return pd.Series(dtype=float)
    df = pd.DataFrame(data)
    if not {"date","value"}.issubset(df.columns):
        return pd.Series(dtype=float)
    df["date"]  = pd.to_datetime(df["date"], errors="coerce")
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    return df.set_index("date")["value"].sort_index()

def get_series(name: str) -> pd.Series:
    s = fetch_fred(SERIES[name])
    if name == "CPI MoM":
        return s.pct_change(1) * 100
    if name == "CPI YoY":
        return s.pct_change(12) * 100
    if name == "Retail Sales MoM":
        return s.pct_change(1) * 100
    return s

st.title("US-Macro-Dashboard")

# Nur Tabellen-Ansicht
metrics = list(SERIES.keys())
st.subheader("Tabelle der letzten 13 Perioden")
# Spalten aus erster Kennzahl ziehen
dates = get_series(metrics[0]).sort_index(ascending=False).index[:13]
cols = [d.strftime("%b %Y") for d in dates]

table = {}
for name in metrics:
    vals = get_series(name).sort_index(ascending=False).head(13).tolist()
    if name in ("CPI MoM","CPI YoY","Retail Sales MoM"):
        row = [f"{v:.2f} %" if pd.notna(v) else "" for v in vals]
    else:
        row = [f"{v:,.2f}"   if pd.notna(v) else "" for v in vals]
    table[name] = row

df = pd.DataFrame.from_dict(table, orient="index", columns=cols)
df.index.name = "Kennzahl"
st.dataframe(df)

st.markdown("""
---
**Hinweis:** PMI-Daten stellt FRED seit 2016 nicht mehr bereit. 
""")
