import plotly.graph_objects as go
import pandas as pd
import streamlit as st
from db import get_connection
from theme import apply_dark_theme


@st.cache_data
def load_f11_losses() -> pd.DataFrame:
    conn = get_connection()
    try:
        query = """
        WITH has_reads AS (
            SELECT DISTINCT Mid FROM MeterReadTfes
        ),
        dt_coverage AS (
            SELECT d.Feeder11Id,
                   COUNT(*)                                                         AS total_dt,
                   SUM(CASE WHEN d.MeterId IS NOT NULL AND hr.Mid IS NOT NULL
                            THEN 1 ELSE 0 END)                                      AS dt_with_reads
            FROM   DistributionSubstation d
            LEFT JOIN has_reads hr ON hr.Mid = d.MeterId
            WHERE  d.Feeder11Id IS NOT NULL
            GROUP BY d.Feeder11Id
        ),
        latest_f11 AS (
            SELECT f.Id    AS f11_id,
                   f.Name  AS f11_name,
                   f.SsId,
                   f.TsId,
                   t.Val * ISNULL(m.MultiplierFactor, 1) AS energy_wh
            FROM   Feeders11 f
            JOIN   Meters m ON m.Id = f.MeterId
            JOIN   (
                SELECT Mid, Val,
                       ROW_NUMBER() OVER (PARTITION BY Mid ORDER BY Ts DESC) AS rn
                FROM   MeterReadTfes
            ) t ON t.Mid = f.MeterId AND t.rn = 1
            WHERE  f.MeterId IS NOT NULL
        ),
        latest_dt AS (
            SELECT d.Feeder11Id,
                   SUM(t.Val * ISNULL(m.MultiplierFactor, 1)) AS dt_total_wh
            FROM   DistributionSubstation d
            JOIN   Meters m ON m.Id = d.MeterId
            JOIN   (
                SELECT Mid, Val,
                       ROW_NUMBER() OVER (PARTITION BY Mid ORDER BY Ts DESC) AS rn
                FROM   MeterReadTfes
            ) t ON t.Mid = d.MeterId AND t.rn = 1
            WHERE  d.MeterId IS NOT NULL
            GROUP BY d.Feeder11Id
        )
        SELECT ISNULL(
                   (SELECT TOP 1 ts2.Name
                    FROM Feeder33Substation fs2
                    JOIN Feeders33 f33b ON f33b.Id = fs2.Feeders33Id
                    JOIN TransmissionStations ts2 ON ts2.Id = f33b.TsId
                    WHERE fs2.SubstationsId = f11.SsId), 'N/A')                    AS [TS],
               s.Name                                                              AS [Podstanica (SS)],
               f11.f11_name                                                        AS [Feeder11],
               ROUND(f11.energy_wh  / 1000000.0, 2)                               AS [F11 (MWh)],
               ROUND(ld.dt_total_wh / 1000000.0, 2)                               AS [DT Suma (MWh)],
               ROUND((f11.energy_wh - ld.dt_total_wh) / 1000000.0, 2)             AS [Gubici (MWh)],
               ROUND((f11.energy_wh - ld.dt_total_wh) / f11.energy_wh * 100, 2)   AS [Gubici (%)],
               dc.dt_with_reads                                                    AS [DT merila],
               dc.total_dt                                                         AS [DT ukupno],
               ROUND(dc.dt_with_reads * 100.0 / dc.total_dt, 0)                   AS [Pokr. (%)]
        FROM   latest_f11 f11
        JOIN   Substations s  ON s.Id          = f11.SsId
        JOIN   latest_dt ld   ON ld.Feeder11Id = f11.f11_id
        JOIN   dt_coverage dc ON dc.Feeder11Id = f11.f11_id
        WHERE  f11.energy_wh > 0
        ORDER BY [Gubici (%)] DESC
        """
        df = pd.read_sql(query, conn)
        return df
    finally:
        conn.close()


@st.cache_data
def load_losses() -> pd.DataFrame:
    conn = get_connection()
    try:
        query = """
        WITH has_reads AS (
            SELECT DISTINCT Mid FROM MeterReadTfes
        ),
        f11_coverage AS (
            SELECT f.SsId,
                   COUNT(*) AS total_f11,
                   SUM(CASE WHEN f.MeterId IS NOT NULL AND hr.Mid IS NOT NULL
                            THEN 1 ELSE 0 END) AS f11_with_reads
            FROM   Feeders11 f
            LEFT JOIN has_reads hr ON hr.Mid = f.MeterId
            GROUP BY f.SsId
        ),
        f33_ss_count AS (
            SELECT Feeders33Id, COUNT(DISTINCT SubstationsId) AS ss_count
            FROM   Feeder33Substation
            GROUP BY Feeders33Id
        ),
        latest_f33 AS (
            SELECT f.Id    AS f33_id,
                   f.Name  AS f33_name,
                   f.TsId,
                   t.Val * ISNULL(m.MultiplierFactor, 1) AS energy_wh,
                   fsc.ss_count
            FROM   Feeders33 f
            JOIN   f33_ss_count fsc ON fsc.Feeders33Id = f.Id
            JOIN   Meters m ON m.Id = f.MeterId
            JOIN   (
                SELECT Mid, Val,
                       ROW_NUMBER() OVER (PARTITION BY Mid ORDER BY Ts DESC) AS rn
                FROM   MeterReadTfes
            ) t ON t.Mid = f.MeterId AND t.rn = 1
            WHERE  f.MeterId IS NOT NULL AND f.IsDeleted = 0
        ),
        latest_f11 AS (
            SELECT f.SsId,
                   SUM(t.Val * ISNULL(m.MultiplierFactor, 1)) AS f11_total_wh
            FROM   Feeders11 f
            JOIN   Meters m ON m.Id = f.MeterId
            JOIN   (
                SELECT Mid, Val,
                       ROW_NUMBER() OVER (PARTITION BY Mid ORDER BY Ts DESC) AS rn
                FROM   MeterReadTfes
            ) t ON t.Mid = f.MeterId AND t.rn = 1
            WHERE  f.MeterId IS NOT NULL
            GROUP BY f.SsId
        ),
        ss_totals AS (
            SELECT s.Id                             AS ss_id,
                   s.Name                           AS ss_name,
                   STRING_AGG(ts.Name, ', ')        AS ts_names,
                   STRING_AGG(f33.f33_name, ', ')   AS feeders33,
                   SUM(f33.energy_wh)               AS f33_total_wh,
                   MAX(lf.f11_total_wh)             AS f11_total_wh,
                   MAX(fc.total_f11)                AS total_f11,
                   MAX(fc.f11_with_reads)           AS f11_with_reads,
                   MAX(f33.ss_count)                AS max_ss_per_f33
            FROM   Substations s
            JOIN   Feeder33Substation fs ON fs.SubstationsId = s.Id
            JOIN   latest_f33 f33        ON f33.f33_id       = fs.Feeders33Id
            JOIN   TransmissionStations ts ON ts.Id          = f33.TsId
            JOIN   latest_f11 lf         ON lf.SsId          = s.Id
            JOIN   f11_coverage fc       ON fc.SsId          = s.Id
            WHERE  f33.energy_wh > 0
            GROUP BY s.Id, s.Name
        )
        SELECT ts_names                                                         AS [TS],
               ss_name                                                          AS [Podstanica (SS)],
               feeders33                                                        AS [Feeder33],
               ROUND(f33_total_wh / 1000000.0, 2)                              AS [F33 (MWh)],
               ROUND(f11_total_wh / 1000000.0, 2)                              AS [F11 (MWh)],
               ROUND((f33_total_wh - f11_total_wh) / 1000000.0, 2)             AS [Gubici (MWh)],
               ROUND((f33_total_wh - f11_total_wh) / f33_total_wh * 100, 2)    AS [Gubici (%)],
               f11_with_reads                                                   AS [F11 merila],
               total_f11                                                        AS [F11 ukupno],
               ROUND(f11_with_reads * 100.0 / total_f11, 0)                    AS [Pokr. (%)],
               max_ss_per_f33                                                   AS [F33 deli SS]
        FROM   ss_totals
        ORDER BY [Gubici (%)] DESC
        """
        df = pd.read_sql(query, conn)
        return df
    finally:
        conn.close()


_ANOMALY_THRESHOLD = 70
_MIN_COVERAGE_PCT = 30


def _split_results(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Returns (reliable, low_coverage, anomaly).

    anomaly     — Gubici < 0% ili > 70%: matematički nemoguće, netačno merenje
    low_coverage— Pokr. < 30%: DT pokrivenost preniska za pouzdane gubitke
    reliable    — ostatak
    """
    anom_mask = (df["Gubici (%)"] < 0) | (df["Gubici (%)"] > _ANOMALY_THRESHOLD)
    non_anom = df[~anom_mask].reset_index(drop=True)
    low_cov_mask = non_anom["Pokr. (%)"] < _MIN_COVERAGE_PCT
    return (
        non_anom[~low_cov_mask].reset_index(drop=True),
        non_anom[low_cov_mask].reset_index(drop=True),
        df[anom_mask].reset_index(drop=True),
    )


def _loss_color_point(pct: float) -> str:
    if pct > 20:
        return "#e53e3e"
    if pct > 10:
        return "#FF8C00"
    if pct > 5:
        return "#ECC94B"
    return "#1db954"


def _scatter_losses(df: pd.DataFrame, mwh_col: str, label_col: str, title: str) -> None:
    max_loss = max(df["Gubici (%)"].max() * 1.15, 25)

    fig = go.Figure()

    # Reference lines
    for y, color, name in [
        (5,  "rgba(29,185,84,0.45)",  "5% prag"),
        (10, "rgba(255,140,0,0.45)",  "10% prag"),
        (20, "rgba(229,62,62,0.45)",  "20% prag"),
    ]:
        fig.add_hline(
            y=y,
            line=dict(color=color, width=1.5, dash="dot"),
            annotation_text=f" {y}%",
            annotation_font=dict(color=color, size=10),
            annotation_position="right",
        )

    # Bubble size scaled to MWh
    mwh = df[mwh_col].fillna(0)
    max_mwh = mwh.max() if mwh.max() > 0 else 1
    sizes = (mwh / max_mwh * 35 + 8).clip(8, 45)
    colors = df["Gubici (%)"].apply(_loss_color_point)

    fig.add_trace(go.Scatter(
        x=df["Pokr. (%)"],
        y=df["Gubici (%)"],
        mode="markers+text",
        text=df[label_col],
        textposition="top center",
        textfont=dict(size=9, color="#718096"),
        marker=dict(
            size=sizes,
            color=colors,
            line=dict(color="rgba(255,255,255,0.2)", width=1),
            opacity=0.88,
        ),
        hovertemplate=(
            "<b>%{text}</b><br>"
            "Pokrivenost merenja: <b>%{x:.0f}%</b><br>"
            "Gubici: <b>%{y:.2f}%</b><br>"
            "<extra></extra>"
        ),
        showlegend=False,
    ))

    # Invisible legend markers for loss zones
    for label, color in [
        ("≤ 5% — prihvatljivo", "#1db954"),
        ("5–10% — povišeno",    "#ECC94B"),
        ("10–20% — kritično",   "#FF8C00"),
        ("> 20% — alarm",       "#e53e3e"),
    ]:
        fig.add_trace(go.Scatter(
            x=[None], y=[None], mode="markers",
            marker=dict(size=10, color=color),
            name=label,
        ))

    apply_dark_theme(fig)
    fig.update_layout(
        title=title,
        xaxis_title="Pokrivenost merenja (%) — pouzdanost podataka",
        yaxis_title="Gubici energije (%)",
        xaxis=dict(range=[-5, 105]),
        yaxis=dict(range=[-1, max_loss]),
        height=480,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    st.plotly_chart(fig, use_container_width=True)


def _styled_table(df: pd.DataFrame, coverage_col: str = "Pokr. (%)") -> None:
    def highlight_row(row):
        styles = [""] * len(row)
        pct = row.get("Gubici (%)", 0)
        pokr = row.get(coverage_col, 100)
        deli = row.get("F33 deli SS", 1)
        loss_col = df.columns.get_loc("Gubici (%)")
        if pokr < 100 or deli > 1:
            styles[loss_col] = "background-color: #2d2d00; color: #ECC94B"
        elif pct > 20:
            styles[loss_col] = "background-color: #3d0a0a; color: #e53e3e"
        elif pct > 10:
            styles[loss_col] = "background-color: #2d1500; color: #FF8C00"
        elif pct > 5:
            styles[loss_col] = "background-color: #2d2000; color: #ECC94B"
        return styles

    st.dataframe(df.style.apply(highlight_row, axis=1), use_container_width=True, height=420)


def show_losses() -> None:
    # ── SS nivo ───────────────────────────────────────────────────────────────
    st.markdown(
        '<h3 style="color:#FF6B35;font-size:1.15rem;font-weight:700;'
        'text-transform:uppercase;letter-spacing:0.06em;margin-bottom:1rem;">'
        '📉 Gubici po podstanicama (SS)</h3>',
        unsafe_allow_html=True,
    )

    df = load_losses()

    if df.empty:
        st.warning("Nema podataka za analizu gubitaka.")
        return

    df_ok, df_lowcov, df_anom = _split_results(df)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("SS pouzdano (Pokr. ≥30%)", len(df_ok))
    col2.metric("Ukupni gubici (MWh)", f"{df_ok['Gubici (MWh)'].sum():,.0f}")
    col3.metric("Prosječni gubici", f"{df_ok['Gubici (%)'].mean():.1f}%")
    col4.metric("SS nepotpuna merenja", len(df_lowcov),
                help=f"Pokr. <{_MIN_COVERAGE_PCT}% — gubici nisu pouzdani")

    if df_ok.empty:
        st.info("Nema SS sa dovoljnom pokrivenošću merenja (≥30%) za pouzdanu analizu gubitaka.")
    else:
        _scatter_losses(
            df_ok,
            mwh_col="F33 (MWh)",
            label_col="Podstanica (SS)",
            title="Pouzdanost mjerenja vs. Gubici energije — nivo SS (Pokr. ≥ 30%)",
        )
        st.caption(
            "Prikazane samo SS sa ≥30% pokrivenosti DT merenja. "
            "Tačke gore-desno (visoka pokrivenost + visoki gubici) = potvrđene problematične SS."
        )
        with st.expander(f"Tabela — {len(df_ok)} podstanica (pouzdano)", expanded=False):
            _styled_table(df_ok)
            st.caption("Boje: 🟨 deljeni F33 | 🟥 >20% | 🟧 >10% | 🟡 >5%")

    if not df_lowcov.empty:
        with st.expander(
            f"⚠️ Nepotpuna merenja — {len(df_lowcov)} SS sa Pokr. <{_MIN_COVERAGE_PCT}% "
            f"(gubici precenjeni, prikazano informativno)",
            expanded=False,
        ):
            st.caption(
                f"Pokr. <{_MIN_COVERAGE_PCT}%: DT merači pokrivaju premalo potrošnje — "
                "izračunati gubici su gornja granica, ne stvarna vrednost."
            )
            _styled_table(df_lowcov)

    if not df_anom.empty:
        with st.expander(
            f"⚠️ Anomalije ({len(df_anom)} SS — gubici < 0% ili > {_ANOMALY_THRESHOLD}%)",
            expanded=False,
        ):
            st.caption(
                "Nerealne vrednosti — neusklađena kumulativna merila, deljeni F33, nepotpuno merenje."
            )

            def highlight_anom(row):
                styles = [""] * len(row)
                loss_col = df_anom.columns.get_loc("Gubici (%)")
                pct = row.get("Gubici (%)", 0)
                styles[loss_col] = (
                    "background-color: #1a1a6e; color: #90cdf4"
                    if pct < 0
                    else "background-color: #3d0a0a; color: #e53e3e"
                )
                return styles

            st.dataframe(df_anom.style.apply(highlight_anom, axis=1), use_container_width=True)

    st.divider()

    # ── F11 nivo ──────────────────────────────────────────────────────────────
    st.markdown(
        '<h3 style="color:#FF6B35;font-size:1.15rem;font-weight:700;'
        'text-transform:uppercase;letter-spacing:0.06em;margin-bottom:1rem;">'
        '📉 Gubici po Feeder11 fiderima</h3>',
        unsafe_allow_html=True,
    )

    df11 = load_f11_losses()

    if df11.empty:
        st.warning("Nema F11 podataka za analizu gubitaka.")
        return

    df11_ok, df11_lowcov, df11_anom = _split_results(df11)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("F11 pouzdano (Pokr. ≥30%)", len(df11_ok))
    col2.metric("Ukupni gubici F11 (MWh)", f"{df11_ok['Gubici (MWh)'].sum():,.0f}")
    col3.metric("Prosječni gubici F11", f"{df11_ok['Gubici (%)'].mean():.1f}%")
    col4.metric("F11 nepotpuna merenja", len(df11_lowcov),
                help=f"Pokr. <{_MIN_COVERAGE_PCT}% — gubici precenjeni")

    if df11_ok.empty:
        st.info("Nema F11 fidera sa dovoljnom pokrivenošću merenja (≥30%).")
    else:
        _scatter_losses(
            df11_ok,
            mwh_col="F11 (MWh)",
            label_col="Feeder11",
            title="Pouzdanost mjerenja vs. Gubici energije — nivo F11 (Pokr. ≥ 30%)",
        )
        st.caption(
            "Prikazani samo F11 fideri sa ≥30% DT pokrivenosti. "
            "Tačke gore-desno = potvrđeni visoki gubici — prioritet za terensku inspekciju."
        )
        with st.expander(f"Tabela — {len(df11_ok)} F11 fidera (pouzdano)", expanded=False):

            def highlight_f11(row):
                styles = [""] * len(row)
                pct = row.get("Gubici (%)", 0)
                loss_col = df11_ok.columns.get_loc("Gubici (%)")
                if pct > 20:
                    styles[loss_col] = "background-color: #3d0a0a; color: #e53e3e"
                elif pct > 10:
                    styles[loss_col] = "background-color: #2d1500; color: #FF8C00"
                elif pct > 5:
                    styles[loss_col] = "background-color: #2d2000; color: #ECC94B"
                return styles

            st.dataframe(df11_ok.style.apply(highlight_f11, axis=1), use_container_width=True, height=420)

    if not df11_lowcov.empty:
        with st.expander(
            f"⚠️ Nepotpuna merenja — {len(df11_lowcov)} F11 sa Pokr. <{_MIN_COVERAGE_PCT}% "
            f"(gubici precenjeni)",
            expanded=False,
        ):
            st.caption(
                f"Pokr. <{_MIN_COVERAGE_PCT}%: izmerena DT potrošnja pokriva manje od trećine fidera. "
                "Gubici su razlika F11_energija − parcijalni_DT_zbir, tj. gornja granica."
            )
            st.dataframe(df11_lowcov, use_container_width=True, height=300)

    if not df11_anom.empty:
        with st.expander(
            f"⚠️ Anomalije F11 ({len(df11_anom)} fidera — gubici < 0% ili > {_ANOMALY_THRESHOLD}%)",
            expanded=False,
        ):
            st.caption(
                "Uzroci: neusklađena kumulativna merila (F11 meter stariji od DT merila), nepotpuno DT merenje."
            )

            def highlight_f11_anom(row):
                styles = [""] * len(row)
                loss_col = df11_anom.columns.get_loc("Gubici (%)")
                pct = row.get("Gubici (%)", 0)
                styles[loss_col] = (
                    "background-color: #1a1a6e; color: #90cdf4"
                    if pct < 0
                    else "background-color: #3d0a0a; color: #e53e3e"
                )
                return styles

            st.dataframe(df11_anom.style.apply(highlight_f11_anom, axis=1), use_container_width=True)
