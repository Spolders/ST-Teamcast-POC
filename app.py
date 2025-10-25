import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import date, timedelta

st.set_page_config(page_title="Ensemble Forecast – DE-LU DA Spread", layout="wide")

# -------- CONFIG --------
DATA_URL = "https://raw.githubusercontent.com/Spolders/ST-Teamcast-POC/refs/heads/main/Teamcast%20-%20Ensemble.csv"

# -------- DATA LOADER --------
@st.cache_data
def load_data(url: str) -> pd.DataFrame:
    df = pd.read_csv(url)
    # expected columns: Date, Forecasted value, Pseudonym, Actual value, (optional) Absolute Error
    # normalize types
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    if "Forecasted value" in df.columns:
        df["Forecasted value"] = pd.to_numeric(df["Forecasted value"], errors="coerce")
    if "Actual value" in df.columns:
        df["Actual value"] = pd.to_numeric(df["Actual value"], errors="coerce")

    # add normalized forecast_date (calendar day)
    df["Forecast date"] = df["Date"].dt.date

    # compute absolute error if not provided (or if NaNs present)
    if "Absolute Error" not in df.columns:
        df["Absolute Error"] = (df["Forecasted value"] - df["Actual value"]).abs()
    else:
        # ensure numeric and fill if missing
        df["Absolute Error"] = pd.to_numeric(df["Absolute Error"], errors="coerce")
        missing_mask = df["Absolute Error"].isna() & df["Forecasted value"].notna() & df["Actual value"].notna()
        df.loc[missing_mask, "Absolute Error"] = (df.loc[missing_mask, "Forecasted value"] - df.loc[missing_mask, "Actual value"]).abs()

    return df

df = load_data(DATA_URL)

# safety: keep only last 14 days if a longer file is ever uploaded
end_d = date.today()
start_d = end_d - timedelta(days=14)
df_recent = df[(df["Forecast date"] >= start_d) & (df["Forecast date"] <= end_d)].copy()

st.title("Ensemble Forecast German DA Spread")

# -------- BOXPLOT (Distribution by Forecast Date) --------
if df_recent.empty or df_recent["Forecasted value"].dropna().empty:
    st.warning("No forecast data available for the last 14 days.")
else:
    fig_box = px.box(
        df_recent.dropna(subset=["Forecasted value"]),
        x="Forecast date",
        y="Forecasted value",
        points="all",
        labels={"Date of Forecast (D-1)": "Date", "Forecasted value": "Forecast Hi-Lo Spread (€)"},
        title="Distribution of Forecasted Day-Ahead Auction DE-LU Hi-Lo Spreads (Last 14 Days)",
        range_y=[
        min(0, float(df_recent["Forecasted value"].min())),
        max(0, float(df_recent["Forecasted value"].max())),
        ],
    )
    fig_box.update_layout(xaxis_title="Date of Forecast (=D-1)", yaxis_title="DAA Hi-Lo Spread (€)")
    st.plotly_chart(fig_box, use_container_width=True)

st.caption("Data updates daily. Contact us for forward-looking data and API access.")

# -------- BAR CHART (Average Daily Errors by Stream and Ensemble) --------
if df_recent.empty or df_recent["Absolute Error"].dropna().empty:
    st.warning("No error data available to calculate average errors.")
else:
    # per-stream mean absolute error
    per_stream = (
        df_recent
        .dropna(subset=["Pseudonym", "Absolute Error"])
        .groupby("Pseudonym", as_index=False)["Absolute Error"]
        .mean()
        .rename(columns={"Pseudonym": "Name", "Absolute Error": "Average Error"})
    )

    # ensemble statistics per day (mean & median across streams vs actual)
    # keep only rows where both forecast and actual exist
    valid = df_recent.dropna(subset=["Forecasted value", "Actual value"]).copy()
    if not valid.empty:
        daily = (
            valid.groupby("Forecast date")
                 .agg(mean_fc=("Forecasted value", "mean"),
                      median_fc=("Forecasted value", "median"),
                      actual=("Actual value", "first"))
                 .reset_index()
        )
        daily["Mean Error"] = (daily["mean_fc"] - daily["actual"]).abs()
        daily["Median Error"] = (daily["median_fc"] - daily["actual"]).abs()

        ensemble_rows = pd.DataFrame({
            "Name": ["Mean of ensemble", "Median of ensemble"],
            "Average Error": [daily["Mean Error"].mean(), daily["Median Error"].mean()]
        })
    else:
        ensemble_rows = pd.DataFrame({"Name": [], "Average Error": []})

    summary = pd.concat([per_stream, ensemble_rows], ignore_index=True)
    summary = summary.sort_values("Average Error", ascending=True)

    if summary.empty:
        st.warning("Insufficient data to compute the error summary.")
    else:
        bar_fig = px.bar(
            summary,
            x="Average Error",
            y="Name",
            orientation="h",
            title="Average Daily Forecast Error by Stream and Ensemble",
            text="Average Error",
        )
        bar_fig.update_traces(texttemplate="%{text:.2f}", textposition="outside", cliponaxis=False)
        bar_fig.update_layout(
            yaxis={"categoryorder": "total ascending"},
            xaxis_title="Average Absolute Error (€)",
            bargap=0.3,
            margin=dict(l=10, r=10, t=60, b=10)
        )

        st.plotly_chart(bar_fig, use_container_width=True)

st.caption("Data updates daily. Contact us for forward-looking data and API access.")
