# Project Overview

This is a Python-based Streamlit application designed to validate the performance of a new database. Its primary purpose is to compare two CSV files, identify matching and missing records based on various criteria (like Lot ID and Chart Name), and provide an interactive web interface for analysis and reporting.

> **New here?** See [USER_GUIDE.md](USER_GUIDE.md) for an end-user walkthrough (install, run, upload, export). To deploy the app to the cloud (T-Cloud Public via SWR + CCE), see [DEPLOYMENT.md](DEPLOYMENT.md). The rest of this README is for developers working on the codebase.

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

## Project Structure

```
ComparisonApp/
├── app.py                       # Streamlit entry point; calls render_*() per section
├── scanning.py                  # robust_scan: header discovery + delimiter detection
├── matching.py                  # extract_metadata, apply_matching_logic
├── trends.py                    # report aggregation, business-date helpers, APC perf
├── charts.py                    # Altair chart builders + reason color palette
├── views/                       # Streamlit per-section UI
│   ├── matching_view.py         #   file upload + side-by-side match panel
│   ├── trend_view.py            #   Daily / Reasons / APC charts + detail table
│   └── weekly_view.py           #   Weekly summary + historical trend
├── tests/                       # unittest suites, one per module
├── requirements.txt
├── Dockerfile                   # builds the container image (Streamlit on :8501)
├── .dockerignore                # excludes git/tests/caches from the image
├── docker-compose.yml           # local container run
├── .streamlit/config.toml       # headless mode, telemetry off, upload limit
├── k8s/deployment.yaml          # portable Kubernetes manifest (CCE/CCI/any cluster)
├── DEPLOYMENT.md                # step-by-step cloud deployment manual
└── .github/workflows/
    ├── tests.yml                # CI: runs the unittest suite on push and PR
    └── build-push-swr.yml       # CD: builds image and pushes to T-Cloud SWR
```

## Building and Running

1.  **Install dependencies** (virtual environment recommended):
    ```bash
    pip install -r requirements.txt
    ```

2.  **Run the application:**
    ```bash
    streamlit run app.py
    ```
    This opens the application in your default web browser.

3.  **Run the tests** (no Streamlit server required):
    ```bash
    python -m unittest discover -s tests -v
    ```

4.  **Run in a container** (optional, requires a container tool):
    ```bash
    docker compose up --build      # serves on http://localhost:8501
    ```

## Deployment

The app is containerized and runs on T-Cloud Public using SWR (image registry) and
CCE (managed Kubernetes). The image is built and pushed automatically by
`.github/workflows/build-push-swr.yml`, then deployed to a cluster.

For the full, beginner-friendly walkthrough (registry setup, cluster creation, node
pool, workload, load balancer, domain, cost control, and troubleshooting), see
**[DEPLOYMENT.md](DEPLOYMENT.md)**. The portable Kubernetes manifest is in
`k8s/deployment.yaml`.

## Development Conventions

*   **Code Structure:** `app.py` is a thin orchestrator. Pure logic lives in `scanning.py`, `matching.py`, and `trends.py`; Altair chart specs live in `charts.py`; per-section UI lives under `views/`. Each view module exposes a single `render_*_section()` function that `app.py` calls in order.
*   **Testing:** Every pure function has unittest coverage under `tests/`. Streamlit-coupled paths (e.g. the `st.toast` call inside `apply_matching_logic`) are exercised with `unittest.mock.patch`. Chart builders have smoke tests that assert key spec fields without rendering.
*   **Error Handling:** Basic error handling is present for file uploads and data processing.
*   **UI/UX:** The application prioritizes a wide layout and clear labeling for user interaction, making heavy use of Streamlit's widgets for file uploading, data display, and charting.
*   **Data Normalization:** Lot IDs and Chart Names are normalized (uppercase, stripped whitespace) for consistent matching.
*   **Comments:** Code uses inline comments only where the *why* is non-obvious. Most identifiers are self-describing.

## Continuous Integration

Every push to `main` and every pull request targeting `main` triggers the workflow at `.github/workflows/tests.yml`. The job sets up Python 3.12, installs `requirements.txt`, and runs the full unittest suite on Ubuntu. The `main` branch is protected: PRs cannot be merged until the `test` check passes, and direct pushes to `main` are blocked.

To add a new test, drop a `test_*.py` file under `tests/` with a `unittest.TestCase` subclass; CI will pick it up automatically.

A second workflow, `.github/workflows/build-push-swr.yml`, handles delivery: on push to `main` (or manual trigger) it builds the container image and pushes it to T-Cloud SWR. It needs the repository secrets/variables documented in [DEPLOYMENT.md](DEPLOYMENT.md) (`SWR_USERNAME`, `SWR_PASSWORD`, `SWR_REGISTRY`, `SWR_ORGANIZATION`).
