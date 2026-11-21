//+------------------------------------------------------------------+
//|                                   Lab_Close_All_Profit_Loss.mq5  |
//|  Closes all positions (and optionally deletes pending orders)    |
//|  when the total floating profit reaches a target in money, or    |
//|  the total floating loss reaches a limit. It never opens trades. |
//|  Free utility. Not financial advice.                             |
//+------------------------------------------------------------------+
#property copyright "Strategy Lab"
#property version   "1.00"
#property description "Closes all positions when the total floating profit reaches your target"
#property description "or the total floating loss reaches your limit (in account currency)."
#property description "It never opens trades. Filters: all symbols or current symbol, any magic or one magic."

#include <Trade\Trade.mqh>

enum ENUM_SCOPE
  {
   SCOPE_ALL_SYMBOLS = 0,   // All symbols
   SCOPE_THIS_SYMBOL = 1    // Only this chart's symbol
  };

input double     InpTargetProfit   = 50.0;   // Close all when total profit >= (money, 0 = off)
input double     InpMaxLoss        = 30.0;   // Close all when total loss >= (money, 0 = off)
input ENUM_SCOPE InpScope          = SCOPE_ALL_SYMBOLS; // Positions to watch
input long       InpMagic          = -1;     // Magic number (-1 = any, 0 = manual trades only)
input bool       InpIncludeSwapFee = true;   // Include swap in the total
input bool       InpDeletePending  = true;   // Also delete pending orders when closing
input bool       InpStopAfterClose = true;   // Stop watching after one close (remove EA)
input int        InpSlippagePoints = 30;     // Max slippage (points)

CTrade trade;
bool   g_done = false;

//+------------------------------------------------------------------+
bool Selected(const string sym, const long magic)
  {
   if(InpScope == SCOPE_THIS_SYMBOL && sym != _Symbol) return false;
   if(InpMagic >= 0 && magic != InpMagic)              return false;
   return true;
  }

//+------------------------------------------------------------------+
double TotalProfit(int &count)
  {
   double total = 0.0;
   count = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(!Selected(PositionGetString(POSITION_SYMBOL), PositionGetInteger(POSITION_MAGIC))) continue;
      total += PositionGetDouble(POSITION_PROFIT);
      if(InpIncludeSwapFee)
         total += PositionGetDouble(POSITION_SWAP);
      count++;
     }
   return total;
  }

//+------------------------------------------------------------------+
void CloseAll(const string reason)
  {
   PrintFormat("Close-all triggered: %s", reason);
   for(int attempt = 0; attempt < 3; attempt++)
     {
      for(int i = PositionsTotal() - 1; i >= 0; i--)
        {
         ulong ticket = PositionGetTicket(i);
         if(ticket == 0) continue;
         if(!Selected(PositionGetString(POSITION_SYMBOL), PositionGetInteger(POSITION_MAGIC))) continue;
         if(!trade.PositionClose(ticket))
            PrintFormat("Could not close #%I64u: %d %s", ticket, trade.ResultRetcode(), trade.ResultRetcodeDescription());
        }
      if(InpDeletePending)
        {
         for(int i = OrdersTotal() - 1; i >= 0; i--)
           {
            ulong ticket = OrderGetTicket(i);
            if(ticket == 0) continue;
            if(!Selected(OrderGetString(ORDER_SYMBOL), OrderGetInteger(ORDER_MAGIC))) continue;
            if(!trade.OrderDelete(ticket))
               PrintFormat("Could not delete order #%I64u: %d", ticket, trade.ResultRetcode());
           }
        }
      int left = 0;
      TotalProfit(left);
      if(left == 0) break;
      Sleep(500);
     }
  }

//+------------------------------------------------------------------+
void ShowStatus(const double profit, const int count)
  {
   string ccy = AccountInfoString(ACCOUNT_CURRENCY);
   Comment(StringFormat("Lab Close All  |  positions watched: %d  |  total: %.2f %s\nTarget: %s   Max loss: %s%s",
                        count, profit, ccy,
                        InpTargetProfit > 0 ? DoubleToString(InpTargetProfit, 2) : "off",
                        InpMaxLoss > 0 ? DoubleToString(InpMaxLoss, 2) : "off",
                        g_done ? "\nDONE: positions closed" : ""));
  }

//+------------------------------------------------------------------+
int OnInit()
  {
   if(InpTargetProfit <= 0 && InpMaxLoss <= 0)
     {
      Alert("Lab Close All: set a profit target and/or a max loss greater than 0.");
      return INIT_PARAMETERS_INCORRECT;
     }
   trade.SetDeviationInPoints(InpSlippagePoints);
   trade.SetAsyncMode(false);
   EventSetTimer(1);
   return INIT_SUCCEEDED;
  }

void OnDeinit(const int reason)
  {
   EventKillTimer();
   Comment("");
  }

//+------------------------------------------------------------------+
void Check()
  {
   if(g_done && InpStopAfterClose) return;
   int count = 0;
   double profit = TotalProfit(count);
   ShowStatus(profit, count);
   if(count == 0) return;

   if(InpTargetProfit > 0 && profit >= InpTargetProfit)
     {
      CloseAll(StringFormat("profit %.2f >= target %.2f", profit, InpTargetProfit));
      g_done = true;
     }
   else if(InpMaxLoss > 0 && profit <= -InpMaxLoss)
     {
      CloseAll(StringFormat("loss %.2f >= limit %.2f", -profit, InpMaxLoss));
      g_done = true;
     }

   if(g_done)
     {
      ShowStatus(profit, count);
      if(InpStopAfterClose)
         ExpertRemove();
     }
  }

void OnTick()  { Check(); }
void OnTimer() { Check(); }
//+------------------------------------------------------------------+
