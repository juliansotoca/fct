"""
Engine: FIFO calculations, price fetching, portfolio valuation
"""

import requests
import time
import threading
from datetime import datetime, timedelta
from decimal import Decimal
from collections import defaultdict
from functools import lru_cache
from web.database import get_db, save_price, get_price, get_yearly_prices, get_settings


STABLECOINS = {"USDT", "USDC", "BUSD", "DAI", "TUSD", "USDP", "USD", "EUR"}

STABLECOIN_RATES = {
    "USDT": 0.92,
    "USDC": 0.92,
    "BUSD": 0.92,
    "DAI": 0.92,
    "EUR": 1.0,
}

HISTORICAL_ANNUAL_PRICES = {
    "BTC": {
        2021: 35000, 2022: 28000, 2023: 42000, 2024: 60000, 2025: 92000, 2026: 65000,
    },
    "ETH": {
        2021: 2200, 2022: 1600, 2023: 2200, 2024: 3000, 2025: 3000, 2026: 2000,
    },
    "BNB": {
        2021: 350, 2022: 300, 2023: 300, 2024: 550, 2025: 700, 2026: 590,
    },
    "SOL": {
        2021: 80, 2022: 40, 2023: 60, 2024: 120, 2025: 150, 2026: 80,
    },
    "ADA": {
        2021: 1.2, 2022: 0.5, 2023: 0.4, 2024: 0.6, 2025: 0.6, 2026: 0.25,
    },
    "DOT": {
        2021: 18, 2022: 7, 2023: 5, 2024: 7, 2025: 5, 2026: 3,
    },
    "DOGE": {
        2021: 0.2, 2022: 0.1, 2023: 0.07, 2024: 0.12, 2025: 0.17, 2026: 0.09,
    },
    "AVAX": {
        2021: 50, 2022: 20, 2023: 15, 2024: 35, 2025: 18, 2026: 9,
    },
    "MATIC": {
        2021: 1.0, 2022: 0.8, 2023: 0.9, 2024: 0.8, 2025: 0.2, 2026: 0.15,
    },
    "LINK": {
        2021: 18, 2022: 7, 2023: 8, 2024: 14, 2025: 15, 2026: 8.5,
    },
    "LTC": {
        2021: 150, 2022: 60, 2023: 70, 2024: 80, 2025: 90, 2026: 80,
    },
    "XRP": {
        2021: 0.8, 2022: 0.4, 2023: 0.5, 2024: 0.6, 2025: 2.0, 2026: 1.5,
    },
    "UNI": {
        2021: 18, 2022: 6, 2023: 6, 2024: 8, 2025: 8, 2026: 6,
    },
    "ATOM": {
        2021: 18, 2022: 12, 2023: 10, 2024: 9, 2025: 5, 2026: 4,
    },
    "SHIB": {
        2021: 0.00002, 2022: 0.000008, 2023: 0.000007, 2024: 0.000015, 2025: 0.000015, 2026: 0.00001,
    },
    "TRX": {
        2021: 0.06, 2022: 0.06, 2023: 0.07, 2024: 0.12, 2025: 0.15, 2026: 0.12,
    },
    "NEAR": {
        2021: 12, 2022: 4, 2023: 2, 2024: 5, 2025: 4, 2026: 2,
    },
    "FTM": {
        2021: 1.5, 2022: 0.3, 2023: 0.3, 2024: 0.6, 2025: 0.7, 2026: 0.5,
    },
    "ALGO": {
        2021: 1.0, 2022: 0.4, 2023: 0.15, 2024: 0.15, 2025: 0.15, 2026: 0.1,
    },
    "MANA": {
        2021: 1.5, 2022: 0.6, 2023: 0.5, 2024: 0.5, 2025: 0.4, 2026: 0.3,
    },
    "SAND": {
        2021: 1.5, 2022: 0.6, 2023: 0.4, 2024: 0.4, 2025: 0.3, 2026: 0.2,
    },
    "AXS": {
        2021: 80, 2022: 15, 2023: 6, 2024: 6, 2025: 5, 2026: 3,
    },
    "ENJ": {
        2021: 1.5, 2022: 0.4, 2023: 0.3, 2024: 0.3, 2025: 0.2, 2026: 0.15,
    },
    "GALA": {
        2021: 0.3, 2022: 0.03, 2023: 0.02, 2024: 0.03, 2025: 0.02, 2026: 0.01,
    },
    "CHZ": {
        2021: 0.3, 2022: 0.1, 2023: 0.08, 2024: 0.1, 2025: 0.07, 2026: 0.05,
    },
    "THETA": {
        2021: 6, 2022: 1.5, 2023: 1, 2024: 1.5, 2025: 1.5, 2026: 1,
    },
    "VET": {
        2021: 0.15, 2022: 0.03, 2023: 0.02, 2024: 0.03, 2025: 0.03, 2026: 0.02,
    },
    "ICP": {
        2021: 100, 2022: 6, 2023: 5, 2024: 10, 2025: 8, 2026: 5,
    },
    "FIL": {
        2021: 80, 2022: 6, 2023: 5, 2024: 5, 2025: 4, 2026: 3,
    },
    "ETC": {
        2021: 50, 2022: 20, 2023: 20, 2024: 25, 2025: 20, 2026: 15,
    },
    "XLM": {
        2021: 0.3, 2022: 0.1, 2023: 0.1, 2024: 0.12, 2025: 0.1, 2026: 0.08,
    },
    "AAVE": {
        2021: 250, 2022: 80, 2023: 70, 2024: 100, 2025: 100, 2026: 80,
    },
    "MKR": {
        2021: 2000, 2022: 800, 2023: 800, 2024: 2500, 2025: 2500, 2026: 1500,
    },
    "COMP": {
        2021: 300, 2022: 50, 2023: 40, 2024: 50, 2025: 50, 2026: 40,
    },
    "SNX": {
        2021: 8, 2022: 3, 2023: 2.5, 2024: 3, 2025: 2, 2026: 1.5,
    },
    "CRV": {
        2021: 2, 2022: 0.8, 2023: 0.6, 2024: 0.5, 2025: 0.4, 2026: 0.3,
    },
    "SUSHI": {
        2021: 5, 2022: 1.5, 2023: 1, 2024: 1, 2025: 0.8, 2026: 0.5,
    },
    "YFI": {
        2021: 25000, 2022: 8000, 2023: 6000, 2024: 8000, 2025: 6000, 2026: 5000,
    },
    "1INCH": {
        2021: 1.5, 2022: 0.4, 2023: 0.3, 2024: 0.4, 2025: 0.3, 2026: 0.2,
    },
    "BAT": {
        2021: 1.0, 2022: 0.3, 2023: 0.2, 2024: 0.2, 2025: 0.2, 2026: 0.15,
    },
    "ZRX": {
        2021: 0.8, 2022: 0.2, 2023: 0.2, 2024: 0.3, 2025: 0.3, 2026: 0.2,
    },
    "KNC": {
        2021: 2, 2022: 0.6, 2023: 0.5, 2024: 0.5, 2025: 0.4, 2026: 0.3,
    },
    "REN": {
        2021: 0.5, 2022: 0.1, 2023: 0.05, 2024: 0.05, 2025: 0.04, 2026: 0.03,
    },
    "LRC": {
        2021: 1.5, 2022: 0.3, 2023: 0.2, 2024: 0.2, 2025: 0.15, 2026: 0.1,
    },
    "STORJ": {
        2021: 1.5, 2022: 0.4, 2023: 0.4, 2024: 0.5, 2025: 0.4, 2026: 0.3,
    },
    "GRT": {
        2021: 0.8, 2022: 0.1, 2023: 0.1, 2024: 0.2, 2025: 0.15, 2026: 0.1,
    },
    "ANKR": {
        2021: 0.15, 2022: 0.03, 2023: 0.02, 2024: 0.03, 2025: 0.02, 2026: 0.015,
    },
    "BAND": {
        2021: 6, 2022: 1.5, 2023: 1, 2024: 1, 2025: 0.8, 2026: 0.6,
    },
    "NMR": {
        2021: 30, 2022: 15, 2023: 15, 2024: 15, 2025: 12, 2026: 10,
    },
    "OCEAN": {
        2021: 0.8, 2022: 0.2, 2023: 0.3, 2024: 0.5, 2025: 0.6, 2026: 0.4,
    },
    "FET": {
        2021: 0.3, 2022: 0.1, 2023: 0.2, 2024: 0.8, 2025: 1.5, 2026: 1,
    },
    "RNDR": {
        2021: 0.5, 2022: 0.2, 2023: 0.3, 2024: 5, 2025: 7, 2026: 5,
    },
    "INJ": {
        2021: 3, 2022: 2, 2023: 5, 2024: 25, 2025: 20, 2026: 12,
    },
    "ARB": {
        2023: 1.2, 2024: 1.0, 2025: 0.8, 2026: 0.5,
    },
    "OP": {
        2022: 1.5, 2023: 1.2, 2024: 2.5, 2025: 1.5, 2026: 1,
    },
    "APT": {
        2022: 5, 2023: 8, 2024: 7, 2025: 6, 2026: 5,
    },
    "SUI": {
        2023: 0.5, 2024: 0.8, 2025: 1.5, 2026: 2,
    },
    "SEI": {
        2023: 0.3, 2024: 0.5, 2025: 0.4, 2026: 0.3,
    },
    "TIA": {
        2023: 5, 2024: 10, 2025: 5, 2026: 3,
    },
    "TON": {
        2021: 3, 2022: 2, 2023: 2, 2024: 5, 2025: 5, 2026: 4,
    },
    "HBAR": {
        2021: 0.25, 2022: 0.06, 2023: 0.05, 2024: 0.08, 2025: 0.08, 2026: 0.06,
    },
    "PEPE": {
        2023: 0.000001, 2024: 0.000008, 2025: 0.00001, 2026: 0.000008,
    },
    "WIF": {
        2023: 0.5, 2024: 2, 2025: 1.5, 2026: 1,
    },
    "BONK": {
        2022: 0.000001, 2023: 0.000002, 2024: 0.000015, 2025: 0.00002, 2026: 0.000015,
    },
    "NOT": {
        2024: 0.008, 2025: 0.005, 2026: 0.004,
    },
    "MEME": {
        2023: 0.01, 2024: 0.02, 2025: 0.015, 2026: 0.01,
    },
}

INCOME_OPERATIONS = {
    "Simple Earn Flexible Interest", "Simple Earn Locked Interest",
    "Simple Earn Flexible Airdrop",
    "Cash Voucher Distribution", "Referral Kickback", "Commission Rebate",
    "Staking", "Staking Rewards", "BNB Vault Rewards",
    "Simple Earn Locked Rewards", "Launchpool",
    "Launchpool Airdrop - System Distribution",
    "Launchpool Airdrop - User Claim Distribution",
    "Airdrop", "Airdrop Assets", "HODLer Airdrops Distribution",
    "Crypto Box", "Binance Pay", "Megadrop Rewards",
    "Distribution", "Referral Commission", "Token Swap - Distribution",
    "Asset Recovery",
    "Strategy Trading Fee Rebate",
}

INTERNAL_TRANSFER_OPERATIONS = {
    "Simple Earn Flexible Subscription", "Simple Earn Locked Subscription",
    "Simple Earn Flexible Redemption", "Simple Earn Locked Redemption",
    "Transfer Between Main and Funding Wallet",
    "Transfer Between Spot and Strategy Account",
    "Transaction Fee",
    "Small Assets Exchange BNB", "Token Swap - Redenomination/Rebranding",
    "Staking Purchase", "Staking Redemption",
}

DEPOSIT_OPERATIONS = {"Deposit", "Buy Crypto With Card", "Buy Crypto With Fiat", "P2P Trading", "Fiat OCBS - Add Fiat and Fees"}
WITHDRAWAL_OPERATIONS = {"Withdraw"}

TRADE_OPERATIONS = {
    "Buy", "Sell", "Trade", "Transaction Related",
    "Transaction Buy", "Transaction Spend", "Transaction Revenue",
    "Transaction Sold", "Binance Convert",
}

_fifo_cache = None
_fifo_cache_lock = threading.Lock()
_price_cache = {}
_annual_cache = {}


def invalidate_cache():
    global _fifo_cache, _price_cache, _annual_cache
    with _fifo_cache_lock:
        _fifo_cache = None
    _price_cache.clear()
    _annual_cache.clear()


def classify_operation(op):
    if op in INCOME_OPERATIONS:
        return "income"
    elif op in DEPOSIT_OPERATIONS:
        return "deposit"
    elif op in WITHDRAWAL_OPERATIONS:
        return "withdrawal"
    elif op in TRADE_OPERATIONS:
        return "trade"
    elif op in INTERNAL_TRANSFER_OPERATIONS:
        return "internal"
    return "other"


def _load_price_cache():
    global _price_cache
    if _price_cache:
        return _price_cache
    conn = get_db()
    rows = conn.execute("SELECT currency, date, price_eur FROM prices").fetchall()
    conn.close()
    _price_cache = {}
    for r in rows:
        c = r["currency"]
        if c not in _price_cache:
            _price_cache[c] = {}
        _price_cache[c][r["date"]] = r["price_eur"]
    return _price_cache


def _load_annual_cache():
    global _annual_cache
    if _annual_cache:
        return _annual_cache
    prices = _load_price_cache()
    _annual_cache = {}
    for currency, dates in prices.items():
        year_prices = defaultdict(list)
        for date_str, price in dates.items():
            year = date_str[:4]
            year_prices[year].append(price)
        for year, vals in year_prices.items():
            if year not in _annual_cache:
                _annual_cache[year] = {}
            _annual_cache[year][currency] = sum(vals) / len(vals)
    for currency, year_prices in HISTORICAL_ANNUAL_PRICES.items():
        for year, price in year_prices.items():
            year_str = str(year)
            if year_str not in _annual_cache:
                _annual_cache[year_str] = {}
            if currency not in _annual_cache[year_str]:
                _annual_cache[year_str][currency] = price
    return _annual_cache


def _get_price_cached(currency, date_str):
    prices = _load_price_cache()
    if currency in prices and date_str in prices[currency]:
        return prices[currency][date_str]
    annual = _load_annual_cache()
    year = date_str[:4]
    if year in annual and currency in annual[year]:
        return annual[year][currency]
    return None


def fetch_prices_batch(currencies, days_back=1825):
    global _price_cache, _annual_cache
    settings = get_settings()
    base_currency = settings.get("base_currency", "EUR").lower()

    coin_map = {
        "BTC": "bitcoin", "ETH": "ethereum", "BNB": "binancecoin",
        "SOL": "solana", "ADA": "cardano", "DOT": "polkadot",
        "DOGE": "dogecoin", "AVAX": "avalanche-2", "MATIC": "matic-network",
        "LINK": "chainlink", "UNI": "uniswap", "ATOM": "cosmos",
        "LTC": "litecoin", "XRP": "ripple", "BCH": "bitcoin-cash",
        "SHIB": "shiba-inu", "TRX": "tron", "NEAR": "near",
        "FTM": "fantom", "ALGO": "algorand", "MANA": "decentraland",
        "SAND": "the-sandbox", "AXS": "axie-infinity", "ENJ": "enjincoin",
        "GALA": "gala", "CHZ": "chiliz", "THETA": "theta-token",
        "VET": "vechain", "ICP": "internet-computer", "FIL": "filecoin",
        "ETC": "ethereum-classic", "XLM": "stellar", "AAVE": "aave",
        "MKR": "maker", "COMP": "compound-governance-token",
        "SNX": "havven", "CRV": "curve-dao-token", "SUSHI": "sushi",
        "YFI": "yearn-finance", "1INCH": "1inch", "BAT": "basic-attention-token",
        "ZRX": "0x", "KNC": "kyber-network-crystal", "REN": "republic-protocol",
        "LRC": "loopring", "STORJ": "storj", "GRT": "the-graph",
        "ANKR": "ankr", "BAND": "band-protocol", "NMR": "numeraire",
        "OCEAN": "ocean-protocol", "FET": "fetch-ai", "AGIX": "singularitynet",
        "RNDR": "render-token", "INJ": "injective-protocol", "ARB": "arbitrum",
        "OP": "optimism", "APT": "aptos", "SUI": "sui",
        "SEI": "sei-network", "TIA": "celestia", "JUP": "jupiter-exchange-solana",
        "WIF": "dogwifcoin", "BONK": "bonk", "PEPE": "pepe",
        "FLOKI": "floki", "MEME": "meme", "NOT": "notcoin",
        "TON": "the-open-network", "HBAR": "hedera-hashgraph",
        "RENDER": "render-token",
    }

    end_date = datetime.now()
    start_date = end_date - timedelta(days=days_back)

    results = {}
    for currency in currencies:
        if currency in STABLECOINS:
            continue
        coin_id = coin_map.get(currency)
        if not coin_id:
            continue

        try:
            url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
            params = {
                "vs_currency": base_currency,
                "days": days_back,
                "interval": "daily",
            }
            resp = requests.get(url, params=params, timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                for ts, price in data.get("prices", []):
                    date_str = datetime.fromtimestamp(ts / 1000).strftime("%Y-%m-%d")
                    save_price(currency.upper(), date_str, price)
                    results[(currency.upper(), date_str)] = price
                time.sleep(1.2)
            elif resp.status_code == 429:
                time.sleep(60)
        except Exception as e:
            print(f"Error fetching {currency}: {e}")

    _price_cache.clear()
    _annual_cache.clear()
    _load_price_cache()
    _load_annual_cache()
    return results


def convert_to_eur(currency, amount, date, price_cache=None):
    if currency in STABLECOINS:
        return Decimal(str(amount)) * Decimal(str(STABLECOIN_RATES.get(currency, 0.92)))

    date_str = date.strftime("%Y-%m-%d") if hasattr(date, "strftime") else str(date)[:10]
    year = date_str[:4]

    if price_cache and year in price_cache and currency in price_cache[year]:
        return Decimal(str(amount)) * Decimal(str(price_cache[year][currency]))

    cached = _get_price_cached(currency, date_str)
    if cached:
        return Decimal(str(amount)) * Decimal(str(cached))

    return Decimal(str(amount)) * Decimal("0")


def compute_fifo_from_db():
    global _fifo_cache
    with _fifo_cache_lock:
        if _fifo_cache is not None:
            return _fifo_cache

    conn = get_db()
    rows = conn.execute(
        "SELECT id, time, account, operation, currency, change, observation FROM transactions ORDER BY time ASC"
    ).fetchall()
    conn.close()

    transactions = []
    for r in rows:
        transactions.append({
            "id": r["id"],
            "time": datetime.fromisoformat(r["time"]),
            "account": r["account"] or "",
            "operation": r["operation"],
            "currency": r["currency"],
            "change": Decimal(str(r["change"])),
            "observation": r["observation"] or "",
            "classification": classify_operation(r["operation"]),
        })

    annual = _load_annual_cache()
    price_cache = {}
    for year in range(2021, 2027):
        price_cache[year] = annual.get(year, {})

    inventory = defaultdict(list)
    disposals = []
    incomes = []
    deposits = []
    withdrawals = []

    for tx in transactions:
        currency = tx["currency"]
        amount = tx["change"]
        classification = tx["classification"]
        eur_value = convert_to_eur(currency, abs(amount), tx["time"], price_cache)

        if classification == "deposit":
            deposits.append(tx)
            if amount > 0 and currency.upper() != "EUR":
                inventory[currency].append({
                    "quantity": abs(amount),
                    "cost_basis": eur_value,
                    "price_per_unit": eur_value / abs(amount) if amount else Decimal("0"),
                    "date": tx["time"],
                    "tx_id": str(tx["id"]),
                })

        elif classification == "income":
            tx["amount_eur"] = eur_value
            incomes.append(tx)
            if amount > 0:
                inventory[currency].append({
                    "quantity": abs(amount),
                    "cost_basis": eur_value,
                    "price_per_unit": eur_value / abs(amount) if amount else Decimal("0"),
                    "date": tx["time"],
                    "tx_id": str(tx["id"]),
                    "is_income": True,
                })

        elif classification == "trade":
            if currency.upper() == "EUR":
                continue
            if amount > 0:
                inventory[currency].append({
                    "quantity": abs(amount),
                    "cost_basis": eur_value,
                    "price_per_unit": eur_value / abs(amount) if amount else Decimal("0"),
                    "date": tx["time"],
                    "tx_id": str(tx["id"]),
                })
            else:
                qty_to_sell = abs(amount)
                if inventory[currency]:
                    disposals_for_tx = []
                    while qty_to_sell > 0 and inventory[currency]:
                        lot = inventory[currency][0]
                        if lot["quantity"] <= qty_to_sell:
                            disposed_qty = lot["quantity"]
                            inventory[currency].pop(0)
                        else:
                            disposed_qty = qty_to_sell
                            lot["quantity"] -= disposed_qty
                            lot["cost_basis"] = lot["price_per_unit"] * lot["quantity"]

                        acquisition_cost = lot["price_per_unit"] * disposed_qty
                        disposals_for_tx.append({
                            "disposal_date": tx["time"],
                            "currency": currency,
                            "disposed_qty": disposed_qty,
                            "acquisition_cost": acquisition_cost,
                            "acquisition_date": lot["date"],
                            "sale_value_eur": eur_value * disposed_qty / abs(amount),
                            "tx_id": str(tx["id"]),
                        })
                        qty_to_sell -= disposed_qty

                    total_acquisition = sum(d["acquisition_cost"] for d in disposals_for_tx)
                    total_sale = eur_value

                    disposals.append({
                        "tx": tx,
                        "disposals": disposals_for_tx,
                        "total_acquisition_cost_eur": total_acquisition,
                        "total_sale_value_eur": total_sale,
                        "gain_loss_eur": total_sale - total_acquisition,
                    })

        elif classification == "withdrawal":
            withdrawals.append(tx)

    result = {
        "disposals": disposals,
        "incomes": incomes,
        "deposits": deposits,
        "withdrawals": withdrawals,
        "inventory": {k: v for k, v in inventory.items() if v},
    }

    with _fifo_cache_lock:
        _fifo_cache = result

    return result


def get_invested_summary():
    conn = get_db()
    rows = conn.execute(
        """SELECT strftime('%Y', time) as year, currency, SUM(CAST(change AS REAL)) as total
           FROM transactions
           WHERE operation IN ('P2P Trading', 'Deposit', 'Buy Crypto With Card', 'Buy Crypto With Fiat')
           GROUP BY year, currency
           ORDER BY year, currency"""
    ).fetchall()
    conn.close()

    yearly = defaultdict(lambda: defaultdict(float))
    total = 0.0
    currencies = set()
    for r in rows:
        yearly[int(r["year"])][r["currency"]] = r["total"]
        total += r["total"]
        currencies.add(r["currency"])

    return {"yearly": dict(yearly), "total": total, "currencies": sorted(currencies)}


def get_portfolio_summary():
    fifo = compute_fifo_from_db()
    inventory = fifo["inventory"]

    settings = get_settings()
    base_currency = settings.get("base_currency", "EUR")
    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")

    prices = _load_price_cache()
    annual = _load_annual_cache()
    today_prices = annual.get(str(now.year), {})

    holdings = []
    total_cost = Decimal("0")
    total_market_value = Decimal("0")

    for currency, lots in sorted(inventory.items()):
        if currency.upper() == "EUR":
            continue
        total_qty = sum(lot["quantity"] for lot in lots)
        total_cost_basis = sum(lot["cost_basis"] for lot in lots)
        avg_cost = total_cost_basis / total_qty if total_qty else Decimal("0")

        market_price = prices.get(currency, {}).get(today_str) or today_prices.get(currency, 0)

        if currency.upper() in STABLECOINS and not market_price:
            market_price = STABLECOIN_RATES.get(currency.upper(), 0.92)

        market_value = Decimal(str(total_qty)) * Decimal(str(market_price)) if market_price else Decimal("0")
        roi = ((market_value - total_cost_basis) / total_cost_basis * 100) if total_cost_basis else Decimal("0")

        total_cost += total_cost_basis
        total_market_value += market_value

        holdings.append({
            "currency": currency,
            "balance": total_qty,
            "cost_eur": total_cost_basis,
            "cost_per_unit": avg_cost,
            "market_value": market_value,
            "market_price": market_price or 0,
            "roi": roi,
        })

    total_unrealized = total_market_value - total_cost
    total_roi = ((total_market_value - total_cost) / total_cost * 100) if total_cost else Decimal("0")

    return {
        "holdings": holdings,
        "total_cost": total_cost,
        "total_market_value": total_market_value,
        "total_unrealized": total_unrealized,
        "total_roi": total_roi,
        "base_currency": base_currency,
    }


def get_tax_summary(year=None):
    fifo = compute_fifo_from_db()

    if year:
        disposals = [d for d in fifo["disposals"] if d["tx"]["time"].year == year]
        incomes = [i for i in fifo["incomes"] if i["time"].year == year]
    else:
        disposals = fifo["disposals"]
        incomes = fifo["incomes"]

    total_gains = Decimal("0")
    total_losses = Decimal("0")
    total_income_value = Decimal("0")

    for d in disposals:
        gl = d["gain_loss_eur"]
        if gl > 0:
            total_gains += gl
        else:
            total_losses += abs(gl)

    for inc in incomes:
        if inc.get("amount_eur"):
            total_income_value += inc["amount_eur"]

    net = total_gains - total_losses

    return {
        "total_gains": total_gains,
        "total_losses": total_losses,
        "net_gain_loss": net,
        "income_value": total_income_value,
        "disposal_count": len(disposals),
        "income_count": len(incomes),
        "deposit_count": len(fifo["deposits"]),
        "withdrawal_count": len(fifo["withdrawals"]),
    }


def get_portfolio_history(days=90):
    fifo = compute_fifo_from_db()
    inventory = fifo["inventory"]

    prices = _load_price_cache()
    annual = _load_annual_cache()

    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)

    currency_quantities = {}
    for currency, lots in inventory.items():
        if currency.upper() == "EUR":
            continue
        currency_quantities[currency] = sum(lot["quantity"] for lot in lots)

    history = []
    current_date = start_date

    while current_date <= end_date:
        date_str = current_date.strftime("%Y-%m-%d")
        year = str(current_date.year)
        year_prices = annual.get(year, {})
        day_value = Decimal("0")

        for currency, qty in currency_quantities.items():
            price = prices.get(currency, {}).get(date_str) or year_prices.get(currency, 0)
            if price:
                day_value += Decimal(str(qty)) * Decimal(str(price))

        history.append({
            "date": date_str,
            "value": float(day_value),
        })
        current_date += timedelta(days=1)

    return history
