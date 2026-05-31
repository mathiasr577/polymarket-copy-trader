from flask import Flask, render_template, jsonify
from apscheduler.schedulers.background import BackgroundScheduler
import json, os
from dotenv import load_dotenv
from tracker import update_positions
from web3 import Web3

load_dotenv()

app = Flask(__name__)

RPC = "https://rpc-mainnet.matic.quiknode.pro"
USDC_POLYGON = Web3.to_checksum_address("0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359")
EOA = Web3.to_checksum_address("0x2c8e572FCfC99029eec2288ea5C3AE0C4e22E9CB")

USDC_ABI = [{"name": "balanceOf", "type": "function", "inputs": [{"name": "account", "type": "address"}], "outputs": [{"name": "", "type": "uint256"}], "stateMutability": "view"}]

def get_real_balance():
    try:
        w3 = Web3(Web3.HTTPProvider(RPC))
        contract = w3.eth.contract(address=USDC_POLYGON, abi=USDC_ABI)
        balance = contract.functions.balanceOf(EOA).call()
        return balance / 1e6
    except:
        return 0

state = {
    "balance": get_real_balance(),
    "positions": [],
    "closed_positions": [],
    "total_pnl": 0.0
}

def job():
    state["balance"] = get_real_balance()
    update_positions(state)

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

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=port, debug=False)