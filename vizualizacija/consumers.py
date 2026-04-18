import pandas as pd
import streamlit as st
from db import get_connection


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
        LEFT JOIN Feeders11  f11 ON f11.Id  = d.Feeder11Id
        LEFT JOIN Substations sub ON sub.Id = f11.SsId
        WHERE d.MeterId IS NULL
           OR d.MeterId NOT IN (
               SELECT DISTINCT Mid FROM MeterReads
               WHERE Cid IN (6,7,8,9,10,11)
           )
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
