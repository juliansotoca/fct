from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from collections import defaultdict
from src.eur_converter import convert_all_to_eur


INCOME_OPERATIONS = {
    "Simple Earn Flexible Interest",
    "Simple Earn Locked Interest",
    "Simple Earn Flexible Airdrop",
    "Cash Voucher Distribution",
    "Referral Kickback",
    "Commission Rebate",
    "Staking",
    "Staking Rewards",
    "BNB Vault Rewards",
    "Simple Earn Locked Rewards",
    "Launchpool",
    "Launchpool Airdrop - System Distribution",
    "Launchpool Airdrop - User Claim Distribution",
    "Airdrop",
    "Airdrop Assets",
    "HODLer Airdrops Distribution",
    "Crypto Box",
    "Binance Pay",
    "Megadrop Rewards",
    "Distribution",
    "Referral Commission",
    "Token Swap - Distribution",
    "Asset Recovery",
    "Strategy Trading Fee Rebate",
}

INTERNAL_TRANSFER_OPERATIONS = {
    "Simple Earn Flexible Subscription",
    "Simple Earn Locked Subscription",
    "Simple Earn Flexible Redemption",
    "Simple Earn Locked Redemption",
    "Transfer Between Main and Funding Wallet",
    "Transfer Between Spot and Strategy Account",
    "Transaction Fee",
    "Small Assets Exchange BNB",
    "Token Swap - Redenomination/Rebranding",
    "Staking Purchase",
    "Staking Redemption",
}

DEPOSIT_OPERATIONS = {"Deposit", "Buy Crypto With Card", "Buy Crypto With Fiat", "P2P Trading", "Fiat OCBS - Add Fiat and Fees"}

WITHDRAWAL_OPERATIONS = {"Withdraw"}

TRADE_OPERATIONS = {
    "Buy",
    "Sell",
    "Trade",
    "Transaction Related",
    "Transaction Buy",
    "Transaction Spend",
    "Transaction Revenue",
    "Transaction Sold",
    "Binance Convert",
}


def classify_transaction(tx):
    op = tx["operation"]
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
    else:
        return "other"


def _classify_and_enrich(transactions):
    for tx in transactions:
        tx["classification"] = classify_transaction(tx)
    return transactions


def compute_fifo(transactions):
    inventory = defaultdict(list)
    disposals = []
    incomes = []
    deposits = []
    withdrawals = []
    internals = []

    for tx in sorted(transactions, key=lambda t: t["time"]):
        classification = tx.get("classification", classify_transaction(tx))
        currency = tx["currency"]
        amount = Decimal(str(tx["change"]))
        eur_value = tx.get("amount_eur") or Decimal("0")

        if classification == "deposit":
            deposits.append(tx)
            if amount > 0 and eur_value and currency.upper() != "EUR":
                inventory[currency].append({
                    "quantity": abs(amount),
                    "cost_basis": eur_value,
                    "price_per_unit": eur_value / abs(amount) if amount else Decimal("0"),
                    "date": tx["time"],
                    "tx_id": tx.get("tx_id", ""),
                })

        elif classification == "income":
            incomes.append(tx)
            if amount > 0 and eur_value:
                inventory[currency].append({
                    "quantity": abs(amount),
                    "cost_basis": eur_value,
                    "price_per_unit": eur_value / abs(amount) if amount else Decimal("0"),
                    "date": tx["time"],
                    "tx_id": tx.get("tx_id", ""),
                    "is_income": True,
                })

        elif classification == "trade":
            if currency.upper() == "EUR":
                continue

            if amount > 0:
                if eur_value and currency.upper() != "EUR":
                    inventory[currency].append({
                        "quantity": abs(amount),
                        "cost_basis": eur_value,
                        "price_per_unit": eur_value / abs(amount) if amount else Decimal("0"),
                        "date": tx["time"],
                        "tx_id": tx.get("tx_id", ""),
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
                            "tx_id": tx.get("tx_id", ""),
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
                else:
                    disposals.append({
                        "tx": tx,
                        "disposals": [],
                        "total_acquisition_cost_eur": Decimal("0"),
                        "total_sale_value_eur": eur_value,
                        "gain_loss_eur": eur_value,
                        "note": "Sin stock previo",
                    })

        elif classification == "withdrawal":
            withdrawals.append(tx)

        elif classification == "internal":
            internals.append(tx)

    return {
        "disposals": disposals,
        "incomes": incomes,
        "deposits": deposits,
        "withdrawals": withdrawals,
        "internals": internals,
        "inventory": {k: v for k, v in inventory.items() if v},
    }


def group_by_year(fifo_result):
    years = defaultdict(lambda: {
        "disposals": [],
        "incomes": [],
        "deposits": [],
        "withdrawals": [],
        "total_gains": Decimal("0"),
        "total_losses": Decimal("0"),
        "net_gain_loss": Decimal("0"),
        "income_value_eur": Decimal("0"),
    })

    for d in fifo_result["disposals"]:
        year = d["tx"]["time"].year
        years[year]["disposals"].append(d)
        gl = d["gain_loss_eur"]
        if gl > 0:
            years[year]["total_gains"] += gl
        else:
            years[year]["total_losses"] += abs(gl)
        years[year]["net_gain_loss"] += gl

    for inc in fifo_result["incomes"]:
        year = inc["time"].year
        years[year]["incomes"].append(inc)
        if inc.get("amount_eur"):
            years[year]["income_value_eur"] += inc["amount_eur"]

    for dep in fifo_result["deposits"]:
        year = dep["time"].year
        years[year]["deposits"].append(dep)

    for w in fifo_result["withdrawals"]:
        year = w["time"].year
        years[year]["withdrawals"].append(w)

    return dict(sorted(years.items()))
