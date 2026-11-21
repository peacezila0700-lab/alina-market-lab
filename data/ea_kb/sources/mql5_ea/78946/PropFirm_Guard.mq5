//+------------------------------------------------------------------+
//| PropFirm_Guard.mq5                                               |
//| Protects a prop-firm challenge account: closes every position    |
//| and pending order BEFORE the daily loss limit or the max         |
//| drawdown is breached, then keeps the account flat (any new trade |
//| from any EA or by hand is closed at once) until the block ends.  |
//| Never opens trades itself (except the tester demo, see below).   |
//|                                                                   |
//| - attach to ANY one chart; it watches the whole account (all     |
//|   symbols, all magics, manual trades) on every tick + every sec  |
//| - daily limit: from the balance (or the higher of balance and    |
//|   equity) at the start of the trading day, InpResetHour server   |
//|   time; amount = % of the initial balance (FTMO style) or % of   |
//|   the day-start value                                            |
//| - max drawdown: static (initial balance) or trailing (equity or  |
//|   balance high), optionally locked at the initial balance        |
//| - InpTriggerPct: act early, e.g. 90 = flatten at 90% of a limit  |
//|   (5% daily -> flatten at -4.5%) to leave room for slippage      |
//| - daily breach: blocked until the next trading day; max DD or    |
//|   profit target: blocked until InpUnblock = true                 |
//| - state (initial balance, day start, peak, block) is kept in     |
//|   terminal global variables, so a restart does not reset it      |
//| - InpDemoTrades (Strategy Tester only): opens random trades so   |
//|   you can watch the guard stop them                              |
//| - limits: a gap (weekend, daily break) or a news spike can jump  |
//|   past the buffer before any EA can close - use InpFridayHM /    |
//|   InpDailyHM and keep risk per trade well below the buffer       |
//+------------------------------------------------------------------+
#property copyright "A.parinya"
#property version   "1.00"
#property description "Prop-firm guard: flattens and blocks the account before the daily loss / max drawdown limit is hit (does not trade)"

#include <Trade/Trade.mqh>

enum ENUM_DAY_BASE
  {
   DAY_BALANCE = 0,  // Day-start balance
   DAY_MAX_BE  = 1   // Higher of day-start balance and equity
  };
enum ENUM_DD_MODE
  {
   DD_STATIC     = 0, // Static (from initial balance)
   DD_TRAIL_EQ   = 1, // Trailing equity high
   DD_TRAIL_BAL  = 2  // Trailing balance high
  };

input group "Challenge rules"
input double        InpInitBalance = 0;            // Initial balance (0 = balance when first attached)
input double        InpDailyPct    = 5.0;          // Max daily loss % (0 = off)
input ENUM_DAY_BASE InpDayBase     = DAY_MAX_BE;   // Daily loss measured from
input bool          InpDailyOfInit = true;         // Daily amount = % of initial balance (false = % of day base)
input double        InpMaxDDPct    = 10.0;         // Max drawdown % of initial balance (0 = off)
input ENUM_DD_MODE  InpDDMode      = DD_STATIC;    // Max drawdown type
input bool          InpTrailLock   = true;         // Trailing floor stops at the initial balance
input double        InpTargetPct   = 0;            // Profit target % -> flatten and stop (0 = off)
input group "Safety"
input double        InpTriggerPct  = 90.0;         // Flatten at this % of a limit (buffer for slippage)
input int           InpResetHour   = 0;            // Trading day starts at this server hour
input int           InpFridayHM    = 0;            // Flatten on Friday at this server time HHMM (0 = off)
input int           InpDailyHM     = 0;            // Flatten every day at this server time HHMM, before the daily break (0 = off)
input int           InpDeviation   = 50;           // Max slippage when closing (points)
input bool          InpUnblock     = false;        // true = clear a max-DD / target block (new challenge)
input group "Display"
input bool          InpPanel       = true;         // Show the status panel on the chart
input bool          InpPush        = true;         // Push notification to the MT5 mobile app on breach
input group "Tester demo"
input bool          InpDemoTrades  = false;        // Strategy Tester only: open random trades to test the guard
input double        InpDemoLots    = 0.3;          // Lots per demo trade
input int           InpDemoMaxSpr  = 60;           // Demo trades only when spread <= this (points)

#define BLOCK_FOREVER D'3000.01.01'

CTrade   g_trade;
string   g_pfx;
double   g_init, g_dayBase, g_peak;
datetime g_dayStart, g_block;
string   g_reason = "";

//+------------------------------------------------------------------+
//| Read a saved state value (terminal global variable)              |
//+------------------------------------------------------------------+
double GVGet(string k, double def)
  {
   return GlobalVariableCheck(g_pfx + k) ? GlobalVariableGet(g_pfx + k) : def;
  }
//+------------------------------------------------------------------+
//| Write a state value                                              |
//+------------------------------------------------------------------+
void GVSet(string k, double v)
  {
   GlobalVariableSet(g_pfx + k, v);
  }

//+------------------------------------------------------------------+
//| Save the whole state, so a restart does not reset it             |
//+------------------------------------------------------------------+
void SaveState()
  {
   GVSet("init", g_init);
   GVSet("dayStart", (double)g_dayStart);
   GVSet("dayBase", g_dayBase);
   GVSet("peak", g_peak);
   GVSet("block", (double)g_block);
  }

//+------------------------------------------------------------------+
//| Start of the current trading day (server time)                   |
//+------------------------------------------------------------------+
datetime DayStart(datetime now)
  {
   MqlDateTime t;
   TimeToStruct(now, t);
   t.hour = InpResetHour;
   t.min  = 0;
   t.sec  = 0;
   datetime d = StructToTime(t);
   return now < d ? d - 86400 : d;
  }

//+------------------------------------------------------------------+
//| New trading day: new day base, lift a daily block                |
//+------------------------------------------------------------------+
void NewDayCheck()
  {
   datetime ds = DayStart(TimeCurrent());
   if(ds == g_dayStart)
      return;
   double bal = AccountInfoDouble(ACCOUNT_BALANCE), eq = AccountInfoDouble(ACCOUNT_EQUITY);
   g_dayStart = ds;
   g_dayBase  = InpDayBase == DAY_MAX_BE ? MathMax(bal, eq) : bal;
   if(g_block != 0 && g_block != BLOCK_FOREVER && g_block <= ds)
     {
      g_block = 0;
      Print("Guard: new trading day, block lifted");
     }
   SaveState();
  }

//+------------------------------------------------------------------+
//| Daily loss amount in money                                       |
//+------------------------------------------------------------------+
double DailyAmt()
  {
   return InpDailyPct / 100.0 * (InpDailyOfInit ? g_init : g_dayBase);
  }
//+------------------------------------------------------------------+
//| Equity level of the daily loss limit                             |
//+------------------------------------------------------------------+
double DailyFloor()
  {
   return g_dayBase - DailyAmt();
  }
//+------------------------------------------------------------------+
//| Max drawdown amount in money                                     |
//+------------------------------------------------------------------+
double DDAmt()
  {
   return InpMaxDDPct / 100.0 * g_init;
  }
//+------------------------------------------------------------------+
//| Equity level of the max drawdown limit                           |
//+------------------------------------------------------------------+
double DDFloor()
  {
   if(InpDDMode == DD_STATIC)
      return g_init - DDAmt();
   double f = g_peak - DDAmt();
   return InpTrailLock ? MathMin(f, g_init) : f;
  }
//+------------------------------------------------------------------+
//| Guard acts at this equity: floor plus the unused part of the buffer|
//+------------------------------------------------------------------+
double Trigger(double floor, double amt)
  {
   return floor + amt * (1.0 - InpTriggerPct / 100.0);
  }

//+------------------------------------------------------------------+
//| Number of open positions and pending orders                      |
//+------------------------------------------------------------------+
int OpenCount()
  {
   return PositionsTotal() + OrdersTotal();
  }

//+------------------------------------------------------------------+
//| Delete all pending orders and close all positions                |
//+------------------------------------------------------------------+
void CloseAll()
  {
   for(int i = OrdersTotal() - 1; i >= 0; i--)
     {
      ulong t = OrderGetTicket(i);
      if(t > 0 && !g_trade.OrderDelete(t))
         Print("Guard: delete order #", t, " failed, retcode ", g_trade.ResultRetcode());
     }
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong t = PositionGetTicket(i);
      if(t > 0 && !g_trade.PositionClose(t, InpDeviation))
         Print("Guard: close #", t, " failed, retcode ", g_trade.ResultRetcode());
     }
  }

//+------------------------------------------------------------------+
//| A limit is reached: block, notify and flatten                    |
//+------------------------------------------------------------------+
void Breach(string reason, datetime until)
  {
   g_block  = until;
   g_reason = reason;
   SaveState();
   string msg = StringFormat("Guard %s: %s - flattening, blocked %s", AccountInfoString(ACCOUNT_SERVER) + " " +
                             IntegerToString(AccountInfoInteger(ACCOUNT_LOGIN)), reason,
                             until == BLOCK_FOREVER ? "until InpUnblock" : "until " + TimeToString(until));
   Print(msg);
   if(InpPush && !MQLInfoInteger(MQL_TESTER))
      SendNotification(msg);
   CloseAll();
  }

//+------------------------------------------------------------------+
//| Main check: limits, block, timed closes, panel                   |
//+------------------------------------------------------------------+
void Check()
  {
   NewDayCheck();
   double bal = AccountInfoDouble(ACCOUNT_BALANCE), eq = AccountInfoDouble(ACCOUNT_EQUITY);
   double hi = InpDDMode == DD_TRAIL_BAL ? bal : eq;
   if(hi > g_peak)
     {
      g_peak = hi;
      GVSet("peak", g_peak);
     }

   if(g_block > TimeCurrent())
     {
      if(OpenCount() > 0)
         CloseAll();
     }
   else if(InpDailyPct > 0 && eq <= Trigger(DailyFloor(), DailyAmt()))
      Breach(StringFormat("daily loss %.2f%% (limit %.2f%%)", (g_dayBase - eq) / g_init * 100, InpDailyPct),
             g_dayStart + 86400);
   else if(InpMaxDDPct > 0 && eq <= Trigger(DDFloor(), DDAmt()))
      Breach(StringFormat("max drawdown, equity %.2f near floor %.2f", eq, DDFloor()), BLOCK_FOREVER);
   else if(InpTargetPct > 0 && eq >= g_init * (1 + InpTargetPct / 100.0))
      Breach(StringFormat("profit target %.2f%% reached", (eq / g_init - 1) * 100), BLOCK_FOREVER);
   else if(InpFridayHM > 0 || InpDailyHM > 0)
     {
      MqlDateTime t;
      TimeToStruct(TimeCurrent(), t);
      int hm = t.hour * 100 + t.min;
      if(InpFridayHM > 0 && t.day_of_week == 5 && hm >= InpFridayHM)
         Breach("Friday close", g_dayStart + 3 * 86400);
      else if(InpDailyHM > 0 && hm >= InpDailyHM)
         Breach("daily close before the break", g_dayStart + 86400);
     }
   if(InpPanel)
      Panel(bal, eq);
  }

//+------------------------------------------------------------------+
//| Status panel on the chart                                        |
//+------------------------------------------------------------------+
void Panel(double bal, double eq)
  {
   string s = "Prop-firm Guard v1.00\n";
   s += StringFormat("Initial %.2f   Balance %.2f   Equity %.2f\n", g_init, bal, eq);
   if(InpDailyPct > 0)
      s += StringFormat("Today %+.2f (%+.2f%%)   daily floor %.2f   room %.2f\n", eq - g_dayBase,
                        (eq - g_dayBase) / g_init * 100, DailyFloor(), eq - Trigger(DailyFloor(), DailyAmt()));
   if(InpMaxDDPct > 0)
      s += StringFormat("Max DD floor %.2f   room %.2f\n", DDFloor(), eq - Trigger(DDFloor(), DDAmt()));
   if(InpTargetPct > 0)
      s += StringFormat("Target %.2f   to go %.2f\n", g_init * (1 + InpTargetPct / 100.0), g_init * (1 + InpTargetPct / 100.0) - eq);
   s += g_block > TimeCurrent() ? "STATUS: BLOCKED - " + g_reason + (g_block == BLOCK_FOREVER ? "" : " (until " + TimeToString(g_block) + ")")
                                : "STATUS: trading allowed";
   Comment(s);
  }

//+------------------------------------------------------------------+
//| Strategy Tester demo: random trades to watch the guard work      |
//+------------------------------------------------------------------+
void DemoTrade()
  {
   if(!InpDemoTrades || !MQLInfoInteger(MQL_TESTER) || g_block > TimeCurrent() || PositionsTotal() > 0)
      return;
   if(MathRand() % 200 != 0 || SymbolInfoInteger(_Symbol, SYMBOL_SPREAD) > InpDemoMaxSpr)
      return;                                                   // no entries into opening spread spikes
   if(MathRand() % 2 == 0)
      g_trade.Buy(InpDemoLots, _Symbol);
   else
      g_trade.Sell(InpDemoLots, _Symbol);
  }

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
  {
   if(InpTriggerPct <= 0 || InpTriggerPct > 100 || InpResetHour < 0 || InpResetHour > 23)
     {
      Print("Guard: InpTriggerPct must be 1-100 and InpResetHour 0-23");
      return INIT_PARAMETERS_INCORRECT;
     }
   g_pfx = "PFG_" + IntegerToString(AccountInfoInteger(ACCOUNT_LOGIN)) + "_";
   g_trade.SetDeviationInPoints(InpDeviation);
   g_trade.SetAsyncMode(false);

   double bal = AccountInfoDouble(ACCOUNT_BALANCE);
   g_init     = InpInitBalance > 0 ? InpInitBalance : GVGet("init", bal);
   g_dayStart = (datetime)GVGet("dayStart", 0);
   g_dayBase  = GVGet("dayBase", bal);
   g_peak     = MathMax(GVGet("peak", g_init), g_init);
   g_block    = (datetime)GVGet("block", 0);
   if(InpUnblock && g_block == BLOCK_FOREVER)
     {
      g_block = 0;
      g_peak  = g_init;
      Print("Guard: block cleared by InpUnblock - set it back to false");
     }
   if(g_block > TimeCurrent())
      g_reason = "earlier breach";
   SaveState();
   Check();
   EventSetTimer(1);
   PrintFormat("Guard started: initial %.2f, daily %.1f%%, max DD %.1f%% (%s), trigger at %.0f%% of limits",
               g_init, InpDailyPct, InpMaxDDPct, EnumToString(InpDDMode), InpTriggerPct);
   return INIT_SUCCEEDED;
  }

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   EventKillTimer();
   Comment("");
  }

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
  {
   Check();
   DemoTrade();
  }

//+------------------------------------------------------------------+
//| Timer function: check once per second without ticks              |
//+------------------------------------------------------------------+
void OnTimer()
  {
   Check();
  }

//+------------------------------------------------------------------+
//| A trade opened while blocked (other EA or manual) is closed      |
//+------------------------------------------------------------------+
void OnTradeTransaction(const MqlTradeTransaction &trans, const MqlTradeRequest &request, const MqlTradeResult &result)
  {
   if(g_block > TimeCurrent() && (trans.type == TRADE_TRANSACTION_DEAL_ADD || trans.type == TRADE_TRANSACTION_ORDER_ADD))
      CloseAll();
  }
//+------------------------------------------------------------------+
