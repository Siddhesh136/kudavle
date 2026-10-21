
import streamlit as st
import pandas as pd
import plotly.express as px
from urllib.parse import urlsplit, urlunsplit

# --------------------------------------------------
# Page configuration
# --------------------------------------------------
st.set_page_config(
    page_title="Google Sheets Analytics Dashboard",
    page_icon="📊",
    layout="wide",
)

st.title("📊 Google Sheets Analytics Dashboard")
st.caption("Live data dashboard powered by Google Sheets, pandas and Plotly")

# --------------------------------------------------
# Google Sheet configuration
# --------------------------------------------------
SHEET_URL = (
    "https://docs.google.com/spreadsheets/d/"
    "130S21b85odR4TOI0uoGpBKJBQtN20KLl8118hjllR1Q/edit?usp=sharing"
)


def make_csv_url(url: str) -> str:
    """Convert a standard Google Sheets URL to its CSV export URL."""
    url = url.split("#")[0]
    url = url.replace("/edit?usp=sharing", "/gviz/tq?tqx=out:csv")

    # Also support common Google Sheets URL variants.
    if "/edit" in url:
        url = url.split("/edit")[0] + "/gviz/tq?tqx=out:csv"

    return url


# --------------------------------------------------
# Data loading and caching
# --------------------------------------------------
@st.cache_data(ttl=300, show_spinner="Loading Google Sheets data...")
def load_data(sheet_url: str) -> pd.DataFrame:
    """Read the published/shared Google Sheet CSV into a DataFrame."""
    csv_url = make_csv_url(sheet_url)

    df = pd.read_csv(csv_url)

    # Normalize column headers.
    df.columns = df.columns.astype(str).str.strip()

    # Remove completely empty rows and columns.
    df = df.dropna(how="all").dropna(axis=1, how="all")

    # Convert text that looks numeric to numeric data.
    for col in df.columns:
        if df[col].dtype == "object":
            cleaned = df[col].astype("string").str.strip()
            numeric = pd.to_numeric(
                cleaned.str.replace(",", "", regex=False),
                errors="coerce",
            )
            if numeric.notna().sum() > 0 and numeric.notna().mean() >= 0.8:
                df[col] = numeric

    return df


# --------------------------------------------------
# Refresh button
# --------------------------------------------------
if st.button("🔄 Refresh Data"):
    st.cache_data.clear()
    st.rerun()

# --------------------------------------------------
# Load data safely
# --------------------------------------------------
try:
    df = load_data(SHEET_URL)

    if df.empty:
        st.warning(
            "The sheet returned no data. Check that the correct worksheet "
            "contains data and that the sheet is accessible."
        )
        st.stop()

except Exception as exc:
    st.error(
        "Could not load the Google Sheet. Make sure the spreadsheet is "
        "shared with access appropriate for CSV export, and check the URL "
        "and worksheet permissions."
    )
    with st.expander("Technical details"):
        st.code(str(exc))
    st.stop()

# --------------------------------------------------
# Identify columns
# --------------------------------------------------
all_columns = df.columns.tolist()

numeric_columns = df.select_dtypes(include="number").columns.tolist()

date_columns = []
for col in all_columns:
    if col in numeric_columns:
        continue

    parsed = pd.to_datetime(df[col], errors="coerce")
    if len(df) > 0 and parsed.notna().mean() >= 0.8:
        date_columns.append(col)

categorical_columns = [
    col for col in all_columns
    if col not in numeric_columns and col not in date_columns
]

# --------------------------------------------------
# Sidebar filters
# --------------------------------------------------
st.sidebar.header("🔎 Dashboard Filters")

filter_options = ["All data"] + categorical_columns
filter_column = st.sidebar.selectbox(
    "Filter by column",
    options=filter_options,
)

filtered_df = df.copy()

if filter_column != "All data":
    values = (
        filtered_df[filter_column]
        .dropna()
        .astype(str)
        .sort_values()
        .unique()
        .tolist()
    )

    selected_values = st.sidebar.multiselect(
        f"Select {filter_column}",
        options=values,
        default=values,
    )

    # If nothing is selected, show no rows rather than all rows.
    if selected_values:
        filtered_df = filtered_df[
            filtered_df[filter_column].astype(str).isin(selected_values)
        ]
    else:
        filtered_df = filtered_df.iloc[0:0]

st.sidebar.divider()
st.sidebar.caption(f"Rows in source: {len(df):,}")
st.sidebar.caption(f"Rows after filtering: {len(filtered_df):,}")

# --------------------------------------------------
# KPI metrics
# --------------------------------------------------
st.subheader("Key Metrics")

kpi1, kpi2, kpi3 = st.columns(3)

with kpi1:
    st.metric("Total Records", f"{len(filtered_df):,}")

with kpi2:
    st.metric("Total Columns", f"{len(all_columns):,}")

with kpi3:
    if numeric_columns:
        default_metric = numeric_columns[0]
        metric_col = st.selectbox(
            "Metric column",
            options=numeric_columns,
            index=0,
            key="kpi_metric_column",
        )
        metric_total = filtered_df[metric_col].sum()
        st.metric(
            f"Total {metric_col}",
            f"{metric_total:,.2f}",
        )
    else:
        st.metric("Non-empty Cells", f"{filtered_df.notna().sum().sum():,}")

st.divider()

# --------------------------------------------------
# Interactive charts
# --------------------------------------------------
st.subheader("Interactive Analysis")

chart_left, chart_right = st.columns(2)

# Chart 1: Line chart
with chart_left:
    st.markdown("#### 📈 Trend Analysis")

    if numeric_columns and (date_columns or categorical_columns):
        x_candidates = date_columns + categorical_columns

        x_col = st.selectbox(
            "X-axis",
            options=x_candidates,
            key="line_x",
        )

        y_col = st.selectbox(
            "Value",
            options=numeric_columns,
            key="line_y",
        )

        plot_df = filtered_df.copy()

        if x_col in date_columns:
            plot_df[x_col] = pd.to_datetime(
                plot_df[x_col], errors="coerce"
            )

        plot_df = plot_df.dropna(subset=[x_col, y_col])

        if not plot_df.empty:
            # Aggregate duplicate dates/categories for a readable trend.
            line_df = (
                plot_df.groupby(x_col, as_index=False)[y_col]
                .sum()
                .sort_values(x_col)
            )

            fig_line = px.line(
                line_df,
                x=x_col,
                y=y_col,
                markers=True,
                title=f"{y_col} by {x_col}",
                template="plotly_white",
            )
            fig_line.update_layout(
                margin=dict(l=10, r=10, t=55, b=10),
                hovermode="x unified",
            )
            st.plotly_chart(fig_line, use_container_width=True)
        else:
            st.info("No usable data for the selected line chart.")
    else:
        st.info(
            "A line chart requires at least one numeric column and one "
            "date or category column."
        )

# Chart 2: Bar chart
with chart_right:
    st.markdown("#### 📊 Category Comparison")

    if numeric_columns and categorical_columns:
        bar_x = st.selectbox(
            "Category",
            options=categorical_columns,
            key="bar_x",
        )

        bar_y = st.selectbox(
            "Measure",
            options=numeric_columns,
            key="bar_y",
        )

        top_n = st.slider(
            "Number of categories",
            min_value=3,
            max_value=20,
            value=10,
            key="bar_top_n",
        )

        plot_df = filtered_df.dropna(subset=[bar_x, bar_y]).copy()
        plot_df[bar_x] = plot_df[bar_x].astype(str)

        bar_df = (
            plot_df.groupby(bar_x, as_index=False)[bar_y]
            .sum()
            .sort_values(bar_y, ascending=False)
            .head(top_n)
        )

        if not bar_df.empty:
            fig_bar = px.bar(
                bar_df,
                x=bar_x,
                y=bar_y,
                title=f"{bar_y} by {bar_x}",
                template="plotly_white",
                text_auto=".3s",
            )
            fig_bar.update_layout(
                margin=dict(l=10, r=10, t=55, b=10),
                xaxis_title=bar_x,
                yaxis_title=bar_y,
            )
            st.plotly_chart(fig_bar, use_container_width=True)
        else:
            st.info("No usable data for the selected bar chart.")
    else:
        st.info(
            "A bar chart requires at least one numeric column and one "
            "categorical column."
        )

# --------------------------------------------------
# Data table
# --------------------------------------------------
st.divider()
st.subheader("📋 Filtered Data")

st.caption(
    f"Showing {len(filtered_df):,} of {len(df):,} source rows."
)

st.dataframe(
    filtered_df,
    use_container_width=True,
    hide_index=True,
)

csv_data = filtered_df.to_csv(index=False).encode("utf-8")

st.download_button(
    label="⬇️ Download filtered data as CSV",
    data=csv_data,
    file_name="filtered_google_sheet_data.csv",
    mime="text/csv",
)

st.caption("Data is cached for up to 5 minutes. Use Refresh Data to reload it.")
