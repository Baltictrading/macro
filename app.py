import streamlit as st
import requests
import pandas as pd
import plotly.express as px

# --- Config ---
API_KEY = st.secrets.get("FRED_API_KEY", "")

# --- US Economic Series Mapping (FRED) ---
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
    """Fetch a monthly series from FRED."""
    url = "https://api.stlouisfed.org/fred/series/observations"
    params = {"series_id": series_id, "api_key": API_KEY, "file_type": "json"}
    data = requests.get(url, params=params).json().get("observations", [])
    if not data:
        return pd.Series(dtype=float)
    df = pd.DataFrame(data)
    if not {"date", "value"}.issubset(df.columns):
        return pd.Series(dtype=float)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    return df.set_index("date")["value"].sort_index()


def get_series(name: str) -> pd.Series:
    """Return series for given metric, apply pct_change where needed."""
    s = fetch_fred(SERIES[name])
    if name == "CPI MoM":
        return s.pct_change(1) * 100
    if name == "CPI YoY":
        return s.pct_change(12) * 100
    if name == "Retail Sales MoM":
        return s.pct_change(1) * 100
    return s

# --- UI ---
st.title("US Economic Dashboard via FRED – Deine Kennzahlen")
view = st.sidebar.radio("Darstellung", ["Grafik", "Tabelle"])
metrics = st.sidebar.multiselect("Kennzahlen", list(SERIES.keys()), default=list(SERIES.keys()))

# --- Plot View ---
if view == "Grafik":
    fig = px.line()
    for name in metrics:
        s = get_series(name)
        if not s.empty:
            fig.add_scatter(x=s.index, y=s.values, mode="lines", name=name)
    fig.update_layout(
        title="US Kennzahlen",
        xaxis_title="Datum",
        yaxis_title="Wert / %"
    )
    st.plotly_chart(fig, use_container_width=True)

# --- Table View ---
else:
    st.subheader("Tabelle der letzten 13 Perioden mit Hervorhebung")
    # Prepare numeric DataFrame
    numeric = {}
    # Determine columns: last 13 periods from first metric
    ref_index = get_series(metrics[0]).sort_index(ascending=False).index[:13]
    cols = [d.strftime('%b %Y') for d in ref_index]
    for name in metrics:
        vals = get_series(name).sort_index(ascending=False).head(13).tolist()
        if len(vals) < 13:
            vals += [None] * (13 - len(vals))
        numeric[name] = vals
    num_df = pd.DataFrame.from_dict(numeric, orient='index', columns=cols)
    num_df.index.name = 'Kennzahl'

    # Highlight improved vs worsened
    def highlight(row):
        styles = []
        for i in range(len(row)):
            cur = row.iloc[i]
            prev = row.iloc[i+1] if i+1 < len(row) else None
            if pd.isna(cur) or pd.isna(prev):
                styles.append("")
            elif cur > prev:
                styles.append('background-color: #d4fcdc')  # greenish
            elif cur < prev:
                styles.append('background-color: #fcdcdc')  # reddish
            else:
                styles.append("")
        return styles

    styled = num_df.style.apply(highlight, axis=1)

    # Apply correct formatting per row
    for name in metrics:
        if name in ("CPI MoM", "CPI YoY", "Retail Sales MoM"):
            styled = styled.format("{:.2f}%", subset=pd.IndexSlice[name, :])
        elif name in ("Nonfarm Payrolls", "New Home Sales", "GDP (Real, Quarterly)", "Consumer Confidence", "Balance of Trade"):
            styled = styled.format("{:, .0f}", subset=pd.IndexSlice[name, :])
        else:
            styled = styled.format("{:.2f}", subset=pd.IndexSlice[name, :])

    st.write(styled)

# Footer
st.markdown("---")
st.markdown("*Datenquelle: FRED API (St. Louis Fed).* ")
