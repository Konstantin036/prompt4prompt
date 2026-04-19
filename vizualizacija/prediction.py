import streamlit as st
import pandas as pd
import numpy as np
import folium
from streamlit_folium import st_folium
import plotly.graph_objects as go
from db import get_connection
from theme import apply_dark_theme, ORANGE

_RISK_COLORS = {
    "Sigurno":    "#36B37E",
    "Umjereno":   "#00C9B1",
    "Upozorenje": "#FFAB00",
    "Kritično":   "#FF2D78",
}


@st.cache_data
def load_current_utilization() -> pd.DataFrame:
    conn = get_connection()
    try:
        query = """
        WITH latest_ts AS (
            SELECT Mid, MAX(Ts) AS ts
            FROM MeterReads WHERE Cid IN (6,7,8,9,10,11)
            GROUP BY Mid
        ),
        pivoted AS (
            SELECT mr.Mid,
                   MAX(CASE WHEN mr.Cid=6  THEN mr.Val END) AS V_A,
                   MAX(CASE WHEN mr.Cid=7  THEN mr.Val END) AS V_B,
                   MAX(CASE WHEN mr.Cid=8  THEN mr.Val END) AS V_C,
                   MAX(CASE WHEN mr.Cid=9  THEN mr.Val END) AS I_A,
                   MAX(CASE WHEN mr.Cid=10 THEN mr.Val END) AS I_B,
                   MAX(CASE WHEN mr.Cid=11 THEN mr.Val END) AS I_C
            FROM MeterReads mr
            JOIN latest_ts lt ON lt.Mid = mr.Mid AND mr.Ts = lt.ts
            WHERE mr.Cid IN (6,7,8,9,10,11)
            GROUP BY mr.Mid
        )
        SELECT
            d.Name          AS DT,
            d.Lat, d.Lon,
            d.NameplateRating AS DT_kVA,
            f11.Id          AS F11Id,
            f11.Name        AS Feeder11,
            f11.NameplateRating AS F11_kVA,
            sub.Name        AS Podstanica,
            ISNULL((
                SELECT TOP 1 ts2.Name
                FROM Feeder33Substation fs2
                JOIN Feeders33 f33b ON f33b.Id = fs2.Feeders33Id
                JOIN TransmissionStations ts2 ON ts2.Id = f33b.TsId
                WHERE fs2.SubstationsId = f11.SsId
            ), 'N/A') AS TS,
            ROUND((
                ISNULL(V_A*I_A,0) + ISNULL(V_B*I_B,0) + ISNULL(V_C*I_C,0)
            ) / 1000000.0, 3) AS S_kVA
        FROM pivoted p
        JOIN DistributionSubstation d  ON d.MeterId = p.Mid
        JOIN Feeders11 f11             ON f11.Id    = d.Feeder11Id
        JOIN Substations sub           ON sub.Id    = f11.SsId
        WHERE (
            (V_A IS NOT NULL AND I_A IS NOT NULL) OR
            (V_B IS NOT NULL AND I_B IS NOT NULL) OR
            (V_C IS NOT NULL AND I_C IS NOT NULL)
        )
        AND ISNULL(V_A,0) < 30000
        AND ISNULL(V_B,0) < 30000
        AND ISNULL(V_C,0) < 30000
        AND d.Lat IS NOT NULL AND d.Lon IS NOT NULL
        AND d.NameplateRating > 0
        AND (ISNULL(V_A*I_A,0) + ISNULL(V_B*I_B,0) + ISNULL(V_C*I_C,0)) > 0
        """
        return pd.read_sql(query, conn)
    finally:
        conn.close()


@st.cache_data
def load_monthly_series() -> pd.DataFrame:
    """Monthly avg S_kVA per feeder for trend regression."""
    conn = get_connection()
    try:
        query = """
        WITH ts_reads AS (
            SELECT mr.Mid, mr.Ts,
                   MAX(CASE WHEN mr.Cid=6  THEN mr.Val END) AS V_A,
                   MAX(CASE WHEN mr.Cid=7  THEN mr.Val END) AS V_B,
                   MAX(CASE WHEN mr.Cid=8  THEN mr.Val END) AS V_C,
                   MAX(CASE WHEN mr.Cid=9  THEN mr.Val END) AS I_A,
                   MAX(CASE WHEN mr.Cid=10 THEN mr.Val END) AS I_B,
                   MAX(CASE WHEN mr.Cid=11 THEN mr.Val END) AS I_C
            FROM MeterReads mr
            WHERE mr.Cid IN (6,7,8,9,10,11)
            GROUP BY mr.Mid, mr.Ts
        ),
        s_vals AS (
            SELECT Mid, Ts,
                   (ISNULL(V_A*I_A,0)+ISNULL(V_B*I_B,0)+ISNULL(V_C*I_C,0))/1000000.0 AS S_kVA
            FROM ts_reads
            WHERE ISNULL(V_A,0) < 30000 AND ISNULL(V_B,0) < 30000 AND ISNULL(V_C,0) < 30000
              AND ((V_A IS NOT NULL AND I_A IS NOT NULL)
                OR (V_B IS NOT NULL AND I_B IS NOT NULL)
                OR (V_C IS NOT NULL AND I_C IS NOT NULL))
              AND (ISNULL(V_A*I_A,0)+ISNULL(V_B*I_B,0)+ISNULL(V_C*I_C,0)) > 0
        )
        SELECT
            d.Feeder11Id     AS F11Id,
            f11.Name         AS Feeder11,
            f11.NameplateRating AS F11_kVA,
            YEAR(s.Ts)  AS yr,
            MONTH(s.Ts) AS mo,
            AVG(s.S_kVA) AS avg_S_kVA
        FROM s_vals s
        JOIN DistributionSubstation d ON d.MeterId = s.Mid
        JOIN Feeders11 f11            ON f11.Id    = d.Feeder11Id
        GROUP BY d.Feeder11Id, f11.Name, f11.NameplateRating, YEAR(s.Ts), MONTH(s.Ts)
        ORDER BY d.Feeder11Id, yr, mo
        """
        return pd.read_sql(query, conn)
    finally:
        conn.close()


def _compute_trend_rates(monthly_df: pd.DataFrame) -> pd.DataFrame:
    """Linear regression per feeder → monthly kVA growth rate."""
    rows = []
    for f11_id, grp in monthly_df.groupby("F11Id"):
        grp = grp.sort_values(["yr", "mo"])
        if len(grp) < 2:
            continue
        x = np.arange(len(grp), dtype=float)
        y = grp["avg_S_kVA"].values
        slope, _ = np.polyfit(x, y, 1)
        rows.append({
            "F11Id": f11_id,
            "monthly_growth_kVA": max(slope, 0.0),
            "data_months": len(grp),
        })
    if not rows:
        return pd.DataFrame(columns=["F11Id", "monthly_growth_kVA", "data_months"])
    return pd.DataFrame(rows)


def _risk_label(util_pct: float) -> str:
    if util_pct >= 90:
        return "Kritično"
    if util_pct >= 70:
        return "Upozorenje"
    if util_pct >= 50:
        return "Umjereno"
    return "Sigurno"


def _compute_predictions(
    dt_df: pd.DataFrame,
    trend_df: pd.DataFrame,
    months: int,
    default_annual_growth_pct: float,
) -> pd.DataFrame:
    df = dt_df.copy()
    df["util_pct"] = (df["S_kVA"] / df["DT_kVA"] * 100).clip(0, 200)
    df = df.merge(trend_df[["F11Id", "monthly_growth_kVA", "data_months"]], on="F11Id", how="left")

    default_monthly = df["S_kVA"] * (default_annual_growth_pct / 100.0 / 12.0)
    has_trend = df["data_months"].notna() & (df["data_months"] >= 2)
    df["monthly_growth_kVA"] = df["monthly_growth_kVA"].fillna(0.0)
    df["monthly_growth_kVA"] = df["monthly_growth_kVA"].where(has_trend, default_monthly)

    df["proj_S_kVA"] = df["S_kVA"] + df["monthly_growth_kVA"] * months
    df["proj_util_pct"] = (df["proj_S_kVA"] / df["DT_kVA"] * 100).clip(0, 200)
    df["risk"] = df["proj_util_pct"].apply(_risk_label)
    df["current_risk"] = df["util_pct"].apply(_risk_label)

    # months until 80% capacity is reached (only relevant if heading there)
    cap80 = 0.8 * df["DT_kVA"]
    heading_there = (df["proj_util_pct"] >= 80) & (df["monthly_growth_kVA"] > 0)
    df["months_to_80pct"] = np.where(
        heading_there,
        ((cap80 - df["S_kVA"]) / df["monthly_growth_kVA"]).clip(lower=0),
        np.nan,
    )
    return df


def _build_prediction_map(df: pd.DataFrame, show_pred: bool, show_current: bool) -> folium.Map:
    lat_c = df["Lat"].median()
    lon_c = df["Lon"].median()
    m = folium.Map(location=[lat_c, lon_c], zoom_start=11, tiles="CartoDB dark_matter")

    current_layer = folium.FeatureGroup(name="Trenutno opterećenje", show=show_current)
    for _, row in df.iterrows():
        color = _RISK_COLORS[row["current_risk"]]
        folium.CircleMarker(
            location=[row["Lat"], row["Lon"]],
            radius=6,
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.6,
            weight=1,
            popup=folium.Popup(
                f"<b>{row['DT']}</b><br>"
                f"Feeder: {row['Feeder11']}<br>"
                f"S = {row['S_kVA']:.1f} / {row['DT_kVA']} kVA<br>"
                f"Iskorištenost: <b>{row['util_pct']:.1f}%</b>",
                max_width=260,
            ),
            tooltip=f"{row['DT']}: {row['util_pct']:.0f}%",
        ).add_to(current_layer)
    current_layer.add_to(m)

    pred_layer = folium.FeatureGroup(name="Projekcija rasta mreže", show=show_pred)
    for _, row in df.iterrows():
        color = _RISK_COLORS[row["risk"]]
        radius = 10 if row["risk"] in ("Kritično", "Upozorenje") else 7
        m80 = f"<br>Dostiže 80% za: <b>{row['months_to_80pct']:.0f} mj.</b>" \
              if pd.notna(row.get("months_to_80pct")) else ""
        folium.CircleMarker(
            location=[row["Lat"], row["Lon"]],
            radius=radius,
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.78,
            weight=2,
            popup=folium.Popup(
                f"<b>{row['DT']}</b><br>"
                f"Feeder: {row['Feeder11']}<br>"
                f"Trenutno: {row['util_pct']:.1f}% → <b>{row['proj_util_pct']:.1f}%</b><br>"
                f"Status: <b style='color:{color}'>{row['risk']}</b>{m80}",
                max_width=280,
            ),
            tooltip=f"{row['DT']}: {row['proj_util_pct']:.0f}% ({row['risk']})",
        ).add_to(pred_layer)
    pred_layer.add_to(m)

    folium.LayerControl(collapsed=False).add_to(m)
    return m


def _utilization_chart(df: pd.DataFrame, months: int) -> None:
    top = df.nlargest(20, "proj_util_pct").copy()
    top["label"] = top["DT"] + "  ·  " + top["Feeder11"]
    colors = [_RISK_COLORS[r] for r in top["risk"]]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=top["util_pct"],
        y=top["label"],
        orientation="h",
        name="Trenutno",
        marker=dict(color="rgba(139,148,158,0.3)", line=dict(width=0)),
    ))
    fig.add_trace(go.Bar(
        x=top["proj_util_pct"],
        y=top["label"],
        orientation="h",
        name=f"Za {months} mj.",
        marker=dict(color=colors, opacity=0.85, line=dict(width=0)),
        text=[f"{v:.0f}%" for v in top["proj_util_pct"]],
        textposition="outside",
    ))
    fig.add_vline(x=80,  line_dash="dash", line_color="#FFAB00", line_width=1.5,
                  annotation_text="80%", annotation_position="top")
    fig.add_vline(x=100, line_dash="dash", line_color="#FF2D78", line_width=1.5,
                  annotation_text="100%", annotation_position="top")

    apply_dark_theme(fig)
    fig.update_layout(
        title=f"Top 20 DT stanica — projekcija opterećenja za {months} mj.",
        barmode="overlay",
        xaxis_title="Iskorištenost (%)",
        yaxis=dict(autorange="reversed", tickfont=dict(size=10)),
        height=560,
        legend=dict(orientation="h", y=1.05, x=0.5, xanchor="center"),
        margin=dict(l=10, r=80, t=70, b=10),
    )
    st.plotly_chart(fig, use_container_width=True)


def _risk_timeline_chart(df: pd.DataFrame, max_months: int) -> None:
    milestones = list(range(1, max_months + 1, max(1, max_months // 24)))
    growth = df["monthly_growth_kVA"].fillna(0)
    labels_per_month = []
    for mo in milestones:
        proj_util = ((df["S_kVA"] + growth * mo) / df["DT_kVA"] * 100).clip(0, 200)
        labels_per_month.append(proj_util.apply(_risk_label))

    counts = {risk: [] for risk in _RISK_COLORS}
    for labels in labels_per_month:
        for risk in _RISK_COLORS:
            counts[risk].append((labels == risk).sum())

    fig = go.Figure()
    fill_colors = {
        "Sigurno":    "rgba(54,179,126,0.3)",
        "Umjereno":   "rgba(0,201,177,0.3)",
        "Upozorenje": "rgba(255,171,0,0.3)",
        "Kritično":   "rgba(255,45,120,0.3)",
    }
    for risk, color in _RISK_COLORS.items():
        fig.add_trace(go.Scatter(
            x=milestones,
            y=counts[risk],
            name=risk,
            mode="lines",
            line=dict(color=color, width=2),
            stackgroup="one",
            fillcolor=fill_colors[risk],
        ))

    apply_dark_theme(fig)
    fig.update_layout(
        title="Evolucija rizika mreže tokom horizonta predikcije",
        xaxis_title="Mjeseci od danas",
        yaxis_title="Broj DT stanica",
        height=360,
        legend=dict(orientation="h", y=1.05, x=0.5, xanchor="center"),
        margin=dict(l=10, r=10, t=70, b=10),
    )
    st.plotly_chart(fig, use_container_width=True)


def show_prediction() -> None:
    st.markdown(
        '<h3 style="color:#FF6B35;font-size:1.15rem;font-weight:700;'
        'text-transform:uppercase;letter-spacing:0.06em;margin-bottom:1rem;">'
        '🔮 Predikcija rasta i opterećenja mreže</h3>',
        unsafe_allow_html=True,
    )

    with st.spinner("Učitavanje podataka o mjerenjima..."):
        dt_df = load_current_utilization()
        monthly_df = load_monthly_series()

    if dt_df.empty:
        st.warning("Nema mjernih podataka (V/I) za predikciju.")
        return

    # ── Controls ──────────────────────────────────────────────────────────────
    col_a, col_b = st.columns(2)
    with col_a:
        months = st.slider(
            "Horizont predikcije (mjeseci)",
            min_value=1, max_value=60, value=24, step=1,
        )
    with col_b:
        default_growth = st.slider(
            "Godišnji rast opterećenja (%) — za DT bez trenda",
            min_value=1.0, max_value=20.0, value=7.0, step=0.5,
        )

    trend_df = _compute_trend_rates(monthly_df)
    df_pred = _compute_predictions(dt_df, trend_df, months, default_growth)

    # ── KPI ───────────────────────────────────────────────────────────────────
    total = len(df_pred)
    crit  = (df_pred["risk"] == "Kritično").sum()
    warn  = (df_pred["risk"] == "Upozorenje").sum()
    safe  = (df_pred["risk"] == "Sigurno").sum()
    driven = trend_df["F11Id"].nunique() if not trend_df.empty else 0

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("DT sa mjerenjima", total)
    c2.metric("🔴 Kritično", int(crit))
    c3.metric("🟡 Upozorenje", int(warn))
    c4.metric("🟢 Sigurno", int(safe))
    c5.metric("Fidera s trendom", driven)

    st.divider()

    # ── Charts ────────────────────────────────────────────────────────────────
    _utilization_chart(df_pred, months)
    _risk_timeline_chart(df_pred, months)

    st.divider()

    # ── Map ───────────────────────────────────────────────────────────────────
    st.markdown(
        '<p style="color:#FF6B35;font-size:0.9rem;font-weight:700;'
        'text-transform:uppercase;letter-spacing:0.08em;margin-bottom:0.5rem;">'
        '🗺️ Mapa projekcije mreže</p>',
        unsafe_allow_html=True,
    )
    col_t1, col_t2 = st.columns(2)
    show_pred_layer = col_t1.toggle("Prikaži projekciju rasta", value=True)
    show_curr_layer = col_t2.toggle("Prikaži trenutno opterećenje", value=False)

    m = _build_prediction_map(df_pred, show_pred=show_pred_layer, show_current=show_curr_layer)
    st_folium(m, use_container_width=True, height=620, returned_objects=[])

    # Legenda
    cols = st.columns(4)
    for col, (label, color) in zip(cols, _RISK_COLORS.items()):
        col.markdown(
            f'<div style="display:flex;align-items:center;gap:8px;margin-top:4px;">'
            f'<div style="width:13px;height:13px;border-radius:50%;'
            f'background:{color};flex-shrink:0;"></div>'
            f'<span style="color:#c9d1d9;font-size:0.85rem;">{label}</span></div>',
            unsafe_allow_html=True,
        )

    st.divider()

    # ── Detail table ─────────────────────────────────────────────────────────
    with st.expander("Detaljna tabela — sve DT stanice"):
        show_df = df_pred[[
            "DT", "Feeder11", "Podstanica", "TS",
            "DT_kVA", "S_kVA", "util_pct", "proj_util_pct", "risk", "months_to_80pct",
        ]].rename(columns={
            "DT_kVA": "Kapacitet (kVA)",
            "S_kVA": "Trenutno (kVA)",
            "util_pct": "Iskorištenost (%)",
            "proj_util_pct": f"Za {months} mj. (%)",
            "risk": "Rizik",
            "months_to_80pct": "Mj. do 80%",
        }).sort_values(f"Za {months} mj. (%)", ascending=False)
        show_df["Iskorištenost (%)"] = show_df["Iskorištenost (%)"].round(1)
        show_df[f"Za {months} mj. (%)"] = show_df[f"Za {months} mj. (%)"].round(1)
        st.dataframe(show_df, use_container_width=True, height=420)
