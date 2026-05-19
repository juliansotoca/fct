"""
Import historical prices from Binance and CoinGecko APIs.
Strategy:
1. Binance API (free) for daily klines - covers ~2023+
2. CoinGecko in 365-day chunks for older data
3. Falls back to annual averages for any remaining gaps
"""

import sys
import os
import time
import requests
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from web.database import get_db, save_price, get_price
from web.engine import HISTORICAL_ANNUAL_PRICES

BINANCE_SYMBOLS = {
    "BTC": ["BTCEUR", "BTCUSDT"],
    "ETH": ["ETHEUR", "ETHUSDT"],
    "BNB": ["BNBEUR", "BNBUSDT"],
    "SOL": ["SOLEUR", "SOLUSDT"],
    "ADA": ["ADAEUR", "ADAUSDT"],
    "DOT": ["DOTEUR", "DOTUSDT"],
    "DOGE": ["DOGEUSDT"],
    "AVAX": ["AVAXEUR", "AVAXUSDT"],
    "MATIC": ["MATICEUR", "MATICUSDT"],
    "LINK": ["LINKEUR", "LINKUSDT"],
    "LTC": ["LTCEUR", "LTCUSDT"],
    "XRP": ["XRPEUR", "XRPUSDT"],
    "UNI": ["UNIUSDT"],
    "ATOM": ["ATOMUSDT"],
    "SHIB": ["SHIBUSDT"],
    "TRX": ["TRXUSDT"],
    "NEAR": ["NEAREUR", "NEARUSDT"],
    "FTM": ["FTMUSDT"],
    "ALGO": ["ALGOUSDT"],
    "MANA": ["MANAUSDT"],
    "SAND": ["SANDUSDT"],
    "AXS": ["AXSUSDT"],
    "ENJ": ["ENJUSDT"],
    "GALA": ["GALAUSDT"],
    "CHZ": ["CHZUSDT"],
    "THETA": ["THETAUSDT"],
    "VET": ["VETUSDT"],
    "ICP": ["ICPUSDT"],
    "FIL": ["FILUSDT"],
    "ETC": ["ETCEUR", "ETCUSDT"],
    "XLM": ["XLMUSDT"],
    "AAVE": ["AAVEUSDT"],
    "MKR": ["MKRUSDT"],
    "COMP": ["COMPUSDT"],
    "SNX": ["SNXUSDT"],
    "CRV": ["CRVUSDT"],
    "SUSHI": ["SUSHIUSDT"],
    "YFI": ["YFIUSDT"],
    "1INCH": ["1INCHUSDT"],
    "BAT": ["BATUSDT"],
    "ZRX": ["ZRXUSDT"],
    "KNC": ["KNCUSDT"],
    "REN": ["RENUSDT"],
    "LRC": ["LRCUSDT"],
    "STORJ": ["STORJUSDT"],
    "GRT": ["GRTUSDT"],
    "ANKR": ["ANKRUSDT"],
    "BAND": ["BANDUSDT"],
    "NMR": ["NMRUSDT"],
    "OCEAN": ["OCEANUSDT"],
    "FET": ["FETUSDT"],
    "RNDR": ["RNDRUSDT"],
    "INJ": ["INJUSDT"],
    "ARB": ["ARBUSDT"],
    "OP": ["OPUSDT"],
    "APT": ["APTUSDT"],
    "SUI": ["SUIUSDT"],
    "SEI": ["SEIUSDT"],
    "TIA": ["TIAUSDT"],
    "TON": ["TONUSDT"],
    "HBAR": ["HBARUSDT"],
    "PEPE": ["PEPEUSDT"],
    "WIF": ["WIFUSDT"],
    "BONK": ["BONKUSDT"],
    "NOT": ["NOTUSDT"],
    "MEME": ["MEMEUSDT"],
    "LUNA": ["LUNAUSDT"],
    "BCH": ["BCHEUR", "BCHUSDT"],
}

COINGECKO_MAP = {
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
    "OCEAN": "ocean-protocol", "FET": "fetch-ai", "RNDR": "render-token",
    "INJ": "injective-protocol", "ARB": "arbitrum", "OP": "optimism",
    "APT": "aptos", "SUI": "sui", "SEI": "sei-network",
    "TIA": "celestia", "TON": "the-open-network", "HBAR": "hedera-hashgraph",
    "PEPE": "pepe", "WIF": "dogwifcoin", "BONK": "bonk",
    "NOT": "notcoin", "MEME": "meme", "LUNA": "terra-luna-2",
}

USDT_EUR = 0.92


def fetch_binance(currency, start_date, end_date):
    """Fetch from Binance. Returns count saved."""
    symbols = BINANCE_SYMBOLS.get(currency, [])
    if not symbols:
        return 0

    saved = 0
    for symbol in symbols:
        is_usdt = symbol.endswith("USDT")
        current_start = int(datetime.strptime(start_date, "%Y-%m-%d").timestamp() * 1000)
        end_ts = int(datetime.strptime(end_date, "%Y-%m-%d").timestamp() * 1000)

        while current_start < end_ts:
            try:
                resp = requests.get("https://api.binance.com/api/v3/klines",
                    params={"symbol": symbol, "interval": "1d",
                            "startTime": current_start, "endTime": end_ts, "limit": 1000},
                    timeout=30)

                if resp.status_code == 200:
                    candles = resp.json()
                    if not candles:
                        break
                    for c in candles:
                        date_str = datetime.fromtimestamp(c[0] / 1000).strftime("%Y-%m-%d")
                        price = float(c[4])
                        if is_usdt:
                            price *= USDT_EUR
                        save_price(currency, date_str, price)
                        saved += 1
                    current_start = candles[-1][0] + 86400000
                    time.sleep(0.3)
                elif resp.status_code == 429:
                    time.sleep(60)
                else:
                    break
            except:
                break

        if saved > 0:
            break
    return saved


def fetch_coingecko(currency, start_date, end_date):
    """Fetch from CoinGecko in 365-day chunks."""
    coin_id = COINGECKO_MAP.get(currency)
    if not coin_id:
        return 0

    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    saved = 0
    current = start

    while current < end:
        chunk_end = min(current + timedelta(days=364), end)
        days = (chunk_end - current).days + 1

        try:
            resp = requests.get(
                f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart",
                params={"vs_currency": "eur", "days": str(days)},
                timeout=30)

            if resp.status_code == 200:
                data = resp.json()
                for ts, price in data.get("prices", []):
                    date_str = datetime.fromtimestamp(ts / 1000).strftime("%Y-%m-%d")
                    if start_date <= date_str <= end_date:
                        save_price(currency, date_str, price)
                        saved += 1
                time.sleep(1.5)
            elif resp.status_code == 429:
                time.sleep(60)
            else:
                break
        except:
            break

        current = chunk_end + timedelta(days=1)
    return saved


def fill_gaps_with_annual(currency, start_date, end_date):
    """Fill missing dates with annual average prices."""
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    current = start
    filled = 0

    while current <= end:
        date_str = current.strftime("%Y-%m-%d")
        if not get_price(currency, date_str):
            year = current.year
            prices = HISTORICAL_ANNUAL_PRICES.get(currency, {})
            if year in prices:
                save_price(currency, date_str, prices[year])
                filled += 1
        current += timedelta(days=1)
    return filled


def main():
    conn = get_db()
    rows = conn.execute("""
        SELECT currency, MIN(time) as first_tx, MAX(time) as last_tx, COUNT(*) as tx_count
        FROM transactions
        WHERE currency NOT IN ('EUR', 'USDT', 'USDC', 'BUSD', 'DAI', 'TUSD', 'USDP', 'USD')
        GROUP BY currency
        ORDER BY tx_count DESC
    """).fetchall()
    conn.close()

    # Save USDT price
    print("Saving USDT/EUR rate...")
    start = datetime(2021, 1, 1)
    end = datetime.now()
    current = start
    while current <= end:
        save_price("USDT", current.strftime("%Y-%m-%d"), USDT_EUR)
        current += timedelta(days=1)
    print(f"  USDT: {(end-start).days} days saved")

    print(f"\nFetching prices for {len(rows)} currencies...\n")

    total_saved = 0
    total_skipped = 0
    total_failed = 0

    for i, row in enumerate(rows):
        currency = row["currency"]
        first = row["first_tx"][:10]
        last = row["last_tx"][:10]
        tx_count = row["tx_count"]

        # Check coverage
        first_price = get_price(currency, first)
        last_price = get_price(currency, last)
        if first_price and last_price:
            # Check how many days we have
            conn = get_db()
            count = conn.execute(
                "SELECT COUNT(*) as cnt FROM prices WHERE currency=? AND date>=? AND date<=?",
                (currency, first, last)).fetchone()["cnt"]
            conn.close()
            total_days = (datetime.strptime(last, "%Y-%m-%d") - datetime.strptime(first, "%Y-%m-%d")).days + 1
            if count >= total_days * 0.9:
                print(f"[{i+1}/{len(rows)}] SKIP {currency} ({count}/{total_days} days)")
                total_skipped += 1
                continue

        print(f"[{i+1}/{len(rows)}] {currency} ({tx_count} txs): {first} to {last}")

        # 1. Try Binance
        saved = fetch_binance(currency, first, last)
        if saved:
            print(f"  Binance: +{saved} prices")

        # 2. Try CoinGecko for gaps
        cg_saved = fetch_coingecko(currency, first, last)
        if cg_saved:
            print(f"  CoinGecko: +{cg_saved} prices")
        saved += cg_saved

        # 3. Fill remaining gaps with annual averages
        gap_filled = fill_gaps_with_annual(currency, first, last)
        if gap_filled:
            print(f"  Annual fallback: +{gap_filled} days")
        saved += gap_filled

        if saved > 0:
            total_saved += saved
        else:
            print(f"  FAILED")
            total_failed += 1

        time.sleep(0.5)

    print(f"\n{'='*50}")
    print(f"Total saved: {total_saved}")
    print(f"Skipped (covered): {total_skipped}")
    print(f"Failed: {total_failed}")


if __name__ == "__main__":
    main()
