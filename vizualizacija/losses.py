import pandas as pd
import streamlit as st
from db import get_connection


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
            -- Koliko SS svaki F33 hrani (da bi detektovali deljene fidere)
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


_ANOMALY_THRESHOLD = 70  # % — iznad ovoga ili ispod 0 smatramo anomalijom


def _split_anomalies(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    mask = (df["Gubici (%)"] < 0) | (df["Gubici (%)"] > _ANOMALY_THRESHOLD)
    return df[~mask].reset_index(drop=True), df[mask].reset_index(drop=True)


def show_losses() -> None:
    st.subheader("Analiza gubitaka po podstanicama (SS)")

    df = load_losses()

    if df.empty:
        st.warning("Nema podataka za analizu gubitaka.")
        return

    df_normal, df_anom = _split_anomalies(df)

    col1, col2, col3 = st.columns(3)
    col1.metric("SS u analizi", len(df_normal))
    col2.metric("Ukupni gubici (MWh)", f"{df_normal['Gubici (MWh)'].sum():,.0f}")
    col3.metric("Prosečni gubici (%)", f"{df_normal['Gubici (%)'].mean():.1f}%")

    def highlight_row(row):
        styles = [""] * len(row)
        pct = row.get("Gubici (%)", 0)
        pokr = row.get("Pokr. (%)", 100)
        deli = row.get("F33 deli SS", 1)
        loss_col = df_normal.columns.get_loc("Gubici (%)")
        if pokr < 100 or deli > 1:
            styles[loss_col] = "background-color: #4a4a00; color: white"
        elif pct > 20:
            styles[loss_col] = "background-color: #8b0000; color: white"
        elif pct > 10:
            styles[loss_col] = "background-color: #cc4400; color: white"
        elif pct > 5:
            styles[loss_col] = "background-color: #997700; color: white"
        return styles

    st.dataframe(df_normal.style.apply(highlight_row, axis=1), use_container_width=True, height=500)
    st.caption(
        "Boje kolone Gubici (%): "
        "🟨 nepouzdani (nepotpuna merila ili deljeni F33) | "
        "🟥 >20% | 🟧 >10% | 🟨 >5%"
    )

    if not df_anom.empty:
        with st.expander(f"Anomalije SS ({len(df_anom)} redova — gubici < 0% ili > {_ANOMALY_THRESHOLD}%)", expanded=False):
            st.caption(
                "Ovi redovi imaju nerealne vrednosti gubitaka. "
                "Uzroci: neusklađena kumulativna merila, deljeni F33 fideri, nepotpuno merenje."
            )

            def highlight_anom(row):
                styles = [""] * len(row)
                loss_col = df_anom.columns.get_loc("Gubici (%)")
                pct = row.get("Gubici (%)", 0)
                if pct < 0:
                    styles[loss_col] = "background-color: #1a1a6e; color: white"
                else:
                    styles[loss_col] = "background-color: #8b0000; color: white"
                return styles

            st.dataframe(df_anom.style.apply(highlight_anom, axis=1), use_container_width=True)

    st.divider()
    st.subheader("Analiza gubitaka po Feeder11 fiderima")

    df11 = load_f11_losses()

    if df11.empty:
        st.warning("Nema F11 podataka za analizu gubitaka.")
        return

    df11_normal, df11_anom = _split_anomalies(df11)

    col1, col2, col3 = st.columns(3)
    col1.metric("F11 fidera u analizi", len(df11_normal))
    col2.metric("Ukupni gubici F11 (MWh)", f"{df11_normal['Gubici (MWh)'].sum():,.0f}")
    col3.metric("Prosečni gubici F11 (%)", f"{df11_normal['Gubici (%)'].mean():.1f}%")

    def highlight_f11(row):
        styles = [""] * len(row)
        pct = row.get("Gubici (%)", 0)
        pokr = row.get("Pokr. (%)", 100)
        loss_col = df11_normal.columns.get_loc("Gubici (%)")
        if pokr < 100:
            styles[loss_col] = "background-color: #4a4a00; color: white"
        elif pct > 20:
            styles[loss_col] = "background-color: #8b0000; color: white"
        elif pct > 10:
            styles[loss_col] = "background-color: #cc4400; color: white"
        elif pct > 5:
            styles[loss_col] = "background-color: #997700; color: white"
        return styles

    st.dataframe(df11_normal.style.apply(highlight_f11, axis=1), use_container_width=True, height=500)
    st.caption(
        "Gubici F11 = F11 energija − Zbir DT merila na tom fideru. "
        "Boje: 🟨 nepotpuna DT merila | 🟥 >20% | 🟧 >10% | 🟨 >5%"
    )

    if not df11_anom.empty:
        with st.expander(f"Anomalije F11 ({len(df11_anom)} redova — gubici < 0% ili > {_ANOMALY_THRESHOLD}%)", expanded=False):
            st.caption(
                "Ovi redovi imaju nerealne vrednosti gubitaka. "
                "Uzroci: neusklađena kumulativna merila (F11 meter stariji od DT merila), nepotpuno DT merenje."
            )

            def highlight_f11_anom(row):
                styles = [""] * len(row)
                loss_col = df11_anom.columns.get_loc("Gubici (%)")
                pct = row.get("Gubici (%)", 0)
                if pct < 0:
                    styles[loss_col] = "background-color: #1a1a6e; color: white"
                else:
                    styles[loss_col] = "background-color: #8b0000; color: white"
                return styles

            st.dataframe(df11_anom.style.apply(highlight_f11_anom, axis=1), use_container_width=True)
