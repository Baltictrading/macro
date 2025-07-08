import os
import streamlit as st
import requests
import pandas as pd
import plotly.express as px

# --- Config ---
API_KEYS = {"FRED": st.secrets.get("FRED_API_KEY", "")}

# --- Series mappings ---
FRED_UNEMPLOY = {
    "USA": "UNRATE",
    "Eurozone": "LRHUTTTTEZM156S",
    "UK": "LRHUTTTTGBM156S",
    "Japan": "LRHUTTTTJPM156S",
    "Australia": "LRUNTTTTAUM156N",
    "Canada": "LRUNTTTTCAM156S",
    "Switzerland": "LRUNTTTTCHQ156N",
    "Germany": "LRHUTTTTDEM156S"
}
CPI_INDEX = {
    "USA": "CPIAUCSL",
    "Eurozone": "CPALTT01EZM657N",
    "UK": "CPALTT01GBM657N",
    "Japan": "CPALTT01JPM657N",
    "Australia": "CPALTT01AUM657N",
    "Canada": "CPALTT01CAM657N",
    "Switzerland": "CPALTT01CHM657N",
    "Germany": "CPALTT01DEM657N"
}
WB_UNEMPLOY_IND = "SL.UEM.TOTL.ZS"
WB_INFLATION_IND = "FP.CPI.TOTL.ZG"
WB_COUNTRIES = ["China", "New Zealand"]

# --- Fetch Functions ---
@st.cache_data(ttl=3600)
def fetch_fred(series_id: str) -> pd.Series:
    "Fetch a monthly time series from FRED; return empty Series if no data."
    url = "https://api.stlouisfed.org/fred/series/observations"
    params = {"series_id": series_id, "api_key": API_KEYS.get("FRED", ""), "file_type": "json"}
    resp = requests.get(url, params=params)
    data = []
    try:
        data = resp.json().get("observations", [])
    except Exception:
        return pd.Series(dtype=float)
    if not data:
        return pd.Series(dtype=float)
    df = pd.DataFrame(data)
    if "date" not in df.columns or "value" not in df.columns:
        return pd.Series(dtype=float)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    return df.set_index("date")["value"].sort_index()

@st.cache_data(ttl=3600)
def fetch_worldbank(country_code: str, indicator: str) -> pd.Series:
    "Fetch an annual series from World Bank; return empty Series if no data."
    url = f"https://api.worldbank.org/v2/country/{country_code}/indicator/{indicator}"
    params = {"format": "json", "per_page": 1000}
    resp = requests.get(url, params=params)
    try:
        content = resp.json()
    except Exception:
        return pd.Series(dtype=float)
    # content[1] should be list of records
    records = content[1] if isinstance(content, list) and len(content) > 1 and isinstance(content[1], list) else []
    rows = []
    for item in records:
        val = item.get("value")
        date = item.get("date")
        if val is None or date is None:
            continue
        try:
            dt = pd.to_datetime(f"{date}-01-01")
        except Exception:
            continue
        rows.append({"date": dt, "value": val})
    if not rows:
        return pd.Series(dtype=float)
    df = pd.DataFrame(rows)
    if "value" not in df.columns:
        return pd.Series(dtype=float)
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    return df.set_index("date")["value"].sort_index()

# --- UI ---
st.title("Makro-Dashboard Major Currencies")
mode = st.sidebar.radio("Darstellung", ["Grafik", "Tabelle"])
indicator = st.sidebar.selectbox(
    "Indikator", ["Unemployment Rate", "Monthly Inflation Rate", "Annual Inflation Rate"]
)
all_countries = list(FRED_UNEMPLOY.keys()) + WB_COUNTRIES
countries = st.sidebar.multiselect("Länder", all_countries, default=all_countries)

# --- Helper to choose the correct series ---
def get_series(country: str) -> pd.Series:
    if indicator == "Unemployment Rate":
        if country in FRED_UNEMPLOY:
            return fetch_fred(FRED_UNEMPLOY[country])
        else:
            return fetch_worldbank(country, WB_UNEMPLOY_IND)
    if indicator == "Monthly Inflation Rate":
        if country in CPI_INDEX:
            idx = fetch_fred(CPI_INDEX[country])
            return idx.pct_change(1) * 100 if not idx.empty else pd.Series(dtype=float)
        else:
            return pd.Series(dtype=float)
    if indicator == "Annual Inflation Rate":
        if country in CPI_INDEX:
            idx = fetch_fred(CPI_INDEX[country])
            return idx.pct_change(12) * 100 if not idx.empty else pd.Series(dtype=float)
        else:
            return fetch_worldbank(country, WB_INFLATION_IND)
    return pd.Series(dtype=float)

# --- Render ---
if mode == "Grafik":
    fig = px.line()
    for c in countries:
        s = get_series(c)
        if not s.empty:
            fig.add_scatter(x=s.index, y=s.values, mode="lines", name=c)
    y_label = "%" if "Inflation" in indicator or "Unemployment" in indicator else "Wert"
    fig.update_layout(title=indicator, xaxis_title="Datum", yaxis_title=y_label)
    st.plotly_chart(fig, use_container_width=True)
else:
    st.subheader(indicator)
    table = {}
    dates = []
    # get columns from first non-empty
    for c in countries:
        s0 = get_series(c).sort_index(ascending=False)
        if not s0.empty:
            dates = s0.index[:13]
            break
    cols = [d.strftime('%b %Y') for d in dates]
    for c in countries:
        s = get_series(c).sort_index(ascending=False).head(13).tolist()
        fmt = [f"{v:.2f}%" if pd.notna(v) else "" for v in s]
        table[c] = fmt
    if dates:
        df = pd.DataFrame.from_dict(table, orient='index', columns=cols)
    else:
        df = pd.DataFrame()
    df.index.name = 'Land'
    st.dataframe(df)

# Footer
st.markdown("*Datenquelle: FRED & World Bank API.*")
