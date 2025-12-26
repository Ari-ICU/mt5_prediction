from http.server import BaseHTTPRequestHandler, HTTPServer
import time
from urllib.parse import parse_qs
from . import config
from .core.events import events, EventType
from .core.logger import logger
from .models.data_models import MarketData, AccountData

# Ensure dataset directory exists at startup
import os
os.makedirs("dataset", exist_ok=True)

class MT5Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != config.ENDPOINT:
            self.send_response(404)
            self.end_headers()
            return

        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length).decode('utf-8', errors='ignore')
        
        # Clean null bytes
        post_data = post_data.replace('\x00', '').strip()
        
        # Robust parsing for MT5 data (which might contain unencoded history)
        data_dict = {}
        if "&history=" in post_data:
            # Special case for history sync: split manually
            parts = post_data.split("&history=", 1)
            # Parse the prefix normally
            data_dict = {k: v[0] for k, v in parse_qs(parts[0]).items()}
            # Assign the raw history (the rest of the string)
            data_dict["history"] = parts[1]
        else:
            # Standard parsing
            data_dict = {k: v[0] for k, v in parse_qs(post_data).items()}

        # Pulse check log (Only every 60 seconds for a quiet console)
        from .state import state
        if time.time() - state.last_heartbeat > 60:
             market_status = data_dict.get('market', 'UNKNOWN')
             logger.debug(f"🔵 Data Pulse: {data_dict.get('symbol')} | {data_dict.get('bid')} | Status: {market_status}")
             state.last_heartbeat = time.time()

        self._process_data(data_dict)
        
        # Response to EA
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        
        response_text = state.pending_command if state.pending_command else "OK"
        self.wfile.write(response_text.encode("utf-8"))

        if state.pending_command:
            logger.info(f"Sent to MT5: {state.pending_command}")
            state.pending_command = ""

    def _process_data(self, data: dict):
        try:
            # 0. Handle Historical Data (for training)
            if "history" in data:
                symbol = data.get("symbol", "UNKNOWN")
                filename = f"dataset/{symbol}_history.csv"
                raw_history = data["history"]
                
                # Basic validation
                lines = raw_history.strip().split("\n")
                if not lines:
                    logger.warning(f"⚠️ Received history batch for {symbol} but it was empty.")
                    return

                # Append history data to file
                try:
                    is_new = not os.path.exists(filename) or os.path.getsize(filename) == 0
                    
                    # Ensure the data ends with a newline to avoid merging with next batch
                    if not raw_history.endswith("\n"):
                        raw_history += "\n"

                    with open(filename, "a") as f:
                        if is_new:
                            f.write("time,open,high,low,close,volume\n")
                        f.write(raw_history)
                    
                    logger.success(f"📁 Saved {len(lines)} candles to {filename}")
                except Exception as e:
                    logger.error(f"❌ Failed to save history to {filename}: {e}")
                
                return # No need to process further if it's just a history batch

            # 1. Market Data
            symbol = data.get("symbol", "")
            bid = float(data.get("bid", 0.0))
            ask = float(data.get("ask", 0.0))
            is_open = data.get("market") == "OPEN"

            if symbol and bid > 0:
                market = MarketData(
                    symbol=symbol,
                    bid=bid,
                    ask=ask,
                    is_open=is_open
                )
                events.emit(EventType.PRICE_UPDATE, market)

            # 2. Account Data
            if "balance" in data:
                account = AccountData(
                    name=data.get("name", "MT5 Account"),
                    balance=float(data.get("balance", 0.0)),
                    equity=float(data.get("equity", 0.0)),
                    margin=float(data.get("margin", 0.0)),
                    free_margin=float(data.get("free_margin", 0.0)),
                    profit=float(data.get("profit", 0.0)),
                    position_count=int(data.get("pos_count", 0))
                )
                events.emit(EventType.ACCOUNT_UPDATE, account)
            
            # 3. Positions Data (Ticket, Profit)
            if "positions" in data:
                raw_pos = data["positions"]
                positions_list = []
                if raw_pos.strip():
                    parts = raw_pos.strip().split("|")
                    from .models.data_models import PositionData
                    for p in parts:
                        if not p: continue
                        fields = p.split(":")
                        if len(fields) >= 2:
                            positions_list.append(PositionData(
                                ticket=int(fields[0]),
                                profit=float(fields[1])
                            ))
                events.emit(EventType.POSITIONS_UPDATE, positions_list)

        except Exception as e:
            logger.warning(f"Error parsing MT5 data: {e}")

    def log_message(self, format, *args):
        # Suppress HTTP server console logs
        return

def start_server():
    try:
        server = HTTPServer((config.HOST, config.PORT), MT5Handler)
        logger.info(f"API Server listening on {config.HOST}:{config.PORT}")
        server.serve_forever()
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
