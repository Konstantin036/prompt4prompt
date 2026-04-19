import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import streamlit as st
from db import get_connection
from theme import apply_dark_theme, ORANGE


@st.cache_data
def load_consumer_estimates() -> pd.DataFrame:
    """One row per DT that has at least one V+I pair in MeterReads at its latest timestamp."""
    conn = get_connection()
    try:
        query = """
        WITH latest_ts AS (
            SELECT Mid, MAX(Ts) AS ts
            FROM MeterReads
            WHERE Cid IN (6,7,8,9,10,11)
            GROUP BY Mid
        ),
        pivoted AS (
            SELECT mr.Mid,
                   MAX(CASE WHEN mr.Cid = 6  THEN mr.Val END) AS V_A,
                   MAX(CASE WHEN mr.Cid = 7  THEN mr.Val END) AS V_B,
                   MAX(CASE WHEN mr.Cid = 8  THEN mr.Val END) AS V_C,
                   MAX(CASE WHEN mr.Cid = 9  THEN mr.Val END) AS I_A,
                   MAX(CASE WHEN mr.Cid = 10 THEN mr.Val END) AS I_B,
                   MAX(CASE WHEN mr.Cid = 11 THEN mr.Val END) AS I_C,
                   MAX(lt.ts)                                  AS last_ts
            FROM MeterReads mr
            JOIN latest_ts lt ON lt.Mid = mr.Mid AND mr.Ts = lt.ts
            WHERE mr.Cid IN (6,7,8,9,10,11)
            GROUP BY mr.Mid
        ),
        s_calc AS (
            SELECT Mid,
                   last_ts,
                   ROUND((
                       ISNULL(V_A * I_A, 0) +
                       ISNULL(V_B * I_B, 0) +
                       ISNULL(V_C * I_C, 0)
                   ) / 1000000.0, 2) AS S_kVA
            FROM pivoted
            WHERE (V_A IS NOT NULL AND I_A IS NOT NULL)
               OR (V_B IS NOT NULL AND I_B IS NOT NULL)
               OR (V_C IS NOT NULL AND I_C IS NOT NULL)
        )
        SELECT
            ISNULL((
                SELECT TOP 1 ts2.Name
                FROM Feeder33Substation fs2
                JOIN Feeders33 f33b ON f33b.Id = fs2.Feeders33Id
                JOIN TransmissionStations ts2 ON ts2.Id = f33b.TsId
                WHERE fs2.SubstationsId = f11.SsId
            ), 'N/A')              AS [TS],
            sub.Name               AS [Podstanica (SS)],
            f11.Name               AS [Feeder11],
            d.Name                 AS [DT Stanica],
            d.NameplateRating      AS [Snaga (kVA)],
            sc.S_kVA               AS [S (kVA)],
            sc.last_ts             AS [Poslednje merenje]
        FROM s_calc sc
        JOIN DistributionSubstation d  ON d.MeterId  = sc.Mid
        JOIN Feeders11 f11             ON f11.Id     = d.Feeder11Id
        JOIN Substations sub           ON sub.Id     = f11.SsId
        WHERE sc.S_kVA > 0
        ORDER BY sc.S_kVA DESC
        """
        return pd.read_sql(query, conn)
    finally:
        conn.close()



def _aggregate_by_feeder(df: pd.DataFrame, kva_per_consumer: float) -> pd.DataFrame:
    """Pure function: aggregate DT-level DataFrame to F11 feeder level."""
    agg = (
        df.groupby(["TS", "Podstanica (SS)", "Feeder11"])
        .agg(
            S_kVA=("S (kVA)", "sum"),
            DT_count=("DT Stanica", "count"),
        )
        .reset_index()
    )
    agg["consumers"] = (agg["S_kVA"] / kva_per_consumer).round(0).astype(int)
    return agg.sort_values("consumers", ascending=False).reset_index(drop=True)


_SUNBURST_PALETTE = [
    "#FF6B35", "#7B61FF", "#00C9B1", "#FF2D78",
    "#FFAB00", "#00B8D9", "#36B37E", "#FF5630",
    "#6554C0", "#00875A", "#DE350B", "#0052CC",
]


def _sunburst_chart(f11_agg: pd.DataFrame) -> None:
    ts_list = f11_agg["TS"].unique().tolist()
    ts_color = {ts: _SUNBURST_PALETTE[i % len(_SUNBURST_PALETTE)] for i, ts in enumerate(ts_list)}

    fig = px.sunburst(
        f11_agg,
        path=["TS", "Podstanica (SS)", "Feeder11"],
        values="consumers",
        color="TS",
        color_discrete_map=ts_color,
        custom_data=["S_kVA", "DT_count", "consumers"],
        height=620,
        branchvalues="total",
    )
    fig.update_traces(
        texttemplate="<b>%{label}</b><br>%{value}",
        textfont=dict(size=11, family="monospace"),
        hovertemplate=(
            "<b>%{label}</b><br>"
            "Potrošači: <b>%{value:,}</b><br>"
            "S ukupno: %{customdata[0]:.1f} kVA<br>"
            "DT stanica: %{customdata[1]}<br>"
            "<extra></extra>"
        ),
        insidetextorientation="radial",
        marker=dict(line=dict(width=1.5, color="rgba(15,15,26,0.85)")),
        leaf=dict(opacity=0.82),
    )
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#a0aec0"),
        title=dict(
            text="Distribucija potrošača — hijerarhija TS → SS → F11",
            font=dict(color=ORANGE, size=14),
            x=0.5,
            xanchor="center",
        ),
        margin=dict(l=10, r=10, t=55, b=10),
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)
    st.caption(
        "Kliknite na sektor da uđete dublje u hijerarhiju (TS → SS → F11). "
        "Veličina = broj potrošača. Svaki TS ima svoju boju."
    )


def _top_feeders_chart(f11_agg: pd.DataFrame) -> None:
    top = f11_agg.nlargest(15, "consumers").copy()
    top["label"] = top["Feeder11"] + "  ·  " + top["Podstanica (SS)"]

    ts_list = f11_agg["TS"].unique().tolist()
    ts_color = {ts: _SUNBURST_PALETTE[i % len(_SUNBURST_PALETTE)] for i, ts in enumerate(ts_list)}
    colors = [ts_color.get(ts, ORANGE) for ts in top["TS"]]

    fig = go.Figure(go.Bar(
        x=top["consumers"],
        y=top["label"],
        orientation="h",
        marker=dict(
            color=colors,
            line=dict(width=0),
            opacity=0.88,
        ),
        text=top["consumers"].apply(lambda v: f"{v:,}"),
        textposition="outside",
        textfont=dict(color="#a0aec0", size=11),
        customdata=top[["TS", "S_kVA", "DT_count"]].values,
        hovertemplate=(
            "<b>%{y}</b><br>"
            "TS: %{customdata[0]}<br>"
            "Potrošači: <b>%{x:,}</b><br>"
            "S mereno: %{customdata[1]:.1f} kVA<br>"
            "DT stanica: %{customdata[2]}<br>"
            "<extra></extra>"
        ),
    ))

    apply_dark_theme(fig)
    fig.update_layout(
        title="Top 15 F11 fidera po broju potrošača",
        xaxis_title="Broj potrošača (est.)",
        yaxis=dict(autorange="reversed", tickfont=dict(size=10)),
        height=500,
        margin=dict(l=10, r=80, t=50, b=10),
    )
    st.plotly_chart(fig, use_container_width=True)


def _ts_donut(f11_agg: pd.DataFrame) -> None:
    ts_agg = (
        f11_agg.groupby("TS")
        .agg(consumers=("consumers", "sum"), S_kVA=("S_kVA", "sum"))
        .reset_index()
        .sort_values("consumers", ascending=False)
    )
    ts_list = ts_agg["TS"].tolist()
    colors = [_SUNBURST_PALETTE[i % len(_SUNBURST_PALETTE)] for i in range(len(ts_list))]

    fig = go.Figure(go.Pie(
        labels=ts_agg["TS"],
        values=ts_agg["consumers"],
        hole=0.62,
        marker=dict(colors=colors, line=dict(color="rgba(15,15,26,0.9)", width=2)),
        textinfo="percent+label",
        textfont=dict(size=11, color="#e6edf3"),
        hovertemplate=(
            "<b>%{label}</b><br>"
            "Potrošači: <b>%{value:,}</b><br>"
            "Udio: %{percent}<br>"
            "<extra></extra>"
        ),
        direction="clockwise",
        sort=True,
    ))
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#a0aec0"),
        title=dict(text="Udio po TS", font=dict(color=ORANGE, size=13), x=0.5, xanchor="center"),
        margin=dict(l=10, r=10, t=50, b=10),
        height=380,
        showlegend=False,
        annotations=[dict(
            text=f"<b>{ts_agg['consumers'].sum():,}</b><br><span style='font-size:11px'>potrošača</span>",
            x=0.5, y=0.5, font=dict(size=16, color="#e6edf3"), showarrow=False,
        )],
    )
    st.plotly_chart(fig, use_container_width=True)


def show_consumers() -> None:
    st.markdown(
        '<h3 style="color:#FF6B35;font-size:1.15rem;font-weight:700;'
        'text-transform:uppercase;letter-spacing:0.06em;margin-bottom:1rem;">'
        '👥 Estimacija broja potrošača po F11 fiderima</h3>',
        unsafe_allow_html=True,
    )

    df = load_consumer_estimates()

    if df.empty:
        st.warning("Nema mernih podataka (V/I) za estimaciju potrošača.")
        return

    kva_per_consumer = st.slider(
        "kVA po potrošaču",
        min_value=0.5, max_value=5.0, value=1.5, step=0.1,
        help="Prosečna vršna prividna snaga po potrošaču u kVA",
    )

    f11_agg = _aggregate_by_feeder(df, kva_per_consumer)

    col1, col2, col3 = st.columns(3)
    col1.metric("F11 fidera sa merenjima", len(f11_agg))
    col2.metric("DT stanica sa merenjima", len(df))
    col3.metric("Ukupno est. potrošača", f"{f11_agg['consumers'].sum():,}")

    # ── Sunburst (puna širina) ──────────────────────────────────────────────
    _sunburst_chart(f11_agg)

    st.divider()

    # ── Top F11 + TS donut (side by side) ──────────────────────────────────
    col_bar, col_pie = st.columns([3, 2], gap="large")
    with col_bar:
        _top_feeders_chart(f11_agg)
    with col_pie:
        _ts_donut(f11_agg)

