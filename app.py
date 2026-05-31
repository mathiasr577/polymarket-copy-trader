from flask import Flask, render_template, jsonify, request
from apscheduler.schedulers.background import BackgroundScheduler
import json, os
from dotenv import load_dotenv
from tracker import update_positions

load_dotenv()

app = Flask(__name__)

# Cola de órdenes pendientes para ejecutar desde la Mac
order_queue = []

state = {
    "balance": 447.65,
    "positions": [],
    "closed_positions": [],
    "total_pnl": 0.0
}

def get_real_balance():
    try:
        from py_clob_client_v2 import ClobClient
        client = ClobClient(
            host="https://clob.polymarket.com",
            chain_id=137,
            key=os.getenv("PRIVATE_KEY"),
        )
        creds = client.create_or_derive_api_key()
        client.set_api_creds(creds)
        balance = client.get_balance()
        return float(balance)
    except Exception as e:
        print(f"Error leyendo balance: {e}")
        return 0

def job():
    bal = get_real_balance()
    if bal > 0:
        state["balance"] = bal
    update_positions(state, order_queue)

scheduler = BackgroundScheduler()
scheduler.add_job(job, 'interval', seconds=30)
scheduler.start()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/state')
def get_state():
    try:
        with open("wallets.json") as f:
            wallets = json.load(f)
    except:
        wallets = []

    return jsonify({
        "balance": state["balance"],
        "positions": state["positions"],
        "closed_positions": state["closed_positions"],
        "total_pnl": state["total_pnl"],
        "wallets": wallets
    })

@app.route('/api/wallets')
def get_wallets():
    try:
        with open("wallets.json") as f:
            return jsonify(json.load(f))
    except:
        return jsonify([])

@app.route('/api/queue')
def get_queue():
    return jsonify(order_queue)

@app.route('/api/queue/clear', methods=['POST'])
def clear_queue():
    global order_queue
    order_queue = []
    return jsonify({"ok": True})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=port, debug=False)