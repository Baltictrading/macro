import os
import streamlit as st
import requests
import pandas as pd
import plotly.express as px

# --- Config ---
API_KEYS = {"FRED": st.secrets["FRED_API_KEY"]}

# Mapping of country to indicator endpoints and series IDs
ENDPOINTS = {
    "USA": {
        "Unemployment Rate": {"series_id": "UNRATE", "fetch_fn": "fred"}
    },
    "Eurozone": {
        "HICP Inflation (m/m)": {"dataset": "prc_hicp_midx", "fetch_fn": "eurostat"},
        "Unemployment Rate": {"series_id": "LRHUTTTTEZM156S", "fetch_fn": "fred"}
    }
    # TODO: weitere Länder/Indikatoren ergänzen
}

# --- Fetch Functions ---
@st.cache_data(ttl=3600)
def fetch_fred(series_id: str, api_key: str) -> pd.DataFrame:
    url = "https://api.stlouisfed.org/fred/series/observations"
    params = {"series_id": series_id, "api_key": api_key, "file_type": "json"}
    r = requests.get(url, params=params)
    data = r.json().get('observations', [])
    df = pd.DataFrame(data)
    df['date'] = pd.to_datetime(df['date'])
    df['value'] = pd.to_numeric(df['value'], errors='coerce')
    return df.set_index('date')

@st.cache_data(ttl=3600)
def fetch_eurostat(dataset: str) -> pd.DataFrame:
    url = f"https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/{dataset}"
    params = {"format": "JSON", "precision": 1, "unitCode": "I15"}
    resp = requests.get(url, params=params).json()
    time_labels = resp['dimension']['time']['category']['label']
    values = resp.get('value', {})
    rows = []
    for code, val in values.items():
        period = time_labels.get(code)
        if not period:
            continue
        rows.append({'date': pd.to_datetime(period), 'value': val})
    df = pd.DataFrame(rows)
    df['value'] = pd.to_numeric(df['value'], errors='coerce')
    return df.set_index('date')

# --- Streamlit UI ---
st.title("Makro-Dashboard Major Currencies")
view = st.sidebar.radio("Darstellung", ["Grafik", "Tabelle"])
indicator = st.sidebar.selectbox("Indikator", [ind for c in ENDPOINTS for ind in ENDPOINTS[c]])
countries = st.sidebar.multiselect("Länder", list(ENDPOINTS.keys()), default=list(ENDPOINTS.keys()))

if view == "Grafik":
    fig = px.line()
    for country in countries:
        cfg = ENDPOINTS[country].get(indicator)
        if not cfg:
            continue
        if cfg['fetch_fn'] == 'fred':
            df = fetch_fred(cfg['series_id'], API_KEYS['FRED'])
        else:
            df = fetch_eurostat(cfg['dataset'])
        if not df.empty:
            fig.add_scatter(x=df.index, y=df['value'], mode='lines', name=country)
    fig.update_layout(title=indicator, xaxis_title='Datum', yaxis_title='Wert')
    st.plotly_chart(fig, use_container_width=True)

else:
    # Tabelle: Überschrift
    st.subheader(indicator)
    # Ermittlung der Datums-Labels aus dem ersten Land
    date_labels = []
    for country in countries:
        cfg = ENDPOINTS[country].get(indicator)
        if not cfg:
            continue
        if cfg['fetch_fn'] == 'fred':
            df0 = fetch_fred(cfg['series_id'], API_KEYS['FRED'])
        else:
            df0 = fetch_eurostat(cfg['dataset'])
        df0 = df0.sort_index(ascending=False)
        dates = df0.index[:13]
        date_labels = [d.strftime('%b %Y') for d in dates]
        break
    # Daten sammeln
    table = {}
    for country in countries:
        cfg = ENDPOINTS[country].get(indicator)
        if not cfg:
            continue
        if cfg['fetch_fn'] == 'fred':
            df = fetch_fred(cfg['series_id'], API_KEYS['FRED'])
        else:
            df = fetch_eurostat(cfg['dataset'])
        df = df.sort_index(ascending=False)
        vals = df['value'].head(13).tolist()
        if len(vals) < 13:
            vals += [None] * (13 - len(vals))
        table[country] = vals
    table_df = pd.DataFrame.from_dict(table, orient='index', columns=date_labels)
    table_df.index.name = 'Land'
    # Heatmap-ähnliche Farbgebung
    styled = table_df.style.background_gradient(axis=None)
    st.dataframe(styled)

# Footer
st.markdown("---")
st.markdown("*Prototyp zur Visualisierung von Zeitreihen und Tabellen aus verschiedenen Makro-APIs.*")
