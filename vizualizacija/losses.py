import pandas as pd
import streamlit as st
from db import get_connection


@st.cache_data
def load_losses() -> pd.DataFrame:
    conn = get_connection()
    try:
        query = """
        WITH latest_f33 AS (
            SELECT f.Id       AS f33_id,
                   f.Name     AS f33_name,
                   t.Val * ISNULL(m.MultiplierFactor, 1) AS energy_wh,
                   t.Ts
            FROM   Feeders33 f
            JOIN   Meters m       ON m.Id  = f.MeterId
            JOIN   (
                SELECT Mid, Val, Ts,
                       ROW_NUMBER() OVER (PARTITION BY Mid ORDER BY Ts DESC) AS rn
                FROM   MeterReadTfes
            ) t ON t.Mid = f.MeterId AND t.rn = 1
            WHERE  f.MeterId IS NOT NULL
              AND  f.IsDeleted = 0
        ),
        latest_f11 AS (
            SELECT f.Id    AS f11_id,
                   f.SsId,
                   t.Val * ISNULL(m.MultiplierFactor, 1) AS energy_wh
            FROM   Feeders11 f
            JOIN   Meters m       ON m.Id  = f.MeterId
            JOIN   (
                SELECT Mid, Val, Ts,
                       ROW_NUMBER() OVER (PARTITION BY Mid ORDER BY Ts DESC) AS rn
                FROM   MeterReadTfes
            ) t ON t.Mid = f.MeterId AND t.rn = 1
            WHERE  f.MeterId IS NOT NULL
        ),
        ss_f11 AS (
            SELECT SsId,
                   SUM(energy_wh) AS f11_total_wh,
                   COUNT(*)       AS f11_meter_count
            FROM   latest_f11
            GROUP BY SsId
        ),
        f33_ss_f11 AS (
            SELECT f33.f33_id,
                   f33.f33_name,
                   f33.energy_wh           AS f33_energy_wh,
                   s.Name                  AS ss_name,
                   sf.f11_total_wh,
                   sf.f11_meter_count
            FROM   latest_f33 f33
            JOIN   Feeder33Substation fs  ON fs.Feeders33Id    = f33.f33_id
            JOIN   Substations s          ON s.Id              = fs.SubstationsId
            JOIN   ss_f11 sf              ON sf.SsId           = s.Id
            WHERE  f33.energy_wh > 0
        ),
        aggregated AS (
            SELECT f33_id,
                   f33_name,
                   MAX(f33_energy_wh)         AS f33_energy_wh,
                   STRING_AGG(ss_name, ', ')  AS substations,
                   SUM(f11_total_wh)          AS f11_total_wh,
                   SUM(f11_meter_count)       AS f11_meter_count
            FROM   f33_ss_f11
            GROUP BY f33_id, f33_name
        )
        SELECT f33_name                                              AS [Feeder33],
               substations                                          AS [Podstanice (SS)],
               ROUND(f33_energy_wh   / 1000000.0, 2)               AS [F33 Energija (MWh)],
               ROUND(f11_total_wh    / 1000000.0, 2)               AS [F11 Suma (MWh)],
               ROUND((f33_energy_wh - f11_total_wh) / 1000000.0, 2) AS [Gubici (MWh)],
               ROUND((f33_energy_wh - f11_total_wh) / f33_energy_wh * 100, 2) AS [Gubici (%)],
               f11_meter_count                                      AS [Br. F11 merila]
        FROM   aggregated
        ORDER BY [Gubici (%)] DESC
        """
        df = pd.read_sql(query, conn)
        return df
    finally:
        conn.close()


def show_losses() -> None:
    st.subheader("Analiza gubitaka po Feeder33")
    st.caption(
        "Gubici = Energija na Feeder33 − Suma energija na svim Feeder11 fiderima "
        "koji izlaze iz SS u koji taj Feeder33 ulazi. "
        "Prikazani su samo F33 fideri gde povezane SS imaju aktivna F11 merila."
    )

    df = load_losses()

    if df.empty:
        st.warning("Nema podataka za analizu gubitaka.")
        return

    col1, col2, col3 = st.columns(3)
    col1.metric("Fideri u analizi", len(df))
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
