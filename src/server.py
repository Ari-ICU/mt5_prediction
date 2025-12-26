from http.server import BaseHTTPRequestHandler, HTTPServer
import time
from . import config
from .state import state

class MT5Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != config.ENDPOINT:
            self.send_response(404)
            self.end_headers()
            return

        state.last_poll_time = time.time()
        if not state.is_connected:
            state.update_connection(True)
            state.log("🔌 MT5 EA connected!", "success")

        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length).decode('utf-8')
        post_data = post_data.replace('\x00', '').replace('\r', '').replace('\n', '').strip()

        data_dict = {}
        for pair in post_data.split('&'):
            if '=' in pair:
                key, value = pair.split('=', 1)
                data_dict[key] = value.strip()

        if "market" in data_dict:
            state.update_market(data_dict["market"] == "OPEN")

        try:
            symbol = data_dict.get("symbol", state.current_symbol)
            bid = float(data_dict.get("bid", state.current_bid))
            ask = float(data_dict.get("ask", state.current_ask))
            
            if bid > 0 and ask > 0:
                state.update_price(symbol, bid, ask)
            
            # Update Account Info
            if "balance" in data_dict:
                name = data_dict.get("name", "Demo Account")
                balance = float(data_dict.get("balance", 0.0))
                equity = float(data_dict.get("equity", 0.0))
                margin = float(data_dict.get("margin", 0.0))
                free_margin = float(data_dict.get("free_margin", 0.0))
                profit = float(data_dict.get("profit", 0.0))
                state.update_account(name, balance, equity, margin, free_margin, profit)
                
        except (ValueError, KeyError) as e:
            state.log(f"⚠ Price parse error: {e}", "warning")

        # Send pending command if any
        response_text = state.pending_command
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(response_text.encode("utf-8"))

        if state.pending_command != "":
            state.log(f"✓ Command sent to MT5: {state.pending_command}", "success")
            state.pending_command = ""

    def log_message(self, format, *args):
        # Suppress default server logging
        return

def start_server():
    server = HTTPServer((config.HOST, config.PORT), MT5Handler)
    state.log(f"🚀 Server started on {config.HOST}:{config.PORT}", "info")
    server.serve_forever()
