//+------------------------------------------------------------------+
//| Basket_Close_Manager.mq5                                         |
//| Closes a basket of positions (whole account, one symbol and/or   |
//| one magic number) when its floating P/L reaches a profit target, |
//| a loss limit, a trailing profit lock, or a set time.             |
//| Never opens trades itself (except the tester demo, see below).   |
//|                                                                   |
//| - basket P/L = profit + swap (+ optional commission estimate     |
//|   per lot), in money and as % of the balance                     |
//| - targets in money and/or %: take profit, stop loss              |
//| - trailing lock: after the basket reaches InpTrailStart, close   |
//|   if it gives back InpTrailGive from its peak                    |
//| - time exits: every day at HHMM and/or Friday at HHMM (server)   |
//| - after a close: keep watching, pause until the next day, or     |
//|   remove the EA from the chart                                   |
//| - basket peak is kept in a terminal global variable, so a        |
//|   restart does not reset the trailing lock                       |
//| - InpDemoTrades (Strategy Tester only): opens random trades so   |
//|   you can watch the manager close them                           |
//+------------------------------------------------------------------+
#property copyright "A.parinya"
#property version   "1.00"
#property description "Closes a basket of positions at a money / % profit target, loss limit, trailing profit lock or set time (does not trade)"

#include <Trade/Trade.mqh>

enum ENUM_SCOPE
  {
   SCOPE_ACCOUNT = 0, // Whole account (all symbols)
   SCOPE_SYMBOL  = 1  // Chart symbol only
  };
enum ENUM_AFTER
  {
   AFTER_CONTINUE = 0, // Keep watching new trades
   AFTER_NEXTDAY  = 1, // Pause until the next server day
   AFTER_REMOVE   = 2  // Remove the EA from the chart
  };

input group "Basket"
input ENUM_SCOPE InpScope       = SCOPE_ACCOUNT;  // Positions to manage
input long       InpMagic       = -1;             // Magic number (-1 = any, 0 = manual trades only)
input double     InpCommPerLot  = 0;              // Round-turn commission per lot to add to P/L (0 = ignore)
input bool       InpDelPending  = false;          // Also delete matching pending orders on a close
input group "Exits (0 = off)"
input double     InpTPMoney     = 0;              // Take profit, account currency
input double     InpTPPct       = 0;              // Take profit, % of balance
input double     InpSLMoney     = 0;              // Loss limit, account currency (positive number)
input double     InpSLPct       = 0;              // Loss limit, % of balance (positive number)
input double     InpTrailStart  = 0;              // Trailing lock starts at this basket profit (money)
input double     InpTrailGive   = 0;              // ... close if the basket gives back this much from its peak (money)
input int        InpDailyHM     = 0;              // Close every day at this server time HHMM
input int        InpFridayHM    = 0;              // Close on Friday at this server time HHMM
input group "After a close"
input ENUM_AFTER InpAfter       = AFTER_CONTINUE; // What to do next
input group "Execution / display"
input int        InpDeviation   = 50;             // Max slippage when closing (points)
input int        InpRetries     = 3;              // Close attempts per position
input bool       InpPanel       = true;           // Status panel on the chart
input bool       InpPush        = false;          // Push notification on every close
input bool       InpDemoTrades  = false;          // Strategy Tester only: open random trades to test the exits

CTrade   g_trade;
string   g_peakVar;
double   g_peak = 0;
datetime g_pausedDay = 0;
datetime g_lastTimeExit = 0;
string   g_lastReason = "-";
string   g_pending = "";          // exit decided, waiting until every position is closed
double   g_pendingPL = 0;
datetime g_pendingAt = 0, g_lastWarn = 0;
const string PANEL = "BCM_panel";

//+------------------------------------------------------------------+
bool Match(string sym, long magic)
  {
   if(InpScope == SCOPE_SYMBOL && sym != _Symbol)
      return false;
   if(InpMagic >= 0 && magic != InpMagic)
      return false;
   return true;
  }

//--- floating P/L of the basket and its position count
double BasketPL(int &count, double &lots)
  {
   double pl = 0;
   count = 0;
   lots = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong t = PositionGetTicket(i);
      if(!t || !Match(PositionGetString(POSITION_SYMBOL), PositionGetInteger(POSITION_MAGIC)))
         continue;
      double v = PositionGetDouble(POSITION_VOLUME);
      pl += PositionGetDouble(POSITION_PROFIT) + PositionGetDouble(POSITION_SWAP) - InpCommPerLot * v;
      lots += v;
      count++;
     }
   return pl;
  }

//--- true when the symbol's trading session is open now (closing in a closed session only fails)
bool SessionOpen(string sym)
  {
   MqlDateTime t;
   TimeToStruct(TimeCurrent(), t);
   datetime sec = (datetime)(t.hour * 3600 + t.min * 60 + t.sec), from, to;
   for(uint i = 0; SymbolInfoSessionTrade(sym, (ENUM_DAY_OF_WEEK)t.day_of_week, i, from, to); i++)
      if(sec >= from && (sec < to || to <= from))
         return true;
   return false;
  }

//--- every symbol in the basket can be traded right now
bool BasketTradable()
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong t = PositionGetTicket(i);
      if(t && Match(PositionGetString(POSITION_SYMBOL), PositionGetInteger(POSITION_MAGIC)) && !SessionOpen(PositionGetString(POSITION_SYMBOL)))
         return false;
     }
   return true;
  }

datetime Today() { return iTime(_Symbol, PERIOD_D1, 0) > 0 ? iTime(_Symbol, PERIOD_D1, 0) : TimeCurrent() - TimeCurrent() % 86400; }

int ServerHM() { MqlDateTime t; TimeToStruct(TimeCurrent(), t); return t.hour * 100 + t.min; }

//--- true once per day when the server time passes HHMM (and only on Friday if fridayOnly)
bool TimeExitDue(int hm, bool fridayOnly)
  {
   if(hm <= 0)
      return false;
   MqlDateTime t;
   TimeToStruct(TimeCurrent(), t);
   if(fridayOnly && t.day_of_week != 5)
      return false;
   return ServerHM() >= hm && g_lastTimeExit < Today();
  }

void SavePeak()
  {
   if(GlobalVariableCheck(g_peakVar) && GlobalVariableGet(g_peakVar) == g_peak)
      return;
   GlobalVariableSet(g_peakVar, g_peak);
  }

//--- close every matching position (and pending orders if asked); returns the number left open
int CloseBasket()
  {
   for(int pass = 0; pass < MathMax(1, InpRetries); pass++)
     {
      for(int i = PositionsTotal() - 1; i >= 0; i--)
        {
         ulong t = PositionGetTicket(i);
         if(!t || !Match(PositionGetString(POSITION_SYMBOL), PositionGetInteger(POSITION_MAGIC)))
            continue;
         if(!g_trade.PositionClose(t))
            PrintFormat("close #%I64u failed: %d %s", t, g_trade.ResultRetcode(), g_trade.ResultRetcodeDescription());
        }
      if(InpDelPending)
         for(int i = OrdersTotal() - 1; i >= 0; i--)
           {
            ulong o = OrderGetTicket(i);
            if(o && Match(OrderGetString(ORDER_SYMBOL), OrderGetInteger(ORDER_MAGIC)))
               g_trade.OrderDelete(o);
           }
      int n;
      double lots;
      BasketPL(n, lots);
      if(n == 0)
         return 0;
      Sleep(300);
     }
   int left;
   double lots;
   BasketPL(left, lots);
   return left;
  }

//--- an exit was hit: close the basket now, or as soon as its symbols are tradable again
void Fire(string reason, double pl)
  {
   if(g_pending == "")
     {
      g_pending = reason;
      g_pendingPL = pl;
      g_pendingAt = TimeCurrent();
      PrintFormat("Basket Close Manager: %s hit, P/L %.2f - closing the basket", reason, pl);
     }
   if(!BasketTradable())
     {
      if(TimeCurrent() - g_lastWarn >= 600)
        {
         g_lastWarn = TimeCurrent();
         Print("Basket Close Manager: market closed for a basket symbol - will close when it reopens");
        }
      return;
     }
   int left = CloseBasket();
   if(left > 0)
     {
      if(TimeCurrent() - g_lastWarn >= 60)
        {
         g_lastWarn = TimeCurrent();
         PrintFormat("Basket Close Manager: %d position(s) still open - retrying", left);
        }
      return;                                                   // retry on the next tick / second
     }
   g_lastReason = StringFormat("%s at %s, P/L %.2f %s", g_pending, TimeToString(g_pendingAt, TIME_DATE | TIME_MINUTES), g_pendingPL, AccountInfoString(ACCOUNT_CURRENCY));
   string msg = "Basket Close Manager: closed - " + g_lastReason;
   Print(msg);
   if(InpPush && !MQLInfoInteger(MQL_TESTER))
      SendNotification(msg);
   g_pending = "";
   g_peak = 0;
   SavePeak();
   if(InpAfter == AFTER_NEXTDAY)
      g_pausedDay = Today();
   else
      if(InpAfter == AFTER_REMOVE)
         ExpertRemove();
  }

//+------------------------------------------------------------------+
void Panel(double pl, int n, double lots, double bal)
  {
   if(!InpPanel)
      return;
   string cur = AccountInfoString(ACCOUNT_CURRENCY);
   string scope = (InpScope == SCOPE_SYMBOL ? _Symbol : "all symbols") + (InpMagic < 0 ? ", any magic" : InpMagic == 0 ? ", manual" : StringFormat(", magic %I64d", InpMagic));
   string lock = "off";
   if(InpTrailStart > 0 && InpTrailGive > 0)
      lock = g_peak >= InpTrailStart ? StringFormat("%.2f (peak %.2f)", g_peak - InpTrailGive, g_peak) : StringFormat("arms at %.2f", InpTrailStart);
   string tp = "", sl = "";
   if(InpTPMoney > 0) tp += StringFormat("%.2f ", InpTPMoney);
   if(InpTPPct > 0)   tp += StringFormat("%.2f%% ", InpTPPct);
   if(InpSLMoney > 0) sl += StringFormat("-%.2f ", InpSLMoney);
   if(InpSLPct > 0)   sl += StringFormat("-%.2f%% ", InpSLPct);
   string state = g_pending != "" ? "CLOSING: " + g_pending : g_pausedDay == Today() ? "PAUSED until next day" : "watching";
   string txt = StringFormat("Basket Close Manager  [%s]\nBasket: %s\nPositions: %d  lots %.2f\nP/L: %.2f %s (%.2f%%)\nTake profit: %s\nLoss limit: %s\nTrailing lock: %s\nLast close: %s",
                             state, scope, n, lots, pl, cur, bal > 0 ? 100 * pl / bal : 0,
                             tp == "" ? "off" : tp, sl == "" ? "off" : sl, lock, g_lastReason);
   Comment(txt);
  }

//--- tester demo: random market orders with no SL/TP so the exits have something to close
void DemoTrades()
  {
   static datetime last = 0;
   if(!InpDemoTrades || !MQLInfoInteger(MQL_TESTER) || TimeCurrent() - last < 3600 || !SessionOpen(_Symbol) || g_pausedDay == Today() || g_pending != "")
      return;
   last = TimeCurrent();
   int n;
   double lots;
   BasketPL(n, lots);
   if(n >= 5 || MathRand() % 3 != 0)
      return;
   double vol = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   g_trade.SetExpertMagicNumber(InpMagic > 0 ? InpMagic : 0);
   if(MathRand() % 2 == 0)
      g_trade.Buy(vol, _Symbol);
   else
      g_trade.Sell(vol, _Symbol);
  }

//+------------------------------------------------------------------+
void Check()
  {
   DemoTrades();
   int n;
   double lots;
   double pl = BasketPL(n, lots);
   double bal = AccountInfoDouble(ACCOUNT_BALANCE);
   if(g_pausedDay != 0 && g_pausedDay != Today())
      g_pausedDay = 0;
   if(g_pending != "")
     {
      Fire(g_pending, g_pendingPL);                              // also finishes the bookkeeping if closed elsewhere
      pl = BasketPL(n, lots);
      Panel(pl, n, lots, bal);
      return;
     }
   if(n == 0)
     {
      if(g_peak != 0)
        {
         g_peak = 0;
         SavePeak();
        }
      if(TimeExitDue(InpDailyHM, false) || TimeExitDue(InpFridayHM, true))
         g_lastTimeExit = Today();                             // nothing to close today
      Panel(pl, n, lots, bal);
      return;
     }
   if(g_pausedDay == Today())
     {
      Fire("paused day: new trade closed", pl);                // keep the basket flat while paused
      Panel(0, 0, 0, bal);
      return;
     }
   if(pl > g_peak)
     {
      g_peak = pl;
      SavePeak();
     }
   string why = "";
   if(InpTPMoney > 0 && pl >= InpTPMoney)
      why = "take profit (money)";
   else if(InpTPPct > 0 && bal > 0 && pl >= bal * InpTPPct / 100)
      why = "take profit (%)";
   else if(InpSLMoney > 0 && pl <= -InpSLMoney)
      why = "loss limit (money)";
   else if(InpSLPct > 0 && bal > 0 && pl <= -bal * InpSLPct / 100)
      why = "loss limit (%)";
   else if(InpTrailStart > 0 && InpTrailGive > 0 && g_peak >= InpTrailStart && pl <= g_peak - InpTrailGive)
      why = "trailing lock";
   else if(TimeExitDue(InpFridayHM, true))
      why = "Friday time exit";
   else if(TimeExitDue(InpDailyHM, false))
      why = "daily time exit";
   if(why != "")
     {
      if(StringFind(why, "time exit") >= 0)
         g_lastTimeExit = Today();
      Fire(why, pl);
      pl = BasketPL(n, lots);
     }
   Panel(pl, n, lots, bal);
  }

//+------------------------------------------------------------------+
int OnInit()
  {
   if(InpSLMoney < 0 || InpSLPct < 0 || InpTPMoney < 0 || InpTPPct < 0 || InpTrailGive < 0 || InpTrailStart < 0)
     {
      Print("Basket Close Manager: use positive numbers for every target and limit");
      return INIT_PARAMETERS_INCORRECT;
     }
   if((InpTrailStart > 0) != (InpTrailGive > 0))
      Print("Basket Close Manager: the trailing lock needs both InpTrailStart and InpTrailGive - it is off");
   if(InpTrailStart > 0 && InpTrailGive >= InpTrailStart)
      Print("Basket Close Manager: InpTrailGive >= InpTrailStart, the lock can close the basket at a loss");
   g_trade.SetDeviationInPoints(InpDeviation);
   g_trade.SetAsyncMode(false);
   g_peakVar = StringFormat("BCM_peak_%I64d_%s_%I64d", AccountInfoInteger(ACCOUNT_LOGIN), InpScope == SCOPE_SYMBOL ? _Symbol : "ALL", InpMagic);
   if(MQLInfoInteger(MQL_TESTER))
      GlobalVariableDel(g_peakVar);
   g_peak = GlobalVariableCheck(g_peakVar) ? GlobalVariableGet(g_peakVar) : 0;
   if(MQLInfoInteger(MQL_TESTER))
      MathSrand(12345);
   EventSetTimer(1);
   Check();
   return INIT_SUCCEEDED;
  }

void OnDeinit(const int reason)
  {
   EventKillTimer();
   Comment("");
  }

void OnTick()  { Check(); }
void OnTimer() { Check(); }
//+------------------------------------------------------------------+
