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
        return int(result.get("balance", 0)) / 1_000_000
    except Exception as e:
        print(f"Error leyendo balance: {e}")
        return 0

def report_balance(balance):
    try:
        requests.post(f"{RAILWAY_URL}/api/update_balance", json={"balance": balance}, timeout=5)
    except:
        pass

def execute_order(order, client, balance):
    try:
        from py_clob_client_v2.clob_types import OrderArgs
        side = order["side"]

        if side == "BUY":
            bet_amount = balance * 0.05
            if bet_amount < 1:
                print(f"Balance muy bajo (${balance:.2f}) — saltando {order['market']}")
                return False
            size = round(bet_amount / order["price"], 2)
            size = max(size, 5.0)
        else:
            size = round(float(order["amount"]), 2)
            size = max(size, 5.0)

        resp = client.create_and_post_order(OrderArgs(
            token_id=order["token_id"],
            price=round(order["price"], 4),
            size=size,
            side=side,
        ))
        status = resp.get("status", "")
        success = resp.get("success", False)
        if success:
            print(f"✅ {side} {order['market']} | {status}")
        else:
            print(f"❌ Falló: {order['market']} | {resp.get('errorMsg')}")
        return success
    except Exception as e:
        print(f"❌ Error: {order['market']} | {e}")
        return False

def run():
    print("🟢 Executor iniciando en Railway...")
    client = get_client()

    try:
        requests.post(f"{RAILWAY_URL}/api/queue/clear")
        print("Cola limpiada al arrancar")
    except:
        pass

    cycle = 0
    while True:
        try:
            balance = get_real_balance(client)

            if balance > 0:
                report_balance(balance)
                if cycle % 10 == 0:
                    print(f"💰 Balance: ${balance:.2f} | 5%: ${balance * 0.05:.2f}")

            r = requests.get(f"{RAILWAY_URL}/api/queue", timeout=10)
            orders = r.json()

            if orders:
                print(f"📋 {len(orders)} ordenes en cola")
                executed = 0
                for order in orders:
                    # Releer balance actualizado antes de cada orden
                    time.sleep(10)
                    balance = get_real_balance(client)
                    if balance < 1:
                        print(f"Sin balance suficiente (${balance:.2f}), parando")
                        break
                    success = execute_order(order, client, balance)
                    if success:
                        executed += 1
                requests.post(f"{RAILWAY_URL}/api/queue/clear")
                if executed > 0:
                    print(f"✅ {executed} ordenes ejecutadas")

        except Exception as e:
            print(f"Error en ciclo: {e}")
            try:
                client = get_client()
            except:
                pass

        cycle += 1
        time.sleep(30)

if __name__ == "__main__":
    run()
