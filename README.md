# Amazon Invoice Downloader

Automates downloading Amazon order invoices using Playwright. It can filter from an Order History report CSV or crawl your order history directly.

## Prerequisites
- Python 3.10 or newer
- Google Chrome or Microsoft Edge installed (Chromium-based browser used by Playwright)
- Amazon Order History Report CSV (optional but recommended)

## Installation
1. Create a virtual environment (optional but recommended):
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\activate
   ```
2. Install the package and its dependencies:
   ```powershell
   pip install --upgrade pip
   pip install -e .
   playwright install
   ```
   The `playwright install` command downloads the Chromium browser used by the script.

## Usage
You can run the tool either as a module or through the installed console script:
```powershell
python -m invoice_downloader --domain www.amazon.ca --start-date 2024-03-01 --end-date 2024-06-30
# or
invoice-downloader --domain www.amazon.ca --start-date 2024-03-01 --end-date 2024-06-30
```

### Helpful flags
- `--csv`: Path to the Amazon Order History CSV (defaults to `reports/orders.csv`).
- `--last4`: Filter orders by the last four digits of the payment method.
- `--start-date` / `--end-date`: Date range for filtering (YYYY-MM-DD).
- `--headless`: Run the browser in headless mode (omit for first-time login).
- `--force-crawl`: Skip CSV filtering and crawl order history pages directly.

Downloaded invoices are saved into `downloads/`. The script caches the filtered order IDs in `reports/order_ids.txt` to avoid repeat work between runs.

## Workflow Tips
1. Generate an Amazon Order History Report for the desired date range and save it to `reports/orders.csv` (or point `--csv` to its location).
2. Run the script and sign in when prompted. The browser profile is stored in `.pw-user-data` so future runs reuse the session.
3. Rerun with `--force-crawl` if the CSV does not contain all orders or if you want to rely solely on on-page data.

## Troubleshooting
- If the script closes immediately, rerun without `--headless` to watch the browser.
- Use `--force-crawl` when no CSV is available. Crawling can take longer but works without the report.
- If Playwright raises driver errors, rerun `playwright install` or `playwright install chromium`.
- Delete `.pw-user-data` to force a fresh login if the stored profile becomes invalid.

## Development
Run linting or type checks as preferred; no dedicated configuration is included yet. Contribution ideas include adding unit tests around CSV parsing, building a small CLI progress display, and expanding support for other marketplaces.

## Quickstart

### Prerequisites
- Python 3.10+
- Google Chrome (or Chromium)
- Playwright Python package and browsers
  - Install package deps in your venv:
    - pip install -e .
  - Install Playwright browsers (first time only):
    - python -m playwright install

### Install
- From GitHub (no clone):
  - pip install "git+https://github.com/YOUR_USER/amazon-invoice-downloader.git"
- Or from a local checkout:
  - pip install -e .

### Usage
Run from the project root with your virtualenv active:

`
python -m invoice_downloader \
  --domain www.amazon.ca \
  --force-crawl \
  --years 2024 2025 \
  --last4 0859
`

Notes
- Keep the browser window visible to sign in and complete MFA.
- The crawler paginates all history for the years you pass and filters invoices by the card last four.
- Multi-invoice orders are saved with numeric suffixes (e.g., _1, _1_2).
- Downloads are written to downloads/ (already .gitignored).
- If you need to target amazon.com, change --domain accordingly.

### CLI Options (excerpt)
- --domain (default www.amazon.ca): Amazon site.
- --last4 (optional): Filter by card last-four.
- --force-crawl: Ignore CSV seeding and crawl order history.
- --years (e.g., 2024 2025): One or more years to crawl. Omit to use default history.
- --headless: Run browser headless.

