import requests
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from web3 import Web3

DATA_API = "https://data-api.polymarket.com"
CLOB_HOST = "https://clob.polymarket.com"
HEADERS = {'User-Agent': 'Mozilla/5.0'}

def get_clob_client():
    from py_clob_client.client import ClobClient
    from py_clob_client.constants import POLYGON

    client = ClobClient(
        host=CLOB_HOST,
        key=os.getenv("PRIVATE_KEY"),
        chain_id=POLYGON,
        signature_type=0
    )
    creds = client.create_or_derive_api_creds()
    client.set_api_creds(creds)
    return client

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

def place_real_order(token_id, amount_usdc, price, side="BUY"):
    try:
        from py_clob_client.client import ClobClient
        from py_clob_client.clob_types import OrderArgs
        from py_clob_client.constants import POLYGON

        client = ClobClient(
            host=CLOB_HOST,
            key=os.getenv("PRIVATE_KEY"),
            chain_id=POLYGON,
            signature_type=0
        )
        creds = client.create_or_derive_api_creds()
        client.set_api_creds(creds)

        size = round(amount_usdc / price, 2) if side == "BUY" else round(amount_usdc, 2)

        order_args = OrderArgs(
            token_id=token_id,
            price=round(price, 4),
            size=size,
            side=side
        )

        resp = client.create_and_post_order(order_args)
        print(f"Orden real {side}: {resp}")
        return resp
    except Exception as e:
        print(f"Error orden real: {e}")
        return None

def process_wallet(wallet, state, snapshot):
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
            if bet_amount <= 0:
                continue

            place_real_order(asset, bet_amount, avg_price, "BUY")

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
            print(f"NUEVA: {title} | {outcome} | ${bet_amount:.2f}")

    for pos in list(state["positions"]):
        if pos["wallet"] == address and pos["condition_id"] not in current_ids:
            current_price = get_token_price(pos["asset"])

            place_real_order(pos["asset"], pos["shares"], current_price, "SELL")

            pnl = (current_price - pos["entry_price"]) * pos["shares"]
            pos["pnl"] = pnl
            state["balance"] += pos["bet_amount"] + pnl
            state["total_pnl"] += pnl
            state["closed_positions"].append(pos)
            state["positions"].remove(pos)
            print(f"CERRADA: {pos['market']} | PNL: ${pnl:.2f}")

def update_positions(state):
    snapshot = load_snapshot()
    try:
        with open("wallets.json") as f:
            wallets = json.load(f)
    except:
        return

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(process_wallet, w, state, snapshot) for w in wallets]
        for f in as_completed(futures):
            try:
                f.result()
            except Exception as e:
                print(f"Error: {e}")