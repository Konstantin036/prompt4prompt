import os

import pandas as pd
import pymssql
import streamlit as st

_DB_CONFIG = {
    "server": os.getenv("DB_SERVER", "localhost"),
    "port": int(os.getenv("DB_PORT", "1433")),
    "database": os.getenv("DB_NAME", "SotexHackathon"),
    "user": os.getenv("DB_USER", "sa"),
    "password": os.getenv("DB_PASSWORD", "SotexSolutions123!"),
    "login_timeout": 5,
}


def get_connection():
    return pymssql.connect(**_DB_CONFIG)


@st.cache_data
def load_data() -> dict[str, pd.DataFrame]:
    conn = get_connection()
    try:
        return {
            "transmission_stations": pd.read_sql("SELECT * FROM TransmissionStations", conn),
            "substations": pd.read_sql("SELECT * FROM Substations", conn),
            "distribution_substations": pd.read_sql("SELECT * FROM DistributionSubstation", conn),
            "feeders11": pd.read_sql("SELECT * FROM Feeders11", conn),
            "feeders33": pd.read_sql("SELECT * FROM Feeders33 WHERE IsDeleted = 0", conn),
            "feeder33_substation": pd.read_sql("SELECT * FROM Feeder33Substation", conn),
        }
    finally:
        conn.close()
