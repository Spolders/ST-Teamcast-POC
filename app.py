import streamlit as st
import pandas as pd
import plotly.express as px
import datetime

@st.cache_data

def load_spread_data():
    url = "https://raw.githubusercontent.com/Spolders/teamcast/refs/heads/main/forecasts"
    df = pd.read_csv(url)
    df['Forecast date'] = pd.to_datetime(df['Forecast date'])
    df['Forecasted value'] = pd.to_numeric(df['Forecasted value'], errors='coerce')
    return df

# --- LOAD DATA ---
df = load_spread_data()

# Filter for last 14 days
end_date = datetime.date.today()
start_date = end_date - datetime.timedelta(days=14)

recent_df = df[(df['Forecast date'].dt.date >= start_date) & (df['Forecast date'].dt.date <= end_date)]

# Create boxplot
if recent_df.empty:
    st.warning("No forecast data available for the last 14 days.")
else:
    st.title("Ensemble Forecast German DA Spread")

    fig = px.box(
        recent_df,
        x=recent_df['Forecast date'].dt.date,
        y="Forecasted value",
        points="all",  # show individual forecasts as dots
        labels={"Forecast date": "Date", "Forecasted value": "Forecast Hi-Lo Spread (€)"},
        title="Distribution of Forecasted Day-Ahead Auction DE-LU Hi-Lo Spreads - Last 14 Days"
    )

    fig.update_layout(xaxis_title="Forecast Date", yaxis_title="Hi-Lo Spread (€)")

    st.plotly_chart(fig, use_container_width=True)

st.caption("Data updates daily. Contact us for forward-looking data, bidding algos, and/or API access.")

# --- BAR CHART: Average Daily Errors by Stream and Ensemble ---

# Normalize date
recent_df['Forecast date'] = pd.to_datetime(recent_df['Forecast date']).dt.date

# 1. Calculate absolute error for each forecast
recent_df['Absolute Error'] = abs(recent_df['Forecasted value'] - recent_df['Actual value'])

# 2. Average absolute error per stream
stream_avg = recent_df.groupby('Stream')['Absolute Error'].mean().reset_index()
stream_avg.columns = ['Name', 'Average Error']

# 3. Ensemble errors per day
ensemble = recent_df.groupby('Forecast date').agg({
    'Forecasted value': ['mean', 'median'],
    'Actual value': 'first'
}).reset_index()
ensemble.columns = ['Forecast date', 'Mean Forecast', 'Median Forecast', 'Actual value']
ensemble['Mean Error'] = abs(ensemble['Mean Forecast'] - ensemble['Actual value'])
ensemble['Median Error'] = abs(ensemble['Median Forecast'] - ensemble['Actual value'])

# 4. Combine all into one summary DataFrame
summary = pd.concat([
    stream_avg,
    pd.DataFrame({
        'Name': ['Mean of 4', 'Median of 4'],
        'Average Error': [ensemble['Mean Error'].mean(), ensemble['Median Error'].mean()]
    })
]).sort_values('Average Error')

# 5. Plot horizontal bar chart
bar_fig = px.bar(
    summary,
    x='Average Error',
    y='Name',
    orientation='h',
    title="Average Daily Forecast Error by Stream and Ensemble",
    text='Average Error',
    text_auto='.2f',
    labels={'Name': 'Stream / Ensemble', 'Average Error': 'Avg Absolute Error (€)'}
)

bar_fig.update_layout(
    yaxis={'categoryorder': 'total descending'},
    xaxis_title="Average Absolute Error (€)",
    bargap=0.3
)

st.plotly_chart(bar_fig, use_container_width=True)

st.caption("Data updates daily. Contact us for forward-looking data, bidding algos, and/or API access.")
