from flask import Flask, render_template, jsonify
from apscheduler.schedulers.background import BackgroundScheduler
import json, os
from dotenv import load_dotenv
from tracker import update_positions

load_dotenv()

app = Flask(__name__)

state = {
    "balance": float(os.getenv("BALANCE", 1000)),
    "positions": [],
    "closed_positions": [],
    "total_pnl": 0.0
}

def job():
    update_positions(state)

scheduler = BackgroundScheduler()
scheduler.add_job(job, 'interval', seconds=5)
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

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=port, debug=False)