#ifndef MEMO_ENGINES_ORDER_BLOCK_ENGINE_MQH
#define MEMO_ENGINES_ORDER_BLOCK_ENGINE_MQH

#include <MEMO\Core\Settings.mqh>
#include <MEMO\Core\MarketData.mqh>
#include <MEMO\Managers\LoggingManager.mqh>

class COrderBlockEngine
{
private:
   MEMO_Settings m_settings;
   CLoggingManager *m_log;

public:
   COrderBlockEngine()
   {
      m_log = NULL;
   }

   void Init(const MEMO_Settings &settings, CLoggingManager *logger)
   {
      m_settings = settings;
      m_log = logger;
   }

   bool DetectRecent(const string symbol,
                     const MEMO_Direction direction,
                     MEMO_OrderBlockZone &zone) const
   {
      zone.Reset();

      MqlRates rates[];
      const int bars = MathMax(20, m_settings.order_block_lookback_bars + 5);
      if(!MEMO_CopyRatesSeries(symbol, m_settings.execution_tf, 0, bars, rates))
         return false;

      for(int i = 2; i < ArraySize(rates); i++)
      {
         const bool bearish_candle = rates[i].close < rates[i].open;
         const bool bullish_candle = rates[i].close > rates[i].open;

         if(direction == MEMO_DIR_BUY && bearish_candle)
         {
            zone.valid = true;
            zone.symbol = symbol;
            zone.direction = MEMO_DIR_BUY;
            zone.time = rates[i].time;
            zone.lower = rates[i].low;
            zone.upper = MathMax(rates[i].open, rates[i].close);
            zone.breaker = false;
            zone.mitigated = IsRetested(symbol, zone);
            break;
         }

         if(direction == MEMO_DIR_SELL && bullish_candle)
         {
            zone.valid = true;
            zone.symbol = symbol;
            zone.direction = MEMO_DIR_SELL;
            zone.time = rates[i].time;
            zone.lower = MathMin(rates[i].open, rates[i].close);
            zone.upper = rates[i].high;
            zone.breaker = false;
            zone.mitigated = IsRetested(symbol, zone);
            break;
         }
      }

      if(m_log != NULL)
      {
         const string verdict = zone.valid ? "ACCEPT" : "REJECT";
         m_log.Decision("OrderBlockEngine", symbol, "OrderBlock", verdict, zone.valid ? 10.0 : 0.0,
                        zone.valid ? "Order block " + DoubleToString(zone.lower, 2) + "-" + DoubleToString(zone.upper, 2)
                                   : "No recent order block in setup direction");
      }

      return zone.valid;
   }

   bool IsRetested(const string symbol, const MEMO_OrderBlockZone &zone) const
   {
      if(!zone.valid)
         return false;

      const double point = SymbolInfoDouble(symbol, SYMBOL_POINT);
      const double sensitivity = m_settings.entry_sensitivity_points * point;
      const double price = zone.direction == MEMO_DIR_BUY ? MEMO_Ask(symbol) : MEMO_Bid(symbol);

      return price >= zone.lower - sensitivity && price <= zone.upper + sensitivity;
   }
};

#endif
