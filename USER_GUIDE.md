# APC Validation User Guide

This guide walks you through installing, running, and using the **APC Validation** tool from scratch. No prior experience with the app is assumed. Basic familiarity with running a command in a terminal is helpful but optional (see the install section).

---

## 1. What the tool does

APC Validation is a browser-based app that compares two sets of CSV exports to verify whether records from one system (**Temptation / hold data**, called *Left*) also exist in another system (**APC / process data**, called *Right*). It then lets you consolidate daily reports into trend charts and produce weekly summaries.

You use it for three things, in order:

1. **Matching** a fresh pair of CSVs and exporting a daily report (Matching / Missing).
2. **Trending** a stack of daily reports to see Matching vs Missing percentages over time and analyse why records are Missing.
3. **Weekly summary** for current and historical weeks.

You never have to write any code. Everything happens through file uploads and clicks in the browser.

---

## 2. Installation (one-time setup)

You need Python 3.10 or newer installed. If you do not have Python, install it from [python.org](https://www.python.org/downloads/) and tick "Add Python to PATH" during setup on Windows.

Open a terminal (PowerShell on Windows, Terminal on macOS / Linux) in the project folder and run:

```bash
pip install -r requirements.txt
```

That installs Streamlit, Pandas, and Altair. It only needs to be done once (and again whenever `requirements.txt` changes).

> **Tip:** if you share a machine with other Python projects, create a virtual environment first:
> ```bash
> python -m venv .venv
> # Windows
> .\.venv\Scripts\activate
> # macOS / Linux
> source .venv/bin/activate
> pip install -r requirements.txt
> ```

---

## 3. Running the app

From the project folder, run:

```bash
streamlit run app.py
```

Your default browser opens at `http://localhost:8501` showing the APC Validation page. Leave the terminal window open while you use the app. Press `Ctrl+C` in the terminal to stop it.

If the browser does not open automatically, copy the URL printed in the terminal and open it manually.

---

## 4. Preparing your CSV files

The app reads CSVs by scanning the first 50 lines for a header row, auto-detecting whether columns are separated by **commas** or **semicolons**. Preamble lines (timestamps, blank lines, banners) above the real header are ignored.

Column names are matched as **uppercase substrings**, so `LOT_ID`, `lot_id`, and `Lot_ID` are all accepted, but slight variations like `Lot ID` (with a space) are not. Use the column names below, in any order, as long as the header line contains them.

### 4.1 Left file (Target result)

One CSV. Required header columns:

| Internal name | Accepted header names                |
|---------------|--------------------------------------|
| `ID`          | `LOT_ID` or `LOTID`                  |
| `Time`        | `LOT_HOLD_TIME` or any header containing `TIME` |
| `Info`        | `LOT_HOLD_COMMENT`                   |

The `Info` column should contain text in the form:

```
... SMCchart <chart name> - Lot ... Equipment <EQP01#1> ...
```

The app uses regex to pull the chart name and equipment ID out of this string.

### 4.2 Right files (Current result)

One or more CSVs (you can upload several at once; they are concatenated and deduplicated). Required header columns:

| Internal name | Accepted header names                          |
|---------------|------------------------------------------------|
| `ID`          | `LOTID`, `LOT_ID`, or `BATCHID`                |
| `Chart`       | `CHARTNAME` or `CHART`                         |
| `Time`        | `DATETIME` or any header containing `TIME`     |
| `Equipment`   | `EQPNAME` or `EQUIPMENT`                       |
| `Eventlist`   | `EVENTLIST` or `EVENT_LIST`                    |

The `Eventlist` column is used to rescue **ChildLot IDs** (IDs containing a dot, e.g. `ABC123.4`) that don't match the Right `ID` column directly but appear inside an event-list text blob.

### 4.3 Time format

The app first tries `YYYYMMDD HHMMSS` (e.g. `20250413 142359`). If more than half the rows fail that parse, it falls back to pandas' general datetime parser. Business date is computed as **datetime minus 7 hours**, so a record stamped at 02:00 belongs to the previous business day.

---

## 5. Using the app

The page has three tabs across the top: **🛡️ Matching**, **📊 Trend Consolidation**, and **📋 Weekly Report**. Work through them left to right. Uploaded files persist while you switch tabs, so you don't lose anything by jumping around.

### Tab 1: Matching

![Matching layout](#)

1. **Upload Left CSV** (single file) on the left.
2. **Upload Right CSV(s)** (one or many) on the right.
3. After both uploads succeed, a green banner shows row counts: `Loaded: X rows (Left) vs Y unique rows (Right)`.
4. The **left panel** lists every Left record with a `MatchFound` checkbox showing whether it was found in any Right file.
   - Click any row to filter the right panel to that record's matches.
   - The **View Chart Name List** expander shows all chart names extracted from the Left file, formatted as a quoted, comma-separated list (useful for copy/paste into other systems).
5. The **right panel** shows the matching Right rows for the selected Left row. If the selected ID contains a dot, the search runs against the `Eventlist` column.
6. **Export Report** downloads a CSV with a `Match_Status` column (`Matching` or `Missing`) and a filename auto-suffixed with the most common business date in the file (e.g. `matching_report_0413.csv`).

This is the file you reuse in the **Trend Consolidation** tab to build trends. Add a `New_Comments` (or `Reason`) column in Excel before re-uploading if you want reason analysis (see below).

### Tab 2: Trend Consolidation

Upload one or more **previously exported** daily reports (the `matching_report_*.csv` files from the Matching tab, optionally edited to add a reason column).

The app expects each file to have at least:

| Column            | Notes                                                                 |
|-------------------|-----------------------------------------------------------------------|
| `Match_Status`    | Values: `Matching`, `Missing`, `Update needed`. Also accepts a column literally named `COMMENT`, which gets renamed to `Match_Status`. |
| `Time`            | Same format as the Left file.                                         |
| `Reason` *(opt.)* | Any of `NEW COMMENT`, `New_Comments`, `new comments`, `new comment`. Optional; needed for charts 2 and 3. |

Three charts are produced:

1. **Daily Matching vs Missing (%)** stacked bar per business date.
2. **Missing Reasons Analysis** stacked bar of why records were Missing or Update-needed, per day. Known reasons get fixed colors; new reasons cycle through a safe palette.
3. **APC Performance Analysis** percentage of Matching rows whose reason contains *"time is more accurate in APC"*, per day. Click **View Performance Details** to see the underlying counts.

Below the charts, a **Detailed Records Analysis** table lets you filter by status and chart name, then export the filtered view as a CSV named `Filtered_Report_<startDate>_to_<endDate>.csv`.

The **Clear All Uploaded Reports** button resets the trend uploader without reloading the page.

### Tab 3: Weekly Report & Trend Analysis

Empty until you've uploaded daily reports in the **Trend Consolidation** tab. Once trend data is available, this tab populates automatically.

**Left side (Current Week Summary):**
- Counts and percentages of `Matching` / `Update needed` / `Missing` across all daily reports currently loaded in the Trend Consolidation tab.
- A bar chart with the Matching percentage labelled on top.
- **Export Weekly Summary (CSV)** downloads a small 3-row file (`weekly_summary_<MMDD>-<MMDD>.csv`). Save these each week to build the historical view.

**Right side (Weekly Historical Trend):**
- Upload several of the weekly-summary CSVs you previously exported.
- The app combines them into a stacked bar chart showing Matching / Update needed / Missing across weeks.
- Each uploaded file must have `Time`, `Match_Status`, and `Percentage` columns. Files that don't match are skipped silently.

---

## 6. Typical end-to-end workflow

A daily / weekly rhythm someone new to the tool can follow:

**Daily:**
1. Pull the Temptation hold export and the APC process exports.
2. Open the app, upload them into Section 1.
3. Skim Missing rows, add a reason in Excel if desired.
4. Export the daily report. Save it in a known folder (e.g. `reports/2025-04/`).

**Weekly:**
1. Upload all 5 daily reports for the week into Section 2.
2. Review the three trend charts. Investigate any spike in Missing or any new reason category.
3. In Section 3, export the **Weekly Summary** CSV and save it alongside last week's.
4. Upload the running collection of weekly summaries into the right side of Section 3 to see the long-term trend.

---

## 7. Troubleshooting

| Symptom                                                              | Likely cause and fix                                                                           |
|----------------------------------------------------------------------|------------------------------------------------------------------------------------------------|
| "Could not find a Header row containing 'LOT'..."                    | The file uses a different column name. Open the CSV and rename the ID column to `LOT_ID` (Left) or `LOTID` (Right). |
| Many rows show as Missing when you know they should match            | Chart names differ between the two systems. Use the chart-list expander to compare names, or check that the Right `CHARTNAME` column actually contains data. |
| "No record found in any uploaded Right file" when clicking a row     | The Left `ID` is not present in any Right file, *and* (for dotted IDs) not in any Right `Eventlist`. |
| Reasons chart says "No 'Reason' column found"                        | Your daily reports don't have a reason column yet. Add `New_Comments` to each before uploading. |
| Section 3 historical trend ignores a file                            | The file is missing `Time`, `Match_Status`, or `Percentage`. Re-export from Section 3 to get the right schema. |
| Browser stuck on loading                                             | Look at the terminal. If you see a Python traceback, that's the real error.                    |

To restart cleanly: stop the terminal with `Ctrl+C` and run `streamlit run app.py` again. Uploaded files live only in memory, so a restart wipes the slate.

---

## 8. Where things live

If you want to dig deeper:

- `app.py` ties everything together.
- `scanning.py` is the CSV header / delimiter detector.
- `matching.py` does the Lot ID + chart name comparison.
- `trends.py` aggregates daily reports for the trend charts.
- `charts.py` is the Altair chart definitions and color palette.
- `views/` holds the Streamlit UI for each section.

For the developer-oriented overview (tests, CI, conventions), see [README.md](README.md).
