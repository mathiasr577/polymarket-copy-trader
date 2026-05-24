import requests
import json

GAMMA_API = "https://gamma-api.polymarket.com"

def get_top_traders(min_win_rate=0.65, limit=20):
    """Busca los mejores traders de Polymarket por win rate"""
    try:
        url = f"{GAMMA_API}/leaderboard?limit=100"
        r = requests.get(url, timeout=10)
        if r.status_code != 200:
            print(f"Error: {r.status_code}")
            return []
        
        traders = r.json()
        good_traders = []

        for trader in traders:
            address = trader.get("account", "")
            profit = float(trader.get("profit", 0))
            trades = int(trader.get("tradeCount", 0))
            
            if trades < 10:
                continue
                
            win_rate = trader.get("winRate", 0)
            if isinstance(win_rate, str):
                win_rate = float(win_rate)
            
            if win_rate >= min_win_rate and profit > 0:
                good_traders.append({
                    "address": address,
                    "win_rate": win_rate,
                    "profit": profit,
                    "trades": trades,
                    "category": classify_trader(address)
                })

        good_traders.sort(key=lambda x: x["win_rate"], reverse=True)
        return good_traders[:limit]

    except Exception as e:
        print(f"Error buscando traders: {e}")
        return []

def classify_trader(address):
    """Por ahora retorna general - después podemos clasificar por mercados"""
    return "general"

def save_wallets(traders):
    with open("wallets.json", "w") as f:
        json.dump(traders, f, indent=2)
    print(f"Guardadas {len(traders)} wallets en wallets.json")

if __name__ == "__main__":
    print("Buscando mejores traders de Polymarket...")
    traders = get_top_traders(min_win_rate=0.65, limit=20)
    if traders:
        save_wallets(traders)
        for t in traders:
            print(f"{t['address'][:10]}... | WR: {t['win_rate']:.0%} | Profit: ${t['profit']:.0f} | Trades: {t['trades']}")
    else:
        print("No se encontraron traders o hubo un error con la API")