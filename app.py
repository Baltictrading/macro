import os
import streamlit as st
import requests
import pandas as pd
import plotly.express as px

# --- Config ---
API_KEYS = {"FRED": st.secrets.get("FRED_API_KEY", "")}

# --- Series mappings ---
# Unemployment (FRED) and CPI index (FRED) series for monthly data
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
# World Bank annual data (unemployment & inflation)
WB_UNEMPLOY_IND = "SL.UEM.TOTL.ZS"
WB_INFLATION_IND = "FP.CPI.TOTL.ZG"
WB_COUNTRIES = ["China", "New Zealand"]

# --- Fetch Functions ---
@st.cache_data(ttl=3600)
def fetch_fred(series_id: str) -> pd.Series:
    "Fetch monthly series from FRED"  
    url = "https://api.stlouisfed.org/fred/series/observations"
    params = {"series_id": series_id, "api_key": API_KEYS["FRED"], "file_type": "json"}
    obs = requests.get(url, params=params).json().get("observations", [])
    df = pd.DataFrame(obs)
    df["date"] = pd.to_datetime(df["date"])
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    return df.set_index("date")["value"].sort_index()

@st.cache_data(ttl=3600)
def fetch_worldbank(country_code: str, indicator: str) -> pd.Series:
    "Fetch annual series from World Bank"  
    url = f"https://api.worldbank.org/v2/country/{country_code}/indicator/{indicator}"
    params = {"format": "json", "per_page": 1000}
    resp = requests.get(url, params=params).json()
    data = resp[1] if isinstance(resp, list) and len(resp) > 1 else []
    rows = []
    for item in data:
        val = item.get("value")
        date = item.get("date")
        if val is None or date is None:
            continue
        try:
            dt = pd.to_datetime(f"{date}-01-01")
        except:
            continue
        rows.append({"date": dt, "value": val})
    df = pd.DataFrame(rows)
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    return df.set_index("date")["value"].sort_index()

# --- UI ---
st.title("Makro-Dashboard Major Currencies")
mode = st.sidebar.radio("Darstellung", ["Grafik", "Tabelle"])
indicator = st.sidebar.selectbox(
    "Indikator", ["Unemployment Rate", "Monthly Inflation Rate", "Annual Inflation Rate"]
)
countries = st.sidebar.multiselect("Länder", list(FRED_UNEMPLOY.keys()) + WB_COUNTRIES,
                                 default=list(FRED_UNEMPLOY.keys()) + WB_COUNTRIES)

# --- Prepare Data ---
def get_series(country: str) -> pd.Series:
    # Unemployment
    if indicator == "Unemployment Rate":
        if country in FRED_UNEMPLOY:
            return fetch_fred(FRED_UNEMPLOY[country])
        else:
            return fetch_worldbank(country, WB_UNEMPLOY_IND)
    # Monthly inflation
    if indicator == "Monthly Inflation Rate":
        if country in CPI_INDEX:
            idx = fetch_fred(CPI_INDEX[country])
            return idx.pct_change(periods=1) * 100
        else:
            return pd.Series(dtype=float)
    # Annual inflation
    if indicator == "Annual Inflation Rate":
        if country in CPI_INDEX:
            idx = fetch_fred(CPI_INDEX[country])
            return idx.pct_change(periods=12) * 100
        else:
            return fetch_worldbank(country, WB_INFLATION_IND)
    return pd.Series(dtype=float)

# --- Plot or Table ---
if mode == "Grafik":
    fig = px.line()
    for c in countries:
        s = get_series(c)
        if not s.empty:
            fig.add_scatter(x=s.index, y=s.values, mode="lines", name=c)
    y_title = "%" if indicator != "Unemployment Rate" else "Rate (%)"
    fig.update_layout(title=indicator, xaxis_title="Datum", yaxis_title=y_title)
    st.plotly_chart(fig, use_container_width=True)
else:
    st.subheader(indicator)
    table = {}
    dates = []
    # get dates from first country
    for c in countries:
        s0 = get_series(c).sort_index(ascending=False)
        dates = s0.index[:13]
        break
    cols = [d.strftime('%b %Y') for d in dates]
    for c in countries:
        s = get_series(c).sort_index(ascending=False).head(13).tolist()
        row = [f"{v:.2f}%" if pd.notna(v) else "" for v in s]
        table[c] = row
    df = pd.DataFrame.from_dict(table, orient='index', columns=cols)
    df.index.name = 'Land'
    st.dataframe(df)

# Footer
st.markdown("*Datenquelle: FRED & World Bank API.*")
