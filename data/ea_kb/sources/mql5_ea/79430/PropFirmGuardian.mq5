//+------------------------------------------------------------------+
//|                                            PropFirmGuardian.mq5 |
//|  Account guardian for prop firm rules (daily loss, max loss,     |
//|  profit target). Attach to ONE chart; it watches the whole       |
//|  account equity on every tick and once per second.               |
//|                                                                  |
//|  - Daily loss: equity <= day-start balance - DailyLoss%          |
//|    -> closes everything and blocks trading until the next day.   |
//|  - Max loss: equity <= floor (static from initial balance, or    |
//|    trailing from the highest balance) -> closes and blocks       |
//|    until you remove the block manually.                          |
//|  - Profit target (optional): equity >= target -> closes and      |
//|    blocks, so you do not give back a passed challenge.           |
//|  - Safety buffer: acts X% before the real limit (slippage).      |
//|                                                                  |
//|  While blocked it closes any position that gets opened (manual   |
//|  or by other EAs) and sets the global variable PFG_BLOCKED = 1   |
//|  so your own EAs can check it before trading.                    |
//|  The day-start balance is rebuilt from the deal history, so it   |
//|  is correct even if the terminal was off at midnight.            |
//+------------------------------------------------------------------+
#property copyright "Augusto Martin D'anna"
#property version   "1.00"
#property description "Closes all trades and blocks trading before the prop firm daily loss or max loss limit is hit."
#property description "Optional profit target lock. Day-start balance rebuilt from history; deposits/withdrawals are not counted as P/L."

#include <Trade/Trade.mqh>

enum ENUM_MAXLOSS_MODE
  {
   MAXLOSS_STATIC   = 0, // Static: from initial balance
   MAXLOSS_TRAILING = 1  // Trailing: from the highest closed balance
  };

enum ENUM_DAILY_BASE
  {
   DAILY_FROM_DAY_START = 0, // % of the balance at day start
   DAILY_FROM_INITIAL   = 1  // % of the initial balance (FTMO style)
  };

input double            InpInitialBalance = 100000;               // Initial account balance
input double            InpDailyLossPct   = 5.0;                  // Daily loss limit, %
input ENUM_DAILY_BASE   InpDailyBase      = DAILY_FROM_INITIAL;   // Daily limit measured as
input double            InpMaxLossPct     = 10.0;                 // Max loss limit, %
input ENUM_MAXLOSS_MODE InpMaxLossMode    = MAXLOSS_STATIC;       // Max loss mode
input double            InpTargetPct      = 0.0;                  // Profit target, % (0 = off)
input double            InpBufferPct      = 0.5;                  // Safety buffer: act this % before the limit
input int               InpResetHour      = 0;                    // Day reset hour (server time)
input bool              InpCloseManual    = true;                 // Also close manual trades (magic 0)
input bool              InpShowPanel      = true;                 // Show status on the chart

#define GV_BLOCK  "PFG_BLOCKED"    // 0 = free, 1 = until next day, 2 = permanent (daily/max/target)
#define GV_DAY    "PFG_DAY"
#define GV_PEAK   "PFG_PEAK"
#define GV_LOGIN  "PFG_LOGIN"

CTrade g_trade;
bool   g_ready = false;

double GV(const string name, const double def) { return GlobalVariableCheck(name) ? GlobalVariableGet(name) : def; }

//--- trading day index: the day starts at InpResetHour (server time)
long DayIndex(const datetime t) { return (long)((t - InpResetHour * 3600) / 86400); }

datetime DayStart(const long day) { return (datetime)(day * 86400 + InpResetHour * 3600); }

//--- P/L of closed trades and balance operations since the day start
void TodayDeals(const long day, double &tradesPnl, double &balanceOps)
  {
   tradesPnl = 0;
   balanceOps = 0;
   if(!HistorySelect(DayStart(day), TimeCurrent() + 60))
      return;
   for(int i = HistoryDealsTotal() - 1; i >= 0; i--)
     {
      ulong deal = HistoryDealGetTicket(i);
      if(deal == 0)
         continue;
      long type = HistoryDealGetInteger(deal, DEAL_TYPE);
      double v = HistoryDealGetDouble(deal, DEAL_PROFIT) + HistoryDealGetDouble(deal, DEAL_SWAP)
               + HistoryDealGetDouble(deal, DEAL_COMMISSION) + HistoryDealGetDouble(deal, DEAL_FEE);
      if(type == DEAL_TYPE_BUY || type == DEAL_TYPE_SELL)
         tradesPnl += v;
      else
         balanceOps += v;          // deposits, withdrawals, credits: not a trading loss
     }
  }

//--- daily floor in equity terms
double DailyFloor(const long day)
  {
   double pnl, ops;
   TodayDeals(day, pnl, ops);
   double balance = AccountInfoDouble(ACCOUNT_BALANCE);
   double dayStart = balance - pnl - ops;                 // balance at the reset hour
   double base = (InpDailyBase == DAILY_FROM_INITIAL) ? InpInitialBalance : dayStart;
   double limit = base * (InpDailyLossPct - InpBufferPct) / 100.0;
   return dayStart + ops - limit;                         // a deposit today moves the floor up, a withdrawal down
  }

double MaxFloor()
  {
   double limit = InpInitialBalance * (InpMaxLossPct - InpBufferPct) / 100.0;
   if(InpMaxLossMode == MAXLOSS_STATIC)
      return InpInitialBalance - limit;
   double peak = MathMax(GV(GV_PEAK, InpInitialBalance), AccountInfoDouble(ACCOUNT_BALANCE));
   GlobalVariableSet(GV_PEAK, peak);
   return peak - limit;
  }

void CloseAll(const string reason)
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0 || (!InpCloseManual && PositionGetInteger(POSITION_MAGIC) == 0))
         continue;
      if(!g_trade.PositionClose(ticket))
         PrintFormat("PFG: close %I64u failed, retcode %u (%s) - will retry", ticket, g_trade.ResultRetcode(), reason);
     }
   for(int i = OrdersTotal() - 1; i >= 0; i--)
     {
      ulong ticket = OrderGetTicket(i);
      if(ticket == 0 || (!InpCloseManual && OrderGetInteger(ORDER_MAGIC) == 0))
         continue;
      if(!g_trade.OrderDelete(ticket))
         PrintFormat("PFG: delete order %I64u failed, retcode %u", ticket, g_trade.ResultRetcode());
     }
  }

void Block(const int level, const string reason)
  {
   if(GV(GV_BLOCK, 0) < level)
     {
      GlobalVariableSet(GV_BLOCK, level);
      Alert("PropFirmGuardian: ", reason);
      Print("PFG: BLOCKED - ", reason);
     }
   CloseAll(reason);
  }

//--- new account: forget the previous account's state
bool Prepare()
  {
   long login = AccountInfoInteger(ACCOUNT_LOGIN);
   if(!TerminalInfoInteger(TERMINAL_CONNECTED) || login <= 0 || AccountInfoDouble(ACCOUNT_BALANCE) <= 0)
      return false;
   if((long)GV(GV_LOGIN, -1) != login)
     {
      GlobalVariableSet(GV_LOGIN, (double)login);
      GlobalVariableSet(GV_BLOCK, 0);
      GlobalVariableSet(GV_PEAK, InpInitialBalance);
      GlobalVariableSet(GV_DAY, (double)DayIndex(TimeCurrent()));
     }
   return true;
  }

void Check()
  {
   if(!g_ready)
     {
      if(!Prepare())
         return;
      g_ready = true;
     }
   long day = DayIndex(TimeCurrent());
   if((long)GV(GV_DAY, -1) != day)                        // new trading day: lift the daily block
     {
      GlobalVariableSet(GV_DAY, (double)day);
      if(GV(GV_BLOCK, 0) == 1)
        {
         GlobalVariableSet(GV_BLOCK, 0);
         Print("PFG: new day, daily block lifted");
        }
     }
   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   double dailyFloor = DailyFloor(day);
   double maxFloor = MaxFloor();
   double target = InpTargetPct > 0 ? InpInitialBalance * (1 + InpTargetPct / 100.0) : 0;

   if(equity <= maxFloor)
      Block(2, StringFormat("max loss: equity %.2f <= %.2f", equity, maxFloor));
   else if(target > 0 && equity >= target)
      Block(2, StringFormat("profit target reached: equity %.2f >= %.2f", equity, target));
   else if(equity <= dailyFloor)
      Block(1, StringFormat("daily loss: equity %.2f <= %.2f", equity, dailyFloor));
   else if(GV(GV_BLOCK, 0) > 0 && (PositionsTotal() > 0 || OrdersTotal() > 0))
      CloseAll("account blocked");

   if(InpShowPanel)
     {
      int b = (int)GV(GV_BLOCK, 0);
      Comment(StringFormat("PropFirmGuardian\nEquity %.2f\nDaily floor %.2f  (room %.2f)\nMax floor %.2f  (room %.2f)%s\nStatus: %s",
                           equity, dailyFloor, equity - dailyFloor, maxFloor, equity - maxFloor,
                           target > 0 ? StringFormat("\nTarget %.2f", target) : "",
                           b == 2 ? "BLOCKED (remove global variable PFG_BLOCKED to reset)" : b == 1 ? "BLOCKED until next day" : "OK"));
     }
  }

int OnInit()
  {
   if(InpInitialBalance <= 0 || InpDailyLossPct <= 0 || InpMaxLossPct <= 0 || InpBufferPct < 0
      || InpBufferPct >= InpDailyLossPct || InpResetHour < 0 || InpResetHour > 23)
     {
      Print("PFG: invalid inputs");
      return INIT_PARAMETERS_INCORRECT;
     }
   g_trade.SetDeviationInPoints(50);
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
