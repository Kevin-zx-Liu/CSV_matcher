import pandas as pd
import streamlit as st

from scanning import robust_scan
from matching import extract_metadata, apply_matching_logic
from trends import get_export_filename


LEFT_TARGETS = {
    'ID': ['LOT_ID', 'LOTID'],
    'Time': ['LOT_HOLD_TIME', 'TIME'],
    'Info': ['LOT_HOLD_COMMENT'],
}
RIGHT_TARGETS = {
    'ID': ['LOTID', 'LOT_ID', 'BATCHID'],
    'Chart': ['CHARTNAME', 'CHART'],
    'Time': ['DATETIME', 'TIME'],
    'Equipment': ['EQPNAME', 'EQUIPMENT'],
    'Eventlist': ['EVENTLIST', 'EVENT_LIST'],
}


def render_matching_section():
    st.markdown("Left File: **Temptation data** | Right Files: **APC data**")

    col1, col2 = st.columns(2)
    with col1:
        left_file = st.file_uploader("Upload Match Target (As is)", type="csv")
    with col2:
        right_files = st.file_uploader(
            "Upload New Result (To be)", type="csv", accept_multiple_files=True
        )

    if not left_file:
        return

    df_left, err_l = robust_scan(left_file, "Left", LEFT_TARGETS)
    if df_left is None:
        st.error(f"❌ Left File Error: {err_l}")
        return

    df_left = extract_metadata(df_left)
    if 'Found_in_Right' not in df_left.columns:
        df_left['Found_in_Right'] = False
    if 'CHARTNAME' not in df_left.columns:
        df_left['CHARTNAME'] = ""
    if 'EQUIP' not in df_left.columns:
        df_left['EQUIP'] = ""
    df_left['__key'] = df_left['ID'].astype(str).str.upper().str.strip()

    df_right = _load_right_files(right_files)
    if df_right is not None:
        df_left, df_right = apply_matching_logic(df_left, df_right)
        st.success(
            f"✅ Loaded: {len(df_left)} rows (Left) vs {len(df_right)} unique rows (Right)"
        )

    c1, c2 = st.columns([1, 1])
    with c1:
        _render_left_panel(df_left)
        selection = _render_left_dataframe(df_left)
    with c2:
        _render_right_panel(df_left, df_right, selection)


def _load_right_files(right_files):
    if not right_files:
        return None

    all_right_dfs = []
    right_errors = []
    for f in right_files:
        df_r, err_r = robust_scan(f, f.name, RIGHT_TARGETS)
        if df_r is not None:
            all_right_dfs.append(df_r)
        else:
            right_errors.append(err_r)

    if right_errors:
        for err in right_errors:
            st.error(f"❌ Right File Error: {err}")
        return None

    if not all_right_dfs:
        return None

    return pd.concat(all_right_dfs, ignore_index=True).drop_duplicates()


def _render_left_panel(df_left):
    st.subheader("1. Temptation Data")

    if 'CHARTNAME' in df_left.columns and not df_left['CHARTNAME'].replace('', pd.NA).dropna().empty:
        unique_charts = sorted(df_left['CHARTNAME'].dropna().unique())
        formatted_list = ", ".join([f'"{chart}"' for chart in unique_charts])
        with st.expander("📋 View Chart Name List (String Format)"):
            st.code(formatted_list, language="text")

    df_export = df_left.copy()
    df_export['Match_Status'] = df_export['Found_in_Right'].apply(lambda x: "Matching" if x else "Missing")
    export_filename = get_export_filename(df_export)
    export_cols = [c for c in ['Match_Status', 'ID', 'Time', 'CHARTNAME', 'EQUIP', 'Info']
                   if c in df_export.columns]

    st.download_button(
        label=f"📥 Export Report ({export_filename})",
        data=df_export[export_cols].to_csv(index=False).encode('utf-8'),
        file_name=export_filename,
        mime="text/csv",
    )


def _render_left_dataframe(df_left):
    display_cols = ['Found_in_Right', 'ID', 'Time', 'CHARTNAME', 'EQUIP']
    return st.dataframe(
        df_left[[c for c in display_cols if c in df_left.columns]],
        on_select="rerun",
        selection_mode="single-row",
        width=1000,
        hide_index=True,
        column_config={
            "Found_in_Right": st.column_config.CheckboxColumn("MatchFound", disabled=True),
            "Time": "Lothold Time",
        },
    )


def _render_right_panel(df_left, df_right, selection):
    st.subheader("2. APC Data (Combined)")
    if df_right is not None and selection.selection["rows"]:
        idx = selection.selection["rows"][0]
        sel_key, sel_display = df_left.iloc[idx]['__key'], df_left.iloc[idx]['ID']
        st.info(f"Searching Combined Process Data for: **{sel_display}**")

        if '.' in sel_display and 'Eventlist' in df_right.columns:
            match = df_right[df_right['Eventlist'].astype(str).str.contains(
                sel_display, case=False, regex=False
            )]
        else:
            match = df_right[df_right['__key'] == sel_key]

        if not match.empty:
            cols_to_show = ['ID', 'Chart', 'Time', 'Equipment']
            if 'Eventlist' in match.columns and '.' in sel_display:
                cols_to_show.append('Eventlist')
            st.dataframe(
                match[[c for c in cols_to_show if c in match.columns]],
                width='stretch',
                hide_index=True,
            )
        else:
            st.warning("❌ No record found in any uploaded Right file.")
    elif df_right is None:
        st.info("Upload Right CSV files to see matching records.")
