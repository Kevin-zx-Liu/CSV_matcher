import streamlit as st


EXPORT_COLUMNS = ['Match_Status', 'ID', 'Time', 'CHARTNAME', 'EQUIP', 'Info']


def build_export_report(df_left):
    """
    Builds the matching-report DataFrame for export: derives Match_Status from
    the Found_in_Right boolean and selects EXPORT_COLUMNS (those present, in order).
    """
    df_export = df_left.copy()
    df_export['Match_Status'] = df_export['Found_in_Right'].apply(
        lambda x: "Matching" if x else "Missing"
    )
    export_cols = [c for c in EXPORT_COLUMNS if c in df_export.columns]
    return df_export[export_cols]


def extract_metadata(df_left):
    """
    Extracts CHARTNAME and EQUIP from the 'Info' column.
    """
    df_left['CHARTNAME'] = (
        df_left['Info']
        .astype(str)
        .str.extract(r'SMCchart\s+(.+?)\s+-\s+Lot', expand=False)
        .str.lower()
    )
    df_left['EQUIP'] = (
        df_left['Info']
        .astype(str)
        .str.extract(r'Equipment\s+([A-Za-z0-9]+#\d+)', expand=False)
    )

    df_left['__key'] = df_left['ID'].astype(str).str.upper().str.strip()
    df_left['__chart_clean'] = df_left['CHARTNAME'].fillna('').str.strip().str.upper()

    return df_left


def apply_matching_logic(df_left, df_right):
    """
    Performs LotID and Chart Name matching once Right data is available.
    """
    df_right['__key'] = df_right['ID'].astype(str).str.upper().str.strip()

    if 'Chart' in df_right.columns:
        df_right['__chart_clean'] = (
            df_right['Chart'].astype(str).replace('nan', '').fillna('').str.strip().str.upper()
        )
    else:
        df_right['__chart_clean'] = ""

    df_left['__composite_key'] = df_left['__key'] + "|" + df_left['__chart_clean']
    df_right['__composite_key'] = df_right['__key'] + "|" + df_right['__chart_clean']

    df_left['Found_in_Right'] = df_left['__composite_key'].isin(df_right['__composite_key'])

    # ChildLot rule: dotted IDs that didn't match exactly may still appear inside an Eventlist string
    mask_special = (~df_left['Found_in_Right']) & (df_left['ID'].astype(str).str.contains('.', regex=False))

    if mask_special.any() and 'Eventlist' in df_right.columns:
        st.toast(f"ℹ️ detected {mask_special.sum()} complex IDs with dots. Scanning Eventlists...")
        right_eventlist_series = df_right['Eventlist'].astype(str)

        for idx in df_left[mask_special].index:
            search_val = df_left.at[idx, 'ID']
            is_found = right_eventlist_series.str.contains(search_val, case=False, regex=False).any()
            if is_found:
                df_left.at[idx, 'Found_in_Right'] = True

    return df_left, df_right
