import plotly.express as px
import pandas as pd
import streamlit as st
from db import get_connection
from theme import apply_dark_theme


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


@st.cache_data
def load_no_reading_dts() -> pd.DataFrame:
    """DTs that have no MeterId or no MeterReads rows for V/I channels."""
    conn = get_connection()
    try:
        query = """
        WITH meters_with_reads AS (
            SELECT DISTINCT Mid FROM MeterReads WHERE Cid IN (6,7,8,9,10,11)
        )
        SELECT
            d.Name                                   AS [DT Stanica],
            d.NameplateRating                        AS [Snaga (kVA)],
            ISNULL(f11.Name, 'N/A')                 AS [Feeder11],
            ISNULL(sub.Name, 'N/A')                 AS [Podstanica (SS)],
            CASE
                WHEN d.MeterId IS NULL THEN 'Nema merača'
                ELSE 'Nema očitavanja V/I'
            END                                      AS [Razlog]
        FROM DistributionSubstation d
        LEFT JOIN meters_with_reads mwr ON mwr.Mid = d.MeterId
        LEFT JOIN Feeders11  f11 ON f11.Id  = d.Feeder11Id
        LEFT JOIN Substations sub ON sub.Id = f11.SsId
        WHERE d.MeterId IS NULL OR mwr.Mid IS NULL
        ORDER BY sub.Name, f11.Name, d.Name
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
        _show_no_readings()
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

    # Treemap — hijerarhija: mreža → TS → SS → F11 fider
    fig = px.treemap(
        f11_agg,
        path=[px.Constant("🌐 Mreža"), "TS", "Podstanica (SS)", "Feeder11"],
        values="consumers",
        color="S_kVA",
        color_continuous_scale=["#1a2040", "#FF6B35", "#ffb347"],
        color_continuous_midpoint=f11_agg["S_kVA"].median(),
        custom_data=["S_kVA", "DT_count", "consumers"],
        labels={
            "consumers": "Potrošači",
            "S_kVA": "S ukupno (kVA)",
            "DT_count": "Broj DT",
        },
        height=600,
    )
    fig.update_traces(
        texttemplate="<b>%{label}</b><br>%{customdata[2]} potrošača",
        hovertemplate=(
            "<b>%{label}</b><br>"
            "Potrošači: <b>%{customdata[2]}</b><br>"
            "S ukupno: %{customdata[0]:.1f} kVA<br>"
            "DT stanica: %{customdata[1]}<br>"
            "<extra></extra>"
        ),
        marker=dict(
            line=dict(width=2, color="#0f0f1a"),
            cornerradius=6,
        ),
        textfont=dict(size=12),
    )
    apply_dark_theme(fig)
    fig.update_layout(
        title="Distribucija potrošača — hijerarhija TS → SS → F11",
        coloraxis_colorbar=dict(
            title="S (kVA)",
            tickfont=dict(color="#a0aec0"),
            titlefont=dict(color="#8892b0"),
        ),
    )
    st.plotly_chart(fig, use_container_width=True)

    st.caption(
        "Veličina kvadrata = broj procijenjenih potrošača. "
        "Boja = ukupna izmjerena snaga (kVA) — toplije = veće opterećenje."
    )

    with st.expander("Detalji po DT stanicama"):
        st.dataframe(
            df[["TS", "Podstanica (SS)", "Feeder11", "DT Stanica",
                "Snaga (kVA)", "S (kVA)", "Poslednje merenje"]],
            use_container_width=True,
            height=400,
        )

    st.divider()
    _show_no_readings()


def _show_no_readings() -> None:
    df_no = load_no_reading_dts()
    st.warning(
        f"**{len(df_no)} stanica bez merenja** — potrebno izvršiti pregled na terenu."
    )
    st.dataframe(df_no, use_container_width=True, height=350)
