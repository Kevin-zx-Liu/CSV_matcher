import pandas as pd

def robust_scan(file, file_label, target_cols):
    """
    Scans a file line-by-line looking for specific column headers.
    Auto-detects whether the separator is a comma (,) or semicolon (;).
    """
    file.seek(0)
    lines = []
    for line in file.readlines():
        if isinstance(line, bytes):
            lines.append(line.decode('latin1', errors='ignore'))
        else:
            lines.append(line)
            
    # A. Detect Header Row & Column Indices
    header_index = -1
    col_indices = {key: -1 for key in target_cols} 
    found_header = False
    delimiter = ',' # Default fallback
    
    # Scan first 50 lines to find a header row that contains our main ID
    for i, line in enumerate(lines[:50]):
        clean_line = line.strip()
        if not clean_line: continue
        
        # --- Improved Delimiter Detection ---
        parts_comma = [p.strip().upper() for p in clean_line.split(',')]
        valid_comma = len(parts_comma) > 1 and any(term in part for part in parts_comma for term in target_cols['ID'])
        
        parts_semi = [p.strip().upper() for p in clean_line.split(';')]
        valid_semi = len(parts_semi) > 1 and any(term in part for part in parts_semi for term in target_cols['ID'])
        
        parts = []
        if valid_semi:
            delimiter = ';'
            parts = parts_semi
            found_header = True
        elif valid_comma:
            delimiter = ','
            parts = parts_comma
            found_header = True
            
        if found_header:
            header_index = i
            for idx, part in enumerate(parts):
                for key, search_terms in target_cols.items():
                    if col_indices[key] == -1:
                        if any(term in part for term in search_terms):
                            col_indices[key] = idx
            break
            
    if not found_header:
        return None, f"Could not find a Header row containing 'LOT' (or delimiters were not detected) in {file_label} file."

    # B. Extract Data
    data = []
    for line in lines[header_index+1:]:
        parts = line.split(delimiter)
        if len(parts) < 2: continue

        row_data = {}
        max_needed = max(col_indices.values())
        
        if len(parts) > max_needed:
            for key, idx in col_indices.items():
                if idx != -1:
                    val = parts[idx].strip().replace('"', '').replace("'", "")
                    row_data[key] = val
                else:
                    row_data[key] = "N/A"
            data.append(row_data)

    return pd.DataFrame(data), None