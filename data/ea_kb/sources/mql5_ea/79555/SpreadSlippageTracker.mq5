//+------------------------------------------------------------------+
//|                                   SpreadSlippageTracker.mq5      |
//|                            Copyright 2026, Omowumi Deborah Adebayo|
//|                                             https://www.mql5.com |
//+------------------------------------------------------------------+
#property copyright "Omowumi Deborah Adebayo"
#property link      "https://www.mql5.com"
#property version   "1.00"
#property description "Live spread stats plus real fill-vs-requested slippage logging, account-wide"
#property strict

//--- NOTE: this is an Expert Advisor, not an indicator - it places no
//--- orders of its own. Slippage (requested price vs actual fill price)
//--- only exists as data on OnTradeTransaction, which indicators never
//--- receive, so an EA shell is the only vehicle that can see it. The
//--- spread side runs on running sums updated in OnTick (no array/
//--- history rescans), and slippage is purely event-driven off real
//--- deals - neither path polls or rescans anything per tick.

//--- input group: spread tracking
input group "Spread tracking";
input bool InpResetStatsDaily = true; // Reset min/avg/max spread stats at the start of each new trading day

//--- input group: slippage tracking
input group "Slippage tracking";
input bool InpTrackAllSymbols      = false; // Track slippage on every symbol traded on this account, not just the chart's own
input int  InpSlippageAlertPoints  = 0;     // Alert when a single deal's adverse slippage exceeds this many points (0 = off)
input bool InpLogToFile            = true;  // Append every tracked deal's slippage to a CSV log

//--- input group: panel
input group "Panel";
input ENUM_BASE_CORNER InpCorner = CORNER_LEFT_UPPER; // Readout panel corner
input int InpCornerX = 20; // Panel X offset, pixels
input int InpCornerY = 20; // Panel Y offset, pixels

//--- globals: spread running stats (no per-tick array kept, just sums)
string   g_prefix;
long     g_curSpreadPts  = 0;
long     g_minSpreadPts  = 0;
long     g_maxSpreadPts  = 0;
long     g_sumSpreadPts  = 0;
long     g_spreadSamples = 0;
datetime g_statsDay      = 0;

//--- globals: slippage running stats, cumulative since this EA attached
long   g_dealCount         = 0;
double g_sumSlipPts        = 0.0;
double g_maxAdverseSlipPts = 0.0;
int    g_fileHandle        = INVALID_HANDLE;

//+------------------------------------------------------------------+
//| Reset the spread min/max/sum block for a new tracking window     |
//+------------------------------------------------------------------+
void ResetSpreadStats()
  {
   g_minSpreadPts  = 0;
   g_maxSpreadPts  = 0;
   g_sumSpreadPts  = 0;
   g_spreadSamples = 0;
  }

//+------------------------------------------------------------------+
//| Create or refresh the on-chart readout - cheap text update only  |
//+------------------------------------------------------------------+
void UpdatePanel()
  {
   double avgSpread = (g_spreadSamples > 0) ? (double)g_sumSpreadPts / g_spreadSamples : 0.0;
   double avgSlip    = (g_dealCount > 0) ? g_sumSlipPts / g_dealCount : 0.0;

   string txt = StringFormat(
      "Spread  now:%d  min:%d  avg:%.1f  max:%d\nSlippage  deals:%d  avg:%.1f  worst:%.1f pts",
      (int)g_curSpreadPts, (int)g_minSpreadPts, avgSpread, (int)g_maxSpreadPts,
      (int)g_dealCount, avgSlip, g_maxAdverseSlipPts);

   string name = g_prefix + "Panel";
   if(ObjectFind(ChartID(), name) < 0)
     {
      ObjectCreate(ChartID(), name, OBJ_LABEL, 0, 0, 0);
      ObjectSetInteger(ChartID(), name, OBJPROP_CORNER, InpCorner);
      ObjectSetInteger(ChartID(), name, OBJPROP_XDISTANCE, InpCornerX);
      ObjectSetInteger(ChartID(), name, OBJPROP_YDISTANCE, InpCornerY);
      ObjectSetString(ChartID(), name, OBJPROP_FONT, "Consolas");
      ObjectSetInteger(ChartID(), name, OBJPROP_FONTSIZE, 9);
      ObjectSetInteger(ChartID(), name, OBJPROP_COLOR, clrSilver);
     }
   ObjectSetString(ChartID(), name, OBJPROP_TEXT, txt);
  }

//+------------------------------------------------------------------+
//| Append one tracked deal's slippage to the CSV log                |
//+------------------------------------------------------------------+
void LogDeal(const string sym, const ulong dealTicket, const string side,
             const double reqPrice, const double fillPrice, const double slipPts, const int digits)
  {
   if(g_fileHandle == INVALID_HANDLE)
      return;

   FileSeek(g_fileHandle, 0, SEEK_END);
   FileWrite(g_fileHandle,
             TimeToString(TimeCurrent(), TIME_DATE | TIME_SECONDS),
             sym,
             IntegerToString((long)dealTicket),
             side,
             DoubleToString(reqPrice, digits),
             DoubleToString(fillPrice, digits),
             DoubleToString(slipPts, 1));
   FileFlush(g_fileHandle);
  }

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
  {
   g_prefix = "SST_" + IntegerToString((int)ChartID()) + "_";

   ResetSpreadStats();
   g_statsDay = iTime(_Symbol, PERIOD_D1, 0);

   if(InpLogToFile)
     {
      string folder = "SpreadSlippageTracker";
      FolderCreate(folder);
      string path = folder + "\\slippage_log.csv";
      g_fileHandle = FileOpen(path, FILE_READ | FILE_WRITE | FILE_CSV | FILE_ANSI, ',');
      if(g_fileHandle == INVALID_HANDLE)
         Print("SpreadSlippageTracker: failed to open log file, error ", GetLastError());
      else
        {
         FileSeek(g_fileHandle, 0, SEEK_END);
         if(FileTell(g_fileHandle) == 0)
            FileWrite(g_fileHandle, "time", "symbol", "deal", "side", "requested", "filled", "slippage_pts");
        }
     }

   UpdatePanel();
   return INIT_SUCCEEDED;
  }

//+------------------------------------------------------------------+
//| Expert tick function - spread side only, running sums, no scans |
//+------------------------------------------------------------------+
void OnTick()
  {
   if(InpResetStatsDaily)
     {
      datetime today = iTime(_Symbol, PERIOD_D1, 0);
      if(today != g_statsDay)
        {
         g_statsDay = today;
         ResetSpreadStats();
        }
     }

   long spreadPts = SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
   g_curSpreadPts = spreadPts;

   if(g_spreadSamples == 0)
     {
      g_minSpreadPts = spreadPts;
      g_maxSpreadPts = spreadPts;
     }
   else
     {
      if(spreadPts < g_minSpreadPts)
         g_minSpreadPts = spreadPts;
      if(spreadPts > g_maxSpreadPts)
         g_maxSpreadPts = spreadPts;
     }
   g_sumSpreadPts += spreadPts;
   g_spreadSamples++;

   UpdatePanel();
  }

//+------------------------------------------------------------------+
//| Fires on every real trade transaction on the account - this is  |
//| where slippage actually gets measured, requested vs filled      |
//+------------------------------------------------------------------+
void OnTradeTransaction(const MqlTradeTransaction &trans,
                        const MqlTradeRequest &request,
                        const MqlTradeResult &result)
  {
   if(trans.type != TRADE_TRANSACTION_DEAL_ADD)
      return;
   if(!InpTrackAllSymbols && trans.symbol != _Symbol)
      return;

   ulong dealTicket = trans.deal;
   if(!HistoryDealSelect(dealTicket))
      return;

   string sym       = HistoryDealGetString(dealTicket, DEAL_SYMBOL);
   long   dealType  = HistoryDealGetInteger(dealTicket, DEAL_TYPE);
   double fillPrice = HistoryDealGetDouble(dealTicket, DEAL_PRICE);
   ulong  orderTicket = (ulong)HistoryDealGetInteger(dealTicket, DEAL_ORDER);

   if(dealType != DEAL_TYPE_BUY && dealType != DEAL_TYPE_SELL)
      return; // balance/credit/correction entries carry no fill price to compare

   double reqPrice = fillPrice; // fallback if the originating order can't be read
   if(orderTicket > 0 && HistoryOrderSelect(orderTicket))
      reqPrice = HistoryOrderGetDouble(orderTicket, ORDER_PRICE_OPEN);

   double point = SymbolInfoDouble(sym, SYMBOL_POINT);
   if(point <= 0.0)
      return;

   double slipPts = (dealType == DEAL_TYPE_BUY) ? (fillPrice - reqPrice) / point
                                                  : (reqPrice - fillPrice) / point;

   g_dealCount++;
   g_sumSlipPts += slipPts;
   if(slipPts > g_maxAdverseSlipPts)
      g_maxAdverseSlipPts = slipPts;

   int digits = (int)SymbolInfoInteger(sym, SYMBOL_DIGITS);
   string side = (dealType == DEAL_TYPE_BUY) ? "BUY" : "SELL";

   if(InpLogToFile)
      LogDeal(sym, dealTicket, side, reqPrice, fillPrice, slipPts, digits);

   if(InpSlippageAlertPoints > 0 && slipPts >= InpSlippageAlertPoints)
     {
      string msg = StringFormat("%s deal #%s slipped %.1f pts (requested %s, filled %s)",
                                 sym, IntegerToString((long)dealTicket), slipPts,
                                 DoubleToString(reqPrice, digits), DoubleToString(fillPrice, digits));
      Print("SpreadSlippageTracker: ", msg);
      Alert(msg);
     }

   UpdatePanel();
  }

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   if(g_fileHandle != INVALID_HANDLE)
      FileClose(g_fileHandle);
   ObjectsDeleteAll(ChartID(), g_prefix);
   ChartRedraw(ChartID());
  }
//+------------------------------------------------------------------+
