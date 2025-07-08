import streamlit as st
import requests
import pandas as pd
import plotly.express as px

# --- Config ---
API_KEY = st.secrets["FRED_API_KEY"]

# --- FRED-Serie ↔ Kennzahl-Mapping ---
SERIES = {
    "Interest Rate":           "FEDFUNDS",
    "Unemployment Rate":       "UNRATE",
    "CPI MoM":                 "CPIAUCSL",
    "CPI YoY":                 "CPIAUCSL",
    "Nonfarm Payrolls":        "PAYEMS",
    "PPI (All Commodities)":   "PPIACO",
    "New Home Sales":          "HSN1F",
    "GDP (Real, Quarterly)":   "GDPC1",
    "Consumer Confidence":     "UMCSENT",
    "Retail Sales MoM":        "RSAFS",
    "Balance of Trade":        "BOPGSTB"
    # PMIs entfallen, da FRED diese seit 2016 nicht mehr bereitstellt
}

# --- Funktion zum Abruf einer FRED-Serie ---
@st.cache_data(ttl=3600)
def fetch_fred(series_id: str) -> pd.Series:
    """
    Holt JSON-Daten von FRED und liefert eine Zeitreihe (Series) zurück.
    Endpoint: fred/series/observations?series_id=…&api_key=…&file_type=json :contentReference[oaicite:0]{index=0}
    """
    url = "https://api.stlouisfed.org/fred/series/observations"
    params = {"series_id": series_id, "api_key": API_KEY, "file_type": "json"}
    r = requests.get(url, params=params)
    data = r.json().get("observations", [])
    if not data:
        return pd.Series(dtype=float)
    df = pd.DataFrame(data)
    if not {"date", "value"}.issubset(df.columns):
        return pd.Series(dtype=float)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    return df.set_index("date")["value"].sort_index()

# --- Streamlit UI ---
st.title("US Economic Dashboard via FRED")

view = st.sidebar.radio("Darstellung", ["Grafik", "Tabelle"])
metrics = st.sidebar.multiselect("Kennzahlen", list(SERIES.keys()), default=list(SERIES.keys()))

# --- Helper: Passe jede Kennzahl an: CPI und Retail Sales in %-Änderung umrechnen ---
def get_series(name: str) -> pd.Series:
    sid = SERIES[name]
    s = fetch_fred(sid)
    if name == "CPI MoM":
        return s.pct_change(1) * 100
    if name == "CPI YoY":
        return s.pct_change(12) * 100
    if name == "Retail Sales MoM":
        return s.pct_change(1) * 100
    return s

# --- Grafikansicht ---
if view == "Grafik":
    fig = px.line()
    for name in metrics:
        s = get_series(name)
        if not s.empty:
            fig.add_scatter(x=s.index, y=s.values, mode="lines", name=name)
    fig.update_layout(legend_title_text="Kennzahl",
                      xaxis_title="Datum",
                      yaxis_title="Wert bzw. %", 
                      title="Zeitreihen US-Kennzahlen") 
    st.plotly_chart(fig, use_container_width=True)

# --- Tabellenansicht ---
else:
    st.subheader("Tabelle der letzten 13 Perioden")
    # Referenz-Dates aus der ersten ausgewählten Kennzahl
    dates = []
    for name in metrics:
        s0 = get_series(name).sort_index(ascending=False)
        if not s0.empty:
            dates = s0.index[:13]
            break
    # Spaltenlabels
    cols = [d.strftime("%b %Y") for d in dates]
    # Werte sammeln
    table = {}
    for name in metrics:
        s = get_series(name).sort_index(ascending=False).head(13).tolist()
        # Formatierung: Prozentwerte mit %, andere als Zahl
        if name in ("CPI MoM", "CPI YoY", "Retail Sales MoM"):
            row = [f"{v:.2f} %" if pd.notna(v) else "" for v in s]
        else:
            row = [f"{v:,.2f}" if pd.notna(v) else "" for v in s]
        table[name] = row
    df = pd.DataFrame.from_dict(table, orient="index", columns=cols)
    df.index.name = "Kennzahl"
    st.dataframe(df)

# Footer
st.markdown("---")
st.markdown("*Datenquelle: FRED API (St. Louis Fed).*)*")
