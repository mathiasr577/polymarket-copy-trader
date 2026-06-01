import requests
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

DATA_API = "https://data-api.polymarket.com"
CLOB_HOST = "https://clob.polymarket.com"
HEADERS = {'User-Agent': 'Mozilla/5.0'}

def load_snapshot():
    try:
        with open("snapshot.json") as f:
            return json.load(f)
    except:
        return {}

def get_wallet_positions(wallet_address):
    try:
        r = requests.get(f"{DATA_API}/positions?user={wallet_address}", headers=HEADERS, timeout=10)
        if r.status_code == 200:
            return r.json()
        return []
    except:
        return []

def get_token_price(asset):
    try:
        r = requests.get(f"{CLOB_HOST}/last-trade-price?token_id={asset}", headers=HEADERS, timeout=10)
        if r.status_code == 200:
            return float(r.json().get("price", 0))
        return 0
    except:
        return 0

def process_wallet(wallet, state, order_queue, snapshot):
    address = wallet.get("address")
    category = wallet.get("category", "general")
    known_ids = snapshot.get(address, [])
    positions = get_wallet_positions(address)

    if not positions:
        return

    current_ids = [p["conditionId"] for p in positions if float(p.get("size", 0)) > 0]

    for pos in positions:
        condition_id = pos.get("conditionId")
        asset = pos.get("asset")
        size = float(pos.get("size", 0))
        avg_price = float(pos.get("avgPrice", 0))
        title = pos.get("title", "Unknown")
        outcome = pos.get("outcome", "YES")

        if condition_id in known_ids:
            existing = next((p for p in state["positions"]
                           if p["condition_id"] == condition_id
                           and p["wallet"] == address), None)
            if existing:
                current_price = get_token_price(asset)
                existing["current_price"] = current_price
                existing["pnl"] = (current_price - existing["entry_price"]) * existing["shares"]
            continue

        existing = next((p for p in state["positions"]
                       if p["condition_id"] == condition_id
                       and p["wallet"] == address), None)

        if not existing and size > 0 and avg_price > 0:
            bet_amount = state["balance"] * 0.05
            if bet_amount < 1:
                continue

            order_queue.append({
                "token_id": asset,
                "amount": bet_amount,
                "price": avg_price,
                "side": "BUY",
                "market": title,
                "condition_id": condition_id
            })
            print(f"NUEVA en cola: {title} | {outcome} | ${bet_amount:.2f}")

            new_pos = {
                "wallet": address,
                "wallet_note": wallet.get("note", address[:10]),
                "category": category,
                "condition_id": condition_id,
                "asset": asset,
                "market": title,
                "side": outcome,
                "entry_price": avg_price,
                "current_price": avg_price,
                "bet_amount": bet_amount,
                "shares": bet_amount / avg_price,
                "pnl": 0.0
            }
            state["positions"].append(new_pos)
            state["balance"] -= bet_amount

    for pos in list(state["positions"]):
        if pos["wallet"] == address and pos["condition_id"] not in current_ids:
            current_price = get_token_price(pos["asset"])

            order_queue.append({
                "token_id": pos["asset"],
                "amount": pos["shares"],
                "price": current_price,
                "side": "SELL",
                "market": pos["market"],
                "condition_id": pos["condition_id"]
            })
            print(f"VENTA en cola: {pos['market']} | ${current_price:.3f}")

            pnl = (current_price - pos["entry_price"]) * pos["shares"]
            pos["pnl"] = pnl
            state["balance"] += pos["bet_amount"] + pnl
            state["total_pnl"] += pnl
            state["closed_positions"].append(pos)
            state["positions"].remove(pos)

def update_positions(state, order_queue):
    snapshot = load_snapshot()
    try:
        with open("wallets.json") as f:
            wallets = json.load(f)
    except:
        return

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(process_wallet, w, state, order_queue, snapshot) for w in wallets]
        for f in as_completed(futures):
            try:
                f.result()
            except Exception as e:
                print(f"Error: {e}")
