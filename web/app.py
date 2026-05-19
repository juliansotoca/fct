import os
import csv
import re
from urllib.parse import urlencode
from datetime import datetime
from decimal import Decimal
from flask import Flask, render_template, request, jsonify, redirect, url_for
from werkzeug.datastructures import MultiDict
from web.database import init_db, get_db, import_transactions, get_settings, save_setting
from web.database import get_transactions, get_total_transactions, get_currencies, get_operations
from web.database import get_transaction_count, clear_all_data
from web.engine import (
    compute_fifo_from_db, get_portfolio_summary, get_tax_summary,
    get_portfolio_history, fetch_prices_batch, classify_operation,
    invalidate_cache, get_invested_summary,
)
from web.i18n import TRANSLATIONS, SUPPORTED_LANGUAGES, DEFAULT_LANGUAGE, get_translation

app = Flask(__name__)
app.secret_key = os.urandom(24)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(os.path.dirname(BASE_DIR), "data")


def detect_browser_language():
    accept = request.headers.get("Accept-Language", "")
    for part in accept.split(","):
        lang = part.split(";")[0].strip().split("-")[0].lower()
        if lang in SUPPORTED_LANGUAGES:
            return lang
    return DEFAULT_LANGUAGE


def get_current_language():
    conn = get_db()
    rows = conn.execute("SELECT key, value FROM settings WHERE key = 'language'").fetchall()
    conn.close()
    if rows:
        lang = rows[0]["value"]
        if lang in SUPPORTED_LANGUAGES:
            return lang
    return detect_browser_language()


@app.context_processor
def utility_processor():
    def build_query(page):
        params = MultiDict(request.args)
        params['page'] = str(page)
        return urlencode(list(params.items(multi=True)))

    def t(key):
        return get_translation(key, lang=current_lang)

    settings = get_settings()
    sidebar_mode = settings.get("sidebar_layout", "False") == "True"
    current_lang = get_current_language()
    return dict(build_query=build_query, sidebar_mode=sidebar_mode, t=t, current_lang=current_lang)


@app.route("/")
def index():
    return redirect(url_for("dashboard"))


@app.route("/dashboard")
def dashboard():
    summary = get_portfolio_summary()
    history = get_portfolio_history(days=1825)
    tx_count = get_transaction_count()
    invested = get_invested_summary()

    sorted_holdings = sorted(summary["holdings"], key=lambda h: float(h["market_value"]), reverse=True)
    summary["holdings"] = sorted_holdings

    return render_template("dashboard.html", summary=summary, history=history, tx_count=tx_count, invested=invested)


@app.route("/transactions")
def transactions():
    page = request.args.get("page", 1, type=int)
    per_page = 50

    currencies = request.args.getlist("currency")
    operations = request.args.getlist("operation")
    invert_currency = request.args.get("invert_currency", "") == "1"
    invert_operation = request.args.get("invert_operation", "") == "1"
    date_from = request.args.get("date_from", "")
    date_to = request.args.get("date_to", "")
    min_value = request.args.get("min_value", "", type=float) or None

    offset = (page - 1) * per_page
    txs = get_transactions(
        limit=per_page, offset=offset,
        currencies=currencies or None, operations=operations or None,
        date_from=date_from or None, date_to=date_to or None,
        invert_currency=invert_currency, invert_operation=invert_operation,
        min_value=min_value,
    )
    total = get_total_transactions(
        currencies=currencies or None, operations=operations or None,
        date_from=date_from or None, date_to=date_to or None,
        invert_currency=invert_currency, invert_operation=invert_operation,
        min_value=min_value,
    )
    total_pages = (total + per_page - 1) // per_page

    all_currencies = get_currencies()
    all_operations = get_operations()

    latest_tx = get_db().execute("SELECT MAX(time) as latest FROM transactions").fetchone()
    latest_date = latest_tx["latest"][:10] if latest_tx and latest_tx["latest"] else datetime.now().strftime("%Y-%m-%d")
    get_db().close()

    if not date_from:
        date_from = f"{datetime.now().year}-01-01"
    if not date_to:
        date_to = latest_date

    return render_template(
        "transactions.html",
        transactions=txs, page=page, total_pages=total_pages, total=total,
        currencies=all_currencies, operations=all_operations,
        selected_currencies=currencies, selected_operations=operations,
        invert_currency=invert_currency, invert_operation=invert_operation,
        date_from=date_from, date_to=date_to,
        min_value=min_value,
    )


@app.route("/tax-reports")
def tax_reports():
    year = request.args.get("year", None, type=int)
    detail = request.args.get("detail", "")

    settings = get_settings()
    fifo = compute_fifo_from_db()

    yearly_data = {}
    for d in fifo["disposals"]:
        y = d["tx"]["time"].year
        if y not in yearly_data:
            yearly_data[y] = {"gains": Decimal("0"), "losses": Decimal("0"), "count": 0}
        gl = d["gain_loss_eur"]
        if gl > 0:
            yearly_data[y]["gains"] += gl
        else:
            yearly_data[y]["losses"] += abs(gl)
        yearly_data[y]["count"] += 1

    # Include years with incomes but no disposals
    for i in fifo["incomes"]:
        y = i["time"].year
        if y not in yearly_data:
            yearly_data[y] = {"gains": Decimal("0"), "losses": Decimal("0"), "count": 0}

    if not yearly_data:
        year = datetime.now().year
    elif year is None:
        year = max(yearly_data.keys())

    summary = get_tax_summary(year)
    invested = get_invested_summary()

    if detail == "disposals":
        disposals = [d for d in fifo["disposals"] if d["tx"]["time"].year == year]
        return render_template(
            "tax_detail_disposals.html",
            year=year, disposals=disposals, summary=summary,
            settings=settings, yearly_data=yearly_data, invested=invested,
        )
    elif detail == "gains":
        disposals = [d for d in fifo["disposals"] if d["tx"]["time"].year == year and d["gain_loss_eur"] > 0]
        return render_template(
            "tax_detail_disposals.html",
            year=year, disposals=disposals, summary=summary,
            settings=settings, yearly_data=yearly_data, invested=invested,
            filter_label="Gains",
        )
    elif detail == "losses":
        disposals = [d for d in fifo["disposals"] if d["tx"]["time"].year == year and d["gain_loss_eur"] < 0]
        return render_template(
            "tax_detail_disposals.html",
            year=year, disposals=disposals, summary=summary,
            settings=settings, yearly_data=yearly_data, invested=invested,
            filter_label="Losses",
        )
    elif detail == "incomes":
        incomes = [i for i in fifo["incomes"] if i["time"].year == year]
        return render_template(
            "tax_detail_incomes.html",
            year=year, incomes=incomes, summary=summary,
            settings=settings, yearly_data=yearly_data, invested=invested,
        )

    return render_template(
        "tax_reports.html",
        year=year, summary=summary, settings=settings,
        yearly_data=yearly_data, invested=invested,
    )


@app.route("/settings")
def settings():
    s = get_settings()
    tx_count = get_transaction_count()
    return render_template("settings.html", settings=s, tx_count=tx_count)


@app.route("/api/import-csv", methods=["POST"])
def import_csv():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400

    try:
        content = file.read().decode("utf-8-sig")
        records = []
        reader = csv.DictReader(content.splitlines())

        col_map = {}
        for col in reader.fieldnames or []:
            cs = col.strip()
            if "ID de usuario" in cs:
                col_map[col] = "user_id"
            elif cs == "Tiempo":
                col_map[col] = "time"
            elif cs == "Cuenta":
                col_map[col] = "account"
            elif cs == "Operación":
                col_map[col] = "operation"
            elif cs == "Moneda":
                col_map[col] = "currency"
            elif cs == "Cambio":
                col_map[col] = "change"
            elif cs == "Observación":
                col_map[col] = "observation"

        for row in reader:
            mapped = {}
            for orig, new in col_map.items():
                val = row.get(orig, "").strip()
                if new == "time" and val:
                    try:
                        mapped[new] = datetime.strptime(val, "%y-%m-%d %H:%M:%S")
                    except ValueError:
                        try:
                            mapped[new] = datetime.strptime(val, "%Y-%m-%d %H:%M:%S")
                        except ValueError:
                            continue
                else:
                    mapped[new] = val

            if "time" in mapped and "currency" in mapped and "operation" in mapped and "change" in mapped:
                records.append(mapped)

        imported, duplicates = import_transactions(records, source=file.filename)
        invalidate_cache()
        return jsonify({
            "imported": imported,
            "duplicates": duplicates,
            "total": len(records),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/fetch-prices", methods=["POST"])
def fetch_prices():
    currencies = request.json.get("currencies", [])
    days = request.json.get("days", 365)
    try:
        results = fetch_prices_batch(currencies, days_back=days)
        return jsonify({"fetched": len(results)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/save-setting", methods=["POST"])
def api_save_setting():
    data = request.json
    key = data.get("key")
    value = data.get("value")
    if key:
        save_setting(key, value)
        return jsonify({"ok": True})
    return jsonify({"error": "Missing key"}), 400


@app.route("/api/clear-data", methods=["POST"])
def api_clear_data():
    clear_all_data()
    init_db()
    invalidate_cache()
    return jsonify({"ok": True})


@app.route("/api/refresh-price", methods=["POST"])
def api_refresh_price():
    data = request.get_json() or {}
    currency = data.get("currency", "").upper()
    date_str = data.get("date", "")
    if not currency or not date_str:
        return jsonify({"error": "Missing currency or date"}), 400

    try:
        from datetime import datetime
        target_date = datetime.fromisoformat(date_str)
        from web.engine import fetch_prices_batch
        from web.database import save_price, get_price

        # Try to fetch from Binance API for the specific date
        import requests
        symbol_map = {
            "BTC": "BTCEUR", "ETH": "ETHEUR", "BNB": "BNBEUR",
            "SOL": "SOLEUR", "ADA": "ADAEUR", "XRP": "XRPEUR",
            "DOGE": "DOGEEUR", "DOT": "DOTEUR", "AVAX": "AVAXEUR",
            "MATIC": "MATICEUR", "LINK": "LINKEUR", "UNI": "UNIEUR",
            "ATOM": "ATOMEUR", "LTC": "LTCEUR", "NEAR": "NEAREUR",
            "FTM": "FTMEUR", "AAVE": "AAVEEUR", "ALGO": "ALGOEUR",
            "SUI": "SUIEUR", "SEI": "SEIEUR", "TIA": "TIAEUR",
            "JUP": "JUPEUR", "WIF": "WIFEUR", "PEPE": "PEPEEUR",
            "RENDER": "RENDEREUR", "FET": "FETEUR", "TAO": "TAOEUR",
            "ONDO": "ONDOEUR", "STRK": "STRKEUR", "ENA": "ENAEUR",
        }
        symbol = symbol_map.get(currency, f"{currency}EUR")
        ts = int(target_date.timestamp() * 1000)

        resp = requests.get(
            "https://api.binance.com/api/v3/klines",
            params={"symbol": symbol, "interval": "1d", "startTime": ts, "limit": 1},
            timeout=10
        )
        if resp.status_code == 200 and resp.json():
            kline = resp.json()[0]
            close_price = float(kline[4])
            save_price(currency, target_date.strftime("%Y-%m-%d"), close_price, "binance")
            invalidate_cache()
            return jsonify({"ok": True, "price": close_price, "source": "binance"})

        # Fallback to CoinGecko
        cg_id_map = {
            "BTC": "bitcoin", "ETH": "ethereum", "BNB": "binancecoin",
            "SOL": "solana", "ADA": "cardano", "XRP": "ripple",
            "DOGE": "dogecoin", "DOT": "polkadot", "AVAX": "avalanche-2",
            "MATIC": "matic-network", "LINK": "chainlink", "UNI": "uniswap",
            "ATOM": "cosmos", "LTC": "litecoin", "NEAR": "near",
            "FTM": "fantom", "AAVE": "aave", "ALGO": "algorand",
            "SUI": "sui", "SEI": "sei-network", "TIA": "celestia",
            "JUP": "jupiter-exchange-solana", "WIF": "dogwifcoin",
            "PEPE": "pepe", "RENDER": "render-token", "FET": "fetch-ai",
            "TAO": "bittensor", "ONDO": "ondo-finance", "STRK": "starknet",
            "ENA": "ethena", "USDT": "tether", "USDC": "usd-coin",
            "BUSD": "binance-usd", "SHIB": "shiba-inu", "ARB": "arbitrum",
            "HIGH": "highstreet", "MC": "mercurial", "SANTOS": "santos-fc-fan-token",
            "NOT": "notcoin", "CAT": "cat-token", "PENGU": "pudgy-penguins",
        }
        cg_id = cg_id_map.get(currency, currency.lower())
        date_fmt = target_date.strftime("%d-%m-%Y")
        cg_resp = requests.get(
            f"https://api.coingecko.com/api/v3/coins/{cg_id}/history",
            params={"date": date_fmt, "localization": "false"},
            headers={"Accept": "application/json"},
            timeout=10
        )
        if cg_resp.status_code == 200:
            cg_data = cg_resp.json()
            eur_price = cg_data.get("market_data", {}).get("current_price", {}).get("eur")
            if eur_price:
                save_price(currency, target_date.strftime("%Y-%m-%d"), eur_price, "coingecko")
                invalidate_cache()
                return jsonify({"ok": True, "price": eur_price, "source": "coingecko"})

        return jsonify({"error": "Price not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/portfolio-data")
def api_portfolio_data():
    summary = get_portfolio_summary()
    return jsonify({
        "total_value": float(summary["total_market_value"]),
        "total_cost": float(summary["total_cost"]),
        "unrealized": float(summary["total_unrealized"]),
        "roi": float(summary["total_roi"]),
        "holdings": [
            {
                "currency": h["currency"],
                "balance": float(h["balance"]),
                "cost_eur": float(h["cost_eur"]),
                "market_value": float(h["market_value"]),
                "roi": float(h["roi"]),
            }
            for h in summary["holdings"]
        ],
    })


@app.route("/api/history-data")
def api_history_data():
    days = request.args.get("days", 90, type=int)
    history = get_portfolio_history(days=days)
    return jsonify(history)


@app.route("/holdings/<currency>")
def holding_detail(currency):
    summary = get_portfolio_summary()
    holding = None
    for h in summary["holdings"]:
        if h["currency"] == currency:
            holding = h
            break
    if not holding:
        return redirect(url_for("dashboard"))

    conn = get_db()
    txs = conn.execute(
        "SELECT * FROM transactions WHERE currency = ? ORDER BY time DESC",
        (currency,),
    ).fetchall()
    conn.close()

    transactions = [dict(r) for r in txs]

    buys = [t for t in transactions if float(t["change"]) > 0]
    sells = [t for t in transactions if float(t["change"]) < 0]

    total_bought = sum(float(t["change"]) for t in buys)
    total_sold = sum(abs(float(t["change"])) for t in sells)

    top_buys = sorted(buys, key=lambda t: abs(float(t["change"])), reverse=True)[:10]

    return render_template(
        "holding_detail.html",
        currency=currency, holding=holding,
        transactions=transactions,
        total_bought=total_bought, total_sold=total_sold,
        top_buys=top_buys,
    )
def api_holdings_data():
    summary = get_portfolio_summary()
    sort_by = request.args.get("sort", "market_value")
    sort_order = request.args.get("order", "desc")

    key_map = {
        "currency": "currency",
        "balance": "balance",
        "cost_eur": "cost_eur",
        "market_value": "market_value",
        "roi": "roi",
    }
    sort_key = key_map.get(sort_by, "market_value")
    reverse = sort_order == "desc"

    sorted_holdings = sorted(
        summary["holdings"],
        key=lambda h: float(h[sort_key]) if sort_key != "currency" else h[sort_key],
        reverse=reverse,
    )

    return jsonify({
        "holdings": [
            {
                "currency": h["currency"],
                "balance": float(h["balance"]),
                "cost_eur": float(h["cost_eur"]),
                "market_value": float(h["market_value"]),
                "roi": float(h["roi"]),
            }
            for h in sorted_holdings
        ],
    })


if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5002)
