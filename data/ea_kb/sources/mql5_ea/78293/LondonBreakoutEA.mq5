//+------------------------------------------------------------------+
//|                                              LondonBreakoutEA.mq5 |
//|  Simple, transparent breakout EA: Asian range -> London breakout. |
//|  No grid, no martingale, no averaging. One trade per day,         |
//|  stop loss on every trade, lot size from risk percent.            |
//+------------------------------------------------------------------+
#property copyright   "AlexLab"
#property version     "1.00"
#property description "London Breakout EA (free, simple, transparent)."
#property description "Trades the breakout of the Asian session range during the London session."
#property description "No grid, no martingale, no averaging. Fixed stop loss, one trade per day."
#property description "Test it in the Strategy Tester and on a DEMO account first. No profit is guaranteed."

#include <Trade/Trade.mqh>

input group "Risk"
input double InpRiskPct    = 0.5;   // Risk per trade, % of balance (max 2)
input double InpRR         = 1.5;   // Take profit = RR x stop distance
input double InpMaxSlAtr   = 3.0;   // Skip the day if stop is farther than this x ATR(H1,14)
input int    InpMaxSpread  = 30;    // Max spread in points (0 = no limit)

input group "Sessions: broker server time, hours 0-23"
input int    InpAsiaStart  = 0;     // Asian range starts
input int    InpAsiaEnd    = 7;     // Asian range ends / London window starts
input int    InpTradeEnd   = 11;    // No new entries from this hour
input int    InpCloseHour  = 20;    // Close an open trade at this hour

input group "Entry"
input int    InpBufferPts  = 10;    // Breakout buffer beyond the range, points
input bool   InpAllowBuy   = true;  // Allow long trades
input bool   InpAllowSell  = true;  // Allow short trades
input long   InpMagic      = 26101201; // Magic number

CTrade   trade;
int      hAtr = INVALID_HANDLE;
datetime lastBar = 0;
int      lastTradeDay = -1;

int OnInit()
{
   if(InpRiskPct <= 0.0 || InpRiskPct > 2.0 || InpRR <= 0.0 ||
      InpAsiaStart < 0 || InpAsiaEnd <= InpAsiaStart || InpAsiaEnd > 23 ||
      InpTradeEnd <= InpAsiaEnd || InpTradeEnd > 23 || InpCloseHour < InpTradeEnd || InpCloseHour > 23)
   {
      Print("London Breakout EA: wrong inputs (risk 0..2%, Asia start < Asia end < trade end <= close hour).");
      return INIT_PARAMETERS_INCORRECT;
   }
   hAtr = iATR(_Symbol, PERIOD_H1, 14);
   if(hAtr == INVALID_HANDLE) return INIT_FAILED;
   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(30);
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   if(hAtr != INVALID_HANDLE) IndicatorRelease(hAtr);
}

bool HavePosition()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong t = PositionGetTicket(i);
      if(t == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) == _Symbol && PositionGetInteger(POSITION_MAGIC) == InpMagic)
         return true;
   }
   return false;
}

void CloseOwn()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong t = PositionGetTicket(i);
      if(t == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) == _Symbol && PositionGetInteger(POSITION_MAGIC) == InpMagic)
         trade.PositionClose(t);
   }
}

// Lot from risk percent. The loss per 1 lot is asked from the terminal itself (OrderCalcProfit),
// because SYMBOL_TRADE_TICK_VALUE can be inconsistent with the real contract size on some symbols.
double CalcLots(const bool isBuy, const double entry, const double sl)
{
   double risk = AccountInfoDouble(ACCOUNT_BALANCE) * InpRiskPct / 100.0;
   double slDist = MathAbs(entry - sl);
   if(slDist <= 0.0) return 0.0;

   double lossPerLot = 0.0;
   double profit = 0.0;
   if(OrderCalcProfit(isBuy ? ORDER_TYPE_BUY : ORDER_TYPE_SELL, _Symbol, 1.0, entry, sl, profit))
      lossPerLot = MathAbs(profit);
   if(lossPerLot <= 0.0)
   {
      double tickVal = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
      double tickSize = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
      if(tickVal <= 0.0 || tickSize <= 0.0) return 0.0;
      lossPerLot = slDist / tickSize * tickVal;
   }

   double lots = risk / lossPerLot;
   double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double vmin = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double vmax = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   if(step <= 0.0) step = vmin;
   lots = MathFloor(lots / step) * step;
   if(lots < vmin)
   {
      Print("London Breakout EA: risk too small for the minimum lot, trade skipped.");
      return 0.0;
   }
   lots = MathMin(lots, vmax);
   PrintFormat("LBO sizing: balance=%.2f risk=%.2f slDist=%.5f lossPerLot=%.2f -> lots=%.2f (loss at stop ~%.2f)",
               AccountInfoDouble(ACCOUNT_BALANCE), risk, slDist, lossPerLot, lots, lots * lossPerLot);
   return lots;
}

void OnTick()
{
   datetime bar0 = iTime(_Symbol, _Period, 0);
   if(bar0 == lastBar) return;               // work once per new bar
   lastBar = bar0;

   MqlDateTime now;
   TimeToStruct(TimeCurrent(), now);

   if(HavePosition())
   {
      if(now.hour >= InpCloseHour) CloseOwn();
      return;
   }

   int dayKey = now.year * 1000 + now.day_of_year;
   if(dayKey == lastTradeDay) return;                        // one trade per day
   if(now.hour < InpAsiaEnd || now.hour >= InpTradeEnd) return;
   if(InpMaxSpread > 0 && SymbolInfoInteger(_Symbol, SYMBOL_SPREAD) > InpMaxSpread) return;

   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   int got = CopyRates(_Symbol, _Period, 0, 600, rates);
   if(got < 50) return;

   double hi = -1.0, lo = 1e18;
   for(int i = 1; i < got; i++)
   {
      MqlDateTime dt;
      TimeToStruct(rates[i].time, dt);
      if(dt.year * 1000 + dt.day_of_year != dayKey)
      {
         if(hi > 0.0) break;                // passed the start of today
         continue;
      }
      if(dt.hour >= InpAsiaStart && dt.hour < InpAsiaEnd)
      {
         hi = MathMax(hi, rates[i].high);
         lo = MathMin(lo, rates[i].low);
      }
   }
   if(hi <= 0.0 || lo > 1e17 || hi <= lo) return;

   double atr[1];
   if(CopyBuffer(hAtr, 0, 1, 1, atr) != 1 || atr[0] <= 0.0) return;

   double close1 = rates[1].close;

   double buf = InpBufferPts * _Point;
   int digits = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   long minStop = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);

   if(InpAllowBuy && close1 > hi + buf)
   {
      double entry = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      double sl = NormalizeDouble(lo - buf, digits);
      double dist = entry - sl;
      if(dist <= 0.0 || dist > InpMaxSlAtr * atr[0] || dist < minStop * _Point) { lastTradeDay = dayKey; return; }
      double lots = CalcLots(true, entry, sl);
      if(lots <= 0.0) { lastTradeDay = dayKey; return; }
      double tp = NormalizeDouble(entry + dist * InpRR, digits);
      if(trade.Buy(lots, _Symbol, entry, sl, tp, "LBO buy")) lastTradeDay = dayKey;
   }
   else if(InpAllowSell && close1 < lo - buf)
   {
      double entry = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      double sl = NormalizeDouble(hi + buf, digits);
      double dist = sl - entry;
      if(dist <= 0.0 || dist > InpMaxSlAtr * atr[0] || dist < minStop * _Point) { lastTradeDay = dayKey; return; }
      double lots = CalcLots(false, entry, sl);
      if(lots <= 0.0) { lastTradeDay = dayKey; return; }
      double tp = NormalizeDouble(entry - dist * InpRR, digits);
      if(trade.Sell(lots, _Symbol, entry, sl, tp, "LBO sell")) lastTradeDay = dayKey;
   }
}
//+------------------------------------------------------------------+
