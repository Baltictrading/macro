import streamlit as st
import pandas as pd
from pandas_datareader import data as web
import datetime

# Page config
st.set_page_config(page_title="US Macro Dashboard", layout="wide")

st.title("US Macro Dashboard")

# Define time range: past year
today = datetime.date.today()
start = today - datetime.timedelta(days=365)

# FRED series mapping
indicators = {
    'Interest Rate (Fed Funds Rate)': 'FEDFUNDS',
    'Unemployment Rate': 'UNRATE',
    'CPI (Monthly)': 'CPIAUCSL',
    'Nonfarm Payrolls': 'PAYEMS',
    'PPI (All Commodities)': 'PPIACO',
    'ISM Manufacturing PMI': 'NAPM',
    'ISM Services PMI': 'NAPME',  # adjust if needed
    'New Home Sales': 'HSN1F',
    'GDP (Quarterly)': 'GDP',
    'Consumer Confidence': 'UMCSENT',
    'Retail Sales MoM': 'RSXFS',
    'Balance of Trade': 'NETEXP'
}

# Fetch data
df = pd.DataFrame()
for name, series in indicators.items():
    try:
        s = web.DataReader(series, 'fred', start, today)
        s = s.resample('M').last()
        if name == 'CPI (Monthly)':
            # calculate YoY for CPI
            df['CPI YoY %'] = s.pct_change(periods=12) * 100
            df['CPI Monthly'] = s
        else:
            df[name] = s
    except Exception as e:
        st.error(f"Error fetching {name}: {e}")

# Prepare table: current value and history
history = df.copy()

# Display table
st.subheader("Indicator Table: Current & Monthly (Past Year)")
st.dataframe(history.T)

# Plot chart
st.subheader("Indicator Trends Over Past Year")
st.line_chart(df)

st.write("Data source: FRED via pandas_datareader")
