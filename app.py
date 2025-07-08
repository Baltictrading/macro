import os
import streamlit as st
import requests
import pandas as pd
import plotly.express as px

# --- Config ---
API_KEYS = {"FRED": st.secrets["FRED_API_KEY"]}

# --- Mapping of country to FRED series for Unemployment Rate ---
COUNTRIES = {
    "USA": "UNRATE",
    "Eurozone": "LRHUTTTTEZM156S",
    "UK": "LRHUTTTTGBM156S",
    "Japan": "LRHUTTTTJPM156S",
    "Australia": "LRUNTTTTAUM156N",
    "Canada": "LRUNTTTTCAM156S",
    "Switzerland": "LRUNTTTTCHQ156N"
}

# --- Data Fetching ---
@st.cache_data(ttl=3600)
def fetch_unemployment(series_id: str) -> pd.Series:
    """Fetch monthly unemployment rate series from FRED"""
    url = "https://api.stlouisfed.org/fred/series/observations"
    params = {
        "series_id": series_id,
        "api_key": API_KEYS["FRED"],
        "file_type": "json"
    }
    resp = requests.get(url, params=params).json().get("observations", [])
    df = pd.DataFrame(resp)
    df["date"] = pd.to_datetime(df["date"])
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    return df.set_index("date")["value"]

# --- Streamlit UI ---
st.title("Makro-Dashboard: Unemployment Rate Major Currencies")
view = st.sidebar.radio("Darstellung", ["Grafik", "Tabelle"])
selected_countries = st.sidebar.multiselect(
    "Länder", list(COUNTRIES.keys()), default=list(COUNTRIES.keys())
)

if view == "Grafik":
    fig = px.line()
    for country in selected_countries:
        series_id = COUNTRIES[country]
        df = fetch_unemployment(series_id)
        if not df.empty:
            fig.add_scatter(x=df.index, y=df.values, mode="lines", name=country)
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
    # Get date labels from first selected country
    for country in selected_countries:
        df0 = fetch_unemployment(COUNTRIES[country]).sort_index(ascending=False)
        last_dates = df0.index[:13]
        date_labels = [d.strftime('%b %Y') for d in last_dates]
        break
    for country in selected_countries:
        df = fetch_unemployment(COUNTRIES[country]).sort_index(ascending=False)
        values = df.head(13).tolist()
        if len(values) < 13:
            values += [None] * (13 - len(values))
        formatted = [f"{v:.2f}%" if pd.notna(v) else "" for v in values]
        table_data[country] = formatted
    cols = ["Aktuell"] + date_labels[1:]
    table_df = pd.DataFrame.from_dict(table_data, orient='index', columns=cols)
    table_df.index.name = 'Land'
    st.dataframe(table_df)

# Footer
st.markdown("*Datenquelle: FRED API (St. Louis Fed).*" )
