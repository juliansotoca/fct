import csv
import os
import time
from datetime import datetime
from src.config import BINANCE_API_KEY, BINANCE_API_SECRET
from binance.client import Client


def get_client():
    if not BINANCE_API_KEY or not BINANCE_API_SECRET:
        raise ValueError("API keys no configuradas. Revisa el archivo .env")
    return Client(BINANCE_API_KEY, BINANCE_API_SECRET)


def load_csv_transactions(csv_path):
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"No se encuentra el CSV: {csv_path}")

    transactions = []
    with open(csv_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            tx = parse_csv_row(row)
            if tx:
                transactions.append(tx)

    transactions.sort(key=lambda t: t["time"])
    return transactions


def parse_csv_row(row):
    time_str = row.get("Tiempo", "").strip()
    if not time_str:
        return None

    try:
        time = datetime.strptime(time_str, "%y-%m-%d %H:%M:%S")
    except ValueError:
        try:
            time = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return None

    currency = row.get("Moneda", "").strip()
    change_str = row.get("Cambio", "").strip().replace(",", ".")
    operation = row.get("Operación", "").strip()
    account = row.get("Cuenta", "").strip()
    observation = row.get("Observación", "").strip()
    tx_id = row.get("ID de usuario", "").strip()

    try:
        change = float(change_str)
    except ValueError:
        return None

    return {
        "tx_id": tx_id,
        "time": time,
        "account": account,
        "operation": operation,
        "currency": currency,
        "change": change,
        "observation": observation,
    }


def fetch_all_transactions_from_api(client, verbose=False):
    transactions = []

    if verbose:
        print("  Obteniendo historial de depósitos...")
    deposit_history = client.get_deposit_history()
    for d in deposit_history:
        transactions.append({
            "time": datetime.fromtimestamp(d["insertTime"] / 1000),
            "operation": "Deposit",
            "currency": d["coin"],
            "change": float(d["amount"]),
            "tx_id": str(d["txId"]),
            "observation": f"Deposit - Status: {d['status']}",
        })

    if verbose:
        print("  Obteniendo historial de retiradas...")
    withdraw_history = client.get_withdraw_history()
    for w in withdraw_history:
        transactions.append({
            "time": datetime.fromtimestamp(int(w["applyTime"]) / 1000),
            "operation": "Withdraw",
            "currency": w["coin"],
            "change": -float(w["amount"]),
            "tx_id": w["txId"],
            "observation": f"Withdraw - Status: {w['status']}",
        })

    if verbose:
        print("  Obteniendo dividendos (staking/earn/airdrops)...")
    try:
        dividend_history = client.get_asset_dividend_history()
        for div in dividend_history.get("rows", []):
            transactions.append({
                "time": datetime.fromtimestamp(div["divTime"] / 1000),
                "operation": _map_dividend_type(div.get("source", "")),
                "currency": div["coin"],
                "change": float(div["amount"]),
                "tx_id": str(div.get("id", "")),
                "observation": f"{div.get('source', 'Dividend')} - {div.get('enInfo', '')}",
            })
    except Exception as e:
        if verbose:
            print(f"  WARNING: No se pudieron obtener dividendos: {e}")

    if verbose:
        print("  Obteniendo historial de trades...")
    trade_count = 0
    try:
        account_info = client.get_account()
        balances = account_info.get("balances", [])
        assets = set()
        for b in balances:
            if float(b["free"]) > 0 or float(b["locked"]) > 0:
                assets.add(b["asset"])

        base_currencies = ["BTC", "ETH", "BNB", "USDT", "EUR", "BUSD", "USDC", "FDUSD", "TRY"]
        relevant_symbols = set()
        for asset in assets:
            for base in base_currencies:
                if asset != base:
                    relevant_symbols.add(f"{asset}{base}")
                    relevant_symbols.add(f"{base}{asset}")

        for i, symbol in enumerate(sorted(relevant_symbols)):
            try:
                trades = client.get_my_trades(symbol=symbol, limit=1000)
                for t in trades:
                    transactions.append({
                        "time": datetime.fromtimestamp(t["time"] / 1000),
                        "operation": "Trade",
                        "currency": t["symbol"],
                        "change": float(t["qty"]) if t["isBuyer"] else -float(t["qty"]),
                        "tx_id": str(t["id"]),
                        "observation": f"Trade - Price: {t['price']} - Commission: {t['commission']} {t['commissionAsset']}",
                    })
                    trade_count += 1
                time.sleep(0.05)
            except Exception:
                continue

            if verbose and (i + 1) % 20 == 0:
                print(f"    Procesados {i + 1}/{len(relevant_symbols)} pares ({trade_count} trades)...")

    except Exception as e:
        if verbose:
            print(f"  WARNING: Error obteniendo trades: {e}")

    if verbose:
        print(f"  Trades obtenidos: {trade_count}")

    transactions.sort(key=lambda t: t["time"])
    return transactions


def _map_dividend_type(source):
    mapping = {
        "STAKING": "Staking",
        "EARN": "Simple Earn Flexible Interest",
        "AIR_DROP": "Airdrop",
        "ACTIVITY": "Launchpool",
        "COMMISSION_REBATE": "Commission Rebate",
    }
    return mapping.get(source, source)
