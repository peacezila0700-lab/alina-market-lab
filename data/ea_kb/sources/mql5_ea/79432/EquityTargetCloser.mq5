//+------------------------------------------------------------------+
//|                                          EquityTargetCloser.mq5 |
//|  Closes all positions (and pending orders) when the account      |
//|  profit or loss reaches a level you set, in money or in %.       |
//|  It does not open trades. Attach to ONE chart.                   |
//|                                                                  |
//|  Measure:                                                        |
//|   - Floating: current open P/L only (profit + swap).             |
//|   - Today: equity vs the balance at the day start (closed +      |
//|     open P/L of the day). Deposits/withdrawals are excluded.     |
//|  Scope: all positions, or only one symbol and/or magic number.   |
//|  After a close it can stop for the rest of the day.              |
//+------------------------------------------------------------------+
#property copyright "Augusto Martin D'anna"
#property version   "1.00"
#property description "Closes all trades when the account profit or loss reaches your target, in money or % of balance."
#property description "Floating P/L or full-day P/L; optional symbol and magic filters; can pause until the next day."

#include <Trade/Trade.mqh>

enum ENUM_MEASURE
  {
   MEASURE_FLOATING = 0, // Floating P/L of open positions
   MEASURE_TODAY    = 1  // Today's P/L (closed + open)
  };

enum ENUM_UNITS
  {
   UNITS_MONEY   = 0, // Money (account currency)
   UNITS_PERCENT = 1  // % of balance
  };

input ENUM_MEASURE InpMeasure      = MEASURE_FLOATING; // What to measure
input ENUM_UNITS   InpUnits        = UNITS_MONEY;      // Units
input double       InpProfitTarget = 500;              // Close all at this profit (0 = off)
input double       InpLossLimit    = 300;              // Close all at this loss, positive number (0 = off)
input string       InpSymbol       = "";               // Only this symbol ("" = all)
input long         InpMagic        = -1;               // Only this magic number (-1 = all)
input bool         InpDeleteOrders = true;             // Also delete pending orders
input bool         InpPauseToday   = true;             // After closing, keep closing new trades until tomorrow
input int          InpResetHour    = 0;                // Day reset hour (server time)

CTrade   g_trade;
long     g_pausedDay = -1;

long DayIndex(const datetime t) { return (long)((t - InpResetHour * 3600) / 86400); }

bool Mine(const string symbol, const long magic)
  {
   return (InpSymbol == "" || symbol == InpSymbol) && (InpMagic < 0 || magic == InpMagic);
  }

double FloatingPnl()
  {
   double sum = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0 || !Mine(PositionGetString(POSITION_SYMBOL), PositionGetInteger(POSITION_MAGIC)))
         continue;
      sum += PositionGetDouble(POSITION_PROFIT) + PositionGetDouble(POSITION_SWAP);
     }
   return sum;
  }

//--- closed P/L of today's trades (deposits/withdrawals excluded)
double ClosedTodayPnl()
  {
   double sum = 0;
   datetime start = (datetime)(DayIndex(TimeCurrent()) * 86400 + InpResetHour * 3600);
   if(!HistorySelect(start, TimeCurrent() + 60))
      return 0;
   for(int i = HistoryDealsTotal() - 1; i >= 0; i--)
     {
      ulong deal = HistoryDealGetTicket(i);
      long type = HistoryDealGetInteger(deal, DEAL_TYPE);
      if(deal == 0 || (type != DEAL_TYPE_BUY && type != DEAL_TYPE_SELL))
         continue;
      if(!Mine(HistoryDealGetString(deal, DEAL_SYMBOL), HistoryDealGetInteger(deal, DEAL_MAGIC)))
         continue;
      sum += HistoryDealGetDouble(deal, DEAL_PROFIT) + HistoryDealGetDouble(deal, DEAL_SWAP)
           + HistoryDealGetDouble(deal, DEAL_COMMISSION) + HistoryDealGetDouble(deal, DEAL_FEE);
     }
   return sum;
  }

int CountMine()
  {
   int n = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket > 0 && Mine(PositionGetString(POSITION_SYMBOL), PositionGetInteger(POSITION_MAGIC)))
         n++;
     }
   return n;
  }

void CloseAll(const string reason)
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0 || !Mine(PositionGetString(POSITION_SYMBOL), PositionGetInteger(POSITION_MAGIC)))
         continue;
      if(!g_trade.PositionClose(ticket))
         PrintFormat("ETC: close %I64u failed, retcode %u - will retry", ticket, g_trade.ResultRetcode());
     }
   if(!InpDeleteOrders)
      return;
   for(int i = OrdersTotal() - 1; i >= 0; i--)
     {
      ulong ticket = OrderGetTicket(i);
      if(ticket > 0 && Mine(OrderGetString(ORDER_SYMBOL), OrderGetInteger(ORDER_MAGIC)) && !g_trade.OrderDelete(ticket))
         PrintFormat("ETC: delete order %I64u failed, retcode %u", ticket, g_trade.ResultRetcode());
     }
  }

void Check()
  {
   long today = DayIndex(TimeCurrent());
   if(g_pausedDay == today)
     {
      if(CountMine() > 0)
         CloseAll("paused until next day");
      Comment("EquityTargetCloser: target/limit hit today - paused until next day");
      return;
     }
   double pnl = FloatingPnl() + (InpMeasure == MEASURE_TODAY ? ClosedTodayPnl() : 0);
   double scale = InpUnits == UNITS_PERCENT ? AccountInfoDouble(ACCOUNT_BALANCE) / 100.0 : 1.0;
   double target = InpProfitTarget * scale, limit = InpLossLimit * scale;
   string hit = "";
   if(InpProfitTarget > 0 && pnl >= target)
      hit = StringFormat("profit target %.2f reached (P/L %.2f)", target, pnl);
   else if(InpLossLimit > 0 && pnl <= -limit)
      hit = StringFormat("loss limit %.2f reached (P/L %.2f)", limit, pnl);
   if(hit != "" && (CountMine() > 0 || InpMeasure == MEASURE_TODAY))
     {
      Print("ETC: ", hit, " - closing");
      CloseAll(hit);
      if(InpPauseToday)
         g_pausedDay = today;
     }
   Comment(StringFormat("EquityTargetCloser\nP/L %.2f   target +%.2f   limit -%.2f", pnl, target, limit));
  }

int OnInit()
  {
   if(InpProfitTarget < 0 || InpLossLimit < 0 || (InpProfitTarget == 0 && InpLossLimit == 0)
      || InpResetHour < 0 || InpResetHour > 23)
     {
      Print("ETC: invalid inputs (set a profit target and/or a loss limit, both as positive numbers)");
      return INIT_PARAMETERS_INCORRECT;
     }
   g_trade.SetDeviationInPoints(50);
   EventSetTimer(1);
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
