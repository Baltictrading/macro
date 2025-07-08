import os
import streamlit as st
import requests
import pandas as pd
import plotly.express as px

# FRED-Key aus Streamlit-Secrets lesen
API_KEYS = {"FRED": st.secrets["FRED_API_KEY"]}

ENDPOINTS = {
    "USA": {
        "Unemployment Rate": {
            "series_id": "UNRATE",
            "fetch_fn": "fred"
        }
    },
    "Eurozone": {
        "HICP Inflation (m/m)": {
            "dataset": "prc_hicp_midx",
            "fetch_fn": "eurostat"
        }
    },
    # weitere Länder …
}

def fetch_fred(series_id, api_key):
    url = "https://api.stlouisfed.org/fred/series/observations"
    params = {"series_id": series_id, "api_key": api_key, "file_type": "json"}
    data = requests.get(url, params=params).json().get("observations", [])
    df = pd.DataFrame(data)
    df.date = pd.to_datetime(df.date)
    df.value = pd.to_numeric(df.value, errors="coerce")
    return df.set_index("date")

def fetch_eurostat(dataset):
    url = f"https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/{dataset}"
    params = {"format": "JSON", "precision": 1, "unitCode": "I15"}
    resp = requests.get(url, params=params).json()
    tl = resp["dimension"]["time"]["category"]["label"]
    vals = resp.get("value", {})
    rows = []
    for code, val in vals.items():
        period = tl.get(code)
        if not period: continue
        rows.append({"date": pd.to_datetime(period), "value": val})
    df = pd.DataFrame(rows).set_index("date")
    df.value = pd.to_numeric(df.value, errors="coerce")
    return df

st.title("Makro-Dashboard Major Currencies")
indicator = st.sidebar.selectbox("Indikator", [i for c in ENDPOINTS for i in ENDPOINTS[c]])
countries = st.sidebar.multiselect("Länder", list(ENDPOINTS), default=list(ENDPOINTS))
fig = px.line()
for country in countries:
    cfg = ENDPOINTS[country].get(indicator)
    if not cfg: continue
    if cfg["fetch_fn"] == "fred":
        df = fetch_fred(cfg["series_id"], API_KEYS["FRED"])
    else:
        df = fetch_eurostat(cfg["dataset"])
    fig.add_scatter(x=df.index, y=df.value, mode="lines", name=country)
fig.update_layout(xaxis_title="Datum", yaxis_title="Wert")
st.plotly_chart(fig, use_container_width=True)
