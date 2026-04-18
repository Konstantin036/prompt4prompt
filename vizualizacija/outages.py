import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import streamlit as st
from db import get_connection
from theme import apply_dark_theme, ORANGE
from consumers import _SUNBURST_PALETTE

_GAP_MIN_H = 2
_GAP_MAX_H = 2000
_EVENT_MIN_METERS = 5


@st.cache_data
def load_outage_timeline() -> pd.DataFrame:
    conn = get_connection()
    try:
        return pd.read_sql(f"""
        WITH ordered AS (
            SELECT Mid, Ts, LAG(Ts) OVER (PARTITION BY Mid ORDER BY Ts) AS prev_ts
            FROM MeterReads WHERE Cid = 6
        ),
        gaps AS (
            SELECT Mid, CAST(prev_ts AS DATE) AS gap_date,
                   DATEDIFF(HOUR, prev_ts, Ts) AS gap_h
            FROM ordered
            WHERE prev_ts IS NOT NULL
              AND DATEDIFF(HOUR, prev_ts, Ts) BETWEEN {_GAP_MIN_H} AND {_GAP_MAX_H}
        )
        SELECT gap_date AS [Datum], COUNT(DISTINCT Mid) AS [Meraci pogodeni],
               AVG(gap_h) AS [Prosek sati], SUM(gap_h) AS [Ukupno sati]
        FROM gaps
        GROUP BY gap_date
        ORDER BY gap_date
        """, conn)
    finally:
        conn.close()


@st.cache_data
def load_major_events() -> pd.DataFrame:
    conn = get_connection()
    try:
        return pd.read_sql(f"""
        WITH ordered AS (
            SELECT Mid, Ts, LAG(Ts) OVER (PARTITION BY Mid ORDER BY Ts) AS prev_ts
            FROM MeterReads WHERE Cid = 6
        ),
        gaps AS (
            SELECT Mid,
                   DATEADD(HOUR, DATEDIFF(HOUR, 0, prev_ts), 0) AS event_hour,
                   DATEDIFF(HOUR, prev_ts, Ts) AS gap_h
            FROM ordered
            WHERE prev_ts IS NOT NULL
              AND DATEDIFF(HOUR, prev_ts, Ts) BETWEEN {_GAP_MIN_H} AND {_GAP_MAX_H}
        )
        SELECT event_hour AS [Vreme],
               COUNT(DISTINCT Mid) AS [Meraci pogodeni],
               AVG(gap_h)          AS [Prosek trajanja (h)],
               MAX(gap_h)          AS [Max trajanja (h)]
        FROM gaps
        GROUP BY event_hour
        HAVING COUNT(DISTINCT Mid) >= {_EVENT_MIN_METERS}
        ORDER BY [Meraci pogodeni] DESC
        """, conn)
    finally:
        conn.close()


@st.cache_data
def load_feeder_downtime() -> pd.DataFrame:
    conn = get_connection()
    try:
        return pd.read_sql(f"""
        WITH ordered AS (
            SELECT Mid, Ts, LAG(Ts) OVER (PARTITION BY Mid ORDER BY Ts) AS prev_ts
            FROM MeterReads WHERE Cid = 6
        ),
        gaps AS (
            SELECT Mid, DATEDIFF(HOUR, prev_ts, Ts) AS gap_h
            FROM ordered
            WHERE prev_ts IS NOT NULL
              AND DATEDIFF(HOUR, prev_ts, Ts) BETWEEN {_GAP_MIN_H} AND {_GAP_MAX_H}
        ),
        meter_totals AS (
            SELECT Mid, SUM(gap_h) AS total_gap_h, COUNT(*) AS gap_count
            FROM gaps GROUP BY Mid
        )
        SELECT
            ISNULL(ts2.Name, 'N/A')  AS [TS],
            sub.Name                  AS [Podstanica (SS)],
            f11.Name                  AS [Feeder11],
            COUNT(DISTINCT d.Id)      AS [DT ukupno],
            COUNT(DISTINCT mt.Mid)    AS [DT sa prekidima],
            SUM(mt.total_gap_h)       AS [Ukupno sati prekida],
            AVG(mt.total_gap_h)       AS [Prosek sati/DT],
            SUM(mt.gap_count)         AS [Broj prekida]
        FROM meter_totals mt
        JOIN DistributionSubstation d ON d.MeterId = mt.Mid
        JOIN Feeders11 f11            ON f11.Id = d.Feeder11Id
        JOIN Substations sub          ON sub.Id = f11.SsId
        LEFT JOIN Feeder33Substation fs ON fs.SubstationsId = sub.Id
        LEFT JOIN Feeders33 f33       ON f33.Id = fs.Feeders33Id
        LEFT JOIN TransmissionStations ts2 ON ts2.Id = f33.TsId
        GROUP BY ts2.Name, sub.Name, f11.Name
        HAVING SUM(mt.total_gap_h) > 0
        ORDER BY SUM(mt.total_gap_h) DESC
        """, conn)
    finally:
        conn.close()


@st.cache_data
def load_event_topology(event_dt: str) -> pd.DataFrame:
    """Topology drill-down for a specific event hour (ISO string)."""
    conn = get_connection()
    try:
        return pd.read_sql(f"""
        WITH ordered AS (
            SELECT Mid, Ts, LAG(Ts) OVER (PARTITION BY Mid ORDER BY Ts) AS prev_ts
            FROM MeterReads WHERE Cid = 6
        ),
        gaps AS (
            SELECT Mid, DATEDIFF(HOUR, prev_ts, Ts) AS gap_h
            FROM ordered
            WHERE prev_ts IS NOT NULL
              AND prev_ts >= DATEADD(HOUR, -6, '{event_dt}')
              AND prev_ts <  DATEADD(HOUR,  6, '{event_dt}')
              AND DATEDIFF(HOUR, prev_ts, Ts) BETWEEN {_GAP_MIN_H} AND {_GAP_MAX_H}
        )
        SELECT
            ISNULL(ts2.Name, 'N/A') AS TS,
            sub.Name                 AS [Podstanica (SS)],
            f11.Name                 AS [Feeder11],
            COUNT(DISTINCT g.Mid)    AS [DT pogodeno],
            AVG(g.gap_h)             AS [Prosek trajanja (h)]
        FROM gaps g
        JOIN DistributionSubstation d ON d.MeterId = g.Mid
        JOIN Feeders11 f11            ON f11.Id = d.Feeder11Id
        JOIN Substations sub          ON sub.Id = f11.SsId
        LEFT JOIN Feeder33Substation fs ON fs.SubstationsId = sub.Id
        LEFT JOIN Feeders33 f33       ON f33.Id = fs.Feeders33Id
        LEFT JOIN TransmissionStations ts2 ON ts2.Id = f33.TsId
        GROUP BY ts2.Name, sub.Name, f11.Name
        ORDER BY COUNT(DISTINCT g.Mid) DESC
        """, conn)
    finally:
        conn.close()


@st.cache_data
def load_flat_energy() -> pd.DataFrame:
    conn = get_connection()
    try:
        return pd.read_sql("""
        WITH ordered AS (
            SELECT Mid, Ts, Val,
                   LAG(Val) OVER (PARTITION BY Mid ORDER BY Ts) AS prev_val,
                   LAG(Ts)  OVER (PARTITION BY Mid ORDER BY Ts) AS prev_ts
            FROM MeterReadTfes
        ),
        flat AS (
            SELECT Mid, SUM(DATEDIFF(HOUR, prev_ts, Ts)) AS flat_h,
                   COUNT(*) AS flat_periods
            FROM ordered
            WHERE prev_val IS NOT NULL AND Val = prev_val
              AND DATEDIFF(HOUR, prev_ts, Ts) > 6
            GROUP BY Mid
        )
        SELECT
            ISNULL(ts2.Name, 'N/A') AS [TS],
            sub.Name                 AS [Podstanica (SS)],
            f11.Name                 AS [Feeder11],
            d.Name                   AS [DT Stanica],
            flat.flat_h              AS [Flat sati],
            flat.flat_periods        AS [Perioda stagnacije]
        FROM flat
        JOIN DistributionSubstation d ON d.MeterId = flat.Mid
        JOIN Feeders11 f11            ON f11.Id = d.Feeder11Id
        JOIN Substations sub          ON sub.Id = f11.SsId
        LEFT JOIN Feeder33Substation fs ON fs.SubstationsId = sub.Id
        LEFT JOIN Feeders33 f33       ON f33.Id = fs.Feeders33Id
        LEFT JOIN TransmissionStations ts2 ON ts2.Id = f33.TsId
        ORDER BY flat.flat_h DESC
        """, conn)
    finally:
        conn.close()


# ── Charts ────────────────────────────────────────────────────────────────────

def _timeline_chart(df: pd.DataFrame) -> None:
    df = df.copy()
    df["Datum"] = pd.to_datetime(df["Datum"])
    max_val = df["Meraci pogodeni"].max()

    fig = go.Figure()

    # Filled area
    fig.add_trace(go.Scatter(
        x=df["Datum"], y=df["Meraci pogodeni"],
        mode="lines",
        fill="tozeroy",
        fillcolor="rgba(255,107,53,0.12)",
        line=dict(color=ORANGE, width=2),
        name="Meraci pogodeni",
        hovertemplate="<b>%{x|%d. %b %Y}</b><br>Merači pogođeni: <b>%{y}</b><extra></extra>",
    ))

    # Highlight spikes > 50% of max
    thresh = max_val * 0.5
    spikes = df[df["Meraci pogodeni"] >= thresh]
    fig.add_trace(go.Scatter(
        x=spikes["Datum"], y=spikes["Meraci pogodeni"],
        mode="markers",
        marker=dict(color="#e53e3e", size=9, symbol="diamond",
                    line=dict(color="white", width=1.5)),
        name=f"Krupni događaj (≥{int(thresh)} merača)",
        hovertemplate="<b>%{x|%d. %b %Y}</b><br><b>%{y} merača</b><extra></extra>",
    ))

    apply_dark_theme(fig)
    fig.update_layout(
        title="Dnevni broj merača s novim prekidom napajanja",
        xaxis_title="Datum",
        yaxis_title="Merači pogođeni",
        height=340,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    st.plotly_chart(fig, use_container_width=True)


def _events_bubble(df: pd.DataFrame) -> None:
    df = df.copy()
    df["Vreme"] = pd.to_datetime(df["Vreme"])
    df["Datum"] = df["Vreme"].dt.date
    df["Sat"] = df["Vreme"].dt.hour
    df["Ozbiljnost"] = df["Meraci pogodeni"].apply(
        lambda v: "Kritičan" if v >= 500 else ("Velik" if v >= 100 else "Srednji")
    )
    color_map = {"Kritičan": "#e53e3e", "Velik": "#FF8C00", "Srednji": "#ECC94B"}

    fig = go.Figure()
    for sev, color in color_map.items():
        sub = df[df["Ozbiljnost"] == sev]
        if sub.empty:
            continue
        sizes = (sub["Meraci pogodeni"] / df["Meraci pogodeni"].max() * 38 + 7).clip(7, 45)
        fig.add_trace(go.Scatter(
            x=sub["Datum"], y=sub["Sat"],
            mode="markers",
            name=sev,
            marker=dict(size=sizes, color=color, opacity=0.82,
                        line=dict(color="rgba(255,255,255,0.2)", width=1)),
            text=sub["Vreme"].dt.strftime("%d.%m. %H:00"),
            customdata=sub[["Meraci pogodeni", "Prosek trajanja (h)", "Max trajanja (h)"]].values,
            hovertemplate=(
                "<b>%{text}</b><br>"
                "Merači: <b>%{customdata[0]}</b><br>"
                "Prosek trajanja: %{customdata[1]}h<br>"
                "Maks trajanja: %{customdata[2]}h<br>"
                "<extra></extra>"
            ),
        ))

    apply_dark_theme(fig)
    fig.update_layout(
        title="Raspored wydarzaja po datumu i satu dana",
        xaxis_title="Datum",
        yaxis_title="Sat dana",
        yaxis=dict(range=[-1, 24], tickvals=list(range(0, 24, 3)),
                   ticktext=[f"{h:02d}:00" for h in range(0, 24, 3)]),
        height=420,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    st.plotly_chart(fig, use_container_width=True)


def _feeder_downtime_chart(df: pd.DataFrame) -> None:
    top = df.head(20).copy()
    ts_list = df["TS"].unique().tolist()
    ts_color = {ts: _SUNBURST_PALETTE[i % len(_SUNBURST_PALETTE)] for i, ts in enumerate(ts_list)}
    colors = [ts_color.get(ts, ORANGE) for ts in top["TS"]]

    top["label"] = top["Feeder11"].str.split("_").str[-1] + "  ·  " + top["Podstanica (SS)"]

    fig = go.Figure(go.Bar(
        x=top["Ukupno sati prekida"],
        y=top["label"],
        orientation="h",
        marker=dict(color=colors, opacity=0.88, line=dict(width=0)),
        text=top["Ukupno sati prekida"].apply(lambda v: f"{v:,}h"),
        textposition="outside",
        textfont=dict(color="#a0aec0", size=10),
        customdata=top[["TS", "DT ukupno", "DT sa prekidima", "Broj prekida", "Prosek sati/DT"]].values,
        hovertemplate=(
            "<b>%{y}</b><br>"
            "TS: %{customdata[0]}<br>"
            "Ukupno sati prekida: <b>%{x:,}h</b><br>"
            "DT pogođeno / ukupno: %{customdata[2]} / %{customdata[1]}<br>"
            "Broj prekida: %{customdata[3]}<br>"
            "Prosek po DT: %{customdata[4]}h<br>"
            "<extra></extra>"
        ),
    ))
    apply_dark_theme(fig)
    fig.update_layout(
        title="Top 20 F11 fidera — ukupni sati prekida napajanja",
        xaxis_title="Ukupno sati prekida",
        yaxis=dict(autorange="reversed", tickfont=dict(size=10)),
        height=560,
        margin=dict(l=10, r=90, t=50, b=10),
    )
    st.plotly_chart(fig, use_container_width=True)


def _event_topology_chart(df: pd.DataFrame, event_label: str) -> None:
    if df.empty:
        st.info("Nema topoloških podataka za ovaj događaj.")
        return

    ts_list = df["TS"].unique().tolist()
    ts_color = {ts: _SUNBURST_PALETTE[i % len(_SUNBURST_PALETTE)] for i, ts in enumerate(ts_list)}

    fig = px.sunburst(
        df,
        path=["TS", "Podstanica (SS)", "Feeder11"],
        values="DT pogodeno",
        color="TS",
        color_discrete_map=ts_color,
        custom_data=["DT pogodeno", "Prosek trajanja (h)"],
        height=500,
        branchvalues="total",
    )
    fig.update_traces(
        texttemplate="<b>%{label}</b><br>%{value} DT",
        textfont=dict(size=10, family="monospace"),
        insidetextorientation="radial",
        marker=dict(line=dict(width=1.5, color="rgba(15,15,26,0.85)")),
        hovertemplate=(
            "<b>%{label}</b><br>"
            "DT pogođeno: <b>%{value}</b><br>"
            "Prosek trajanja: %{customdata[1]}h<br>"
            "<extra></extra>"
        ),
    )
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#a0aec0"),
        title=dict(
            text=f"Topologija pogođenih čvorova — {event_label}",
            font=dict(color=ORANGE, size=13), x=0.5, xanchor="center",
        ),
        margin=dict(l=10, r=10, t=50, b=10),
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)


# ── Main entry point ──────────────────────────────────────────────────────────

def show_outages() -> None:
    st.markdown(
        '<h3 style="color:#FF6B35;font-size:1.15rem;font-weight:700;'
        'text-transform:uppercase;letter-spacing:0.06em;margin-bottom:1rem;">'
        '⚡ Analiza nestanka struje</h3>',
        unsafe_allow_html=True,
    )

    df_tl = load_outage_timeline()
    df_ev = load_major_events()
    df_fd = load_feeder_downtime()

    # ── KPI ──────────────────────────────────────────────────────────────────
    worst_day = df_tl.loc[df_tl["Meraci pogodeni"].idxmax(), "Datum"]
    worst_cnt = df_tl["Meraci pogodeni"].max()
    worst_event = df_ev.iloc[0]

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Merači u analizi", f"{df_tl['Meraci pogodeni'].sum():,}",
                help="Ukupno započetih prekida u periodu jan–apr 2026")
    col2.metric("Najteži dan",
                pd.to_datetime(worst_day).strftime("%d. %b"),
                f"{worst_cnt} merača")
    col3.metric("Najveći jednotni događaj",
                f"{int(worst_event['Meraci pogodeni'])} merača",
                pd.to_datetime(worst_event["Vreme"]).strftime("%d.%m. %H:00h"))
    col4.metric("F11 fidera sa prekidima", len(df_fd))

    st.divider()

    # ── Timeline ─────────────────────────────────────────────────────────────
    st.markdown(
        '<p style="color:#8892b0;font-size:0.85rem;margin-bottom:0.25rem;">'
        'VREMENSKI TOK PREKIDA</p>',
        unsafe_allow_html=True,
    )
    _timeline_chart(df_tl)

    st.divider()

    # ── Bubble chart događaji ─────────────────────────────────────────────────
    st.markdown(
        '<p style="color:#8892b0;font-size:0.85rem;margin-bottom:0.25rem;">'
        'RASPORED DOGAĐAJA PO DATUMU I SATU</p>',
        unsafe_allow_html=True,
    )
    st.caption(
        "Svaka tačka = sat kada je >=5 merača istovremeno izgubilo napajanje. "
        "Veličina = broj pogođenih merača."
    )
    _events_bubble(df_ev)

    st.divider()

    # ── Feeder ranking ────────────────────────────────────────────────────────
    st.markdown(
        '<p style="color:#8892b0;font-size:0.85rem;margin-bottom:0.25rem;">'
        'FIDERI SA NAJVEĆIM UKUPNIM ISPADOM</p>',
        unsafe_allow_html=True,
    )
    _feeder_downtime_chart(df_fd)

    with st.expander(f"Tabela — svi fideri ({len(df_fd)} F11)", expanded=False):
        st.dataframe(df_fd, use_container_width=True, height=400)

    st.divider()

    # ── Event drill-down ──────────────────────────────────────────────────────
    st.markdown(
        '<p style="color:#8892b0;font-size:0.85rem;margin-bottom:0.25rem;">'
        'TOPOLOŠKI UVID U DOGAĐAJ</p>',
        unsafe_allow_html=True,
    )

    top20 = df_ev.head(20).copy()
    top20["Vreme"] = pd.to_datetime(top20["Vreme"])
    top20["label"] = (
        top20["Vreme"].dt.strftime("%d.%m. %H:00h")
        + " — "
        + top20["Meraci pogodeni"].astype(str)
        + " merača"
    )
    event_labels = top20["label"].tolist()
    sel = st.selectbox("Izaberi događaj za analizu:", event_labels)
    if sel:
        row = top20[top20["label"] == sel].iloc[0]
        event_iso = row["Vreme"].strftime("%Y-%m-%d %H:%M:%S")
        topo = load_event_topology(event_iso)
        _event_topology_chart(topo, sel)

    st.divider()

    # ── Flat energija ─────────────────────────────────────────────────────────
    st.markdown(
        '<p style="color:#8892b0;font-size:0.85rem;margin-bottom:0.25rem;">'
        'STAGNACIJA ENERGETSKOG BROJILA (FLAT-LINE)</p>',
        unsafe_allow_html=True,
    )
    st.caption(
        "DT stanice čiji MeterReadTfes brojač nije rastao duže od 6h — "
        "signal stvarnog ili mernog nestanka energije."
    )
    df_flat = load_flat_energy()
    col1, col2 = st.columns(2)
    col1.metric("DT sa flat energijom", len(df_flat))
    col2.metric("Najduža stagnacija", f"{df_flat['Flat sati'].max():,}h")
    st.dataframe(df_flat, use_container_width=True, height=360)
