import pandas as pd
import streamlit as st
from db import get_connection


@st.cache_data
def load_losses() -> pd.DataFrame:
    conn = get_connection()
    try:
        query = """
        WITH latest_f33 AS (
            SELECT f.Id   AS f33_id,
                   f.Name AS f33_name,
                   t.Val * ISNULL(m.MultiplierFactor, 1) AS energy_wh
            FROM   Feeders33 f
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
                   SUM(t.Val * ISNULL(m.MultiplierFactor, 1)) AS f11_total_wh,
                   COUNT(*) AS f11_meter_count
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
            -- Za svaku SS: zbir svih F33 koji u nju ulaze + F11 suma koja iz nje izlazi
            SELECT s.Id                         AS ss_id,
                   s.Name                       AS ss_name,
                   STRING_AGG(f33.f33_name, ', ') AS feeders33,
                   SUM(f33.energy_wh)           AS f33_total_wh,
                   MAX(lf.f11_total_wh)         AS f11_total_wh,
                   MAX(lf.f11_meter_count)      AS f11_meter_count
            FROM   Substations s
            JOIN   Feeder33Substation fs  ON fs.SubstationsId = s.Id
            JOIN   latest_f33 f33         ON f33.f33_id       = fs.Feeders33Id
            JOIN   latest_f11 lf          ON lf.SsId          = s.Id
            WHERE  f33.energy_wh > 0
            GROUP BY s.Id, s.Name
        )
        SELECT ss_name                                                    AS [Podstanica (SS)],
               feeders33                                                  AS [Feeder33 fideri],
               ROUND(f33_total_wh  / 1000000.0, 2)                       AS [F33 Ukupno (MWh)],
               ROUND(f11_total_wh  / 1000000.0, 2)                       AS [F11 Suma (MWh)],
               ROUND((f33_total_wh - f11_total_wh) / 1000000.0, 2)       AS [Gubici (MWh)],
               ROUND((f33_total_wh - f11_total_wh) / f33_total_wh * 100, 2) AS [Gubici (%)],
               f11_meter_count                                            AS [Br. F11 merila]
        FROM   ss_totals
        ORDER BY [Gubici (%)] DESC
        """
        df = pd.read_sql(query, conn)
        return df
    finally:
        conn.close()


def show_losses() -> None:
    st.subheader("Analiza gubitaka po podstanicama (SS)")
    st.caption(
        "Gubici = Zbir energija svih F33 koji ulaze u SS − Suma energija F11 fidere koji izlaze iz SS. "
        "Prikazane su samo SS gde postoje aktivna F11 merila."
    )

    df = load_losses()

    if df.empty:
        st.warning("Nema podataka za analizu gubitaka.")
        return

    col1, col2, col3 = st.columns(3)
    col1.metric("SS u analizi", len(df))
    col2.metric("Ukupni gubici (MWh)", f"{df['Gubici (MWh)'].sum():,.0f}")
    col3.metric("Prosečni gubici (%)", f"{df['Gubici (%)'].mean():.1f}%")

    def highlight_losses(val):
        if isinstance(val, float):
            if val > 20:
                return "background-color: #8b0000; color: white"
            if val > 10:
                return "background-color: #cc4400; color: white"
            if val > 5:
                return "background-color: #997700; color: white"
        return ""

    styled = df.style.map(highlight_losses, subset=["Gubici (%)"])
    st.dataframe(styled, use_container_width=True, height=500)
