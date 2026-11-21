//+------------------------------------------------------------------+
//|                                          PropFirmEquityGuard.mq5 |
//|                                   Copyright 2026, Deepanshu Goyal |
//|                 https://www.mql5.com/en/users/deepanshugoyal99   |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, Deepanshu Goyal"
#property link      "https://www.mql5.com/en/users/deepanshugoyal99"
#property version   "1.00"
#property description "Prop Firm Equity Guard: watches the daily loss limit and the maximum"
#property description "overall loss of your account (FTMO-style rules). When a limit is hit it"
#property description "closes all positions, deletes pending orders and keeps the account flat"
#property description "until the next trading day. Attach it to one chart; it guards every symbol."

#include <Trade/Trade.mqh>

//--- inputs
input double InpDailyLossPercent    = 5.0;   // Daily loss limit, % of day-start balance/equity (0 = off)
input double InpMaxLossPercent      = 10.0;  // Max overall loss, % of initial balance (0 = off)
input double InpInitialBalance      = 0.0;   // Initial balance (0 = balance when first attached)
input double InpSafetyBufferPercent = 0.5;   // Act this many % before the real limit
input int    InpDayResetHour        = 0;     // Daily reset hour, server time (0-23)
input double InpProfitTargetPercent = 0.0;   // Close all at this % profit on initial balance (0 = off)
input bool   InpBlockAfterBreach    = true;  // Close any new trade opened after a limit is hit
input long   InpMagicFilter         = -1;    // Magic number to guard (-1 = all trades, manual included)
input bool   InpSendAlerts          = true;  // Alert and push notification on warnings and breaches
input bool   InpResetLocks          = false; // Clear a saved max-loss / target lock on start

CTrade   trade;
string   g_prefix;          // global variable prefix, per account
double   g_dayStart;        // max(balance, equity) at the start of the trading day
double   g_initBalance;     // base for the max loss and profit target
long     g_dayKey;          // current trading-day number
bool     g_lockDay, g_lockMax, g_lockTarget;
ulong    g_lastCloseMs = 0; // throttles close requests
datetime g_lastWarn    = 0;

//+------------------------------------------------------------------+
//| Terminal global variables survive restarts of MT5 and the VPS     |
//+------------------------------------------------------------------+
double GvGet(const string name, const double def)
  {
   return GlobalVariableCheck(g_prefix + name) ? GlobalVariableGet(g_prefix + name) : def;
  }
void GvSet(const string name, const double value) { GlobalVariableSet(g_prefix + name, value); }

long DayKey() { return (long)((TimeCurrent() - InpDayResetHour * 3600) / 86400); }

bool IsGuarded(const long magic) { return InpMagicFilter < 0 || magic == InpMagicFilter; }

//+------------------------------------------------------------------+
int OnInit()
  {
   if(InpDailyLossPercent < 0 || InpMaxLossPercent < 0 || InpProfitTargetPercent < 0 ||
      InpSafetyBufferPercent < 0 || InpDayResetHour < 0 || InpDayResetHour > 23)
     {
      Print("Invalid inputs: percentages must be >= 0 and the reset hour 0-23.");
      return INIT_PARAMETERS_INCORRECT;
     }
   if((InpDailyLossPercent > 0 && InpSafetyBufferPercent >= InpDailyLossPercent) ||
      (InpMaxLossPercent > 0 && InpSafetyBufferPercent >= InpMaxLossPercent))
     {
      Print("The safety buffer must be smaller than the loss limits.");
      return INIT_PARAMETERS_INCORRECT;
     }

   g_prefix = "PFEG_" + IntegerToString(AccountInfoInteger(ACCOUNT_LOGIN)) + "_";
   if(InpResetLocks)
     {
      GlobalVariableDel(g_prefix + "lockmax");
      GlobalVariableDel(g_prefix + "locktarget");
     }

   double balance = AccountInfoDouble(ACCOUNT_BALANCE);
   g_initBalance  = InpInitialBalance > 0 ? InpInitialBalance : GvGet("init", balance);
   GvSet("init", g_initBalance);

   g_lockMax    = GvGet("lockmax", 0) > 0;
   g_lockTarget = GvGet("locktarget", 0) > 0;
   RefreshDay();

   trade.SetDeviationInPoints(50);
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
//| Starts a new trading day: the daily floor is based on the higher |
//| of balance and equity at the day start, as most prop firms do.   |
//+------------------------------------------------------------------+
void RefreshDay()
  {
   long key = DayKey();
   if(key == g_dayKey && g_dayStart > 0)
      return;
   double start = MathMax(AccountInfoDouble(ACCOUNT_BALANCE), AccountInfoDouble(ACCOUNT_EQUITY));
   if((long)GvGet("daykey", -1) != key)
     {
      g_dayStart = start;
      g_lockDay  = false;
      GvSet("daykey", (double)key);
      GvSet("daystart", g_dayStart);
      GvSet("lockday", 0);
     }
   else
     {
      g_dayStart = GvGet("daystart", start);
      g_lockDay  = GvGet("lockday", 0) > 0;
     }
   g_dayKey = key;
  }

//+------------------------------------------------------------------+
void Check()
  {
   RefreshDay();
   double equity   = AccountInfoDouble(ACCOUNT_EQUITY);
   double dayFloor = InpDailyLossPercent > 0 ? g_dayStart * (1.0 - (InpDailyLossPercent - InpSafetyBufferPercent) / 100.0) : 0;
   double maxFloor = InpMaxLossPercent > 0 ? g_initBalance * (1.0 - (InpMaxLossPercent - InpSafetyBufferPercent) / 100.0) : 0;
   double target   = InpProfitTargetPercent > 0 ? g_initBalance * (1.0 + InpProfitTargetPercent / 100.0) : 0;

   if(!g_lockMax && maxFloor > 0 && equity <= maxFloor)
     {
      g_lockMax = true;
      GvSet("lockmax", 1);
      Breach(StringFormat("Max loss limit hit: equity %.2f <= %.2f. Trading stays locked.", equity, maxFloor));
     }
   else if(!g_lockDay && dayFloor > 0 && equity <= dayFloor)
     {
      g_lockDay = true;
      GvSet("lockday", 1);
      Breach(StringFormat("Daily loss limit hit: equity %.2f <= %.2f. Locked until the next trading day.", equity, dayFloor));
     }
   if(!g_lockTarget && target > 0 && equity >= target)
     {
      g_lockTarget = true;
      GvSet("locktarget", 1);
      Breach(StringFormat("Profit target reached: equity %.2f >= %.2f. Positions closed.", equity, target));
     }

   bool locked = g_lockDay || g_lockMax || g_lockTarget;
   if(locked && InpBlockAfterBreach)
      CloseAll();

   //--- early warning at 80% of the daily allowance, at most every 15 minutes
   if(!locked && InpSendAlerts && InpDailyLossPercent > 0 &&
      equity <= g_dayStart * (1.0 - 0.8 * InpDailyLossPercent / 100.0) &&
      TimeCurrent() - g_lastWarn > 900)
     {
      g_lastWarn = TimeCurrent();
      Notify(StringFormat("Warning: 80%% of today's loss allowance used (equity %.2f).", equity));
     }

   DrawPanel(equity, dayFloor, maxFloor, target);
  }

//+------------------------------------------------------------------+
void Breach(const string message)
  {
   Print(message);
   CloseAll();
   if(InpSendAlerts)
      Notify(message);
  }

void Notify(const string message)
  {
   Alert("Equity Guard: ", message);
   SendNotification("Equity Guard: " + message);
  }

//+------------------------------------------------------------------+
//| Closes guarded positions and deletes guarded pending orders.     |
//| Throttled to one pass per 2 seconds to respect server limits.    |
//+------------------------------------------------------------------+
void CloseAll()
  {
   if(GetTickCount64() - g_lastCloseMs < 2000)
      return;
   g_lastCloseMs = GetTickCount64();

   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0 || !IsGuarded(PositionGetInteger(POSITION_MAGIC)))
         continue;
      trade.SetTypeFillingBySymbol(PositionGetString(POSITION_SYMBOL));
      if(!trade.PositionClose(ticket))
         PrintFormat("Could not close position %I64u: retcode %u", ticket, trade.ResultRetcode());
     }
   for(int i = OrdersTotal() - 1; i >= 0; i--)
     {
      ulong ticket = OrderGetTicket(i);
      if(ticket == 0 || !IsGuarded(OrderGetInteger(ORDER_MAGIC)))
         continue;
      if(!trade.OrderDelete(ticket))
         PrintFormat("Could not delete order %I64u: retcode %u", ticket, trade.ResultRetcode());
     }
  }

//+------------------------------------------------------------------+
void DrawPanel(const double equity, const double dayFloor, const double maxFloor, const double target)
  {
   string status = "TRADING ALLOWED";
   if(g_lockMax)
      status = "LOCKED: max loss limit hit";
   else if(g_lockDay)
      status = "LOCKED: daily loss limit hit (resets next trading day)";
   else if(g_lockTarget)
      status = "LOCKED: profit target reached";

   double dayUsed = g_dayStart > 0 ? (g_dayStart - equity) / g_dayStart * 100.0 : 0;
   string text = "Prop Firm Equity Guard\n";
   text += StringFormat("Equity: %.2f\n", equity);
   if(dayFloor > 0)
      text += StringFormat("Day start: %.2f | Daily floor: %.2f | Used today: %.2f%% of %.2f%%\n",
                           g_dayStart, dayFloor, MathMax(dayUsed, 0), InpDailyLossPercent);
   if(maxFloor > 0)
      text += StringFormat("Initial: %.2f | Max-loss floor: %.2f\n", g_initBalance, maxFloor);
   if(target > 0)
      text += StringFormat("Profit target: %.2f\n", target);
   text += "Status: " + status;
   Comment(text);
  }
//+------------------------------------------------------------------+
