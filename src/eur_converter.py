from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from collections import defaultdict
import json
import os


_STABLECOIN_EUR_RATES = {
    "USDT": Decimal("0.92"),
    "USDC": Decimal("0.92"),
    "DAI": Decimal("0.92"),
    "BUSD": Decimal("0.92"),
    "EUR": Decimal("1.00"),
    "TRY": Decimal("0.028"),
    "GBP": Decimal("1.17"),
    "ARS": Decimal("0.0008"),
    "RUB": Decimal("0.01"),
    "UAH": Decimal("0.023"),
    "NGN": Decimal("0.0006"),
    "BRL": Decimal("0.18"),
    "AUD": Decimal("0.62"),
    "CAD": Decimal("0.68"),
    "JPY": Decimal("0.0062"),
    "KRW": Decimal("0.0007"),
    "INR": Decimal("0.011"),
    "MXN": Decimal("0.053"),
    "RON": Decimal("0.21"),
    "PLN": Decimal("0.23"),
    "FDUSD": Decimal("0.92"),
    "TUSD": Decimal("0.92"),
    "USD": Decimal("0.92"),
    "EUR": Decimal("1.00"),
}


_ANNUAL_AVG_PRICES = {
    "BTC": {
        2021: Decimal("36500"), 2022: Decimal("28000"), 2023: Decimal("35000"),
        2024: Decimal("60000"), 2025: Decimal("85000"),
    },
    "ETH": {
        2021: Decimal("2200"), 2022: Decimal("1800"), 2023: Decimal("2200"),
        2024: Decimal("3200"), 2025: Decimal("3500"),
    },
    "BNB": {
        2021: Decimal("350"), 2022: Decimal("320"), 2023: Decimal("310"),
        2024: Decimal("400"), 2025: Decimal("650"),
    },
    "SOL": {
        2021: Decimal("80"), 2022: Decimal("50"), 2023: Decimal("60"),
        2024: Decimal("120"), 2025: Decimal("180"),
    },
    "XRP": {
        2021: Decimal("0.65"), 2022: Decimal("0.40"), 2023: Decimal("0.50"),
        2024: Decimal("0.55"), 2025: Decimal("1.50"),
    },
    "ADA": {
        2021: Decimal("1.20"), 2022: Decimal("0.50"), 2023: Decimal("0.35"),
        2024: Decimal("0.55"), 2025: Decimal("0.80"),
    },
    "DOGE": {
        2021: Decimal("0.20"), 2022: Decimal("0.09"), 2023: Decimal("0.07"),
        2024: Decimal("0.12"), 2025: Decimal("0.25"),
    },
    "DOT": {
        2021: Decimal("18"), 2022: Decimal("8.50"), 2023: Decimal("5.50"),
        2024: Decimal("7.50"), 2025: Decimal("5.00"),
    },
    "MATIC": {
        2021: Decimal("0.60"), 2022: Decimal("0.75"), 2023: Decimal("0.85"),
        2024: Decimal("0.70"), 2025: Decimal("0.30"),
    },
    "AVAX": {
        2021: Decimal("40"), 2022: Decimal("20"), 2023: Decimal("15"),
        2024: Decimal("35"), 2025: Decimal("25"),
    },
    "SHIB": {
        2021: Decimal("0.00002"), 2022: Decimal("0.000008"), 2023: Decimal("0.000008"),
        2024: Decimal("0.000015"), 2025: Decimal("0.000012"),
    },
    "LINK": {
        2021: Decimal("18"), 2022: Decimal("7.50"), 2023: Decimal("7.00"),
        2024: Decimal("14"), 2025: Decimal("18"),
    },
    "LTC": {
        2021: Decimal("150"), 2022: Decimal("65"), 2023: Decimal("75"),
        2024: Decimal("80"), 2025: Decimal("100"),
    },
    "UNI": {
        2021: Decimal("20"), 2022: Decimal("6"), 2023: Decimal("5.50"),
        2024: Decimal("9"), 2025: Decimal("10"),
    },
    "ATOM": {
        2021: Decimal("20"), 2022: Decimal("15"), 2023: Decimal("9"),
        2024: Decimal("8.50"), 2025: Decimal("5.50"),
    },
    "FIL": {
        2021: Decimal("80"), 2022: Decimal("7"), 2023: Decimal("4"),
        2024: Decimal("5"), 2025: Decimal("4"),
    },
    "ETC": {
        2021: Decimal("45"), 2022: Decimal("22"), 2023: Decimal("18"),
        2024: Decimal("25"), 2025: Decimal("20"),
    },
    "TRX": {
        2021: Decimal("0.06"), 2022: Decimal("0.05"), 2023: Decimal("0.07"),
        2024: Decimal("0.11"), 2025: Decimal("0.22"),
    },
    "ALGO": {
        2021: Decimal("1.20"), 2022: Decimal("0.40"), 2023: Decimal("0.12"),
        2024: Decimal("0.12"), 2025: Decimal("0.25"),
    },
    "XLM": {
        2021: Decimal("0.25"), 2022: Decimal("0.10"), 2023: Decimal("0.10"),
        2024: Decimal("0.11"), 2025: Decimal("0.25"),
    },
    "AAVE": {
        2021: Decimal("250"), 2022: Decimal("85"), 2023: Decimal("70"),
        2024: Decimal("95"), 2025: Decimal("180"),
    },
    "NEAR": {
        2021: Decimal("10"), 2022: Decimal("4"), 2023: Decimal("1.50"),
        2024: Decimal("5.50"), 2025: Decimal("4"),
    },
    "APT": {
        2022: Decimal("5"), 2023: Decimal("4.50"), 2024: Decimal("7"),
        2025: Decimal("7"),
    },
    "ARB": {
        2023: Decimal("1"), 2024: Decimal("1.10"), 2025: Decimal("0.55"),
    },
    "OP": {
        2022: Decimal("1.50"), 2023: Decimal("1"), 2024: Decimal("2.50"),
        2025: Decimal("1.10"),
    },
    "SUI": {
        2023: Decimal("0.50"), 2024: Decimal("0.80"), 2025: Decimal("2.50"),
    },
    "PEPE": {
        2023: Decimal("0.000001"), 2024: Decimal("0.000007"), 2025: Decimal("0.00001"),
    },
    "TON": {
        2024: Decimal("5"), 2025: Decimal("4.50"),
    },
    "WLD": {
        2023: Decimal("2.50"), 2024: Decimal("3"), 2025: Decimal("1.50"),
    },
    "TIA": {
        2023: Decimal("8"), 2024: Decimal("8"), 2025: Decimal("4"),
    },
    "INJ": {
        2023: Decimal("8"), 2024: Decimal("25"), 2025: Decimal("15"),
    },
    "SEI": {
        2023: Decimal("0.30"), 2024: Decimal("0.40"), 2025: Decimal("0.25"),
    },
    "FET": {
        2021: Decimal("0.40"), 2022: Decimal("0.20"), 2023: Decimal("0.25"),
        2024: Decimal("1.50"), 2025: Decimal("1.20"),
    },
    "RENDER": {
        2023: Decimal("1.50"), 2024: Decimal("7"), 2025: Decimal("5"),
    },
    "IMX": {
        2021: Decimal("2"), 2022: Decimal("0.60"), 2023: Decimal("0.60"),
        2024: Decimal("1.50"), 2025: Decimal("1"),
    },
    "GRT": {
        2021: Decimal("0.50"), 2022: Decimal("0.12"), 2023: Decimal("0.12"),
        2024: Decimal("0.20"), 2025: Decimal("0.15"),
    },
    "RUNE": {
        2021: Decimal("5"), 2022: Decimal("2.50"), 2023: Decimal("1.50"),
        2024: Decimal("5"), 2025: Decimal("3.50"),
    },
    "FTM": {
        2021: Decimal("0.80"), 2022: Decimal("0.25"), 2023: Decimal("0.25"),
        2024: Decimal("0.55"), 2025: Decimal("0.70"),
    },
    "SAND": {
        2021: Decimal("0.40"), 2022: Decimal("0.50"), 2023: Decimal("0.35"),
        2024: Decimal("0.35"), 2025: Decimal("0.30"),
    },
    "MANA": {
        2021: Decimal("1"), 2022: Decimal("0.55"), 2023: Decimal("0.35"),
        2024: Decimal("0.40"), 2025: Decimal("0.35"),
    },
    "AXS": {
        2021: Decimal("60"), 2022: Decimal("9"), 2023: Decimal("5"),
        2024: Decimal("5.50"), 2025: Decimal("4"),
    },
    "ENJ": {
        2021: Decimal("2"), 2022: Decimal("0.40"), 2023: Decimal("0.25"),
        2024: Decimal("0.25"), 2025: Decimal("0.15"),
    },
    "CHZ": {
        2021: Decimal("0.25"), 2022: Decimal("0.12"), 2023: Decimal("0.08"),
        2024: Decimal("0.10"), 2025: Decimal("0.06"),
    },
    "THETA": {
        2021: Decimal("4"), 2022: Decimal("1"), 2023: Decimal("0.80"),
        2024: Decimal("1.20"), 2025: Decimal("1.50"),
    },
    "VET": {
        2021: Decimal("0.12"), 2022: Decimal("0.02"), 2023: Decimal("0.02"),
        2024: Decimal("0.03"), 2025: Decimal("0.03"),
    },
    "HBAR": {
        2021: Decimal("0.20"), 2022: Decimal("0.05"), 2023: Decimal("0.05"),
        2024: Decimal("0.07"), 2025: Decimal("0.18"),
    },
    "EGLD": {
        2021: Decimal("200"), 2022: Decimal("45"), 2023: Decimal("35"),
        2024: Decimal("40"), 2025: Decimal("30"),
    },
    "XTZ": {
        2021: Decimal("2.50"), 2022: Decimal("1"), 2023: Decimal("0.80"),
        2024: Decimal("0.85"), 2025: Decimal("0.80"),
    },
    "EOS": {
        2021: Decimal("1.20"), 2022: Decimal("1"), 2023: Decimal("0.75"),
        2024: Decimal("0.70"), 2025: Decimal("0.70"),
    },
    "ICP": {
        2021: Decimal("100"), 2022: Decimal("5"), 2023: Decimal("4"),
        2024: Decimal("10"), 2025: Decimal("5"),
    },
    "FLOW": {
        2021: Decimal("15"), 2022: Decimal("1.50"), 2023: Decimal("0.65"),
        2024: Decimal("0.70"), 2025: Decimal("0.55"),
    },
    "KLAY": {
        2021: Decimal("1"), 2022: Decimal("0.25"), 2023: Decimal("0.15"),
        2024: Decimal("0.15"), 2025: Decimal("0.15"),
    },
    "MINA": {
        2021: Decimal("3"), 2022: Decimal("0.50"), 2023: Decimal("0.40"),
        2024: Decimal("0.55"), 2025: Decimal("0.40"),
    },
    "SNX": {
        2021: Decimal("8"), 2022: Decimal("2.50"), 2023: Decimal("2.50"),
        2024: Decimal("2.50"), 2025: Decimal("1.50"),
    },
    "CRV": {
        2021: Decimal("2"), 2022: Decimal("0.70"), 2023: Decimal("0.50"),
        2024: Decimal("0.35"), 2025: Decimal("0.60"),
    },
    "YFI": {
        2021: Decimal("20000"), 2022: Decimal("6000"), 2023: Decimal("5500"),
        2024: Decimal("6000"), 2025: Decimal("5000"),
    },
    "GMX": {
        2022: Decimal("50"), 2023: Decimal("40"), 2024: Decimal("35"),
        2025: Decimal("25"),
    },
    "PENDLE": {
        2023: Decimal("0.30"), 2024: Decimal("3"), 2025: Decimal("4"),
    },
    "DYDX": {
        2021: Decimal("5"), 2022: Decimal("2"), 2023: Decimal("1.50"),
        2024: Decimal("2"), 2025: Decimal("1"),
    },
    "STRK": {
        2024: Decimal("1.50"), 2025: Decimal("0.40"),
    },
    "PYTH": {
        2023: Decimal("0.30"), 2024: Decimal("0.35"), 2025: Decimal("0.20"),
    },
    "JUP": {
        2024: Decimal("0.80"), 2025: Decimal("0.70"),
    },
    "ENA": {
        2024: Decimal("0.50"), 2025: Decimal("0.40"),
    },
    "ETHFI": {
        2024: Decimal("3"), 2025: Decimal("1.50"),
    },
    "WIF": {
        2024: Decimal("2"), 2025: Decimal("1"),
    },
    "BONK": {
        2023: Decimal("0.000001"), 2024: Decimal("0.000015"), 2025: Decimal("0.00002"),
    },
    "FLOKI": {
        2021: Decimal("0.00003"), 2022: Decimal("0.00001"), 2023: Decimal("0.00002"),
        2024: Decimal("0.0001"), 2025: Decimal("0.00012"),
    },
    "ORDI": {
        2023: Decimal("15"), 2024: Decimal("35"), 2025: Decimal("12"),
    },
    "CAKE": {
        2021: Decimal("10"), 2022: Decimal("3"), 2023: Decimal("2"),
        2024: Decimal("2.50"), 2025: Decimal("2"),
    },
    "HIGH": {
        2021: Decimal("4"), 2022: Decimal("2"), 2023: Decimal("1.50"),
        2024: Decimal("1.50"), 2025: Decimal("1"),
    },
    "MC": {
        2021: Decimal("0.15"), 2022: Decimal("0.05"), 2023: Decimal("0.05"),
        2024: Decimal("0.10"), 2025: Decimal("0.08"),
    },
    "SANTOS": {
        2021: Decimal("5"), 2022: Decimal("3"), 2023: Decimal("3"),
        2024: Decimal("3.50"), 2025: Decimal("3"),
    },
    "ANC": {
        2022: Decimal("0.10"),
    },
    "LUNA": {
        2021: Decimal("50"), 2022: Decimal("0.0001"),
    },
    "LUNC": {
        2022: Decimal("0.0001"), 2023: Decimal("0.0001"), 2024: Decimal("0.0001"),
        2025: Decimal("0.00008"),
    },
    "GAL": {
        2022: Decimal("5"), 2023: Decimal("2"), 2024: Decimal("1.50"),
        2025: Decimal("1.50"),
    },
    "HFT": {
        2022: Decimal("0.30"), 2023: Decimal("0.20"), 2024: Decimal("0.15"),
        2025: Decimal("0.12"),
    },
    "RDNT": {
        2023: Decimal("0.20"), 2024: Decimal("0.10"), 2025: Decimal("0.05"),
    },
    "MAV": {
        2023: Decimal("0.20"), 2024: Decimal("0.15"), 2025: Decimal("0.10"),
    },
    "CYBER": {
        2023: Decimal("10"), 2024: Decimal("5"), 2025: Decimal("4"),
    },
    "NTRN": {
        2023: Decimal("0.50"), 2024: Decimal("0.50"), 2025: Decimal("0.30"),
    },
    "MEME": {
        2023: Decimal("0.005"), 2024: Decimal("0.01"), 2025: Decimal("0.008"),
    },
    "ACE": {
        2023: Decimal("2"), 2024: Decimal("3"), 2025: Decimal("1.50"),
    },
    "NFP": {
        2023: Decimal("0.30"), 2024: Decimal("0.25"), 2025: Decimal("0.20"),
    },
    "AI": {
        2024: Decimal("1"), 2025: Decimal("0.80"),
    },
    "XAI": {
        2024: Decimal("0.50"), 2025: Decimal("0.30"),
    },
    "MANTA": {
        2024: Decimal("2"), 2025: Decimal("0.60"),
    },
    "ALT": {
        2024: Decimal("0.15"), 2025: Decimal("0.10"),
    },
    "PIXEL": {
        2024: Decimal("0.30"), 2025: Decimal("0.08"),
    },
    "PORTAL": {
        2024: Decimal("1"), 2025: Decimal("0.30"),
    },
    "AEVO": {
        2024: Decimal("1"), 2025: Decimal("0.30"),
    },
    "REZ": {
        2024: Decimal("0.30"), 2025: Decimal("0.10"),
    },
    "BB": {
        2024: Decimal("0.05"), 2025: Decimal("0.04"),
    },
    "NOT": {
        2024: Decimal("0.005"), 2025: Decimal("0.003"),
    },
    "IO": {
        2024: Decimal("2"), 2025: Decimal("1.50"),
    },
    "LISTA": {
        2024: Decimal("0.40"), 2025: Decimal("0.35"),
    },
    "BANANA": {
        2024: Decimal("0.30"), 2025: Decimal("0.20"),
    },
    "DOGS": {
        2024: Decimal("0.0005"), 2025: Decimal("0.0003"),
    },
    "CATI": {
        2024: Decimal("0.30"), 2025: Decimal("0.15"),
    },
    "HMSTR": {
        2024: Decimal("0.003"), 2025: Decimal("0.002"),
    },
    "SCR": {
        2024: Decimal("0.50"), 2025: Decimal("0.40"),
    },
    "USUAL": {
        2024: Decimal("0.50"), 2025: Decimal("0.40"),
    },
    "THE": {
        2024: Decimal("0.05"), 2025: Decimal("0.03"),
    },
    "MOVE": {
        2024: Decimal("0.50"), 2025: Decimal("0.40"),
    },
    "VANA": {
        2024: Decimal("5"), 2025: Decimal("4"),
    },
    "1000CAT": {
        2024: Decimal("0.05"), 2025: Decimal("0.04"),
    },
    "PENGU": {
        2024: Decimal("0.02"), 2025: Decimal("0.015"),
    },
    "BIO": {
        2025: Decimal("0.20"),
    },
    "ACT": {
        2025: Decimal("0.15"),
    },
    "ANIME": {
        2025: Decimal("0.03"),
    },
    "BERA": {
        2025: Decimal("3"),
    },
    "LAYER": {
        2025: Decimal("0.50"),
    },
    "KAITO": {
        2025: Decimal("1"),
    },
    "SHELL": {
        2025: Decimal("0.15"),
    },
    "RED": {
        2025: Decimal("0.10"),
    },
    "GPS": {
        2025: Decimal("0.05"),
    },
    "BMT": {
        2025: Decimal("0.10"),
    },
    "NIL": {
        2025: Decimal("0.30"),
    },
    "PARTI": {
        2025: Decimal("0.10"),
    },
    "GUN": {
        2025: Decimal("0.05"),
    },
    "BABY": {
        2025: Decimal("0.003"),
    },
    "WCT": {
        2025: Decimal("0.30"),
    },
    "HYPER": {
        2025: Decimal("10"),
    },
    "INIT": {
        2025: Decimal("0.20"),
    },
    "SIGN": {
        2025: Decimal("0.15"),
    },
    "STO": {
        2025: Decimal("0.10"),
    },
    "SXT": {
        2025: Decimal("0.05"),
    },
    "NXPC": {
        2025: Decimal("0.20"),
    },
    "HAEDAL": {
        2025: Decimal("0.15"),
    },
    "HUMA": {
        2025: Decimal("0.10"),
    },
    "SOPH": {
        2025: Decimal("0.05"),
    },
    "RESOLV": {
        2025: Decimal("0.50"),
    },
    "HOME": {
        2025: Decimal("0.20"),
    },
    "SPK": {
        2025: Decimal("0.10"),
    },
    "NEWT": {
        2025: Decimal("0.15"),
    },
    "SAHARA": {
        2025: Decimal("0.05"),
    },
    "W": {
        2025: Decimal("0.10"),
    },
    "LA": {
        2025: Decimal("0.20"),
    },
    "ERA": {
        2025: Decimal("0.30"),
    },
}


_LOCAL_CACHE_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "price_cache.json")


def _is_stablecoin(currency):
    return currency.upper() in _STABLECOIN_EUR_RATES


def _get_stablecoin_rate(currency):
    return _STABLECOIN_EUR_RATES.get(currency.upper())


def _get_annual_price(currency, year):
    prices = _ANNUAL_AVG_PRICES.get(currency.upper())
    if not prices:
        return None
    return prices.get(year)


def _load_local_cache():
    if os.path.exists(_LOCAL_CACHE_FILE):
        try:
            with open(_LOCAL_CACHE_FILE, "r") as f:
                data = json.load(f)
            cache = {}
            for key, val in data.items():
                currency, date_str = key.split("|")
                cache[(currency, date_str)] = Decimal(str(val))
            return cache
        except Exception:
            pass
    return {}


def _save_local_cache(cache):
    os.makedirs(os.path.dirname(_LOCAL_CACHE_FILE), exist_ok=True)
    data = {f"{k[0]}|{k[1]}": str(v) for k, v in cache.items()}
    try:
        with open(_LOCAL_CACHE_FILE, "w") as f:
            json.dump(data, f)
    except Exception:
        pass


def convert_all_to_eur(transactions, verbose=False):
    if not transactions:
        return []

    local_cache = _load_local_cache()
    price_cache = {}

    for tx in transactions:
        currency = tx["currency"]
        date = tx["time"]
        date_str = date.strftime("%Y-%m-%d")
        year = date.year
        key = (currency, date_str)

        if key in price_cache:
            continue

        if _is_stablecoin(currency):
            rate = _get_stablecoin_rate(currency)
            price_cache[key] = rate
        elif key in local_cache:
            price_cache[key] = local_cache[key]
        else:
            annual_price = _get_annual_price(currency, year)
            if annual_price:
                price_cache[key] = annual_price
            else:
                if verbose and currency not in [k[0] for k in price_cache.keys() if k[0] == currency]:
                    print(f"  WARNING: Sin precio EUR para {currency} (usando 0)")
                price_cache[key] = Decimal("0")

    _save_local_cache(price_cache)

    converted = []
    missing_currencies = set()

    for tx in transactions:
        currency = tx["currency"]
        amount = Decimal(str(tx["change"]))
        date = tx["time"]
        date_str = date.strftime("%Y-%m-%d")

        price = price_cache.get((currency, date_str), Decimal("0"))

        if price == 0 and currency.upper() not in missing_currencies:
            missing_currencies.add(currency.upper())
            if verbose:
                print(f"  WARNING: Sin precio para {currency} el {date_str}")

        if price > 0:
            eur_value = (abs(amount) * price).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
            converted.append({
                **tx,
                "eur_price": price,
                "amount_eur": eur_value,
                "signed_amount_eur": eur_value if amount > 0 else -eur_value,
            })
        else:
            converted.append({
                **tx,
                "eur_price": None,
                "amount_eur": None,
                "signed_amount_eur": None,
            })

    return converted
