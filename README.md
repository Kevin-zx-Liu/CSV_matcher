# Project Overview

This is a Python-based Streamlit application designed to validate the performance of a new database. Its primary purpose is to compare two CSV files, identify matching and missing records based on various criteria (like Lot ID and Chart Name), and provide an interactive web interface for analysis and reporting.

**Key Features:**
*   **Robust CSV Scanning:** Automatically detects delimiters (comma or semicolon) and intelligently identifies relevant columns even with variations in headers.
*   **Data Matching:** Compares records between two uploaded CSV files based on Lot ID and extracted Chart Names. Includes special handling for complex "ChildLot" IDs.
*   **Interactive UI:** Provides a user-friendly interface powered by Streamlit to upload files, view matching results, and interact with data.
*   **Report Generation:** Allows users to export a detailed matching report with "Matching" or "Missing" statuses.
*   **Trend Analysis:** Consolidates multiple exported reports to visualize daily trends of matching/missing percentages and analyze reasons for missing data using Altair charts.

**Technologies Used:**
*   **Python:** The core programming language.
*   **Streamlit:** For building the interactive web application UI.
*   **Pandas:** For efficient data manipulation and analysis of CSV data.
*   **Altair:** For creating interactive and visually appealing data visualizations (charts).

## Building and Running

To set up and run this project, follow these steps:

1.  **Install Dependencies:**
    It is recommended to use a virtual environment.
    ```bash
    pip install streamlit pandas altair
    ```

2.  **Run the Application:**
    Navigate to the directory containing `app.py` and run the Streamlit application:
    ```bash
    streamlit run app.py
    ```
    This command will open the application in your default web browser.

## Development Conventions

*   **Code Structure:** The main application logic resides in `app.py`. Functions are organized for robust CSV scanning (`robust_scan`), main application flow, and trend consolidation.
*   **Error Handling:** Basic error handling is present for file uploads and data processing.
*   **UI/UX:** The application prioritizes a wide layout and clear labeling for user interaction, making heavy use of Streamlit's widgets for file uploading, data display, and charting.
*   **Data Normalization:** Lot IDs and Chart Names are normalized (uppercase, stripped whitespace) for consistent matching.
*   **Comments:** Code includes comments to explain complex logic, especially within the scanning and matching sections.

## TODO:
*   Re-structre the program into several modules: `app.py` only as entry point, `utils.py` for general-purpose helper functions like data cleaning, `logic.py` for data manipulation functions
*   Consider adding a `requirements.txt` file to explicitly manage Python dependencies.
*   Add unit tests for core functionalities like `robust_scan` and matching logic.
