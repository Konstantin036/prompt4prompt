import plotly.graph_objects as go
import pandas as pd
import streamlit as st
from db import get_connection
from theme import ZONE_COLORS_CHART, ZONE_COLORS_TABLE, apply_dark_theme

_ZONE_COLORS = ZONE_COLORS_TABLE


def _color_load(pct: float) -> str:
    if pct >= 85:
        return "Kritično"
    if pct >= 70:
        return "Upozorenje"
    return "Normalno"


@st.cache_data
def load_f11() -> pd.DataFrame:
    """Load factor per F11 feeder — measured S_kVA vs nominal NameplateRating."""
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
                   MAX(CASE WHEN mr.Cid = 11 THEN mr.Val END) AS I_C
            FROM MeterReads mr
            JOIN latest_ts lt ON lt.Mid = mr.Mid AND mr.Ts = lt.ts
            WHERE mr.Cid IN (6,7,8,9,10,11)
            GROUP BY mr.Mid
        ),
        s_dt AS (
            SELECT Mid,
                   ROUND((
                       ISNULL(V_A * I_A, 0) +
                       ISNULL(V_B * I_B, 0) +
                       ISNULL(V_C * I_C, 0)
                   ) / 1000000.0, 2) AS S_kVA
            FROM pivoted
            WHERE ((V_A IS NOT NULL AND I_A IS NOT NULL)
               OR  (V_B IS NOT NULL AND I_B IS NOT NULL)
               OR  (V_C IS NOT NULL AND I_C IS NOT NULL))
              -- Exclude meters on 11kV primary side (V > 30000 centivolt = > 300V)
              AND ISNULL(V_A, 0) < 30000
              AND ISNULL(V_B, 0) < 30000
              AND ISNULL(V_C, 0) < 30000
        ),
        f11_load AS (
            SELECT
                d.Feeder11Id,
                SUM(ISNULL(s.S_kVA, 0))                                              AS S_measured_kVA,
                -- S_nominal only for DTs that have reads — ensures apples-to-apples comparison
                SUM(CASE WHEN s.Mid IS NOT NULL THEN d.NameplateRating ELSE 0 END) * 1.0 AS S_nominal_kVA,
                SUM(d.NameplateRating) * 1.0                                          AS S_nominal_all_kVA,
                COUNT(*)                                                               AS dt_total,
                SUM(CASE WHEN s.Mid IS NOT NULL THEN 1 ELSE 0 END)                   AS dt_with_reads
            FROM DistributionSubstation d
            LEFT JOIN s_dt s ON s.Mid = d.MeterId
            WHERE d.Feeder11Id IS NOT NULL AND d.NameplateRating > 0
            GROUP BY d.Feeder11Id
        )
        SELECT
            ISNULL((
                SELECT TOP 1 ts2.Name
                FROM Feeder33Substation fs2
                JOIN Feeders33 f33b ON f33b.Id = fs2.Feeders33Id
                JOIN TransmissionStations ts2 ON ts2.Id = f33b.TsId
                WHERE fs2.SubstationsId = f11.SsId
            ), 'N/A')                                               AS [TS],
            sub.Name                                                AS [Podstanica (SS)],
            f11.Name                                                AS [Feeder11],
            ROUND(fl.S_measured_kVA, 2)                            AS [S mereno (kVA)],
            ROUND(fl.S_nominal_kVA, 2)                             AS [S nominalno (kVA)],
            ROUND(fl.S_nominal_all_kVA, 2)                         AS [S nominalno sve DT (kVA)],
            ROUND(fl.S_measured_kVA / fl.S_nominal_kVA * 100, 1)  AS [Opterećenje (%)],
            fl.dt_with_reads                                        AS [DT merila],
            fl.dt_total                                             AS [DT ukupno],
            ROUND(fl.dt_with_reads * 100.0 / fl.dt_total, 0)      AS [Pokr. (%)]
        FROM f11_load fl
        JOIN Feeders11 f11   ON f11.Id  = fl.Feeder11Id
        JOIN Substations sub ON sub.Id  = f11.SsId
        WHERE fl.S_nominal_kVA > 0 AND fl.dt_with_reads > 0
        ORDER BY [Opterećenje (%)] DESC
        """
        return pd.read_sql(query, conn)
    finally:
        conn.close()


@st.cache_data
def load_f11_no_reads() -> pd.DataFrame:
    """F11 feeders where no DT has V/I readings."""
    conn = get_connection()
    try:
        query = """
        WITH meters_with_reads AS (
            SELECT DISTINCT Mid FROM MeterReads WHERE Cid IN (6,7,8,9,10,11)
        ),
        f11_stats AS (
            SELECT
                d.Feeder11Id,
                COUNT(*)                                                     AS dt_total,
                SUM(d.NameplateRating) * 1.0                                AS S_nominal_kVA,
                SUM(CASE WHEN mwr.Mid IS NOT NULL THEN 1 ELSE 0 END)        AS dt_with_reads
            FROM DistributionSubstation d
            LEFT JOIN meters_with_reads mwr ON mwr.Mid = d.MeterId
            WHERE d.Feeder11Id IS NOT NULL
            GROUP BY d.Feeder11Id
        )
        SELECT
            ISNULL((
                SELECT TOP 1 ts2.Name
                FROM Feeder33Substation fs2
                JOIN Feeders33 f33b ON f33b.Id = fs2.Feeders33Id
                JOIN TransmissionStations ts2 ON ts2.Id = f33b.TsId
                WHERE fs2.SubstationsId = f11.SsId
            ), 'N/A')                        AS [TS],
            sub.Name                         AS [Podstanica (SS)],
            f11.Name                         AS [Feeder11],
            fs.dt_total                      AS [DT ukupno],
            ROUND(fs.S_nominal_kVA, 2)      AS [Nominalni kapacitet (kVA)]
        FROM f11_stats fs
        JOIN Feeders11 f11   ON f11.Id = fs.Feeder11Id
        JOIN Substations sub ON sub.Id = f11.SsId
        WHERE fs.dt_with_reads = 0
        ORDER BY sub.Name, f11.Name
        """
        return pd.read_sql(query, conn)
    finally:
        conn.close()


@st.cache_data
def load_f33() -> pd.DataFrame:
    """Load factor per F33 feeder — sum of DT measured loads vs sum of DT ratings."""
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
                   MAX(CASE WHEN mr.Cid = 11 THEN mr.Val END) AS I_C
            FROM MeterReads mr
            JOIN latest_ts lt ON lt.Mid = mr.Mid AND mr.Ts = lt.ts
            WHERE mr.Cid IN (6,7,8,9,10,11)
            GROUP BY mr.Mid
        ),
        s_dt AS (
            SELECT Mid,
                   ROUND((
                       ISNULL(V_A * I_A, 0) +
                       ISNULL(V_B * I_B, 0) +
                       ISNULL(V_C * I_C, 0)
                   ) / 1000000.0, 2) AS S_kVA
            FROM pivoted
            WHERE ((V_A IS NOT NULL AND I_A IS NOT NULL)
               OR  (V_B IS NOT NULL AND I_B IS NOT NULL)
               OR  (V_C IS NOT NULL AND I_C IS NOT NULL))
              AND ISNULL(V_A, 0) < 30000
              AND ISNULL(V_B, 0) < 30000
              AND ISNULL(V_C, 0) < 30000
        ),
        dt_load AS (
            SELECT
                d.Feeder11Id,
                SUM(ISNULL(s.S_kVA, 0))                                              AS S_measured_kVA,
                SUM(CASE WHEN s.Mid IS NOT NULL THEN d.NameplateRating ELSE 0 END) * 1.0 AS S_nominal_kVA,
                SUM(d.NameplateRating) * 1.0                                          AS S_nominal_all_kVA,
                SUM(CASE WHEN s.Mid IS NOT NULL THEN 1 ELSE 0 END)                   AS dt_with_reads,
                COUNT(*)                                                               AS dt_total
            FROM DistributionSubstation d
            LEFT JOIN s_dt s ON s.Mid = d.MeterId
            WHERE d.Feeder11Id IS NOT NULL AND d.NameplateRating > 0
            GROUP BY d.Feeder11Id
        ),
        f33_load AS (
            SELECT
                fs.Feeders33Id,
                SUM(dl.S_measured_kVA)             AS S_measured_kVA,
                SUM(dl.S_nominal_kVA)              AS S_nominal_kVA,
                SUM(dl.S_nominal_all_kVA)          AS S_nominal_all_kVA,
                SUM(dl.dt_with_reads)              AS dt_with_reads,
                SUM(dl.dt_total)                   AS dt_total,
                STRING_AGG(sub.Name, ', ')         AS ss_names
            FROM dt_load dl
            JOIN Feeders11 f11             ON f11.Id  = dl.Feeder11Id
            JOIN Substations sub           ON sub.Id  = f11.SsId
            JOIN Feeder33Substation fs     ON fs.SubstationsId = sub.Id
            GROUP BY fs.Feeders33Id
        )
        SELECT
            ts.Name                                                          AS [TS],
            f33.Name                                                         AS [Feeder33],
            fl.ss_names                                                      AS [Podstanice (SS)],
            ROUND(fl.S_measured_kVA, 2)                                     AS [S mereno (kVA)],
            ROUND(fl.S_nominal_kVA, 2)                                      AS [S nominalno (kVA)],
            ROUND(fl.S_nominal_all_kVA, 2)                                  AS [S nominalno sve DT (kVA)],
            ROUND(fl.S_measured_kVA / fl.S_nominal_kVA * 100, 1)           AS [Opterećenje (%)],
            fl.dt_with_reads                                                 AS [DT merila],
            fl.dt_total                                                      AS [DT ukupno],
            ROUND(fl.dt_with_reads * 100.0 / fl.dt_total, 0)               AS [Pokr. (%)]
        FROM f33_load fl
        JOIN Feeders33 f33             ON f33.Id  = fl.Feeders33Id
        JOIN TransmissionStations ts   ON ts.Id   = f33.TsId
        WHERE fl.S_nominal_kVA > 0 AND fl.dt_with_reads > 0
        ORDER BY [Opterećenje (%)] DESC
        """
        return pd.read_sql(query, conn)
    finally:
        conn.close()


@st.cache_data
def load_f33_no_reads() -> pd.DataFrame:
    """F33 feeders where no connected DT has V/I readings."""
    conn = get_connection()
    try:
        query = """
        WITH meters_with_reads AS (
            SELECT DISTINCT Mid FROM MeterReads WHERE Cid IN (6,7,8,9,10,11)
        ),
        dt_stats AS (
            SELECT
                d.Feeder11Id,
                COUNT(*)                                                    AS dt_total,
                SUM(d.NameplateRating) * 1.0                               AS S_nominal_kVA,
                SUM(CASE WHEN mwr.Mid IS NOT NULL THEN 1 ELSE 0 END)       AS dt_with_reads
            FROM DistributionSubstation d
            LEFT JOIN meters_with_reads mwr ON mwr.Mid = d.MeterId
            WHERE d.Feeder11Id IS NOT NULL
            GROUP BY d.Feeder11Id
        ),
        f33_stats AS (
            SELECT
                fs.Feeders33Id,
                SUM(ds.dt_total)                    AS dt_total,
                SUM(ds.S_nominal_kVA)               AS S_nominal_kVA,
                SUM(ds.dt_with_reads)               AS dt_with_reads,
                STRING_AGG(sub.Name, ', ')          AS ss_names
            FROM dt_stats ds
            JOIN Feeders11 f11             ON f11.Id  = ds.Feeder11Id
            JOIN Substations sub           ON sub.Id  = f11.SsId
            JOIN Feeder33Substation fs     ON fs.SubstationsId = sub.Id
            GROUP BY fs.Feeders33Id
        )
        SELECT
            ts.Name                              AS [TS],
            f33.Name                             AS [Feeder33],
            fss.ss_names                         AS [Podstanice (SS)],
            fss.dt_total                         AS [DT ukupno],
            ROUND(fss.S_nominal_kVA, 2)         AS [Nominalni kapacitet (kVA)]
        FROM f33_stats fss
        JOIN Feeders33 f33             ON f33.Id  = fss.Feeders33Id
        JOIN TransmissionStations ts   ON ts.Id   = f33.TsId
        WHERE fss.dt_with_reads = 0
        ORDER BY ts.Name, f33.Name
        """
        return pd.read_sql(query, conn)
    finally:
        conn.close()


def _capacity_scatter(df: pd.DataFrame, name_col: str, section_label: str) -> None:
    """Scatter: X = S nominalno, Y = S mereno, diagonal threshold lines."""
    df = df.copy()
    df["Zona"] = df["Opterećenje (%)"].apply(_color_load)

    max_nom = df["S nominalno (kVA)"].max()
    x_ref = [0, max_nom * 1.05]

    fig = go.Figure()

    # Zone shading (fill between diagonal lines)
    fig.add_trace(go.Scatter(
        x=x_ref + x_ref[::-1],
        y=[0, max_nom * 1.05 * 0.70] + [max_nom * 1.05 * 0.85, 0],
        fill="toself",
        fillcolor="rgba(29,185,84,0.06)",
        line=dict(width=0),
        showlegend=False,
        hoverinfo="skip",
    ))
    fig.add_trace(go.Scatter(
        x=x_ref + x_ref[::-1],
        y=[0, max_nom * 1.05 * 0.85] + [max_nom * 1.05 * 1.0, 0],
        fill="toself",
        fillcolor="rgba(255,140,0,0.06)",
        line=dict(width=0),
        showlegend=False,
        hoverinfo="skip",
    ))
    fig.add_trace(go.Scatter(
        x=x_ref + [x_ref[-1], x_ref[-1]],
        y=[0, max_nom * 1.05 * 1.0] + [max_nom * 1.05 * 1.3, 0],
        fill="toself",
        fillcolor="rgba(229,62,62,0.06)",
        line=dict(width=0),
        showlegend=False,
        hoverinfo="skip",
    ))

    # Threshold diagonal lines
    for factor, color, dash, label in [
        (0.70, "rgba(29,185,84,0.55)",  "dot",    "70% — normalno/upozorenje"),
        (0.85, "rgba(255,140,0,0.55)",  "dot",    "85% — upozorenje/kritično"),
        (1.00, "rgba(229,62,62,0.55)",  "dashdot","100% — nominalni kapacitet"),
    ]:
        fig.add_trace(go.Scatter(
            x=x_ref,
            y=[v * factor for v in x_ref],
            mode="lines",
            line=dict(color=color, width=1.5, dash=dash),
            name=label,
        ))

    # Data points per zone
    marker_size_col = "DT merila"
    for zone in ["Normalno", "Upozorenje", "Kritično"]:
        sub = df[df["Zona"] == zone]
        if sub.empty:
            continue
        sizes = (sub[marker_size_col].clip(1, 50) / df[marker_size_col].max() * 22 + 9)
        fig.add_trace(go.Scatter(
            x=sub["S nominalno (kVA)"],
            y=sub["S mereno (kVA)"],
            mode="markers",
            name=zone,
            marker=dict(
                size=sizes,
                color=ZONE_COLORS_CHART[zone],
                line=dict(color="rgba(255,255,255,0.25)", width=1),
                opacity=0.9,
            ),
            text=sub[name_col],
            customdata=sub[["Opterećenje (%)", "DT merila", "DT ukupno", "Pokr. (%)"]].values,
            hovertemplate=(
                "<b>%{text}</b><br>"
                "S nominalno: <b>%{x:,.0f} kVA</b><br>"
                "S mereno: <b>%{y:,.0f} kVA</b><br>"
                "Opterećenje: <b>%{customdata[0]:.1f}%</b><br>"
                "DT merila / ukupno: %{customdata[1]} / %{customdata[2]}<br>"
                "Pokrivenost: %{customdata[3]:.0f}%<br>"
                "<extra></extra>"
            ),
        ))

    apply_dark_theme(fig)
    fig.update_layout(
        title=f"Instalisani kapacitet vs. Trenutno opterećenje — {section_label}",
        xaxis_title="S nominalno merenih DT (kVA) — kapacitet samo transformatora sa merenjima",
        yaxis_title="S mereno (kVA) — izmjereno opterećenje",
        height=520,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    st.plotly_chart(fig, use_container_width=True)
    st.caption(
        "Svaka tačka = jedan fider. Veličina tačke = broj DT stanica sa merenjima. "
        "Tačke iznad crvene linije = preopterećen fider. "
        "Zelena zona ≤ 70% | Žuta 70–85% | Crvena > 85%."
    )


def _styled_load_table(df: pd.DataFrame) -> None:
    def _highlight(row):
        styles = [""] * len(row)
        idx = df.columns.get_loc("Opterećenje (%)")
        zone = _color_load(row["Opterećenje (%)"])
        color = _ZONE_COLORS[zone]
        styles[idx] = f"background-color: {color}; color: white"
        return styles

    display_cols = [c for c in df.columns if c != "Zona"]
    st.dataframe(
        df[display_cols].style.apply(_highlight, axis=1),
        use_container_width=True,
        height=380,
    )


def _render_load_section(
    df: pd.DataFrame,
    df_no: pd.DataFrame,
    name_col: str,
    section_label: str,
) -> None:
    if df.empty:
        st.info(f"Nema mernih podataka za {section_label}.")
    else:
        df = df.copy()
        df["Zona"] = df["Opterećenje (%)"].apply(_color_load)

        col1, col2, col3 = st.columns(3)
        col1.metric(f"{section_label} u analizi", len(df))
        col2.metric(
            "Kritično opterećenih",
            int((df["Zona"] == "Kritično").sum()),
        )
        col3.metric(
            "Prosječno opterećenje",
            f"{df['Opterećenje (%)'].mean():.1f}%",
        )

        _capacity_scatter(df, name_col, section_label)

        with st.expander(f"Tabela — {len(df)} {section_label}", expanded=False):
            _styled_load_table(df)

    if not df_no.empty:
        with st.expander(
            f"⚠️ {section_label} bez merenja ({len(df_no)}) — potreban terenski pregled",
            expanded=False,
        ):
            st.dataframe(df_no, use_container_width=True)


def show_load() -> None:
    st.markdown(
        '<h3 style="color:#FF6B35;font-size:1.15rem;font-weight:700;'
        'text-transform:uppercase;letter-spacing:0.06em;margin-bottom:1rem;">'
        '⚡ Opterećenje F11 fidera</h3>',
        unsafe_allow_html=True,
    )
    _render_load_section(
        df=load_f11(),
        df_no=load_f11_no_reads(),
        name_col="Feeder11",
        section_label="F11 fidera",
    )

    st.divider()

    st.markdown(
        '<h3 style="color:#FF6B35;font-size:1.15rem;font-weight:700;'
        'text-transform:uppercase;letter-spacing:0.06em;margin-bottom:1rem;">'
        '⚡ Opterećenje F33 fidera</h3>',
        unsafe_allow_html=True,
    )
    _render_load_section(
        df=load_f33(),
        df_no=load_f33_no_reads(),
        name_col="Feeder33",
        section_label="F33 fidera",
    )
