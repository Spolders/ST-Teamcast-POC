import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import date, timedelta

px.defaults.template = "plotly_dark"

def darkify(fig):
    return fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)"
    )

st.set_page_config(page_title="Ensemble Forecast – DE-LU DA Spread", layout="wide")

# -------- CONFIG --------
DATA_URL = "https://raw.githubusercontent.com/Spolders/ST-Teamcast-POC/refs/heads/main/data/Teamcast-Ensemble.csv"

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

st.title("Collaborative Forecast German DA Spread")

# -------- BOXPLOT (Distribution by Forecast Date) --------
if df_recent.empty or df_recent["Forecasted value"].dropna().empty:
    st.warning("No forecast data available for the last 14 days.")
else:
    # Make a label column for categorical x and fix the sort order
    df_recent = df_recent.copy()
    df_recent["date_label"] = pd.to_datetime(df_recent["Forecast date"]).dt.strftime("%Y-%m-%d")
    order = sorted(df_recent["date_label"].unique())

    # compute bounds
    ymin = float(df_recent["Forecasted value"].min())
    ymax = float(df_recent["Forecasted value"].max())

    fig_box = px.box(
        df_recent.dropna(subset=["Forecasted value"]),
        x="date_label",
        y="Forecasted value",
        points="all",
        labels={
            "date_label": "Date of Forecast (=D-1)",
            "Forecasted value": "Forecast Hi-Lo Spread (€)",
        },
        title="Ensemble Forecast of Day-Ahead Auction DE-LU Hi-Lo Spreads (Last 14 Days)",
        range_y=[min(0.0, ymin), ymax + 50],
    )
    
    fig_box.update_layout(xaxis_title="Date of Forecast (=D-1)", yaxis_title="DAA Hi-Lo Spread (€)")
    st.plotly_chart(fig_box, use_container_width=True)

st.caption("Data updates daily. Contact us for forward-looking data and API access.")

# -------- BAR CHART (Forecaster Ranking by Mean Absolute Error) --------
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
            title="Ranking: Mean Absolute Forecast Error by Forecaster and Ensemble (Last 14 Days)",
            text="Average Error",
        )
        bar_fig.update_traces(texttemplate="%{text:.2f}", textposition="outside", cliponaxis=False)
        bar_fig.update_layout(
            yaxis={"categoryorder": "total descending"},
            yaxis_title="Forecaster Name or Nickname",
            xaxis_title="Mean Absolute Error (€)",
            bargap=0.3,
            margin=dict(l=10, r=10, t=60, b=10)
        )
        bar_fig.update_traces(
        hovertemplate="%{y}<br>Avg Error: %{x:.2f}€<extra></extra>"
        )

        st.plotly_chart(bar_fig, use_container_width=True)

st.caption("Data updates daily. Contact us for forward-looking data and API access.")
