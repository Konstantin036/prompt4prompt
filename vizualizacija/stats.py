import streamlit as st


def compute_stats(data: dict, ts_ids=None, ss_ids=None, feeder11_filter=None) -> dict:
    f11_all = data["feeders11"]
    f11_idx = f11_all.set_index("Id")
    dt = data["distribution_substations"]
    f33 = data["feeders33"]
    f33_ss = data["feeder33_substation"]

    if ss_ids:
        visible_ss_ids = ss_ids
    elif ts_ids:
        linked_f33 = f33[f33["TsId"].isin(ts_ids)]["Id"].tolist()
        linked_ss = f33_ss[f33_ss["Feeders33Id"].isin(linked_f33)]["SubstationsId"].tolist()
        visible_ss_ids = [int(x) for x in linked_ss]
    else:
        visible_ss_ids = None

    if ss_ids:
        ss_count = len(ss_ids)
    elif ts_ids:
        ss_count = len(visible_ss_ids)
    else:
        ss_count = len(data["substations"])

    # F33 count
    if ts_ids:
        f33_count = len(f33[f33["TsId"].isin(ts_ids) & (f33["IsDeleted"] == False)])
    else:
        f33_count = len(f33[f33["IsDeleted"] == False])

    # F11 count
    if feeder11_filter is not None:
        visible_f11 = f11_all[f11_all["Id"] == feeder11_filter]
    elif visible_ss_ids:
        visible_f11 = f11_all[f11_all["SsId"].isin(visible_ss_ids)]
    else:
        visible_f11 = f11_all
    f11_count = len(visible_f11)
    f11_power = int(visible_f11["NameplateRating"].sum(skipna=True))

    # DT filter
    if feeder11_filter is not None:
        dt = dt[dt["Feeder11Id"] == feeder11_filter]
    elif visible_ss_ids:
        visible_f11_ids = f11_idx[f11_idx["SsId"].isin(visible_ss_ids)].index.tolist()
        dt = dt[dt["Feeder11Id"].isin(visible_f11_ids)]

    dt_power = int(dt["NameplateRating"].sum(skipna=True))
    dt_with_meter = int(dt["MeterId"].notna().sum())
    dt_avg_kva = round(dt["NameplateRating"].mean(skipna=True)) if len(dt) > 0 else 0

    return {
        "ts_count":      len(ts_ids) if ts_ids else len(data["transmission_stations"]),
        "ss_count":      ss_count,
        "f33_count":     f33_count,
        "f11_count":     f11_count,
        "f11_power_kva": f11_power,
        "dt_count":      len(dt),
        "dt_with_meter": dt_with_meter,
        "dt_avg_kva":    dt_avg_kva,
        "dt_power_kva":  dt_power,
    }


def show_stats(data: dict, ts_ids=None, ss_ids=None, feeder11_filter=None) -> None:
    s = compute_stats(data, ts_ids=ts_ids, ss_ids=ss_ids, feeder11_filter=feeder11_filter)

    st.sidebar.markdown(
        '<p style="color:#FF6B35;font-size:0.75rem;font-weight:700;'
        'text-transform:uppercase;letter-spacing:0.12em;'
        'text-align:center;margin:0.5rem 0 0.75rem 0;">'
        '📊 Statistike mreže</p>',
        unsafe_allow_html=True,
    )

    col1, col2 = st.sidebar.columns(2)
    col1.metric("Prenos. stanice", s["ts_count"])
    col2.metric("Podstanice", s["ss_count"])
    col1.metric("Vodovi 33kV", s["f33_count"])
    col2.metric("Vodovi 11kV", s["f11_count"])
    col1.metric("DT stanice", s["dt_count"])
    col2.metric("DT sa mjeračem", s["dt_with_meter"])

    st.sidebar.markdown(
        '<p style="color:#8892b0;font-size:0.7rem;text-transform:uppercase;'
        'letter-spacing:0.1em;text-align:center;margin:0.6rem 0 0.3rem 0;">'
        'Kapaciteti</p>',
        unsafe_allow_html=True,
    )
    col1, col2 = st.sidebar.columns(2)
    col1.metric("DT ukupno (kVA)", f"{s['dt_power_kva']:,}")
    col2.metric("Prosj. DT (kVA)", f"{s['dt_avg_kva']:,}")
    st.sidebar.metric("Vodovi 11kV ukupno (kVA)", f"{s['f11_power_kva']:,}")
