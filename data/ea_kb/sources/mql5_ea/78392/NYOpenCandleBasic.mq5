//+------------------------------------------------------------------+
//|                                          NYOpenCandleBasic.mq5   |
//|  Basic version: trades the direction of the M5 candle that opens |
//|  the New York session (9:30 NY) on index CFDs such as US100.     |
//|  One trade per day, fixed SL/TP, forced close. No martingale.    |
//+------------------------------------------------------------------+
#property copyright   "AlexLab"
#property version     "1.00"
#property description "Basic NY open candle EA: one trade per day in the direction of the 9:30 New York M5 candle."
#property description "Entry only if the candle body is larger than the sum of its wicks and the tick volume is above average."
#property description "Fixed stop loss and take profit, forced close at a chosen time. No martingale, grid or averaging."
#property description "Educational example. No profit is guaranteed. Test on your broker's data first."

#include <Trade/Trade.mqh>

input double InpRiskMoney    = 100.0;   // Risk per trade in account currency (lot is calculated from the stop)
input bool   InpUseFixedLot  = false;   // Use a fixed lot instead
input double InpFixedLot     = 0.10;    // Fixed lot size
input double InpSlPoints     = 30.0;    // Stop loss in price units (made for index prices about 20000, scaled on other symbols)
input double InpTpPoints     = 120.0;   // Take profit in price units
input int    InpCandleHour   = 16;      // Hour of the 9:30 NY candle on the broker server (16 on most NY-close servers)
input int    InpCandleMinute = 30;      // Minute of that candle
input bool   InpUseVolFilter = true;    // Require tick volume above its average
input int    InpVolMaLen     = 20;      // Number of M5 bars for the average volume
input double InpVolMult      = 1.5;     // Candle volume must be above average x this value
input int    InpCloseHour    = 19;      // Forced close hour, broker server time
input long   InpMagic        = 26102001; // Magic number

CTrade   trade;
datetime lastBar = 0;
int      lastTradeDay = -1;
double   scale = 1.0;

int OnInit()
{
   if(InpSlPoints <= 0.0 || InpTpPoints <= 0.0 || InpVolMaLen < 2 || InpRiskMoney <= 0.0)
   {
      Print("NY Open Candle Basic: wrong inputs.");
      return INIT_PARAMETERS_INCORRECT;
   }
   double px = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   scale = (px >= 5000.0 || px <= 0.0) ? 1.0 : px / 20000.0;   // other symbols: same percentage stop
   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(50);
   trade.SetTypeFillingBySymbol(_Symbol);
   return INIT_SUCCEEDED;
}

ulong OwnPosition()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong t = PositionGetTicket(i);
      if(t == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) == _Symbol && PositionGetInteger(POSITION_MAGIC) == InpMagic)
         return t;
   }
   return 0;
}

double NormalizeLots(double lots)
{
   double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double vmin = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double vmax = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   if(step <= 0.0) step = vmin;
   lots = MathFloor(lots / step + 1e-9) * step;
   if(lots < vmin) return 0.0;
   return MathMin(lots, vmax);
}

// Lot from the risk money; reduced if the free margin is not enough
double CalcLots(const bool isBuy, const double entry, const double sl)
{
   double lots;
   if(InpUseFixedLot) lots = NormalizeLots(InpFixedLot);
   else
   {
      double profit = 0.0;
      if(!OrderCalcProfit(isBuy ? ORDER_TYPE_BUY : ORDER_TYPE_SELL, _Symbol, 1.0, entry, sl, profit) || profit == 0.0)
         return 0.0;
      lots = NormalizeLots(InpRiskMoney / MathAbs(profit));
   }
   if(lots <= 0.0) return 0.0;
   double margin = 0.0;
   if(OrderCalcMargin(isBuy ? ORDER_TYPE_BUY : ORDER_TYPE_SELL, _Symbol, lots, entry, margin) && margin > 0.0)
   {
      double freeMargin = AccountInfoDouble(ACCOUNT_MARGIN_FREE) * 0.9;
      if(margin > freeMargin) lots = NormalizeLots(lots * freeMargin / margin);
   }
   return lots;
}

void CloseIfTime()
{
   ulong t = OwnPosition();
   if(t == 0) return;
   MqlDateTime now, op;
   TimeToStruct(TimeCurrent(), now);
   TimeToStruct((datetime)PositionGetInteger(POSITION_TIME), op);
   bool otherDay = (op.year * 1000 + op.day_of_year) != (now.year * 1000 + now.day_of_year);
   if(otherDay || now.hour >= InpCloseHour)
      trade.PositionClose(t);
}

void OnTick()
{
   CloseIfTime();

   datetime bar0 = iTime(_Symbol, PERIOD_M5, 0);
   if(bar0 == lastBar) return;
   lastBar = bar0;
   if(OwnPosition() != 0) return;

   MqlDateTime now;
   TimeToStruct(TimeCurrent(), now);
   int dayKey = now.year * 1000 + now.day_of_year;
   if(dayKey == lastTradeDay) return;

   int need = InpVolMaLen + 3;
   MqlRates r[];
   ArraySetAsSeries(r, true);
   if(CopyRates(_Symbol, PERIOD_M5, 0, need, r) < need) return;

   MqlDateTime st;
   TimeToStruct(r[1].time, st);                       // last closed M5 candle must be the NY open candle
   if(st.hour != InpCandleHour || st.min != InpCandleMinute) return;
   if(st.year * 1000 + st.day_of_year != dayKey) return;
   lastTradeDay = dayKey;

   double body  = MathAbs(r[1].close - r[1].open);
   double wicks = (r[1].high - r[1].low) - body;
   bool up = r[1].close > r[1].open;
   bool dn = r[1].close < r[1].open;
   double vsum = 0.0;
   for(int i = 1; i <= InpVolMaLen; i++) vsum += (double)r[i].tick_volume;
   double volMa = vsum / InpVolMaLen;
   bool volOk = !InpUseVolFilter || ((double)r[1].tick_volume > volMa * InpVolMult);
   if(!(body > wicks) || !volOk || (!up && !dn)) return;

   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   int digits = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   double sl = InpSlPoints * scale, tp = InpTpPoints * scale;
   if(up)
   {
      double slp = NormalizeDouble(ask - sl, digits), tpp = NormalizeDouble(ask + tp, digits);
      double lots = CalcLots(true, ask, slp);
      if(lots > 0.0) trade.Buy(lots, _Symbol, ask, slp, tpp, "NYO basic buy");
   }
   else
   {
      double slp = NormalizeDouble(bid + sl, digits), tpp = NormalizeDouble(bid - tp, digits);
      double lots = CalcLots(false, bid, slp);
      if(lots > 0.0) trade.Sell(lots, _Symbol, bid, slp, tpp, "NYO basic sell");
   }
}
//+------------------------------------------------------------------+
