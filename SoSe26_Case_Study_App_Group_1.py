"""
Executive Quality Dashboard – Automotive Component & Transmission Analysis
Single-file Streamlit application.

Business questions answered (per case study "205"):
  1. Market share of "205" parts vs. competitors.
  2. "In every xth gearbox there are parts from 205" – advertising metric.
  3. Relative defect frequency of "205" parts vs. competitors.
  4. Defect propagation: a gearbox is treated as defective if ANY of its
     installed parts is defective.

All rate/share figures below are computed as sum(numerator) / sum(denominator)
across the filtered scope. A pre-aggregated dataset like this one must never
have its ratio columns (market_share, defect_frequency, every_xth_gearbox)
averaged directly, since the underlying group sizes differ substantially –
doing so silently over- or under-states the headline numbers.
"""

from __future__ import annotations

import io
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
DATASET_PATH = "SoSe26_Case_Study_finalData_Group_01.csv"
LOGO_PATH = "www/data-analytics-logo.jpg"
APP_DIR = Path(__file__).resolve().parent
FOCUS_MANUFACTURER = 205


# ---------------------------------------------------------------------------
# Data Loading & Preparation
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def load_data() -> pd.DataFrame:
    """Load the single final processed dataset (no raw source files)."""
    csv_path = APP_DIR / DATASET_PATH
    if not csv_path.exists():
        st.error(
            f"Dataset not found at `{csv_path}`. "
            f"Please place `{DATASET_PATH}` in the same directory as app.py."
        )
        st.stop()
    return pd.read_csv(csv_path)


@st.cache_data(show_spinner=False)
def split_records(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split the long-format dataset into its two record types."""
    df_cat = df.copy()
    for col in ["record_type", "gearbox_family", "part_type"]:
        if col in df_cat.columns:
            df_cat[col] = df_cat[col].astype("category")

    parts = df_cat[df_cat["record_type"] == "part_summary"].dropna(how="all", axis=1).copy()
    gearboxes = df_cat[df_cat["record_type"] == "gearbox_summary"].dropna(how="all", axis=1).copy()
    return parts, gearboxes


# ---------------------------------------------------------------------------
# Styling
# ---------------------------------------------------------------------------
def inject_custom_css() -> None:
    """Inject styling for header, icon fonts, and specific widget colors."""
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Source+Sans+Pro:wght@300;400;600;700&display=swap');

        [data-testid="stHeader"] {
            background-color: transparent !important;
            background: transparent !important;
        }

        [data-testid="stSidebarCollapseButton"] *,
        [data-testid="stSidebarExpandButton"] *,
        [data-testid="stHeader"] *,
        .material-icons,
        [class*="material-symbols"] {
            font-family: 'Material Symbols Outlined', 'Material Icons' !important;
        }

        div[data-baseweb="select"] > div,
        div[data-baseweb="input"] > div {
            background-color: #FFFFFF !important;
            border-color: #FFFFFF !important;
        }

        div[data-baseweb="select"] input,
        div[data-baseweb="input"] input {
            color: #000000 !important;
            -webkit-text-fill-color: #000000 !important;
        }

        div[data-baseweb="input"] input::placeholder {
            color: #666666 !important;
            -webkit-text-fill-color: #666666 !important;
        }

        span[data-baseweb="tag"] {
            background-color: #0D47A1 !important;
            color: #FFFFFF !important;
            border: none !important;
        }
        span[data-baseweb="tag"] span,
        span[data-baseweb="tag"] svg {
            color: #FFFFFF !important;
            fill: #FFFFFF !important;
        }

        button[kind="primary"] {
            background-color: #0D47A1 !important;
            color: #FFFFFF !important;
            border: none !important;
        }
        button[kind="primary"]:hover {
            background-color: #1E88E5 !important;
        }
        button[kind="primary"] * {
            color: #FFFFFF !important;
        }

        .dashboard-header {
            background: linear-gradient(to left, #74B0FF, #1E69CB);
            color: white !important;
            padding: 1.2rem 1.5rem;
            border-radius: 12px;
            margin-bottom: 1.5rem;
        }
        .dashboard-header h1 {
            color: white !important;
            margin: 0;
            font-size: 1.8rem;
        }
        .dashboard-header p {
            margin: 0.3rem 0 0 0;
            opacity: 0.92;
            color: white !important;
        }

        div[data-testid="stMetric"] {
            background: #E3F2FD;
            border: 1px solid #64B5F6;
            border-radius: 12px;
            padding: 14px 16px;
        }
        div[data-testid="stMetric"] label {
            color: #0D47A1 !important;
            font-weight: 600 !important;
        }
        div[data-testid="stMetric"] [data-testid="stMetricValue"] {
            color: #1E88E5 !important;
            font-weight: 700 !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Filtering helpers
# ---------------------------------------------------------------------------
def apply_part_filters(
    parts: pd.DataFrame,
    year_range: tuple[int, int],
    vehicle_types: list,
    families: list,
    part_types: list,
    manufacturers: list,
) -> pd.DataFrame:
    """Filter the parts table to the selected analysis period and scope."""
    start_year, end_year = year_range
    mask = (
        parts["vehicle_year"].between(start_year, end_year)
        & parts["vehicle_type"].isin(vehicle_types)
        & parts["gearbox_family"].isin(families)
        & parts["part_type"].isin(part_types)
        & parts["part_manufacturer"].isin(manufacturers)
    )
    return parts.loc[mask].copy()


def apply_gearbox_filters(
    gearboxes: pd.DataFrame,
    year_range: tuple[int, int],
    vehicle_types: list,
    families: list,
) -> pd.DataFrame:
    """Filter the gearbox table to the selected analysis period and scope."""
    start_year, end_year = year_range
    mask = (
        gearboxes["vehicle_year"].between(start_year, end_year)
        & gearboxes["vehicle_type"].isin(vehicle_types)
        & gearboxes["gearbox_family"].isin(families)
    )
    return gearboxes.loc[mask].copy()


def manufacturer_label(value) -> str:
    return f"Mfr {int(value)}"


# ---------------------------------------------------------------------------
# Correct, volume-weighted business calculations
# ---------------------------------------------------------------------------
def weighted_rate(df: pd.DataFrame, group_cols: list) -> pd.DataFrame:
    """
    Aggregate defect rate correctly as sum(defective_parts) / sum(installed_parts)
    per group. This must never be the mean of the pre-computed 'defect_frequency'
    column, since groups can carry very different installed volumes and an
    unweighted mean overweights small groups.
    """
    columns = group_cols + ["installed_parts", "defective_parts", "defect_pct"]
    if df.empty:
        return pd.DataFrame(columns=columns)

    grouped = df.groupby(group_cols, as_index=False, observed=True).agg(
        installed_parts=("installed_parts", "sum"),
        defective_parts=("defective_parts", "sum"),
    )
    safe_denom = grouped["installed_parts"].replace(0, pd.NA)
    grouped["defect_pct"] = (grouped["defective_parts"] / safe_denom * 100).fillna(0.0)
    return grouped


def compute_market_share(df: pd.DataFrame) -> pd.DataFrame:
    """
    Volume-weighted market share per manufacturer: each manufacturer's share
    of total installed parts in the filtered scope. Never the mean of the
    pre-computed 'market_share' column, which would conflate part-type
    segments of very different sizes.
    """
    columns = ["part_manufacturer", "manufacturer_label", "installed_parts", "share_pct"]
    if df.empty:
        return pd.DataFrame(columns=columns)

    grouped = df.groupby("part_manufacturer", as_index=False, observed=True)["installed_parts"].sum()
    total = grouped["installed_parts"].sum()
    grouped["share_pct"] = (grouped["installed_parts"] / total * 100) if total else 0.0
    grouped["manufacturer_label"] = grouped["part_manufacturer"].apply(manufacturer_label)
    return grouped


def compute_every_xth_gearbox(filtered_gearboxes: pd.DataFrame) -> float:
    """
    Weighted 'in every xth gearbox there are parts from 205' figure.
    Computed as sum(gearboxes_total) / sum(gearboxes_with_205) across the
    filtered scope – never the mean of the pre-computed 'every_xth_gearbox'
    ratio column, which mixes gearbox families with very different
    penetration rates and produces a number that matches neither.
    """
    if filtered_gearboxes.empty:
        return float("nan")
    total = filtered_gearboxes["gearboxes_total"].sum()
    with_205 = filtered_gearboxes["gearboxes_with_205"].sum()
    return (total / with_205) if with_205 else float("nan")


def compute_relative_defect_index(df: pd.DataFrame, group_col: str = "part_type") -> pd.DataFrame:
    """
    Relative defect frequency: for each (group, manufacturer), express that
    manufacturer's defect rate as a percentage of the combined rate of every
    OTHER manufacturer active in the same group.

        index = own_rate / competitor_rate * 100

    100  -> exactly on par with the competition
    <100 -> fewer defects than the competition (better)
    >100 -> more defects than the competition (worse)

    This is the literal "relative defect frequency ... in comparison to the
    competition" the case study asks for, as opposed to plotting raw defect
    rates side by side (which, on this dataset, all cluster near ~10% and
    are visually indistinguishable even though real differences exist).
    """
    columns = [group_col, "part_manufacturer", "own_rate_pct", "competitor_rate_pct", "relative_index_pct"]
    if df.empty:
        return pd.DataFrame(columns=columns)

    per_group_mfr = df.groupby([group_col, "part_manufacturer"], as_index=False, observed=True).agg(
        installed_parts=("installed_parts", "sum"),
        defective_parts=("defective_parts", "sum"),
    )
    group_totals = df.groupby(group_col, observed=True).agg(
        total_installed=("installed_parts", "sum"),
        total_defective=("defective_parts", "sum"),
    )
    merged = per_group_mfr.merge(group_totals, left_on=group_col, right_index=True)

    own_denom = merged["installed_parts"].replace(0, pd.NA)
    merged["own_rate_pct"] = (merged["defective_parts"] / own_denom * 100).fillna(0.0)

    competitor_installed = merged["total_installed"] - merged["installed_parts"]
    competitor_defective = merged["total_defective"] - merged["defective_parts"]
    comp_denom = competitor_installed.replace(0, pd.NA)
    merged["competitor_rate_pct"] = (competitor_defective / comp_denom * 100)

    merged["relative_index_pct"] = merged["own_rate_pct"] / merged["competitor_rate_pct"].replace(0, pd.NA) * 100
    # NaN means this manufacturer had no competitor in the group under the current
    # filters (sole supplier) -> the comparison is undefined, not "at parity".

    return merged[columns]


def compute_205_market_share(filtered_parts: pd.DataFrame) -> float:
    """
    Overall market share of manufacturer 205, restricted to the part types
    that 205 actually supplies. Including part types 205 doesn't compete in
    at all would artificially dilute their share within the segments where
    they do compete.
    """
    mfr205 = filtered_parts[filtered_parts["part_manufacturer"] == FOCUS_MANUFACTURER]
    if mfr205.empty:
        return 0.0
    active_types = mfr205["part_type"].unique()
    scope = filtered_parts[filtered_parts["part_type"].isin(active_types)]
    scope_installed = scope["installed_parts"].sum()
    mfr205_installed = mfr205["installed_parts"].sum()
    return (mfr205_installed / scope_installed * 100) if scope_installed else 0.0


def compute_gearbox_defect_probability(filtered_parts: pd.DataFrame) -> pd.DataFrame:
    """
    Defect propagation logic: a gearbox is defective if ANY of its installed
    parts is defective.

    The final dataset is pre-aggregated (installed/defective counts per part
    type & manufacturer), not per physical unit, so a literal row-level OR
    cannot be applied. Instead this propagates rates upward using the
    standard reliability-engineering formulation, assuming independence
    across the distinct part types that make up a gearbox family:

        P(gearbox defective) = 1 - PRODUCT over constituent part types of
                                    (1 - defect_rate of that part type)

    Two scenarios are computed per gearbox family:
      * "observed": using each part type's actual blended defect rate
        (all suppliers, volume-weighted, i.e. the real current supplier mix).
      * "if_205": using manufacturer 205's own defect rate for any part type
        205 supplies, and the market rate for part types 205 doesn't make.
        This isolates the quality benefit of sourcing from 205.
    """
    result_columns = ["gearbox_family", "part_types", "observed_defect_pct", "if_205_defect_pct"]
    if filtered_parts.empty:
        return pd.DataFrame(columns=result_columns)

    type_rates = weighted_rate(filtered_parts, ["part_type"]).set_index("part_type")

    mfr205 = filtered_parts[filtered_parts["part_manufacturer"] == FOCUS_MANUFACTURER]
    mfr205_rates = weighted_rate(mfr205, ["part_type"]).set_index("part_type")

    records = []
    for family, group in filtered_parts.groupby("gearbox_family", observed=True):
        constituent_types = sorted(group["part_type"].unique())
        if not constituent_types:
            continue

        observed_survival = 1.0
        if205_survival = 1.0
        for part_type in constituent_types:
            p_overall = (
                type_rates.loc[part_type, "defect_pct"] / 100
                if part_type in type_rates.index
                else 0.0
            )
            observed_survival *= (1 - p_overall)

            if part_type in mfr205_rates.index:
                p_205 = mfr205_rates.loc[part_type, "defect_pct"] / 100
            else:
                p_205 = p_overall  # 205 doesn't supply this part -> fall back to market rate
            if205_survival *= (1 - p_205)

        records.append(
            {
                "gearbox_family": family,
                "part_types": ", ".join(constituent_types),
                "observed_defect_pct": (1 - observed_survival) * 100,
                "if_205_defect_pct": (1 - if205_survival) * 100,
            }
        )

    return pd.DataFrame(records, columns=result_columns)


# ---------------------------------------------------------------------------
# Chart theming
# ---------------------------------------------------------------------------
def apply_chart_theme(fig: go.Figure, legend_title: str | None = None) -> go.Figure:
    layout_kwargs = dict(
        plot_bgcolor="#FFFFFF",
        paper_bgcolor="#FFFFFF",
        font=dict(family="Source Sans Pro", color="#000000", size=13),
    )
    if legend_title:
        layout_kwargs["legend_title_text"] = legend_title
    fig.update_layout(**layout_kwargs)
    fig.update_xaxes(gridcolor="#E3F2FD")
    fig.update_yaxes(gridcolor="#E3F2FD")
    return fig


def highlight_205(fig: go.Figure) -> go.Figure:
    for trace in fig.data:
        name = str(getattr(trace, "name", "") or "")
        if "205" in name:
            if getattr(trace, "type", "") == "bar" or isinstance(trace, go.Bar):
                trace.marker.color = "#1E88E5"
                trace.marker.line = dict(color="#0D47A1", width=1.5)
            elif getattr(trace, "type", "") == "scatter" or isinstance(trace, go.Scatter):
                trace.line = dict(color="#1E88E5", width=3)
    return fig


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
def render_sidebar_logo() -> None:
    logo_file = APP_DIR / LOGO_PATH
    if logo_file.exists():
        _, col, _ = st.sidebar.columns([1, 2, 1])
        with col:
            st.image(str(logo_file), width=120)
    else:
        st.sidebar.markdown("### 📊 Data Analytics")


def render_sidebar_filters(parts: pd.DataFrame) -> dict:
    st.sidebar.markdown("### 🔍 Filters")

    # --- Analysis period: a deliberately chosen production window, not an
    # open-ended "everything selected by default" control. Defaults to the
    # most recent 5 model years present in the data; adjustable from there.
    year_min, year_max = int(parts["vehicle_year"].min()), int(parts["vehicle_year"].max())
    default_start = max(year_min, year_max - 4)

    st.sidebar.markdown("**Analysis Period**")
    year_range = st.sidebar.slider(
        "Production Year Range",
        min_value=year_min,
        max_value=year_max,
        value=(default_start, year_max),
    )
    st.sidebar.caption(
        f"Chosen analysis window: **{year_range[0]}–{year_range[1]}** "
        f"({year_range[1] - year_range[0] + 1} model year(s)). "
        "All figures below refer to parts produced in this period only."
    )

    st.sidebar.markdown("---")

    vtypes = sorted(parts["vehicle_type"].unique())
    families = sorted(parts["gearbox_family"].dropna().unique())
    ptypes = sorted(parts["part_type"].dropna().unique())
    mfrs = sorted(parts["part_manufacturer"].dropna().unique())

    selected_vtypes = st.sidebar.multiselect("Vehicle Type", vtypes, default=vtypes)
    selected_families = st.sidebar.multiselect("Gearbox Family", families, default=families)
    selected_ptypes = st.sidebar.multiselect("Part Type", ptypes, default=ptypes)
    selected_mfrs = st.sidebar.multiselect("Part Manufacturer", mfrs, default=mfrs)

    return {
        "year_range": year_range,
        "vehicle_types": selected_vtypes,
        "families": selected_families,
        "part_types": selected_ptypes,
        "manufacturers": selected_mfrs,
    }


# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
def tab_executive_kpi(filtered_parts: pd.DataFrame, filtered_gearboxes: pd.DataFrame) -> None:
    total_installed = filtered_parts["installed_parts"].sum()

    mfr205 = filtered_parts[filtered_parts["part_manufacturer"] == FOCUS_MANUFACTURER]
    mfr205_installed = mfr205["installed_parts"].sum()
    mfr205_defective = mfr205["defective_parts"].sum()
    mfr205_defect_rate = (mfr205_defective / mfr205_installed * 100) if mfr205_installed else 0.0

    # Competitor rate is scoped to the SAME part types 205 supplies, so the
    # comparison is apples-to-apples (matches the market-share scope below).
    # Pulling in part types 205 doesn't even make (e.g. T24/T25) would dilute
    # a comparison that is supposed to be "205 vs. the competition it faces".
    active_types = mfr205["part_type"].unique()
    scope = filtered_parts[filtered_parts["part_type"].isin(active_types)]
    competitors = scope[scope["part_manufacturer"] != FOCUS_MANUFACTURER]
    comp_installed = competitors["installed_parts"].sum()
    comp_defective = competitors["defective_parts"].sum()
    comp_defect_rate = (comp_defective / comp_installed * 100) if comp_installed else 0.0

    mfr205_share = compute_205_market_share(filtered_parts)
    every_xth = compute_every_xth_gearbox(filtered_gearboxes)
    every_xth_display = f"{every_xth:.2f}" if pd.notna(every_xth) else "n/a"

    # Delta vs. competitor rate, in percentage points. A NEGATIVE delta means
    # 205 has FEWER defects than the competition, which is a good outcome, so
    # delta_color="inverse" is used to render it green rather than red.
    delta_pp = mfr205_defect_rate - comp_defect_rate

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Installed Components", f"{total_installed:,.0f}")
    c2.metric("Mfr 205 Market Share", f"{mfr205_share:.2f}%")
    c3.metric("\u201cIn every xth gearbox\u201d", every_xth_display)
    c4.metric(
        "Mfr 205 Defect Rate",
        f"{mfr205_defect_rate:.3f}%",
        delta=f"{delta_pp:+.3f} pp vs. competition",
        delta_color="inverse",
    )
    c5.metric(
        "Relative Defect Frequency",
        f"{(mfr205_defect_rate / comp_defect_rate * 100):.1f}" if comp_defect_rate else "n/a",
        help="Index where 100 = exactly on par with the competition, "
        "below 100 = fewer defects than the competition.",
    )
    st.caption(
        "Market share and defect-rate comparisons are scoped to the part types Mfr 205 actually "
        "supplies. \u201cIn every xth gearbox\u201d = total gearboxes ÷ gearboxes containing a 205 part. "
        "All figures are volume-weighted across the selected filters (never an average of ratios)."
    )

    st.markdown("---")
    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("Defect Rate by Part Type & Manufacturer")
        defect_avg = weighted_rate(filtered_parts, ["part_type", "part_manufacturer"])
        if not defect_avg.empty:
            defect_avg["manufacturer_label"] = defect_avg["part_manufacturer"].apply(manufacturer_label)
            fig_bar = px.bar(
                defect_avg,
                x="part_type",
                y="defect_pct",
                color="manufacturer_label",
                barmode="group",
                text=defect_avg["defect_pct"].round(2).astype(str) + "%",
                title="Absolute Defect Rate by Part Type & Manufacturer",
                labels={
                    "part_type": "Part Type",
                    "defect_pct": "Defect Rate (%)",
                    "manufacturer_label": "Manufacturer",
                },
                color_discrete_map={
                    "Mfr 205": "#1E88E5",
                    "Mfr 206": "#FFB74D",
                    "Mfr 207": "#81C784",
                    "Mfr 208": "#E57373",
                },
            )
            fig_bar.update_traces(textposition="outside", textfont_size=11)
            max_defect = defect_avg["defect_pct"].max()
            fig_bar.update_yaxes(
                range=[9.5, max_defect + 0.15], # Adds a slight buffer above the max value
                dtick=0.1
            )
            apply_chart_theme(fig_bar, legend_title="Manufacturer")
            highlight_205(fig_bar)
            st.plotly_chart(fig_bar, use_container_width=True)
            st.caption(
                "Values cluster tightly around a shared baseline for this dataset — see the "
                "**Relative Defect Frequency Index** chart below for the same data expressed as "
                "a % of the competition, which makes the (real, if small) differences legible."
            )
        else:
            st.info("No data for the current filter selection.")

    with col_right:
        st.subheader("Supplier Market Share")
        share_df = compute_market_share(filtered_parts)
        if not share_df.empty:
            # High-contrast palette: Pure White for Mfr 207, paired with high-contrast blues
            blue_contrast_palette = {
                205: "#03045E",  # Deep Midnight Blue (42.0%)
                208: "#0077B6",  # Cobalt Blue (29.3%)
                206: "#90E0EF",  # Soft Light Blue (16.7%)
                207: "#FFFFFF",  # Pure White (12.0%)
            }
            colors = [
                blue_contrast_palette.get(m, "#0077B6")
                for m in share_df["part_manufacturer"]
            ]
            fig_donut = go.Figure(
                data=[
                    go.Pie(
                        labels=share_df["manufacturer_label"],
                        values=share_df["share_pct"],
                        hole=0.45,
                        marker=dict(colors=colors, line=dict(color="#03045E", width=2)),
                        texttemplate="%{label}<br>%{value:.1f}%",
                    )
                ]
            )
            fig_donut.update_layout(title="Volume-Weighted Market Share by Manufacturer (%)")
            apply_chart_theme(fig_donut, legend_title="Manufacturer")
            st.plotly_chart(fig_donut, use_container_width=True)
        else:
            st.info("No data for the current filter selection.")

    st.markdown("---")
    st.subheader("Relative Defect Frequency Index — Mfr 205 vs. Competition")
    st.caption(
        "For each part type, Mfr 205's defect rate expressed as a % of the combined defect rate "
        "of every other manufacturer supplying that part. **100 = exactly on par**; "
        "below 100 = fewer defects than the competition; above 100 = more defects."
    )
    rel_df = compute_relative_defect_index(filtered_parts, "part_type")
    rel_205 = rel_df[
        (rel_df["part_manufacturer"] == FOCUS_MANUFACTURER) & rel_df["relative_index_pct"].notna()
    ].sort_values("part_type")

    if not rel_205.empty:
        bar_colors = [
            "#43A047" if v < 100 else "#E53935" for v in rel_205["relative_index_pct"]
        ]
        fig_rel = go.Figure(
            data=[
                go.Bar(
                    x=rel_205["part_type"],
                    y=rel_205["relative_index_pct"],
                    text=rel_205["relative_index_pct"].round(1),
                    texttemplate="%{text}",
                    textposition="outside",
                    marker_color=bar_colors,
                )
            ]
        )
        fig_rel.add_hline(
            y=100,
            line_dash="dash",
            line_color="#0D47A1",
            annotation_text="Competitor baseline (100)",
            annotation_position="top left",
        )
        pad = max(3.0, (rel_205["relative_index_pct"].max() - rel_205["relative_index_pct"].min()) * 0.6)
        fig_rel.update_yaxes(
            range=[rel_205["relative_index_pct"].min() - pad, rel_205["relative_index_pct"].max() + pad],
            title="Relative Defect Frequency Index",
        )
        fig_rel.update_xaxes(title="Part Type")
        fig_rel.update_layout(title="Mfr 205 Defect Rate as % of Competitor Rate, by Part Type")
        apply_chart_theme(fig_rel)
        st.plotly_chart(fig_rel, use_container_width=True)
    else:
        st.info("No comparable competitor data for Mfr 205 under the current filter selection.")


def tab_trends(filtered_parts: pd.DataFrame) -> None:
    st.subheader("Defect Rate Trend by Manufacturer")
    st.caption("Volume-weighted defect rate per model year — 205 highlighted against competitors.")

    trend = weighted_rate(filtered_parts, ["vehicle_year", "part_manufacturer"])
    if trend.empty:
        st.info("No data for the current filter selection.")
        return

    trend["manufacturer_label"] = trend["part_manufacturer"].apply(manufacturer_label)
    fig_trend = px.line(
        trend,
        x="vehicle_year",
        y="defect_pct",
        color="manufacturer_label",
        markers=True,
        title="Defect Rate Over Time by Manufacturer",
        labels={
            "vehicle_year": "Model Year",
            "defect_pct": "Defect Rate (%)",
            "manufacturer_label": "Manufacturer",
        },
    )
    apply_chart_theme(fig_trend, legend_title="Manufacturer")
    highlight_205(fig_trend)
    st.plotly_chart(fig_trend, use_container_width=True)


def tab_defect_propagation(filtered_parts: pd.DataFrame) -> None:
    st.subheader("Gearbox-Level Defect Probability (Propagation Logic)")
    st.caption(
        "A gearbox is treated as defective if **any** of its installed parts is defective. "
        "Since the final dataset is pre-aggregated (no per-unit records), this is estimated "
        "by propagating part-level defect rates upward, assuming independence across the "
        "distinct part types in a gearbox: "
        "P(gearbox defective) = 1 − Π(1 − defect rate of each constituent part type)."
    )

    prob_df = compute_gearbox_defect_probability(filtered_parts)
    if prob_df.empty:
        st.info("No data for the current filter selection.")
        return

    # The observed-vs-if-205 gap is often a fraction of a percentage point,
    # which is invisible as a bar-height difference at this scale. Surface
    # it explicitly as a delta metric per family before the chart, rather
    # than relying on the eye to spot near-identical bar heights.
    prob_df["delta_pp"] = prob_df["if_205_defect_pct"] - prob_df["observed_defect_pct"]
    metric_cols = st.columns(len(prob_df))
    for col, (_, row) in zip(metric_cols, prob_df.iterrows()):
        col.metric(
            f"{row['gearbox_family']} Defect Probability",
            f"{row['observed_defect_pct']:.3f}%",
            delta=f"{row['delta_pp']:+.3f} pp if sourced from 205",
            delta_color="inverse",
            help="Delta shows the change in gearbox-level defect probability if every "
            "part type 205 supplies were sourced entirely from 205, holding the market "
            "rate for part types 205 doesn't make. Negative = fewer defects (better).",
        )

    melted = prob_df.melt(
        id_vars=["gearbox_family", "part_types"],
        value_vars=["observed_defect_pct", "if_205_defect_pct"],
        var_name="scenario",
        value_name="defect_probability_pct",
    )
    melted["scenario"] = melted["scenario"].map(
        {
            "observed_defect_pct": "Observed (actual supplier mix)",
            "if_205_defect_pct": "If sourced from 205 where possible",
        }
    )

    fig = px.bar(
        melted,
        x="gearbox_family",
        y="defect_probability_pct",
        color="scenario",
        barmode="group",
        text=melted["defect_probability_pct"].round(3).astype(str) + "%",
        title="Estimated Probability a Gearbox Contains at Least One Defective Part",
        labels={
            "gearbox_family": "Gearbox Family",
            "defect_probability_pct": "Defect Probability (%)",
            "scenario": "Scenario",
        },
        color_discrete_map={
            "Observed (actual supplier mix)": "#90A4AE",
            "If sourced from 205 where possible": "#1E88E5",
        },
    )
    fig.update_traces(textposition="outside", textfont_size=11)
    fig.update_yaxes(range=[0, melted["defect_probability_pct"].max() * 1.2])
    apply_chart_theme(fig, legend_title="Scenario")
    st.plotly_chart(fig, use_container_width=True)
    st.caption(
        "The two bars per family are close because, in this dataset, Mfr 205's defect rate is "
        "close to the blended market rate for most part types — see the metrics above and the "
        "table below for the exact, otherwise-imperceptible differences."
    )

    st.markdown("**Constituent part types per gearbox family**")
    st.dataframe(
        prob_df.rename(
            columns={
                "gearbox_family": "Gearbox Family",
                "part_types": "Part Types Installed",
                "observed_defect_pct": "Observed Defect Probability (%)",
                "if_205_defect_pct": "If-205 Defect Probability (%)",
                "delta_pp": "Delta (pp)",
            }
        ).round(3),
        use_container_width=True,
        hide_index=True,
    )


def tab_data_explorer(full_df: pd.DataFrame) -> None:
    st.subheader("Interactive Data Explorer")
    search_term = st.text_input("Search across all columns", placeholder="Type to filter…")

    display_df = full_df.copy()
    if search_term:
        mask = display_df.astype(str).apply(lambda col: col.str.contains(search_term, case=False, na=False))
        display_df = display_df[mask.any(axis=1)]

    st.dataframe(display_df, use_container_width=True, hide_index=True)

    csv_buffer = io.StringIO()
    display_df.to_csv(csv_buffer, index=False)
    st.download_button(
        label="⬇️ Download Filtered Data as CSV",
        data=csv_buffer.getvalue(),
        file_name="quality_export.csv",
        mime="text/csv",
        type="primary",
        use_container_width=True,
    )


# ---------------------------------------------------------------------------
# Main Application
# ---------------------------------------------------------------------------
def main() -> None:
    st.set_page_config(
        page_title="Executive Quality Dashboard",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    inject_custom_css()

    df = load_data()
    parts, gearboxes = split_records(df)

    render_sidebar_logo()
    filters = render_sidebar_filters(parts)

    filtered_parts = apply_part_filters(
        parts,
        year_range=filters["year_range"],
        vehicle_types=filters["vehicle_types"],
        families=filters["families"],
        part_types=filters["part_types"],
        manufacturers=filters["manufacturers"],
    )
    filtered_gearboxes = apply_gearbox_filters(
        gearboxes,
        filters["year_range"],
        filters["vehicle_types"],
        filters["families"],
    )

    st.markdown(
        """
        <div class="dashboard-header">
            <h1>Executive Quality Dashboard</h1>
            <p>Automotive component defect rates · supplier market share · transmission penetration</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    tab1, tab2, tab3, tab4 = st.tabs(
        [
            "📈 Executive KPI Overview",
            "📉 Defect Trends",
            "🧩 Defect Propagation",
            "🔎 Interactive Data Explorer",
        ]
    )

    with tab1:
        tab_executive_kpi(filtered_parts, filtered_gearboxes)
    with tab2:
        tab_trends(filtered_parts)
    with tab3:
        tab_defect_propagation(filtered_parts)
    with tab4:
        tab_data_explorer(df)


if __name__ == "__main__":
    main()