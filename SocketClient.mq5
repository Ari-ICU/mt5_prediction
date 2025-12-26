#property strict
#property version "1.92"

// --- Inputs ---
input string ServerURL = "http://127.0.0.1:5555/trade"; // Python HTTP server
input double DefaultLot = 0.01;
input bool TestingMode = true; // TRUE to trade even if market closed

// --- Global Variables ---
datetime lastRequestTime = 0;
bool hasWarnedAboutAlgo = false;

//+------------------------------------------------------------------+
//| Timer Event                                                      |
//+------------------------------------------------------------------+
void OnTimer()
{
    // --- PERMISSION CHECK ---
    if(!TerminalInfoInteger(TERMINAL_TRADE_ALLOWED) || !MQLInfoInteger(MQL_TRADE_ALLOWED))
    {
        if(!hasWarnedAboutAlgo)
        {
            Print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!");
            Print("[CRITICAL WARNING] AUTO TRADING IS DISABLED!");
            Print("1. Click 'Algo Trading' button in Toolbar (Make it GREEN)");
            Print("2. Press F7 -> Common -> Check 'Allow Algorithmic Trading'");
            Print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!");
            hasWarnedAboutAlgo = true;
        }
    }
    else
    {
        hasWarnedAboutAlgo = false;
    }

    // Limit requests to once per second
    if(TimeCurrent() - lastRequestTime < 1) return;
    lastRequestTime = TimeCurrent();

    // Check market status (Revised for multiple sessions)
    string marketStatus = IsMarketOpen(_Symbol) ? "OPEN" : "CLOSED";
    
    // Get current prices
    double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
    double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
    
    // --- FETCH ACCOUNT INFO ---
    double balance = AccountInfoDouble(ACCOUNT_BALANCE);
    double equity = AccountInfoDouble(ACCOUNT_EQUITY);
    double margin = AccountInfoDouble(ACCOUNT_MARGIN);
    double free_margin = AccountInfoDouble(ACCOUNT_MARGIN_FREE);
    double profit = AccountInfoDouble(ACCOUNT_PROFIT);
    string name = AccountInfoString(ACCOUNT_NAME);

    // Prepare POST data
    string post_str = "request=next&market=" + marketStatus + 
                      "&symbol=" + _Symbol + 
                      "&bid=" + DoubleToString(bid, _Digits) + 
                      "&ask=" + DoubleToString(ask, _Digits) +
                      "&balance=" + DoubleToString(balance, 2) + 
                      "&equity=" + DoubleToString(equity, 2) + 
                      "&margin=" + DoubleToString(margin, 2) + 
                      "&free_margin=" + DoubleToString(free_margin, 2) + 
                      "&profit=" + DoubleToString(profit, 2) + 
                      "&name=" + name;
    
    char post_char[];
    StringToCharArray(post_str, post_char);
    uchar post_uchar[];
    ArrayResize(post_uchar, ArraySize(post_char));
    for(int i=0; i<ArraySize(post_char); i++)
        post_uchar[i] = (uchar)post_char[i];

    // Prepare result buffer
    uchar result_uchar[];
    ArrayResize(result_uchar, 1024);
    string response_headers; 

    // Make HTTP POST request
    int http_res = WebRequest(
        "POST",
        ServerURL,
        "Content-Type: application/x-www-form-urlencoded\r\n", 
        5000, post_uchar, result_uchar, response_headers
    );

    if(http_res == -1)
    {
        int err = GetLastError();
        if(err == 4060) Print("CHECK: Tools > Options > Expert Advisors > Allow WebRequest");
        return;
    }

    // Convert result to string
    string result_str = CharArrayToString(result_uchar, 0, ArraySize(result_uchar));
    StringReplace(result_str, "\r", "");
    StringReplace(result_str, "\n", "");
    StringReplace(result_str, "\0", "");

    if(StringLen(result_str) > 0)
    {
        Print("Received from Python: ", result_str);
        ProcessCommand(result_str);
    }
}

//+------------------------------------------------------------------+
//| Process Command                                                  |
//+------------------------------------------------------------------+
void ProcessCommand(string cmd)
{
    string parts[];
    if(StringSplit(cmd, '|', parts) < 2) return;

    string action = parts[0];
    string symbol = parts[1];
    double lot = (ArraySize(parts) >= 3) ? StringToDouble(parts[2]) : DefaultLot;
    double sl_price = (ArraySize(parts) >= 5) ? StringToDouble(parts[3]) : 0;
    double tp_price = (ArraySize(parts) >= 5) ? StringToDouble(parts[4]) : 0;

    if(!SymbolSelect(symbol, true)) { Print("[ERROR] Symbol ", symbol, " not found"); return; }

    if(action == "BUY")  Trade(symbol, ORDER_TYPE_BUY, lot, sl_price, tp_price);
    if(action == "SELL") Trade(symbol, ORDER_TYPE_SELL, lot, sl_price, tp_price);
    if(action == "CLOSE_ALL") CloseAll(symbol);
    if(action == "CLOSE_WIN") ClosePositions(symbol, true);   
    if(action == "CLOSE_LOSS") ClosePositions(symbol, false);
}

//+------------------------------------------------------------------+
//| Check Market Open (ALL SESSIONS)                                 |
//+------------------------------------------------------------------+
bool IsMarketOpen(string symbol)
{
    datetime now = TimeTradeServer();
    MqlDateTime dt;
    TimeToStruct(now, dt);
    ENUM_DAY_OF_WEEK day = (ENUM_DAY_OF_WEEK)dt.day_of_week;

    datetime from, to;
    // Check up to 10 sessions per day (handles lunch breaks)
    for(int i=0; i<10; i++) 
    {
        if(!SymbolInfoSessionTrade(symbol, day, i, from, to)) break; 
        if(now >= from && now <= to) return true;
    }
    return false;
}

//+------------------------------------------------------------------+
//| Execute Trade                                                    |
//+------------------------------------------------------------------+
void Trade(string symbol, ENUM_ORDER_TYPE type, double lot, double sl, double tp)
{
    // Double check permissions before trying
    if(!TerminalInfoInteger(TERMINAL_TRADE_ALLOWED)) {
        Print("[FAIL] Global 'Algo Trading' button is OFF. Please enable it.");
        return;
    }
    if(!MQLInfoInteger(MQL_TRADE_ALLOWED)) {
        Print("[FAIL] 'Allow Algo Trading' in EA Properties is OFF. Press F7 to fix.");
        return;
    }

    if(!TestingMode && !IsMarketOpen(symbol))
    {
        Print("[BLOCKED] ", symbol, " Market CLOSED");
        return;
    }

    double price = (type == ORDER_TYPE_BUY) ? SymbolInfoDouble(symbol, SYMBOL_ASK) : SymbolInfoDouble(symbol, SYMBOL_BID);
    
    MqlTradeRequest req;
    MqlTradeResult res;
    ZeroMemory(req); ZeroMemory(res);

    req.action = TRADE_ACTION_DEAL;
    req.symbol = symbol;
    req.volume = lot;
    req.type = type;
    req.price = price;
    req.sl = sl; 
    req.tp = tp;
    req.deviation = 50;
    req.type_filling = ORDER_FILLING_IOC;

    if(!OrderSend(req, res))
    {
        Print("[TRADE ERROR] ", symbol, " ", EnumToString(type), " Failed - Retcode: ", res.retcode);
        if(res.retcode == 10027) Print(">>> FIX 10027: Enable 'Algo Trading' button in Toolbar <<<");
    }
    else
    {
        Print("[TRADE SUCCESS] ", symbol, " ", EnumToString(type), " - Deal: ", res.deal);
    }
}

//+------------------------------------------------------------------+
//| Close Utilities                                                  |
//+------------------------------------------------------------------+
void CloseAll(string symbol) {
    for(int i=PositionsTotal()-1; i>=0; i--) {
        ulong ticket = PositionGetTicket(i);
        if(PositionGetString(POSITION_SYMBOL) == symbol) CloseTicket(ticket);
    }
}

void ClosePositions(string symbol, bool profitOnly) {
    for(int i=PositionsTotal()-1; i>=0; i--) {
        ulong ticket = PositionGetTicket(i);
        if(PositionGetString(POSITION_SYMBOL) == symbol) {
            double profit = PositionGetDouble(POSITION_PROFIT);
            if((profitOnly && profit > 0) || (!profitOnly && profit < 0)) CloseTicket(ticket);
        }
    }
}

void CloseTicket(ulong ticket) {
    MqlTradeRequest req;
    MqlTradeResult res;
    ZeroMemory(req); ZeroMemory(res);
    
    if(!PositionSelectByTicket(ticket)) return;

    ENUM_POSITION_TYPE posType = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);

    req.action = TRADE_ACTION_DEAL;
    req.position = ticket;
    req.symbol = PositionGetString(POSITION_SYMBOL);
    req.volume = PositionGetDouble(POSITION_VOLUME);
    
    // Explicitly handle type assignment using Ternary on compatible types
    req.type = (posType == POSITION_TYPE_BUY) ? ORDER_TYPE_SELL : ORDER_TYPE_BUY;
    
    req.price = (req.type == ORDER_TYPE_BUY) ? SymbolInfoDouble(req.symbol, SYMBOL_ASK) : SymbolInfoDouble(req.symbol, SYMBOL_BID);
    
    if(!OrderSend(req, res))
        Print("[CLOSE FAIL] Ticket: ", ticket, " Retcode: ", res.retcode);
}

int OnInit() { EventSetTimer(1); return INIT_SUCCEEDED; }
void OnDeinit(const int reason) { EventKillTimer(); }
