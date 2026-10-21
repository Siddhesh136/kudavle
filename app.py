import streamlit as st
import pandas as pd
import plotly.express as px

# ============================================================
# Google Sheets source
# ============================================================
SHEET_URL = (
    "https://docs.google.com/spreadsheets/d/"
    "130S21b85odR4TOI0uoGpBKJBQtN20KLl8118hjllR1Q/edit?usp=sharing"
)

PROFESSION_COL = "Current Profession (सध्याचे नोकरी/पद्)"
STATION_COL = "Current Station/Place"

st.set_page_config(
    page_title="Profession & Station Dashboard",
    page_icon="📊",
    layout="wide",
)

st.markdown(
    """
    <style>
      .block-container {padding-top: 1.5rem; padding-bottom: 2rem;}
      div[data-testid="stMetric"] {
        background: var(--secondary-background-color);
        border: 1px solid rgba(128,128,128,.18);
        padding: 16px 18px;
        border-radius: 14px;
      }
    </style>
    """,
    unsafe_allow_html=True,
)


def make_csv_url(url: str) -> str:
    """Convert the Google Sheets share URL to its GViz CSV export URL."""
    base = url.split("#", 1)[0]
    if "/edit" in base:
        base = base.split("/edit", 1)[0]
    return f"{base}/gviz/tq?tqx=out:csv"


@st.cache_data(ttl=300, show_spinner="Loading the latest Google Sheets data…")
def load_data(csv_url: str) -> pd.DataFrame:
    df = pd.read_csv(csv_url)
    df.columns = df.columns.astype(str).str.strip()
    df = df.dropna(how="all").dropna(axis=1, how="all")
    return df


def resolve_column(columns, preferred_name):
    """Find exact column first; otherwise match normalized header text."""
    if preferred_name in columns:
        return preferred_name
    normalize = lambda s: " ".join(str(s).strip().lower().split())
    target = normalize(preferred_name)
    matches = [c for c in columns if normalize(c) == target]
    if matches:
        return matches[0]
    # Fallback supports small differences in punctuation/spacing.
    target_compact = "".join(ch for ch in target if ch.isalnum())
    for col in columns:
        compact = "".join(ch for ch in normalize(col) if ch.isalnum())
        if compact == target_compact:
            return col
    return None


# ============================================================
# Header and refresh
# ============================================================
head, refresh_col = st.columns([5, 1])
with head:
    st.title("📊 Profession & Current Station Dashboard")
    st.caption(
        "Explore the distribution of current professions and places/stations "
        "from your Google Sheet."
    )
with refresh_col:
    st.write("")
    if st.button("🔄 Refresh Data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

try:
    df = load_data(make_csv_url(SHEET_URL))
except Exception as exc:
    st.error(
        "Could not load the Google Sheet. Confirm that the sheet is accessible "
        "through CSV export (for example, shared as Anyone with the link — Viewer)."
    )
    with st.expander("Technical details"):
        st.code(str(exc))
    st.link_button("Open Google Sheet", SHEET_URL)
    st.stop()

if df.empty:
    st.warning("The Google Sheet returned no data.")
    st.stop()

profession_col = resolve_column(df.columns, PROFESSION_COL)
station_col = resolve_column(df.columns, STATION_COL)

missing = []
if profession_col is None:
    missing.append(PROFESSION_COL)
if station_col is None:
    missing.append(STATION_COL)

if missing:
    st.error("Could not find the following expected column(s) in the sheet:")
    for name in missing:
        st.write(f"- `{name}`")
    st.write("Available columns:")
    st.code("\n".join(map(str, df.columns)))
    st.info(
        "Update PROFESSION_COL or STATION_COL near the top of app.py to match "
        "the exact header text in your worksheet."
    )
    st.stop()

# Treat blank values consistently in filters and charts.
data = df.copy()
for col in [profession_col, station_col]:
    data[col] = data[col].astype("string").str.strip()
    data[col] = data[col].replace("", pd.NA)

# ============================================================
# Sidebar filters
# ============================================================
st.sidebar.header("🔎 Filters")

profession_options = sorted(data[profession_col].dropna().unique().tolist(), key=str.casefold)
station_options = sorted(data[station_col].dropna().unique().tolist(), key=str.casefold)

selected_professions = st.sidebar.multiselect(
    "Current Profession (सध्याचे नोकरी/पद्)",
    options=profession_options,
    default=[],
    placeholder="All professions",
)
selected_stations = st.sidebar.multiselect(
    "Current Station/Place",
    options=station_options,
    default=[],
    placeholder="All stations/places",
)

filtered = data.copy()
if selected_professions:
    filtered = filtered[filtered[profession_col].isin(selected_professions)]
if selected_stations:
    filtered = filtered[filtered[station_col].isin(selected_stations)]

st.sidebar.divider()
st.sidebar.caption(f"Source records: {len(data):,}")
st.sidebar.caption(f"Filtered records: {len(filtered):,}")
st.sidebar.caption("No selection means all values.")

# ============================================================
# KPI summary
# ============================================================
st.subheader("Overview")
k1, k2, k3 = st.columns(3)
k1.metric("Filtered Records", f"{len(filtered):,}")
k2.metric(
    "Unique Professions",
    f"{filtered[profession_col].nunique(dropna=True):,}",
)
k3.metric(
    "Unique Stations / Places",
    f"{filtered[station_col].nunique(dropna=True):,}",
)

st.divider()

# ============================================================
# Charts
# ============================================================
left, right = st.columns(2, gap="large")

with left:
    st.subheader("👔 Current Profession")
    profession_counts = (
        filtered[profession_col]
        .dropna()
        .value_counts()
        .rename_axis("Profession")
        .reset_index(name="People / Records")
    )
    if not profession_counts.empty:
        chart_type = st.radio(
            "Profession chart style",
            ["Bar chart", "Donut chart"],
            horizontal=True,
            key="profession_chart_type",
        )
        if chart_type == "Bar chart":
            fig = px.bar(
                profession_counts.sort_values("People / Records"),
                x="People / Records",
                y="Profession",
                orientation="h",
                text="People / Records",
                title="Records by current profession",
                template="plotly_white",
            )
        else:
            fig = px.pie(
                profession_counts,
                names="Profession",
                values="People / Records",
                hole=0.48,
                title="Profession distribution",
                template="plotly_white",
            )
        fig.update_layout(margin=dict(l=10, r=10, t=55, b=10))
        st.plotly_chart(fig, use_container_width=True)
        with st.expander("Profession count table"):
            st.dataframe(profession_counts, use_container_width=True, hide_index=True)
    else:
        st.info("No profession values match the selected filters.")

with right:
    st.subheader("📍 Place overview")

    station_counts = (
        filtered[station_col]
        .dropna()
        .value_counts()
        .rename_axis("Station / Place")
        .reset_index(name="People / Records")
    )

    if not station_counts.empty:
        fig = px.pie(
            station_counts,
            names="Station / Place",
            values="People / Records",
            hole=0.0,
            title="Distribution by Current Station / Place",
            template="plotly_white",
        )

        fig.update_traces(
            textposition="inside",
            textinfo="percent+label",
            hovertemplate=(
                "<b>%{label}</b><br>"
                "Records: %{value}<br>"
                "Share: %{percent}"
                "<extra></extra>"
            ),
        )

        fig.update_layout(
            margin=dict(l=10, r=10, t=55, b=10),
            legend_title_text="Station / Place",
        )

        st.plotly_chart(fig, use_container_width=True)

        with st.expander("Place count details"):
            st.dataframe(
                station_counts,
                use_container_width=True,
                hide_index=True,
            )
    else:
        st.info("No station/place values match the selected filters.")
        
# Cross-analysis
st.divider()
st.subheader("Profession × Station / Place")
cross = filtered.dropna(subset=[profession_col, station_col])
if not cross.empty:
    cross_tab = pd.crosstab(
        cross[profession_col],
        cross[station_col],
    )
    fig = px.imshow(
        cross_tab,
        labels=dict(x="Current Station / Place", y="Current Profession", color="Records"),
        aspect="auto",
        title="Heatmap of profession by station / place",
        text_auto=True,
        color_continuous_scale="Blues",
    )
    fig.update_layout(margin=dict(l=10, r=10, t=60, b=10))
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No rows have both profession and station/place values.")

# ============================================================
# Filtered records and export
# ============================================================
st.divider()
st.subheader("📋 Filtered Records")
st.caption(f"Showing {len(filtered):,} of {len(data):,} source rows.")
st.dataframe(filtered, use_container_width=True, hide_index=True)

st.download_button(
    "⬇️ Download filtered records (CSV)",
    data=filtered.to_csv(index=False).encode("utf-8-sig"),
    file_name="profession_station_filtered.csv",
    mime="text/csv",
)

st.caption("Data is cached for up to 5 minutes. Use Refresh Data to fetch the sheet again.")
