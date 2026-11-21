//+------------------------------------------------------------------+
//| H4BreakoutRetest_XAU.mq5                                         |
//| First H4 candle breakout + retest Expert Advisor for gold.       |
//|                                                                  |
//| The first 4 hours of the broker day define a zone (high/low).    |
//| When an M5 candle closes outside the zone the EA waits for the   |
//| price to come back and test the broken level (retest) and enters |
//| in the direction of the breakout when an M5 candle closes again  |
//| outside the zone. Fixed stop loss and take profit in % of price, |
//| position size from the risk percentage.                          |
//|                                                                  |
//| Attach it to a gold chart (XAUUSD / GOLD). Any timeframe works,  |
//| the logic always uses M5 candles.                                |
//| DISCLAIMER: educational and research code, not financial advice. |
//| Trading CFDs on gold is high risk and you can lose more than    |
//| your deposit. Backtests are hypothetical and do not guarantee   |
//| future results. Test on a demo account first. No liability for  |
//| any loss is accepted by the author.                              |
//+------------------------------------------------------------------+
#property copyright "Free code"
#property version   "1.10"
#property strict
#property description "Breakout of the first H4 candle of the day with retest confirmation, for gold."
#property description "Fixed % stop loss and take profit, risk based lot size, drawdown guard."
#property description "Backtests are strongly dependent on the gold trend: test on a demo account first."

#include <Trade\Trade.mqh>

input group "Zone"
input int    ZoneStartHour      = 0;      // Zone start (broker server hour)
input int    ZoneHours          = 4;      // Zone length in hours (4 = first H4 candle)

input group "Stop loss / take profit"
input double StopLossPercent    = 2.0;    // Stop loss, % of the entry price
input double TakeProfitPercent  = 4.0;    // Take profit, % of the entry price

input group "Risk and execution"
input double RiskPercent        = 1.0;    // Risk per trade, % of equity
input double MaxMinLotRiskPct   = 3.0;    // If the minimum lot risks more than this % of equity, skip (0 = off)
input int    MaxSpreadPoints    = 500;    // Maximum spread in points
input int    MaxTradesPerDay    = 1;      // Maximum number of entries per server day
input bool   AllowStacking      = false;  // false: one position at a time; true: a new signal may add to / reverse an open position (netting)
input double MaxDrawdownPercent = 15.0;   // Stop new entries if equity falls this % below its peak
input int    DrawdownCooldownDays = 14;   // Days of pause after the drawdown guard, then the peak is reset
input int    MagicNumber        = 20260920; // Magic number
input int    DeviationPoints    = 20;     // Maximum slippage in points

enum PatternState { STATE_NONE, STATE_WAIT_RETEST_BULL, STATE_WAIT_RETEST_BEAR };

CTrade       g_trade;
datetime     g_currentDay   = 0;
bool         g_zoneReady    = false;
double       g_zoneHigh     = 0;
double       g_zoneLow      = 0;
PatternState g_state        = STATE_NONE;
bool         g_retestTouched = false;
int          g_tradesToday  = 0;
datetime     g_lastBarTime  = 0;
double       g_equityPeak   = 0;
datetime     g_blockedSince = 0;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
  {
   if(ZoneHours < 1 || ZoneHours > 12 || ZoneStartHour < 0 || ZoneStartHour > 23 || ZoneStartHour + ZoneHours > 24)
     {
      Print("Invalid zone settings: the zone must fit inside one server day.");
      return INIT_PARAMETERS_INCORRECT;
     }
   g_trade.SetExpertMagicNumber(MagicNumber);
   g_trade.SetDeviationInPoints(DeviationPoints);
   g_trade.SetTypeFillingBySymbol(_Symbol);
   g_equityPeak = AccountInfoDouble(ACCOUNT_EQUITY);
   PrintFormat("H4BreakoutRetest_XAU started on %s (zone %02d:00 + %d h, server time)", _Symbol, ZoneStartHour, ZoneHours);
   ResetForNewDay();
   return INIT_SUCCEEDED;
  }

//+------------------------------------------------------------------+
//| Truncates a time to the start of its day                         |
//+------------------------------------------------------------------+
datetime GetDayStart(datetime t)
  {
   MqlDateTime dt;
   TimeToStruct(t, dt);
   dt.hour = 0;
   dt.min  = 0;
   dt.sec  = 0;
   return StructToTime(dt);
  }

//+------------------------------------------------------------------+
//| Clears the daily state                                           |
//+------------------------------------------------------------------+
void ResetForNewDay()
  {
   g_currentDay    = GetDayStart(TimeCurrent());
   g_zoneReady     = false;
   g_zoneHigh      = 0;
   g_zoneLow       = 0;
   g_state         = STATE_NONE;
   g_retestTouched = false;
   g_tradesToday   = 0;
  }

//+------------------------------------------------------------------+
//| Starts a new day when the server date changes                    |
//+------------------------------------------------------------------+
void CheckNewDay()
  {
   if(GetDayStart(TimeCurrent()) != g_currentDay)
      ResetForNewDay();
  }

//+------------------------------------------------------------------+
//| Computes the zone from the M5 candles inside the zone window     |
//| (only candles that opened inside [start, end) are used)          |
//+------------------------------------------------------------------+
void MaybeComputeZone()
  {
   if(g_zoneReady) return;
   datetime zoneStart = g_currentDay + ZoneStartHour * 3600;
   datetime zoneEnd   = zoneStart + ZoneHours * 3600;
   if(TimeCurrent() < zoneEnd) return;               // the zone window is not over yet
   MqlRates r[];
   int n = CopyRates(_Symbol, PERIOD_M5, zoneStart, zoneEnd - 1, r);
   if(n <= 0) return;                                // no data yet, retry on the next tick
   double hi = r[0].high, lo = r[0].low;
   for(int i = 1; i < n; i++)
     {
      if(r[i].high > hi) hi = r[i].high;
      if(r[i].low  < lo) lo = r[i].low;
     }
   g_zoneHigh  = hi;
   g_zoneLow   = lo;
   g_zoneReady = true;
   PrintFormat("Zone of the day ready (%d M5 candles): High=%.2f Low=%.2f", n, g_zoneHigh, g_zoneLow);
  }

//+------------------------------------------------------------------+
//| True if this EA already has a position on the symbol             |
//+------------------------------------------------------------------+
bool HaveOwnPosition()
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong t = PositionGetTicket(i);
      if(t != 0 && PositionSelectByTicket(t) && PositionGetString(POSITION_SYMBOL) == _Symbol
         && PositionGetInteger(POSITION_MAGIC) == MagicNumber)
         return true;
     }
   return false;
  }

//+------------------------------------------------------------------+
//| Lot size from the risk percentage and the stop distance          |
//| Returns 0 when the trade must be skipped                         |
//+------------------------------------------------------------------+
double CalcLotSize(double riskDistance)
  {
   double equity    = AccountInfoDouble(ACCOUNT_EQUITY);
   double riskMoney = equity * RiskPercent / 100.0;
   double tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE_LOSS);
   if(tickValue <= 0) tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSize  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double lotStep   = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double lotMin    = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double lotMax    = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   if(tickSize <= 0 || tickValue <= 0 || lotStep <= 0) return 0;
   double lossPerLot = riskDistance / tickSize * tickValue;
   if(lossPerLot <= 0) return 0;
   double lots = MathFloor(riskMoney / lossPerLot / lotStep) * lotStep;
   if(lots < lotMin)
     {
      // the broker minimum lot risks more than requested
      if(MaxMinLotRiskPct > 0 && lotMin * lossPerLot / equity * 100.0 > MaxMinLotRiskPct)
        {
         PrintFormat("Skipped: the minimum lot %.2f would risk %.1f%% of equity (limit %.1f%%).", lotMin, lotMin * lossPerLot / equity * 100.0, MaxMinLotRiskPct);
         return 0;
        }
      lots = lotMin;
     }
   lots = MathMin(lots, lotMax);
   int digits = (int)MathMax(0, MathRound(-MathLog10(lotStep)));
   return NormalizeDouble(lots, digits);
  }

//+------------------------------------------------------------------+
//| Opens a market order with fixed percentage stop and target       |
//+------------------------------------------------------------------+
void OpenTrade(bool isBuy)
  {
   if(!AllowStacking && HaveOwnPosition())
     {
      Print("Signal ignored: a position is already open (AllowStacking = false).");
      return;
     }
   if(SymbolInfoInteger(_Symbol, SYMBOL_SPREAD) > MaxSpreadPoints)
     {
      Print("Spread too high, trade skipped.");
      return;
     }
   if(!TerminalInfoInteger(TERMINAL_TRADE_ALLOWED) || !MQLInfoInteger(MQL_TRADE_ALLOWED))
     {
      Print("Trading is not allowed (check the AutoTrading button and the EA settings).");
      return;
     }
   int    dg    = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   double price = isBuy ? SymbolInfoDouble(_Symbol, SYMBOL_ASK) : SymbolInfoDouble(_Symbol, SYMBOL_BID);
   if(price <= 0) return;
   double slDist = price * StopLossPercent / 100.0;
   double tpDist = price * TakeProfitPercent / 100.0;
   double sl = NormalizeDouble(isBuy ? price - slDist : price + slDist, dg);
   double tp = NormalizeDouble(isBuy ? price + tpDist : price - tpDist, dg);
   double lots = CalcLotSize(slDist);
   if(lots <= 0) return;
   double margin = 0;
   if(OrderCalcMargin(isBuy ? ORDER_TYPE_BUY : ORDER_TYPE_SELL, _Symbol, lots, price, margin)
      && margin > AccountInfoDouble(ACCOUNT_MARGIN_FREE) * 0.95)
     {
      PrintFormat("Skipped: not enough free margin (needed %.2f).", margin);
      return;
     }
   bool ok = isBuy ? g_trade.Buy(lots, _Symbol, 0, sl, tp, "H4BreakoutRetest")
                   : g_trade.Sell(lots, _Symbol, 0, sl, tp, "H4BreakoutRetest");
   uint rc = g_trade.ResultRetcode();
   if(ok && (rc == TRADE_RETCODE_DONE || rc == TRADE_RETCODE_DONE_PARTIAL || rc == TRADE_RETCODE_PLACED))
     {
      g_tradesToday++;
      PrintFormat("Trade opened: %s | lots %.2f | price %.2f | SL %.2f | TP %.2f", isBuy ? "BUY" : "SELL", lots, price, sl, tp);
     }
   else
      PrintFormat("Order failed: retcode %u - %s", rc, g_trade.ResultRetcodeDescription());
  }

//+------------------------------------------------------------------+
//| Breakout + retest state machine, evaluated once per closed M5    |
//+------------------------------------------------------------------+
void ProcessClosedBar()
  {
   double lastClose = iClose(_Symbol, PERIOD_M5, 1);
   double lastLow   = iLow(_Symbol, PERIOD_M5, 1);
   double lastHigh  = iHigh(_Symbol, PERIOD_M5, 1);
   if(lastClose <= 0) return;

   if(g_state == STATE_NONE)
     {
      if(lastClose > g_zoneHigh)
        {
         g_state = STATE_WAIT_RETEST_BULL;
         g_retestTouched = false;
         PrintFormat("Close above the zone (%.2f): waiting for the retest.", g_zoneHigh);
        }
      else if(lastClose < g_zoneLow)
        {
         g_state = STATE_WAIT_RETEST_BEAR;
         g_retestTouched = false;
         PrintFormat("Close below the zone (%.2f): waiting for the retest.", g_zoneLow);
        }
     }
   else if(g_state == STATE_WAIT_RETEST_BULL)
     {
      if(lastLow <= g_zoneHigh)
         g_retestTouched = true;                       // price came back to test the broken level
      if(lastClose < g_zoneLow)
         g_state = STATE_NONE;                         // failed breakout: price is back under the whole zone
      else if(g_retestTouched && lastClose > g_zoneHigh)
        {
         OpenTrade(true);                              // retest confirmed, closing above the zone again
         g_state = STATE_NONE;
        }
     }
   else if(g_state == STATE_WAIT_RETEST_BEAR)
     {
      if(lastHigh >= g_zoneLow)
         g_retestTouched = true;
      if(lastClose > g_zoneHigh)
         g_state = STATE_NONE;
      else if(g_retestTouched && lastClose < g_zoneLow)
        {
         OpenTrade(false);
         g_state = STATE_NONE;
        }
     }
  }

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
  {
   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   g_equityPeak = MathMax(g_equityPeak, equity);
   double ddPercent = (g_equityPeak > 0) ? (g_equityPeak - equity) / g_equityPeak * 100.0 : 0;
   bool tradingBlocked = (ddPercent >= MaxDrawdownPercent);
   if(tradingBlocked)
     {
      if(g_blockedSince == 0)
         g_blockedSince = TimeCurrent();
      else if(TimeCurrent() - g_blockedSince >= (datetime)DrawdownCooldownDays * 86400)
        {
         PrintFormat("Drawdown pause of %d days is over: trading resumes, equity peak reset.", DrawdownCooldownDays);
         g_equityPeak = equity;
         tradingBlocked = false;
         g_blockedSince = 0;
        }
     }
   else
      g_blockedSince = 0;

   CheckNewDay();
   MaybeComputeZone();

   datetime barTime = iTime(_Symbol, PERIOD_M5, 0);
   if(barTime == g_lastBarTime) return;               // the logic runs once per new M5 candle
   g_lastBarTime = barTime;
   if(g_zoneReady && !tradingBlocked && g_tradesToday < MaxTradesPerDay)
      ProcessClosedBar();
  }
