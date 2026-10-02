import os
import time
import sqlite3
import datetime
from threading import Thread
from fyers_apiv3 import fyersModel
from fyers_apiv3.FyersWebsocket import data_ws

TOKEN_FILE = "access_token.txt"
DB_FILE = "oi_memory.db"
CLIENT_ID = "4O0N8E4C4S-100"

# चालू महिन्याची एक्सपायरी फॉरमॅट (उदा. 26AUG / 26SEP)
EXPIRY_CODE = "26OCT"

# २०८ प्रमुख FnO स्टॉक्सची पूर्ण लिस्ट
FNO_STOCKS = [
    "ADANIENT", "ADANIPORTS", "ADANIPOWER", "HAL", "BDL", "BEL", "COCHINSHIP", "RVNL", "IREDA", "BHEL", "RECLTD", 
    "DIXON", "BSE", "ANGELONE", "CDSL", "TRENT", "JIOFIN", "PAYTM", "POLICYBZR", "NYKAA", "DELHIVERY", "BAJFINANCE", 
    "BAJAJFINSV", "ICICIBANK", "AXISBANK", "INDUSINDBK", "KOTAKBANK", "CHOLAFIN", "SHRIRAMFIN", "MUTHOOTFIN", 
    "MANAPPURAM", "COFORGE", "PERSISTENT", "TATAELXSI", "LTM", "OFSS", "KPITTECH", "NAUKRI", "VEDL", "HINDALCO", 
    "TATASTEEL", "JINDALSTEL", "JSWSTEEL", "SAIL", "NATIONALUM", "COALINDIA", "DLF", "GODREJPROP", "OBEROIRLTY", 
    "LODHA", "PRESTIGE", "INFY", "LT", "BHARTIARTL", "WIPRO", "HCLTECH", "TECHM", "MARUTI", "M&M", "TITAN", 
    "ASIANPAINT", "ULTRACEMCO", "GRASIM", "AMBUJACEM", "BANKBARODA", "CANBK", "PNB", "IDFCFIRSTB", "BANDHANBNK", 
    "AUBANK", "FEDERALBNK", "RBLBANK", "ABCAPITAL", "LICHSGFIN", "LTF", "HDFCAMC", "MOTILALOFS", "NUVAMA", 
    "KFINTECH", "SBICARD", "HDFCLIFE", "SBILIFE", "ICICIGI", "LICI", "MFSL", "NTPC", "TATAPOWER", "POWERGRID", 
    "ONGC", "OIL", "GAIL", "IOC", "BPCL", "HINDPETRO", "PETRONET", "JSWENERGY", "TVSMOTOR", "ASHOKLEY", 
    "BAJAJ-AUTO", "HEROMOTOCO", "EICHERMOT", "FORCEMOT", "MOTHERSON", "BHARATFORG", "INDIGO", "CONCOR", 
    "INDUSTOWER", "EXIDEIND", "PNBHOUSING", "CGPOWER", "CUMMINSIND", "SIEMENS", "ABB", "WAAREEENER", "PREMIERENE", 
    "UNITDSPR", "UNOMINDA", "TMPV", "VMM", "YESBANK", "SUNPHARMA", "DIVISLAB", "DRREDDY", "CIPLA", "APOLLOHOSP", 
    "AUROPHARMA", "LUPIN", "BIOCON", "GLENMARK", "ZYDUSLIFE", "ALKEM", "LAURUSLABS", "TORNTPHARM", "MANKIND", 
    "MAXHEALTH", "FORTIS", "HINDUNILVR", "BRITANNIA", "TATACONSUM", "DABUR", "MARICO", "COLPAL", "GODREJCP", 
    "NESTLEIND", "VBL", "JUBLFOOD", "PAGEIND", "PIDILITIND", "SRF", "UPL", "DALBHARAT", "DMART", "INDHOTEL", 
    "PATANJALI", "KALYANKJIL", "ETERNAL", "HAVELLS", "VOLTAS", "BLUESTARCO", "AMBER", "KAYNES", "POLYCAB", 
    "KEI", "ASTRAL", "SUPREMEIND", "ACC", "AARTIIND", "ATGL", "ATUL", "BALKRISIND", "BATAINDIA", "BSOFT", 
    "CHAMBLFERT", "COROMANDEL", "CROMPTON", "CYIENT", "DEEPAKNTR", "GNFC", "GRANULES", "HDFCBANK", "HUDCO", 
    "HYUNDAI", "IEX", "IGL", "INDIACEM", "IPCALAB", "JKCEMENT", "MCX", "MGL", "MPHASIS", "NAVINFLUOR", "NMDC", 
    "PFC", "PIIND", "POONAWALLA", "RAMCOCEM", "SBIN", "SHREECEM", "SYNGENE", "TATACHEM", "TATACOMM", "TCS", 
    "TIINDIA", "TORNTPOWER", "UBL"
]

# --- 1. SQLITE DATABASE SETUP ---
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS oi_snapshots (
            timestamp TEXT,
            symbol TEXT,
            ltp REAL,
            oi INTEGER,
            PRIMARY KEY (timestamp, symbol)
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# --- 2. ACCESS TOKEN LOADING ---
def get_access_token():
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "r") as f:
            return f.read().strip()
    return None

access_token = get_access_token()

if not access_token:
    print("❌ Error: Access token not found in access_token.txt. Please run fyers_auth.py first.")
    exit()

fyers = fyersModel.FyersModel(client_id=CLIENT_ID, is_async=False, token=access_token, log_path="")

# --- 3. DYNAMIC STRIKE GENERATOR ENGINE ---
def generate_auto_option_symbols(stocks):
    """थेट स्पॉट प्राईसनुसार ऑटोमॅटिकली व्हॅलिड ATM व OTM स्ट्राइक्स तयार करणे"""
    generated_symbols = []
    chunk_size = 50
    spot_symbols = [f"NSE:{stock}-EQ" for stock in stocks]
    
    print("🔄 Dynamic Strike Price Generator चालू होत आहे...")
    
    for i in range(0, len(spot_symbols), chunk_size):
        batch = spot_symbols[i:i + chunk_size]
        try:
            quotes = fyers.quotes({"symbols": ",".join(batch)})
            if quotes and "d" in quotes:
                for item in quotes["d"]:
                    sym_name = item.get("n", "").split(":")[1].replace("-EQ", "")
                    spot_price = item.get("v", {}).get("lp", 0)
                    
                    # फक्त व्हॅलिड प्राईस असेल तरच स्ट्राइक जनरेट करणे
                    if spot_price > 10:
                        step = 50 if spot_price > 1000 else (10 if spot_price > 200 else 2.5)
                        atm_strike = round(spot_price / step) * step
                        strikes = [atm_strike - step, atm_strike, atm_strike + step]
                        
                        for st_val in strikes:
                            formatted_strike = str(int(st_val))
                            generated_symbols.append(f"NSE:{sym_name}{EXPIRY_CODE}{formatted_strike}CE-OPT")
                            generated_symbols.append(f"NSE:{sym_name}{EXPIRY_CODE}{formatted_strike}PE-OPT")
        except Exception as e:
            pass
            
    print(f"✅ एकूण {len(generated_symbols)} व्हॅलिड ऑप्शन्स स्ट्राइक प्राईस जनरेट झाल्या आहेत!")
    return generated_symbols

# Global Live Cache
live_cache = {}

# --- 4. WEBSOCKET HANDLERS ---
def on_message(message):
    try:
        if isinstance(message, dict):
            symbol = message.get("symbol")
            ltp = message.get("ltp")
            oi = message.get("oi")
            
            if symbol and oi is not None:
                clean_sym = symbol.replace("-OPT", "")
                live_cache[clean_sym] = {
                    "ltp": ltp,
                    "oi": oi,
                    "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
    except Exception:
        pass

def on_error(message):
    print("WebSocket Error:", message)

def on_close(message):
    print("WebSocket Connection Closed")

def on_open():
    print("✅ Fyers Real-time WebSocket कनेक्ट झाले आहे!")
    auto_symbols = generate_auto_option_symbols(FNO_STOCKS)
    
    if auto_symbols:
        chunk = 50  # Stable batching for Fyers WebSocket
        for i in range(0, len(auto_symbols), chunk):
            sub_batch = auto_symbols[i:i + chunk]
            fyers_ws.subscribe(symbols=sub_batch, data_type="SymbolUpdate")
            time.sleep(0.1)
        print("🚀 सर्व ऑटोमॅटिक स्ट्राइक प्राईस WebSocket ला यशस्वीरीत्या सबस्क्राईब झाल्या आहेत!")
    
    fyers_ws.keep_running()

# --- 5. 5-MINUTE SNAPSHOT SAVER THREAD ---
def snapshot_saver():
    while True:
        now = datetime.datetime.now()
        timestamp_str = now.strftime("%Y-%m-%d %H:%M:00")
        
        if len(live_cache) > 0:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            for sym, data in live_cache.items():
                cursor.execute('''
                    INSERT OR REPLACE INTO oi_snapshots (timestamp, symbol, ltp, oi)
                    VALUES (?, ?, ?, ?)
                ''', (timestamp_str, sym, data["ltp"], data["oi"]))
            conn.commit()
            conn.close()
            print(f"📸 [{timestamp_str}] जतन केले: {len(live_cache)} ऑप्शन्सचा 5-Min OI स्नॅपशॉट.")
            
        time.sleep(300)

saver_thread = Thread(target=snapshot_saver, daemon=True)
saver_thread.start()

# --- 6. WEBSOCKET CONNECTION LAUNCH ---
fyers_ws = data_ws.FyersDataSocket(
    access_token=f"{CLIENT_ID}:{access_token}",
    log_path="",
    on_connect=on_open,
    on_close=on_close,
    on_error=on_error,
    on_message=on_message
)

fyers_ws.connect()