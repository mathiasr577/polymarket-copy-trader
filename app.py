from flask import Flask, render_template, jsonify, request
from apscheduler.schedulers.background import BackgroundScheduler
import json, os, requests
from dotenv import load_dotenv
from tracker import update_positions

load_dotenv()

app = Flask(__name__)

order_queue = []

state = {
    "balance": 0,
    "cash": 0,
    "portfolio": 0,
    "positions": [],
    "closed_positions": [],
    "total_pnl": 0.0
}

PROXY_WALLET = os.getenv("PROXY_WALLET", "0x5fa918d6752074476dCfa68ae5618fC70Bc49945")

def get_polymarket_data():
    try:
        r = requests.get(
            f"https://data-api.polymarket.com/value?user={PROXY_WALLET}",
            headers={'User-Agent': 'Mozilla/5.0'},
            timeout=10
        )
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, list) and len(data) > 0:
                return float(data[0].get("value", 0))
        return 0
    except:
        return 0

def job():
    portfolio = get_polymarket_data()
    if portfolio > 0:
        state["portfolio"] = portfolio
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

    open_pnl = sum(p.get("pnl", 0) for p in state["positions"])
    closed_pnl = state["total_pnl"]
    total_pnl = open_pnl + closed_pnl

    wallet_stats = {}
    for pos in state["positions"] + state["closed_positions"]:
        wk = pos.get("wallet_note", pos.get("wallet", ""))
        if wk not in wallet_stats:
            wallet_stats[wk] = {"pnl": 0, "wins": 0, "total": 0, "open": 0}
        wallet_stats[wk]["pnl"] += pos.get("pnl", 0)
        wallet_stats[wk]["total"] += 1
        if pos in state["closed_positions"]:
            if pos.get("pnl", 0) > 0:
                wallet_stats[wk]["wins"] += 1
        else:
            wallet_stats[wk]["open"] += 1

    return jsonify({
        "portfolio": round(state["cash"] + state["portfolio"], 2),
        "cash": round(state["cash"], 2),
        "balance": round(state["balance"], 2),
        "total_pnl": round(total_pnl, 2),
        "open_pnl": round(open_pnl, 2),
        "closed_pnl": round(closed_pnl, 2),
        "positions": state["positions"],
        "closed_positions": state["closed_positions"],
        "wallet_stats": wallet_stats,
        "wallets": wallets
    })

@app.route('/api/update_balance', methods=['POST'])
def update_balance():
    data = request.get_json()
    balance = data.get("balance", 0)
    if balance > 0:
        state["cash"] = balance
        state["balance"] = balance
    return jsonify({"ok": True})

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