# CryptoTax

Web application for cryptocurrency tax reporting, compliant with Spanish tax law (IRPF). Import your Binance transaction history, track your portfolio, and generate detailed tax reports with FIFO cost basis calculation.

## Features

- **Portfolio Dashboard** — Real-time overview of holdings, market value, ROI, and historical performance chart
- **Transaction History** — Browse, search, and filter 20,000+ transactions with multi-select filters, date ranges, and bulk statistics
- **Tax Reports** — Year-by-year FIFO capital gains/losses breakdown with drill-down into individual disposals and income transactions
- **Holding Details** — Per-asset analysis with top purchases, activity breakdown, and full transaction history
- **CSV Import** — Upload Binance transaction history CSVs directly from the web interface
- **Multi-language** — Spanish, English, and German with automatic browser language detection
- **Privacy Mode** — Blur all monetary values with a single click
- **Layout Options** — Toggle between sidebar and top navigation layouts

## Tax Compliance

- **FIFO cost basis** (First In, First Out)
- **EUR conversion** using historical daily prices (Binance API → CoinGecko fallback → annual averages)
- **Spanish IRPF 2024** savings income tax brackets:

| Bracket | Rate |
|---------|------|
| Up to €6,000 | 19% |
| €6,000 – €50,000 | 21% |
| €50,000 – €200,000 | 23% |
| €200,000 – €2,000,000 | 27% |
| Over €2,000,000 | 28% |

> **Disclaimer:** This tool is for informational purposes only. Consult a tax advisor for official IRPF declarations.

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | Python 3, Flask |
| Database | SQLite |
| Frontend | TailwindCSS, HTMX, Chart.js |
| i18n | Custom translation engine (ES/EN/DE) |

## Quick Start

### 1. Install dependencies

```bash
cd web
pip install -r requirements.txt
```

### 2. Run the server

```bash
python -m web.app
```

Or specify a custom port:

```bash
python -c "from web.app import app; app.run(port=5002)"
```

### 3. Open in browser

```
http://127.0.0.1:5000
```

### 4. Import your data

Go to **Settings** → Upload your Binance Transaction History CSV file. The app will automatically parse, deduplicate, and store transactions in SQLite.

## Project Structure

```
tax-report/
├── web/                        # Web application
│   ├── app.py                  # Flask routes, API endpoints, i18n
│   ├── database.py             # SQLite schema, queries, settings
│   ├── engine.py               # FIFO engine, portfolio, price fetching
│   ├── i18n.py                 # Translation dictionaries (ES/EN/DE)
│   ├── requirements.txt        # Python dependencies
│   ├── templates/              # Jinja2 HTML templates
│   │   ├── base.html           # Base layout with sidebar/topnav
│   │   ├── _header.html        # Header partial (sidebar + topnav)
│   │   ├── dashboard.html      # Portfolio overview
│   │   ├── transactions.html   # Transaction list with filters
│   │   ├── tax_reports.html    # Tax summary by year
│   │   ├── tax_detail_disposals.html  # Gains/losses drill-down
│   │   ├── tax_detail_incomes.html    # Income transactions
│   │   ├── holding_detail.html        # Per-asset analysis
│   │   └── settings.html       # Import, settings, language
│   └── static/                 # Static assets
├── src/                        # CLI tools (legacy)
│   ├── binance_client.py       # Binance API client
│   ├── consolidator.py         # CSV consolidation
│   ├── eur_converter.py        # EUR price conversion
│   ├── fifo_calculator.py      # FIFO calculation engine
│   ├── import_prices.py        # Historical price fetcher
│   └── report_generator.py     # Excel report generation
├── data/                       # Transaction data (gitignored)
├── .env                        # API keys (gitignored)
├── .env.example                # Template for API keys
├── .gitignore
├── requirements.txt            # CLI dependencies
└── README.md
```

## Configuration

### Environment Variables

Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
```

```
BINANCE_API_KEY=your_api_key
BINANCE_API_SECRET=your_api_secret
```

### Settings (in-app)

- **Language** — Español / English / Deutsch (auto-detected from browser, override in Settings)
- **Country** — Spain, Germany, France, Portugal
- **Base Currency** — EUR, USD, GBP
- **Cost Basis Method** — FIFO, LIFO, Average Cost
- **Cost Tracking** — Universal or per-wallet
- **Crypto-to-Crypto Gains** — Taxable or not
- **Layout** — Sidebar or top navigation

## Pages

| Page | Description |
|------|-------------|
| `/dashboard` | Portfolio overview, holdings table, value chart, invested summary |
| `/transactions` | Full transaction list with multi-select filters, date range, bulk stats |
| `/tax-reports` | Year selector, gains/losses summary, historical table, IRPF brackets |
| `/holdings/<coin>` | Per-asset detail: balance, cost basis, top purchases, activity breakdown |
| `/settings` | CSV import, language, tax config, layout toggle, price fetching |

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/import-csv` | POST | Upload and import Binance CSV |
| `/api/fetch-prices` | POST | Fetch historical prices from CoinGecko |
| `/api/save-setting` | POST | Save a user setting (key/value) |
| `/api/clear-data` | POST | Clear all transactions and prices |
| `/api/portfolio-data` | GET | JSON portfolio summary |
| `/api/history-data` | GET | JSON historical value data |

## Price Data Strategy

The app uses a 3-tier approach for historical EUR prices:

1. **Binance API** — Primary source for daily closing prices
2. **CoinGecko API** — Fallback for coins not on Binance
3. **Annual averages** — Gap filler for missing dates

Stablecoins (USDT, USDC, BUSD) use fixed EUR rates.

## Privacy & Security

- All data is stored locally in SQLite — no cloud sync
- `.env`, `data/`, `*.db`, and `*.json` are gitignored
- Privacy mode blurs all monetary values client-side

## License

MIT
