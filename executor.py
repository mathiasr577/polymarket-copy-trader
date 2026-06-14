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

def get_current_price(token_id):
    try:
        r = requests.get(
            f"https://clob.polymarket.com/last-trade-price?token_id={token_id}",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=5
        )
        if r.status_code == 200:
            price = float(r.json().get("price", 0))
            if 0.02 <= price <= 0.98:
                return price
        return None
    except:
        return None

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
                return False, balance

            # Obtener precio actual del mercado
            price = get_current_price(order["token_id"])
            if price is None:
                print(f"SKIP precio inválido: {order['market']}")
                return False, balance

            size = round(bet_amount / price, 2)
            size = max(size, 5.0)

            resp = client.create_and_post_order(OrderArgs(
                token_id=order["token_id"],
                price=round(price, 4),
                size=size,
                side=side,
            ))
            balance = balance - bet_amount

        else:  # SELL
            size = round(float(order["amount"]), 2)
            size = max(size, 5.0)

            # Para SELL usar precio actual también
            price = get_current_price(order["token_id"])
            if price is None:
                price = round(order["price"], 4)

            resp = client.create_and_post_order(OrderArgs(
                token_id=order["token_id"],
                price=round(price, 4),
                size=size,
                side=side,
            ))

        success = resp.get("success", False)
        status = resp.get("status", "")
        if success:
            print(f"✅ {side} {order['market']} | ${bet_amount if side == 'BUY' else 0:.2f} | {status}")
        else:
            print(f"❌ Falló: {order['market']} | {resp.get('errorMsg')}")
        return success, balance
    except Exception as e:
        print(f"❌ Error: {order['market']} | {e}")
        return False, balance

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
                for order in orders:
                    if balance < 1:
                        print(f"Sin balance suficiente (${balance:.2f}), parando")
                        break
                    success, balance = execute_order(order, client, balance)
                    time.sleep(3)
                requests.post(f"{RAILWAY_URL}/api/queue/clear")

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