#property strict
#property version "2.1"
#property description "SocketClient - Python Mac AI Bridge"

// --- Inputs ---
input string ServerURL = "http://127.0.0.1:5555/trade"; // Python HTTP server
input double DefaultLot = 0.01;
input bool TestingMode = true;        // TRUE to trade even if market closed
input int HistoryBars = 5000;         // Number of bars to sync for AI training
input bool AutoSyncHistory = false;   // Set TRUE to sync history on startup

// --- Global Variables ---
datetime lastRequestTime = 0;
bool hasWarnedAboutAlgo = false;
bool historySynced = false;

//+------------------------------------------------------------------+
//| Initialization                                                   |
//+------------------------------------------------------------------+
int OnInit()
{
    EventSetMillisecondTimer(250); // Faster polling for lower latency
    CreateSyncButton();
    if(AutoSyncHistory) SyncHistory(PERIOD_H1, HistoryBars);
    return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| Chart Event Handler                                              |
//+------------------------------------------------------------------+
void OnChartEvent(const int id, const long &lparam, const double &dparam, const string &sparam)
{
    if(id == CHARTEVENT_OBJECT_CLICK && sparam == "btn_sync_history")
    {
        // Visual feedback
        ObjectSetString(0, "btn_sync_history", OBJPROP_TEXT, "⚡ SYNCING...");
        ObjectSetInteger(0, "btn_sync_history", OBJPROP_BGCOLOR, clrOrangeRed);
        ChartRedraw();
        
        SyncHistory(PERIOD_H1, HistoryBars);
        
        // Reset visual state
        ObjectSetString(0, "btn_sync_history", OBJPROP_TEXT, "SYNC HISTORY");
        ObjectSetInteger(0, "btn_sync_history", OBJPROP_BGCOLOR, clrDodgerBlue);
        ObjectSetString(0, "lbl_sync_status", OBJPROP_TEXT, "Last Sync: " + TimeToString(TimeCurrent(), TIME_MINUTES));
        ObjectSetInteger(0, "btn_sync_history", OBJPROP_STATE, false);
        ChartRedraw();
    }
}

void CreateSyncButton()
{
    string btn_name = "btn_sync_history";
    string lbl_name = "lbl_sync_status";
    
    // Create Button
    ObjectDelete(0, btn_name);
    ObjectCreate(0, btn_name, OBJ_BUTTON, 0, 0, 0);
    ObjectSetInteger(0, btn_name, OBJPROP_CORNER, CORNER_LEFT_UPPER);
    ObjectSetInteger(0, btn_name, OBJPROP_XDISTANCE, 20);
    ObjectSetInteger(0, btn_name, OBJPROP_YDISTANCE, 60);
    ObjectSetInteger(0, btn_name, OBJPROP_XSIZE, 140);
    ObjectSetInteger(0, btn_name, OBJPROP_YSIZE, 35);
    ObjectSetString(0, btn_name, OBJPROP_TEXT, "SYNC HISTORY");
    ObjectSetInteger(0, btn_name, OBJPROP_FONTSIZE, 9);
    ObjectSetString(0, btn_name, OBJPROP_FONT, "Trebuchet MS");
    ObjectSetInteger(0, btn_name, OBJPROP_COLOR, clrWhite);
    ObjectSetInteger(0, btn_name, OBJPROP_BGCOLOR, clrDodgerBlue);
    ObjectSetInteger(0, btn_name, OBJPROP_BORDER_COLOR, clrWhite);
    ObjectSetInteger(0, btn_name, OBJPROP_SELECTABLE, false);

    // Create Status Label
    ObjectDelete(0, lbl_name);
    ObjectCreate(0, lbl_name, OBJ_LABEL, 0, 0, 0);
    ObjectSetInteger(0, lbl_name, OBJPROP_CORNER, CORNER_LEFT_UPPER);
    ObjectSetInteger(0, lbl_name, OBJPROP_XDISTANCE, 25);
    ObjectSetInteger(0, lbl_name, OBJPROP_YDISTANCE, 100);
    ObjectSetString(0, lbl_name, OBJPROP_TEXT, "Ready to Sync");
    ObjectSetInteger(0, lbl_name, OBJPROP_COLOR, clrSilver);
    ObjectSetInteger(0, lbl_name, OBJPROP_FONTSIZE, 8);
}

//+------------------------------------------------------------------+
//| Deinitialization                                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason) 
{ 
    EventKillTimer(); 
    ObjectDelete(0, "btn_sync_history");
    ObjectDelete(0, "lbl_sync_status");
}

//+------------------------------------------------------------------+
//| Timer Event - The heartbeat of the bridge                        |
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

    // Rate limiting: 250ms matches timer
    // if(TimeCurrent() - lastRequestTime < 1) return;
    // lastRequestTime = TimeCurrent();

    // Data collection
    string marketStatus = IsMarketOpen(_Symbol) ? "OPEN" : "CLOSED";
    double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
    double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
    double balance = AccountInfoDouble(ACCOUNT_BALANCE);
    double equity = AccountInfoDouble(ACCOUNT_EQUITY);
    double margin = AccountInfoDouble(ACCOUNT_MARGIN);
    double free_margin = AccountInfoDouble(ACCOUNT_MARGIN_FREE);
    double profit = AccountInfoDouble(ACCOUNT_PROFIT);
    string name = AccountInfoString(ACCOUNT_NAME);

    // Prepare Positions Data
    string positions_str = "";
    int total = PositionsTotal();
    for(int i=0; i<total; i++)
    {
        ulong ticket = PositionGetTicket(i);
        if(PositionSelectByTicket(ticket))
        {
            // Format: Ticket:Profit:Type:PriceOpen:SL:TP
            positions_str += IntegerToString(ticket) + ":" + 
                             DoubleToString(PositionGetDouble(POSITION_PROFIT), 2) + ":" +
                             IntegerToString(PositionGetInteger(POSITION_TYPE)) + ":" +
                             DoubleToString(PositionGetDouble(POSITION_PRICE_OPEN), _Digits) + ":" +
                             DoubleToString(PositionGetDouble(POSITION_SL), _Digits) + ":" +
                             DoubleToString(PositionGetDouble(POSITION_TP), _Digits) + "|";
        }
    }

    // Get all symbols from Market Watch
    string symbols_list = "";
    int sym_count = SymbolsTotal(true);
    for(int i=0; i<sym_count; i++)
    {
        symbols_list += SymbolName(i, true) + (i < sym_count - 1 ? "," : "");
    }

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
                      "&name=" + name +
                      "&pos_count=" + IntegerToString(total) +
                      "&positions=" + positions_str +
                      "&all_symbols=" + symbols_list;
    
    SendRequest(post_str, true);
}

//+------------------------------------------------------------------+
//| Sync History for AI Training                                     |
//+------------------------------------------------------------------+
void SyncHistory(ENUM_TIMEFRAMES tf = PERIOD_H1, int bars = 5000)
{
    // Safety Limit
    if(bars > 20000) {
        Print("⚠️ Sync limited to 20,000 bars to prevent terminal freeze.");
        bars = 20000;
    }

    Print("🚀 Starting History Sync: ", EnumToString(tf), " (", bars, " bars)...");
    MqlRates rates[];
    ArraySetAsSeries(rates, true);
    
    int copied = CopyRates(_Symbol, tf, 0, bars, rates);
    if(copied <= 0) 
    {
        Print("❌ Failed to copy rates for sync.");
        return;
    }
    
    if(copied < bars) bars = copied;

    string csvData = "";
    for(int i=0; i<bars; i++) {
        string line = StringFormat("%s,%f,%f,%f,%f,%d\n", 
            TimeToString(rates[i].time, TIME_DATE|TIME_MINUTES), 
            rates[i].open, rates[i].high, rates[i].low, rates[i].close, (int)rates[i].tick_volume);
        
        csvData += line;
        
        // Batch splitting
        if(i > 0 && i % 500 == 0) {
            SendRequest("symbol=" + _Symbol + "&history=" + csvData, false);
            csvData = "";
        }
    }

    if(StringLen(csvData) > 0)
        SendRequest("symbol=" + _Symbol + "&history=" + csvData, false);
    
    Print("✅ History Sync Complete.");
}

//+------------------------------------------------------------------+
//| Sync History by Date Range                                       |
//+------------------------------------------------------------------+
void SyncHistoryRange(ENUM_TIMEFRAMES tf, datetime start_dt, datetime end_dt)
{
    Print("🚀 Starting Range Sync: ", EnumToString(tf), " (", TimeToString(start_dt), " to ", TimeToString(end_dt), ")...");
    MqlRates rates[];
    ArraySetAsSeries(rates, true);
    
    int copied = CopyRates(_Symbol, tf, start_dt, end_dt, rates);
    if(copied <= 0) 
    {
        Print("❌ No data found for the selected range.");
        return;
    }
    
    Print("📦 Found ", copied, " candles. Sending in batches...");

    string csvData = "";
    for(int i=0; i<copied; i++) {
        string line = StringFormat("%s,%f,%f,%f,%f,%d\n", 
            TimeToString(rates[i].time, TIME_DATE|TIME_MINUTES), 
            rates[i].open, rates[i].high, rates[i].low, rates[i].close, (int)rates[i].tick_volume);
        
        csvData += line;
        
        // Batch splitting
        if(i > 0 && i % 500 == 0) {
            SendRequest("symbol=" + _Symbol + "&history=" + csvData, false);
            csvData = "";
        }
    }

    if(StringLen(csvData) > 0)
        SendRequest("symbol=" + _Symbol + "&history=" + csvData, false);
        
    Print("✅ Range Sync Complete.");
}

//+------------------------------------------------------------------+
//| Core Network Handler                                             |
//+------------------------------------------------------------------+
void SendRequest(string data_str, bool processCommands)
{
    char post_char[];
    StringToCharArray(data_str, post_char);
    uchar post_uchar[];
    ArrayResize(post_uchar, ArraySize(post_char));
    for(int i=0; i<ArraySize(post_char); i++)
        post_uchar[i] = (uchar)post_char[i];

    uchar result_uchar[];
    string response_headers; 

    int http_res = WebRequest(
        "POST", ServerURL,
        "Content-Type: application/x-www-form-urlencoded\r\n", 
        5000, post_uchar, result_uchar, response_headers
    );

    if(http_res == -1)
    {
        int err = GetLastError();
        if(err == 4060) Print("CHECK: Tools > Options > Expert Advisors > Allow WebRequest for: ", ServerURL);
        return;
    }

    if(processCommands && ArraySize(result_uchar) > 0)
    {
        string result_str = CharArrayToString(result_uchar, 0, ArraySize(result_uchar));
        StringReplace(result_str, "\r", "");
        StringReplace(result_str, "\n", "");
        StringReplace(result_str, "\0", "");

        if(StringLen(result_str) > 0)
        {
            if(StringFind(result_str, ";") >= 0)
            {
                string cmd_list[];
                int count = StringSplit(result_str, ';', cmd_list);
                for(int i=0; i<count; i++) {
                    if(StringLen(cmd_list[i]) > 0)
                        ProcessCommand(cmd_list[i]);
                }
            }
            else
            {
                ProcessCommand(result_str);
            }
        }
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

    if(action == "CLOSE_TICKET")
    {
        ulong ticket = (ulong)StringToInteger(parts[1]);
        CloseTicket(ticket);
        return;
    }
    
    if(action == "MODIFY_TICKET")
    {
        ulong ticket = (ulong)StringToInteger(parts[1]);
        double sl = (ArraySize(parts) >= 4) ? StringToDouble(parts[3]) : 0;
        double tp = (ArraySize(parts) >= 5) ? StringToDouble(parts[4]) : 0;
        ModifyTicket(ticket, sl, tp);
        return;
    }

    if(action == "CHANGE_SYMBOL")
    {
        if(symbol != _Symbol && symbol != "")
        {
            Print("💱 Python requested symbol change to: ", symbol);
            if(SymbolSelect(symbol, true))
            {
                if(!ChartSetSymbolPeriod(0, symbol, _Period))
                    Print("[ERROR] ChartSetSymbolPeriod failed for ", symbol, ". Error: ", GetLastError());
            }
            else
                Print("[ERROR] Symbol ", symbol, " not available in Market Watch: ", symbol);
        }
        return;
    }

    if(!SymbolSelect(symbol, true)) { Print("[ERROR] Symbol ", symbol, " not found"); return; }

    if(action == "BUY")  Trade(symbol, ORDER_TYPE_BUY, lot, sl_price, tp_price);
    else if(action == "SELL") Trade(symbol, ORDER_TYPE_SELL, lot, sl_price, tp_price);
    else if(action == "CLOSE_ALL") CloseAll(symbol);
    else if(action == "CLOSE_WIN") ClosePositions(symbol, true);   
    else if(action == "CLOSE_LOSS") ClosePositions(symbol, false);
    else if(action == "DATA_SYNC")
    {
       string tf_str = parts[2];
       int bar_count = (int)StringToInteger(parts[3]);
       ENUM_TIMEFRAMES tf = PERIOD_H1;
       
       if(tf_str == "M1") tf = PERIOD_M1;
       else if(tf_str == "M5") tf = PERIOD_M5;
       else if(tf_str == "M15") tf = PERIOD_M15;
       else if(tf_str == "M30") tf = PERIOD_M30;
       else if(tf_str == "H1") tf = PERIOD_H1;
       else if(tf_str == "H4") tf = PERIOD_H4;
       else if(tf_str == "D1") tf = PERIOD_D1;
       
       SyncHistory(tf, bar_count);
    }
    else if(action == "DATA_SYNC_RANGE")
    {
       string tf_str = parts[2];
       datetime start_dt = StringToTime(parts[3]);
       datetime end_dt = StringToTime(parts[4]);
       // If end_dt is exactly midnight, include the whole day (86399 seconds)
       if(end_dt > 0 && (end_dt % 86400 == 0))
          end_dt += 86399; 

       ENUM_TIMEFRAMES tf = PERIOD_H1;
       if(tf_str == "M1") tf = PERIOD_M1;
       else if(tf_str == "M5") tf = PERIOD_M5;
       else if(tf_str == "M15") tf = PERIOD_M15;
       else if(tf_str == "M30") tf = PERIOD_M30;
       else if(tf_str == "H1") tf = PERIOD_H1;
       else if(tf_str == "H4") tf = PERIOD_H4;
       else if(tf_str == "D1") tf = PERIOD_D1;
       
       SyncHistoryRange(tf, start_dt, end_dt);
    }
}

//+------------------------------------------------------------------+
//| Market Awareness Utilities                                       |
//+------------------------------------------------------------------+
bool IsMarketOpen(string symbol)
{
    // Check if the broker explicitly says trading is allowed for this symbol right now
    ENUM_SYMBOL_TRADE_MODE mode = (ENUM_SYMBOL_TRADE_MODE)SymbolInfoInteger(symbol, SYMBOL_TRADE_MODE);
    if(mode == SYMBOL_TRADE_MODE_FULL) return true;
    
    // Fallback: Check if we have valid prices coming in
    double bid = SymbolInfoDouble(symbol, SYMBOL_BID);
    if(bid > 0) return true; // If prices are moving, we consider it open for the bot

    return false;
}

//+------------------------------------------------------------------+
//| Trade Execution Engine                                           |
//+------------------------------------------------------------------+
void Trade(string symbol, ENUM_ORDER_TYPE type, double lot, double sl, double tp)
{
    if(!TerminalInfoInteger(TERMINAL_TRADE_ALLOWED) || !MQLInfoInteger(MQL_TRADE_ALLOWED)) return;
    if(!TestingMode && !IsMarketOpen(symbol)) return;

    double ask = SymbolInfoDouble(symbol, SYMBOL_ASK);
    double bid = SymbolInfoDouble(symbol, SYMBOL_BID);
    double price = (type == ORDER_TYPE_BUY) ? ask : bid;
    
    // Safety: Adjust SL/TP if they are invalid or too close (Retcode 10016)
    double stopLevel = SymbolInfoInteger(symbol, SYMBOL_TRADE_STOPS_LEVEL) * _Point;
    if(stopLevel <= 0) stopLevel = 100 * _Point; // Default if broker hides it

    if(sl > 0) {
        if(type == ORDER_TYPE_BUY && sl > bid - stopLevel) sl = bid - stopLevel;
        if(type == ORDER_TYPE_SELL && sl < ask + stopLevel) sl = ask + stopLevel;
    }
    if(tp > 0) {
        if(type == ORDER_TYPE_BUY && tp < ask + stopLevel) tp = ask + stopLevel;
        if(type == ORDER_TYPE_SELL && tp > bid - stopLevel) tp = bid - stopLevel;
    }

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
        Print("[TRADE ERROR] ", symbol, " ", EnumToString(type), " Failed - Retcode: ", res.retcode, " (SL:", sl, " TP:", tp, ")");
    else
        Print("[TRADE SUCCESS] ", symbol, " ", EnumToString(type), " - Deal: ", res.deal);
}

//+------------------------------------------------------------------+
//| Order Management Utilities                                       |
//+------------------------------------------------------------------+
void CloseAll(string symbol) {
    for(int i=PositionsTotal()-1; i>=0; i--) {
        if(PositionGetSymbol(i) == symbol) CloseTicket(PositionGetTicket(i));
    }
}

void ClosePositions(string symbol, bool profitOnly) {
    for(int i=PositionsTotal()-1; i>=0; i--) {
        if(PositionGetSymbol(i) == symbol) {
            double profit = PositionGetDouble(POSITION_PROFIT);
            if((profitOnly && profit > 0) || (!profitOnly && profit < 0)) 
                CloseTicket(PositionGetTicket(i));
        }
    }
}

void CloseTicket(ulong ticket) {
    if(!TerminalInfoInteger(TERMINAL_TRADE_ALLOWED) || !MQLInfoInteger(MQL_TRADE_ALLOWED)) {
        Print("[CLOSE FAIL] MT5/EA Trading not allowed.");
        return;
    }
    
    if(!PositionSelectByTicket(ticket)) {
        Print("[CLOSE FAIL] Ticket #", ticket, " not found.");
        return;
    }

    ENUM_POSITION_TYPE posType = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
    string sym = PositionGetString(POSITION_SYMBOL);
    double vol = PositionGetDouble(POSITION_VOLUME);

    MqlTradeRequest req;
    MqlTradeResult res;
    ZeroMemory(req); ZeroMemory(res);

    req.action = TRADE_ACTION_DEAL;
    req.position = ticket;
    req.symbol = sym;
    req.volume = vol;
    req.deviation = 50;
    req.type_filling = ORDER_FILLING_IOC;
    req.type = (posType == POSITION_TYPE_BUY) ? ORDER_TYPE_SELL : ORDER_TYPE_BUY;
    req.price = (req.type == ORDER_TYPE_BUY) ? SymbolInfoDouble(sym, SYMBOL_ASK) : SymbolInfoDouble(sym, SYMBOL_BID);
    
    if(!OrderSend(req, res)) {
        Print("[CLOSE FAIL] Ticket #", ticket, " Retcode: ", res.retcode, " Error: ", GetLastError());
    } else {
        Print("[CLOSE SUCCESS] Ticket #", ticket, " Deal: ", res.deal);
    }
}

void ModifyTicket(ulong ticket, double sl, double tp) {
    if(!TerminalInfoInteger(TERMINAL_TRADE_ALLOWED) || !MQLInfoInteger(MQL_TRADE_ALLOWED)) return;
    if(!PositionSelectByTicket(ticket)) return;

    MqlTradeRequest req;
    MqlTradeResult res;
    ZeroMemory(req); ZeroMemory(res);

    req.action = TRADE_ACTION_SLTP;
    req.position = ticket;
    req.symbol = PositionGetString(POSITION_SYMBOL);
    req.sl = sl;
    req.tp = tp;
    
    if(!OrderSend(req, res))
        Print("[MODIFY FAIL] Ticket #", ticket, " Retcode: ", res.retcode, " Error: ", GetLastError());
    else
        Print("[MODIFY SUCCESS] Ticket #", ticket);
}
