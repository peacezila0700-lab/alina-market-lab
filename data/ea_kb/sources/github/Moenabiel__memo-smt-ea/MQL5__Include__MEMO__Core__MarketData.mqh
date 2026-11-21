#ifndef MEMO_CORE_MARKET_DATA_MQH
#define MEMO_CORE_MARKET_DATA_MQH

#include <MEMO\Core\Types.mqh>

bool MEMO_CopyRatesSeries(const string symbol,
                          const ENUM_TIMEFRAMES timeframe,
                          const int start_pos,
                          const int count,
                          MqlRates &rates[])
{
   ArrayResize(rates, 0);
   if(count <= 0)
      return false;

   const int copied = CopyRates(symbol, timeframe, start_pos, count, rates);
   if(copied < count)
      return false;

   ArraySetAsSeries(rates, true);
   return true;
}

double MEMO_ATRPoints(const string symbol,
                      const ENUM_TIMEFRAMES timeframe,
                      const int period,
                      const int shift = 1)
{
   const double point = SymbolInfoDouble(symbol, SYMBOL_POINT);
   if(point <= 0.0)
      return 0.0;

   const int handle = iATR(symbol, timeframe, period);
   if(handle == INVALID_HANDLE)
      return 0.0;

   double buffer[];
   ArraySetAsSeries(buffer, true);
   const int copied = CopyBuffer(handle, 0, shift, 1, buffer);
   IndicatorRelease(handle);

   if(copied < 1)
      return 0.0;

   return buffer[0] / point;
}

double MEMO_ADXValue(const string symbol,
                     const ENUM_TIMEFRAMES timeframe,
                     const int period,
                     const int shift = 1)
{
   const int handle = iADX(symbol, timeframe, period);
   if(handle == INVALID_HANDLE)
      return 0.0;

   double buffer[];
   ArraySetAsSeries(buffer, true);
   const int copied = CopyBuffer(handle, 0, shift, 1, buffer);
   IndicatorRelease(handle);

   if(copied < 1)
      return 0.0;

   return buffer[0];
}

double MEMO_Bid(const string symbol)
{
   double value = 0.0;
   SymbolInfoDouble(symbol, SYMBOL_BID, value);
   return value;
}

double MEMO_Ask(const string symbol)
{
   double value = 0.0;
   SymbolInfoDouble(symbol, SYMBOL_ASK, value);
   return value;
}

double MEMO_MidPrice(const string symbol)
{
   const double bid = MEMO_Bid(symbol);
   const double ask = MEMO_Ask(symbol);
   if(bid <= 0.0 || ask <= 0.0)
      return 0.0;
   return (bid + ask) * 0.5;
}

double MEMO_NormalizeVolume(const string symbol, const double lots)
{
   const double min_volume = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN);
   const double max_volume = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MAX);
   const double step = SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP);

   if(step <= 0.0)
      return lots;

   double normalized = MathFloor(lots / step) * step;
   if(normalized < min_volume)
      normalized = min_volume;
   if(normalized > max_volume)
      normalized = max_volume;

   return NormalizeDouble(normalized, 2);
}

double MEMO_RiskDistance(const MEMO_Direction direction, const double entry, const double stop)
{
   if(direction == MEMO_DIR_BUY)
      return entry - stop;
   if(direction == MEMO_DIR_SELL)
      return stop - entry;
   return 0.0;
}

#endif
