import os
import streamlit as st
import requests
import pandas as pd
import plotly.express as px

# --- Config ---
API_KEYS = {"FRED": st.secrets["FRED_API_KEY"]}

# --- Mapping of country to data source and code ---
COUNTRIES = {
    "USA":          {"source": "fred",       "code": "UNRATE"},
    "Eurozone":    {"source": "fred",       "code": "LRHUTTTTEZM156S"},
    "UK":           {"source": "fred",       "code": "LRHUTTTTGBM156S"},
    "Japan":        {"source": "fred",       "code": "LRHUTTTTJPM156S"},
    "Australia":    {"source": "fred",       "code": "LRUNTTTTAUM156N"},
    "Canada":       {"source": "fred",       "code": "LRUNTTTTCAM156S"},
    "Switzerland":  {"source": "fred",       "code": "LRUNTTTTCHQ156N"},
    "Germany":      {"source": "fred",       "code": "LRHUTTTTDEM156S"},
    "China":        {"source": "worldbank",  "code": "CN"},
    "New Zealand":  {"source": "worldbank",  "code": "NZ"}
}

# --- Data Fetching Functions ---
@st.cache_data(ttl=3600)
def fetch_fred_series(series_id: str) -> pd.Series:
    """Fetch monthly series from FRED"""
    url = "https://api.stlouisfed.org/fred/series/observations"
    params = {"series_id": series_id, "api_key": API_KEYS["FRED"], "file_type": "json"}
    data = requests.get(url, params=params).json().get("observations", [])
    df = pd.DataFrame(data)
    df["date"] = pd.to_datetime(df["date"])
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    return df.set_index("date")["value"]

@st.cache_data(ttl=3600)
def fetch_worldbank(country_code: str) -> pd.Series:
    """Fetch annual unemployment rate from World Bank"""
    url = f"https://api.worldbank.org/v2/country/{country_code}/indicator/SL.UEM.TOTL.ZS"
    params = {"format": "json", "per_page": 1000}
    resp = requests.get(url, params=params).json()
    items = resp[1] if len(resp) > 1 else []
    rows = []
    for item in items:
        val = item.get("value")
        date_str = item.get("date")
        if val is None or date_str is None:
            continue
        try:
            date = pd.to_datetime(date_str + "-01-01")
        except:
            continue
        rows.append({"date": date, "value": val})
    df = pd.DataFrame(rows)
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    return df.set_index("date")["value"].sort_index(ascending=False)

# --- Streamlit UI ---
st.title("Makro-Dashboard: Unemployment Rate Major Currencies")
view = st.sidebar.radio("Darstellung", ["Grafik", "Tabelle"])
selected = st.sidebar.multiselect("Länder", list(COUNTRIES.keys()), default=list(COUNTRIES.keys()))

if view == "Grafik":
    fig = px.line()
    for country in selected:
        cfg = COUNTRIES[country]
        if cfg["source"] == "fred":
            series = fetch_fred_series(cfg["code"])
        else:
            series = fetch_worldbank(cfg["code"])
        if not series.empty:
            fig.add_scatter(x=series.index, y=series.values, mode="lines", name=country)
    fig.update_layout(
        title="Unemployment Rate (%)",
        xaxis_title="Datum",
        yaxis_title="Rate (%)"
    )
    st.plotly_chart(fig, use_container_width=True)

else:
    st.subheader("Unemployment Rate (%)")
    table_data = {}
    date_labels = []
    # Determine column labels from first selected country
    for country in selected:
        cfg = COUNTRIES[country]
        series = fetch_fred_series(cfg["code"]) if cfg["source"] == "fred" else fetch_worldbank(cfg["code"])
        dates = series.sort_index(ascending=False).index[:13]
        date_labels = [d.strftime('%b %Y') for d in dates]
        break
    # Build rows
    for country in selected:
        cfg = COUNTRIES[country]
        series = fetch_fred_series(cfg["code"]) if cfg["source"] == "fred" else fetch_worldbank(cfg["code"])
        values = series.sort_index(ascending=False).head(13).tolist()
        if len(values) < 13:
            values += [None] * (13 - len(values))
        formatted = [f"{v:.2f}%" if pd.notna(v) else "" for v in values]
        table_data[country] = formatted
    cols = ["Aktuell"] + date_labels[1:]
    table_df = pd.DataFrame.from_dict(table_data, orient='index', columns=cols)
    table_df.index.name = 'Land'
    st.dataframe(table_df)

# Footer
st.markdown("*Datenquelle: FRED API & World Bank API.*")
