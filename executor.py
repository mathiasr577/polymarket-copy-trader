import requests
import time
import os
from dotenv import load_dotenv
load_dotenv()

RAILWAY_URL = "https://web-production-3f48f.up.railway.app"
DEPOSIT_WALLET = "0x5fa918d6752074476dCfa68ae5618fC70Bc49945"

def get_client():
    from py_clob_client_v2 import ClobClient
    from py_clob_client_v2.clob_types import ApiCreds
    client = ClobClient(
        host="https://clob.polymarket.com",
        chain_id=137,
        key=os.getenv("PRIVATE_KEY"),
        funder=DEPOSIT_WALLET,
        signature_type=3
    )
    client.set_api_creds(ApiCreds(
        api_key=os.getenv("CLOB_API_KEY"),
        api_secret=os.getenv("CLOB_SECRET"),
        api_passphrase=os.getenv("CLOB_PASSPHRASE")
    ))
    return client

def get_real_balance(client):
    try:
        from py_clob_client_v2.clob_types import BalanceAllowanceParams, AssetType
        result = client.get_balance_allowance(params=BalanceAllowanceParams(asset_type=AssetType.COLLATERAL))
        balance_raw = int(result.get("balance", 0))
        return balance_raw / 1_000_000
    except Exception as e:
        print(f"Error balance: {e}")
        return 0

def report_balance(balance):
    try:
        requests.post(f"{RAILWAY_URL}/api/update_balance", json={"balance": balance}, timeout=5)
    except:
        pass

def execute_order(order, client):
    try:
        from py_clob_client_v2.clob_types import OrderArgs
        balance = get_real_balance(client)
        if balance <= 0:
            print(f"Sin balance para {order['market']}")
            return False
        bet_amount = balance * 0.05
        if bet_amount < 1:
            print(f"Balance muy bajo (${balance:.2f}) para {order['market']}")
            return False
        size = round(bet_amount / order["price"], 2) if order["side"] == "BUY" else round(order["amount"], 2)
        size = max(size, 1.0)
        resp = client.create_and_post_order(OrderArgs(
            token_id=order["token_id"],
            price=round(order["price"], 4),
            size=size,
            side=order["side"],
        ))
        print(f"Orden ejecutada: {order['side']} {order['market']} | ${bet_amount:.2f} | {resp}")
        return True
    except Exception as e:
        print(f"Error orden: {e}")
        return False

def run():
    print("Executor corriendo en Railway...")
    client = get_client()
    while True:
        try:
            balance = get_real_balance(client)
            if balance > 0:
                report_balance(balance)
                print(f"Balance real: ${balance:.2f}")
            r = requests.get(f"{RAILWAY_URL}/api/queue", timeout=10)
            orders = r.json()
            if orders:
                print(f"{len(orders)} ordenes en cola")
                for order in orders:
                    if order["side"] == "BUY":
                        execute_order(order, client)
                        time.sleep(2)
                requests.post(f"{RAILWAY_URL}/api/queue/clear")
        except Exception as e:
            print(f"Error: {e}")
            try:
                client = get_client()
            except:
                pass
        time.sleep(30)

if __name__ == "__main__":
    run()
