#ifndef MEMO_ENGINES_MARKET_STRUCTURE_ENGINE_MQH
#define MEMO_ENGINES_MARKET_STRUCTURE_ENGINE_MQH

#include <MEMO\Core\Settings.mqh>
#include <MEMO\Core\MarketData.mqh>
#include <MEMO\Managers\LoggingManager.mqh>

class CMarketStructureEngine
{
private:
   MEMO_Settings m_settings;
   CLoggingManager *m_log;

   bool IsSwingHigh(const MqlRates &rates[], const int index, const int depth) const
   {
      for(int j = 1; j <= depth; j++)
      {
         if(index - j < 0 || index + j >= ArraySize(rates))
            return false;
         if(rates[index].high <= rates[index - j].high || rates[index].high <= rates[index + j].high)
            return false;
      }
      return true;
   }

   bool IsSwingLow(const MqlRates &rates[], const int index, const int depth) const
   {
      for(int j = 1; j <= depth; j++)
      {
         if(index - j < 0 || index + j >= ArraySize(rates))
            return false;
         if(rates[index].low >= rates[index - j].low || rates[index].low >= rates[index + j].low)
            return false;
      }
      return true;
   }

public:
   CMarketStructureEngine()
   {
      m_log = NULL;
   }

   void Init(const MEMO_Settings &settings, CLoggingManager *logger)
   {
      m_settings = settings;
      m_log = logger;
   }

   bool Detect(const string symbol,
               const MEMO_Direction direction,
               MEMO_StructureSignal &signal) const
   {
      signal.Reset();

      MqlRates rates[];
      const int bars = m_settings.structure_lookback_bars + m_settings.swing_depth * 2 + 5;
      if(!MEMO_CopyRatesSeries(symbol, m_settings.structure_tf, 0, bars, rates))
         return false;

      double swing_high = 0.0;
      double swing_low = 0.0;
      datetime swing_high_time = 0;
      datetime swing_low_time = 0;

      for(int i = m_settings.swing_depth + 2; i < ArraySize(rates) - m_settings.swing_depth; i++)
      {
         if(swing_high_time == 0 && IsSwingHigh(rates, i, m_settings.swing_depth))
         {
            swing_high = rates[i].high;
            swing_high_time = rates[i].time;
         }

         if(swing_low_time == 0 && IsSwingLow(rates, i, m_settings.swing_depth))
         {
            swing_low = rates[i].low;
            swing_low_time = rates[i].time;
         }

         if(swing_high_time > 0 && swing_low_time > 0)
            break;
      }

      const MqlRates last = rates[1];
      const MqlRates previous = rates[2];

      if(direction == MEMO_DIR_BUY && swing_high_time > 0 && last.close > swing_high)
      {
         signal.valid = true;
         signal.mss = true;
         signal.choch = previous.close <= swing_high;
         signal.symbol = symbol;
         signal.direction = MEMO_DIR_BUY;
         signal.event_time = last.time;
         signal.break_level = swing_high;
         signal.reason = signal.choch ? "Bullish CHOCH above swing high" : "Bullish MSS above swing high";
      }
      else if(direction == MEMO_DIR_SELL && swing_low_time > 0 && last.close < swing_low)
      {
         signal.valid = true;
         signal.mss = true;
         signal.choch = previous.close >= swing_low;
         signal.symbol = symbol;
         signal.direction = MEMO_DIR_SELL;
         signal.event_time = last.time;
         signal.break_level = swing_low;
         signal.reason = signal.choch ? "Bearish CHOCH below swing low" : "Bearish MSS below swing low";
      }

      if(m_log != NULL)
      {
         const string verdict = signal.valid ? "ACCEPT" : "REJECT";
         m_log.Decision("MarketStructureEngine", symbol, "Structure", verdict, signal.valid ? 20.0 : 0.0,
                        signal.valid ? signal.reason : "No MSS/CHOCH in setup direction");
      }

      return signal.valid;
   }
};

#endif
