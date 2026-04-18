# vizualizacija/load.py
import pandas as pd
import streamlit as st
from db import get_connection

_ZONE_COLORS = {
    "Normalno":   "#2d6a2d",
    "Upozorenje": "#997700",
    "Kritično":   "#8b0000",
}


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
            WHERE (V_A IS NOT NULL AND I_A IS NOT NULL)
               OR (V_B IS NOT NULL AND I_B IS NOT NULL)
               OR (V_C IS NOT NULL AND I_C IS NOT NULL)
        ),
        f11_load AS (
            SELECT
                d.Feeder11Id,
                SUM(ISNULL(s.S_kVA, 0))          AS S_measured_kVA,
                SUM(d.NameplateRating) / 1000.0   AS S_nominal_kVA,
                COUNT(*)                           AS dt_total,
                SUM(CASE WHEN s.Mid IS NOT NULL THEN 1 ELSE 0 END) AS dt_with_reads
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
                SUM(d.NameplateRating) / 1000.0                             AS S_nominal_kVA,
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
            WHERE (V_A IS NOT NULL AND I_A IS NOT NULL)
               OR (V_B IS NOT NULL AND I_B IS NOT NULL)
               OR (V_C IS NOT NULL AND I_C IS NOT NULL)
        ),
        dt_load AS (
            SELECT
                d.Feeder11Id,
                SUM(ISNULL(s.S_kVA, 0))          AS S_measured_kVA,
                SUM(d.NameplateRating) / 1000.0   AS S_nominal_kVA,
                SUM(CASE WHEN s.Mid IS NOT NULL THEN 1 ELSE 0 END) AS dt_with_reads,
                COUNT(*)                           AS dt_total
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
                SUM(d.NameplateRating) / 1000.0                            AS S_nominal_kVA,
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
