from flask import Flask, render_template, jsonify, request
from apscheduler.schedulers.background import BackgroundScheduler
import json, os, requests
from dotenv import load_dotenv
from tracker import update_positions

load_dotenv()

app = Flask(__name__)

order_queue = []

state = {
    "balance": 76.79,
    "positions": [],
    "closed_positions": [],
    "total_pnl": 0.0
}

def get_real_balance():
    try:
        proxy_wallet = os.getenv("PROXY_WALLET", "0x5fa918d6752074476dCfa68ae5618fC70Bc49945")
        r = requests.get(
            f"https://data-api.polymarket.com/value?user={proxy_wallet}",
            headers={'User-Agent': 'Mozilla/5.0'},
            timeout=10
        )
        if r.status_code == 200:
            data = r.json()
            cash = float(data.get("cashBalance", 0))
            return cash
        return 0
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