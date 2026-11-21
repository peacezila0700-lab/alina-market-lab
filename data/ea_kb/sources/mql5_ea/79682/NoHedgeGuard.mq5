//+------------------------------------------------------------------+
//|                                                 NoHedgeGuard.mq5 |
//|  Keeps a hedging account free of hedges: if a buy and a sell are |
//|  open on the same symbol at the same time (from any EA or        |
//|  manual), it closes the newer side at once. Many prop firms      |
//|  forbid hedging; two EAs on one symbol can create a hedge by     |
//|  accident.                                                       |
//|                                                                  |
//|  Attach to ONE chart. It reacts to every trade event and also    |
//|  checks once per second. It never opens trades.                  |
//+------------------------------------------------------------------+
#property copyright "Augusto Martin D'anna"
#property version   "1.00"
#property description "Closes the newer side when a buy and a sell are open on the same symbol (manual or any EA)."
#property description "For prop firm accounts that forbid hedging. Never opens trades."

#include <Trade/Trade.mqh>

enum ENUM_GUARD_ACTION
  {
   ACTION_CLOSE = 0, // Close the newer opposite position
   ACTION_ALERT = 1  // Alert only, do not close
  };

enum ENUM_GUARD_SCOPE
  {
   SCOPE_ALL   = 0, // All symbols of the account
   SCOPE_CHART = 1  // Only the chart symbol
  };

input ENUM_GUARD_ACTION InpAction  = ACTION_CLOSE; // When a hedge appears
input ENUM_GUARD_SCOPE  InpScope   = SCOPE_ALL;    // Symbols to watch
input string            InpMagics  = "";           // Only these magic numbers, comma separated (empty = all, 0 = manual)
input bool              InpPopup   = true;         // Show a popup alert
input bool              InpPanel   = true;         // Show status on the chart

CTrade g_trade;
long   g_magics[];
int    g_closed = 0;
string g_last = "none";

bool Watched(long magic)
  {
   int n = ArraySize(g_magics);
   if(n == 0) return true;
   for(int i = 0; i < n; i++) if(g_magics[i] == magic) return true;
   return false;
  }

void ParseMagics()
  {
   string parts[];
   int n = StringSplit(InpMagics, ',', parts);
   ArrayResize(g_magics, 0);
   for(int i = 0; i < n; i++)
     {
      string s = parts[i];
      StringTrimLeft(s); StringTrimRight(s);
      if(s == "") continue;
      int k = ArraySize(g_magics);
      ArrayResize(g_magics, k + 1);
      g_magics[k] = StringToInteger(s);
     }
  }

// Close the positions of `symbol` that are opposite to its oldest watched position
void FixSymbol(const string symbol)
  {
   ulong  oldest = 0;
   long   oldestMs = LONG_MAX;
   int    oldestDir = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong t = PositionGetTicket(i);
      if(t == 0 || PositionGetString(POSITION_SYMBOL) != symbol || !Watched(PositionGetInteger(POSITION_MAGIC))) continue;
      long ms = PositionGetInteger(POSITION_TIME_MSC);
      if(ms < oldestMs) { oldestMs = ms; oldest = t; oldestDir = PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY ? 1 : -1; }
     }
   if(oldest == 0) return;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong t = PositionGetTicket(i);
      if(t == 0 || PositionGetString(POSITION_SYMBOL) != symbol || !Watched(PositionGetInteger(POSITION_MAGIC))) continue;
      int dir = PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY ? 1 : -1;
      if(dir == oldestDir) continue;
      long magic = PositionGetInteger(POSITION_MAGIC);
      double vol = PositionGetDouble(POSITION_VOLUME);
      string msg = StringFormat("Hedge on %s: %s %.2f (magic %I64d) is opposite to the older %s position",
                                symbol, dir > 0 ? "buy" : "sell", vol, magic, oldestDir > 0 ? "buy" : "sell");
      if(InpAction == ACTION_ALERT)
        {
         if(g_last != msg) { Print(msg); if(InpPopup) Alert(msg); g_last = msg; }
         continue;
        }
      if(g_trade.PositionClose(t))
        {
         g_closed++;
         g_last = msg + " -> closed";
         Print(g_last);
         if(InpPopup) Alert(g_last);
        }
      else
         PrintFormat("%s -> close failed: %d %s", msg, g_trade.ResultRetcode(), g_trade.ResultRetcodeDescription());
     }
  }

void CheckAll()
  {
   if(InpScope == SCOPE_CHART) { FixSymbol(_Symbol); return; }
   string done = ";";
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      if(PositionGetTicket(i) == 0) continue;
      string s = PositionGetString(POSITION_SYMBOL);
      if(StringFind(done, ";" + s + ";") >= 0) continue;
      done += s + ";";
      FixSymbol(s);
     }
  }

void Panel()
  {
   if(!InpPanel) return;
   Comment(StringFormat("No Hedge Guard\nWatching: %s%s\nAction: %s\nClosed so far: %d\nLast: %s",
                        InpScope == SCOPE_ALL ? "all symbols" : _Symbol,
                        InpMagics == "" ? "" : " (magic " + InpMagics + ")",
                        InpAction == ACTION_CLOSE ? "close the newer side" : "alert only", g_closed, g_last));
  }

int OnInit()
  {
   if(AccountInfoInteger(ACCOUNT_MARGIN_MODE) != ACCOUNT_MARGIN_MODE_RETAIL_HEDGING)
      Print("This is a netting account: it cannot hold a buy and a sell on the same symbol, so there is nothing to guard.");
   ParseMagics();
   g_trade.SetDeviationInPoints(50);
   EventSetTimer(1);
   CheckAll();
   Panel();
   return INIT_SUCCEEDED;
  }

void OnDeinit(const int reason) { EventKillTimer(); Comment(""); }

void OnTradeTransaction(const MqlTradeTransaction &tr, const MqlTradeRequest &rq, const MqlTradeResult &rs)
  {
   if(tr.type == TRADE_TRANSACTION_DEAL_ADD) { CheckAll(); Panel(); }
  }

void OnTimer() { CheckAll(); Panel(); }
void OnTick()  {}
//+------------------------------------------------------------------+
