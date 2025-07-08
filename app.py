import os
import streamlit as st
import requests
import pandas as pd
import plotly.express as px

# --- Konfiguration ---
API_KEYS = {
    "FRED": st.secrets.get("FRED_API_KEY", ""),
    "E_STAT": st.secrets.get("E_STAT_API_KEY", "")
}

st.set_page_config(layout="wide")
st.title("Makro-Dashboard Major Currencies")

# --- Country-List ---
COUNTRIES = [
    "USA", "Eurozone", "UK", "Germany", "Australia",
    "New Zealand", "Japan", "Switzerland", "Canada", "China"
]

# --- Sidebar ---
mode = st.sidebar.radio("Darstellung", ["Grafik", "Tabelle"])
indicator = st.sidebar.selectbox(
    "Indikator",
    ["Unemployment Rate", "Monthly Inflation Rate", "Annual Inflation Rate"]
)
countries = st.sidebar.multiselect("Länder", COUNTRIES, default=COUNTRIES)

# --- Hilfs-Funktionen zum Parsen ---  
def parse_sdmx_json(response):
    """Parse ABS- oder GENESIS- SDMX-JSON-Format (vereinfachter Ansatz)."""
    data = response.json()
    # Wir suchen alle observations im JSON-Baum
    obs = []
    def recurse(obj):
        if isinstance(obj, dict):
            for k,v in obj.items():
                if k.lower() in ("obs","observation","value"):
                    # Single obs: {"TIME_PERIOD":"2020-01","OBS_VALUE":...
                    if "TIME_PERIOD" in obj and "OBS_VALUE" in obj:
                        obs.append(obj)
                        return
                recurse(v)
        elif isinstance(obj, list):
            for item in obj:
                recurse(item)
    recurse(data)
    rows = []
    for o in obs:
        d = o.get("TIME_PERIOD") or o.get("date") or o.get("TIME") or o.get("time")
        v = o.get("OBS_VALUE") or o.get("value") or o.get("Value")
        try:
            date = pd.to_datetime(d)
            val = float(v)
            rows.append({"date": date, "value": val})
        except:
            continue
    df = pd.DataFrame(rows)
    if df.empty:
        return pd.Series(dtype=float)
    df = df.dropna(subset=["value"])
    return df.set_index("date")["value"].sort_index()

# --- Fetch-Funktionen pro Land/Quelle ---

@st.cache_data(ttl=3600)
def fetch_usa(series_id):
    """FRED (USA)"""
    url = "https://api.stlouisfed.org/fred/series/observations"
    params = {"series_id": series_id, "api_key": API_KEYS["FRED"], "file_type": "json"}
    j = requests.get(url, params=params).json().get("observations", [])
    df = pd.DataFrame(j)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    return df.set_index("date")["value"].sort_index()

@st.cache_data(ttl=3600)
def fetch_eurostat(dataset, filters=""):
    """Eurostat JSON-API"""
    url = f"https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/{dataset}"
    params = {"format": "JSON"} 
    # e.g. filters="&precision=1&unitCode=I15&geo=EU27_2020"
    resp = requests.get(url + filters, params=params)
    data = resp.json()
    # Zeit und Wert wie beim ersten Entwurf parsen
    tl = data["dimension"]["time"]["category"]["label"]
    vals = data.get("value", {})
    rows = []
    for code,val in vals.items():
        per = tl.get(code)
        if not per: continue
        try:
            dt = pd.to_datetime(per)
            rows.append({"date":dt, "value":val})
        except: continue
    df = pd.DataFrame(rows)
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    return df.set_index("date")["value"].sort_index()

@st.cache_data(ttl=3600)
def fetch_uk_unemp():
    """ONS UK: Unemployment Rate"""
    url = ("https://api.beta.ons.gov.uk/v1/datasets/LMSI/editions/time-series/"
           "versions/3/observations")
    # Filter geography=K02000001 (UK), labourMarketStatus=Unemployed
    params = {"filters":"geography=K02000001|labourMarketStatus=Unemployed"}
    j = requests.get(url, params=params).json().get("observations", {})
    rows = []
    for k,v in j.items():
        # k = "2020-01", v["value"]
        try:
            dt = pd.to_datetime(k)
            rows.append({"date":dt, "value":v["value"]})
        except: continue
    df = pd.DataFrame(rows)
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    return df.set_index("date")["value"].sort_index()

@st.cache_data(ttl=3600)
def fetch_uk_cpi():
    """ONS UK CPI (Consumer Prices Index)"""
    url = ("https://api.beta.ons.gov.uk/v1/datasets/CPX/editions/time-series/"
           "versions/3/observations")
    # Filter geography=K02000001 (UK), measure=all-items
    params = {"filters":"geography=K02000001|measure=all"}
    j = requests.get(url, params=params).json().get("observations", {})
    rows = []
    for k,v in j.items():
        try:
            dt = pd.to_datetime(k)
            rows.append({"date":dt, "value":v["value"]})
        except: continue
    df = pd.DataFrame(rows)
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    return df.set_index("date")["value"].sort_index()

@st.cache_data(ttl=3600)
def fetch_germany(code):
    """GENESIS-Online (Destatis)"""
    url = "https://api-genesis.destatis.de/SDEServer/rest/data"
    params = {"searchText":code}
    resp = requests.get(url, params=params)
    return parse_sdmx_json(resp)

@st.cache_data(ttl=3600)
def fetch_abs(code):
    """ABS Australia (SDMX-JSON)"""
    url = f"http://stat.data.abs.gov.au/sdmx-json/data/ABS,{code},1/all"
    resp = requests.get(url)
    return parse_sdmx_json(resp)

@st.cache_data(ttl=3600)
def fetch_statsnz(code):
    """Stats NZ Infoshare"""
    url = f"https://api.stats.govt.nz/services/v1/data/infoshare/{code}"
    resp = requests.get(url, params={"startPeriod":"2015"})
    return parse_sdmx_json(resp)

@st.cache_data(ttl=3600)
def fetch_estat(key, statsDataId):
    """e-Stat Japan"""
    url = "https://api.e-stat.go.jp/rest/3.0/app/json/getStatsData"
    params = {"appId":key, "statsDataId":statsDataId}
    resp = requests.get(url, params=params)
    data = resp.json().get("GET_STATS_DATA",{}).get("STATISTICAL_DATA",{})
    # Datum im 'VALUE' Array
    values = data.get("DATA_INF",{}).get("VALUE",[])
    rows = []
    for item in values:
        d = item.get("@TIME")  # "2020"
        v = item.get("#text")
        try:
            dt = pd.to_datetime(d + "-01-01")
            rows.append({"date":dt, "value":float(v)})
        except: continue
    df = pd.DataFrame(rows)
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    return df.set_index("date")["value"].sort_index()

@st.cache_data(ttl=3600)
def fetch_pxweb(url):
    """PXWeb JSON (Schweiz)"""
    resp = requests.get(url)
    return parse_sdmx_json(resp)

@st.cache_data(ttl=3600)
def fetch_statcan(table_id, lang="eng"):
    """Statistics Canada WDS API"""
    url = f"https://api.statcan.gc.ca/data/{table_id}"
    resp = requests.get(url, params={"lang":lang})
    data = resp.json().get("object",[])
    rows = []
    for item in data:
        d = item.get("REF_DATE")
        v = item.get("VALUE")
        try:
            dt = pd.to_datetime(d)
            rows.append({"date":dt, "value":float(v)})
        except: continue
    df = pd.DataFrame(rows)
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    return df.set_index("date")["value"].sort_index()

@st.cache_data(ttl=3600)
def fetch_worldbank(country_code, indicator):
    """World Bank (China & NZ)"""
    url = f"https://api.worldbank.org/v2/country/{country_code}/indicator/{indicator}"
    resp = requests.get(url, params={"format":"json","per_page":1000}).json()
    recs = resp[1] if isinstance(resp,list) and len(resp)>1 else []
    rows=[]
    for r in recs:
        d = r.get("date"); v = r.get("value")
        try:
            dt = pd.to_datetime(f"{d}-01-01"); rows.append({"date":dt,"value":float(v)})
        except: continue
    df=pd.DataFrame(rows)
    df["value"]=pd.to_numeric(df["value"],errors="coerce")
    return df.set_index("date")["value"].sort_index()

# --- Helper: Series je nach Land+Indikator ---
def get_series(country):
    if indicator=="Unemployment Rate":
        if country=="USA": return fetch_usa("UNRATE")
        if country=="Eurozone": return fetch_eurostat("une_rt_m","?precision=1&unit=PC_ACT&geo=EU27_2020")
        if country=="UK": return fetch_uk_unemp()
        if country=="Germany": return fetch_germany("43121-0002")
        if country=="Australia": return fetch_abs("6202.0")
        if country=="New Zealand": return fetch_statsnz("LBUR5")
        if country=="Japan": return fetch_estat(API_KEYS["E_STAT"],"000336113")
        if country=="Switzerland": return fetch_pxweb("https://www.pxweb.bfs.admin.ch/api/v1/de/px.json/ch.statistik.bfs.statistiken/LM06")
        if country=="Canada": return fetch_statcan("14-10-0287-01")
        if country=="China": return fetch_worldbank("CN", WB_UNEMPLOY_IND)
    if indicator=="Monthly Inflation Rate":
        if country=="USA": 
            idx=fetch_usa("CPIAUCSL"); return idx.pct_change(1)*100
        if country=="Eurozone": return fetch_eurostat("prc_hicp_midx","?precision=1&unitCode=I15")
        if country=="UK":
            idx=fetch_uk_cpi(); return idx.pct_change(1)*100
        if country=="Germany":
            idx=fetch_germany("43121-0002"); return idx.pct_change(1)*100
        if country=="Australia":
            idx=fetch_abs("6401.0"); return idx.pct_change(1)*100
        if country=="New Zealand":
            idx=fetch_statsnz("PEZRD"); return idx.pct_change(1)*100
        if country=="Japan":
            idx=fetch_estat(API_KEYS["E_STAT"],"000341231"); return idx.pct_change(1)*100
        if country=="Switzerland":
            idx=fetch_pxweb("https://www.pxweb.bfs.admin.ch/api/v1/de/px.json/ch.statistik.bfs.statistiken/PRICES"); return idx.pct_change(1)*100
        if country=="Canada":
            idx=fetch_statcan("18-10-0004-01"); return idx.pct_change(1)*100
        if country=="China": return pd.Series(dtype=float)
    if indicator=="Annual Inflation Rate":
        if country=="USA":
            idx=fetch_usa("CPIAUCSL"); return idx.pct_change(12)*100
        if country=="Eurozone": 
            m=fetch_eurostat("prc_hicp_midx","?precision=1&unitCode=I15"); return m.pct_change(12)*100
        if country=="UK":
            idx=fetch_uk_cpi(); return idx.pct_change(12)*100
        if country=="Germany":
            idx=fetch_germany("43121-0002"); return idx.pct_change(12)*100
        if country=="Australia":
            idx=fetch_abs("6401.0"); return idx.pct_change(12)*100
        if country=="New Zealand":
            idx=fetch_statsnz("PEZRD"); return idx.pct_change(12)*100
        if country=="Japan":
            idx=fetch_estat(API_KEYS["E_STAT"],"000341231"); return idx.pct_change(12)*100
        if country=="Switzerland":
            idx=fetch_pxweb("https://www.pxweb.bfs.admin.ch/api/v1/de/px.json/ch.statistik.bfs.statistiken/PRICES"); return idx.pct_change(12)*100
        if country=="Canada":
            idx=fetch_statcan("18-10-0004-01"); return idx.pct_change(12)*100
        if country=="China": return fetch_worldbank("CN", WB_INFLATION_IND)
    return pd.Series(dtype=float)

# --- Renderung ---
if mode=="Grafik":
    fig=px.line()
    for c in countries:
        s=get_series(c)
        if not s.empty:
            fig.add_scatter(x=s.index,y=s.values,mode="lines",name=c)
    st.plotly_chart(fig,use_container_width=True)
else:
    st.subheader(indicator)
    table, dates = {}, []
    # Spalten aus erstem Dataset
    for c in countries:
        s0=get_series(c).sort_index(ascending=False)
        if not s0.empty:
            dates=s0.index[:13]
            break
    cols=[d.strftime("%b %Y") for d in dates]
    for c in countries:
        s=get_series(c).sort_index(ascending=False).head(13).tolist()
        table[c]=[f"{v:.2f}%" if pd.notna(v) else "" for v in s]
    df=pd.DataFrame.from_dict(table,orient="index",columns=cols)
    df.index.name="Land"
    st.dataframe(df)

# Footer
st.markdown("*Datenquellen: native APIs pro Land*")
