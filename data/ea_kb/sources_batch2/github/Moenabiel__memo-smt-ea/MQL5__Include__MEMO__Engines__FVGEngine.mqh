#ifndef MEMO_ENGINES_FVG_ENGINE_MQH
#define MEMO_ENGINES_FVG_ENGINE_MQH

#include <MEMO\Core\Settings.mqh>
#include <MEMO\Core\MarketData.mqh>
#include <MEMO\Managers\LoggingManager.mqh>

class CFVGEngine
{
private:
   MEMO_Settings m_settings;
   CLoggingManager *m_log;

public:
   CFVGEngine()
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
                     MEMO_FVGZone &zone) const
   {
      zone.Reset();

      MqlRates rates[];
      if(!MEMO_CopyRatesSeries(symbol, m_settings.execution_tf, 0, 60, rates))
         return false;

      const double point = SymbolInfoDouble(symbol, SYMBOL_POINT);
      if(point <= 0.0)
         return false;

      for(int i = 1; i + 2 < ArraySize(rates); i++)
      {
         const MqlRates newer = rates[i];
         const MqlRates older = rates[i + 2];

         double lower = 0.0;
         double upper = 0.0;
         bool valid = false;

         if(direction == MEMO_DIR_BUY && older.high < newer.low)
         {
            lower = older.high;
            upper = newer.low;
            valid = true;
         }
         else if(direction == MEMO_DIR_SELL && older.low > newer.high)
         {
            lower = newer.high;
            upper = older.low;
            valid = true;
         }

         if(!valid)
            continue;

         const double gap_points = (upper - lower) / point;
         if(gap_points < m_settings.minimum_fvg_points)
            continue;
         if(m_settings.maximum_fvg_points > 0.0 && gap_points > m_settings.maximum_fvg_points)
            continue;

         zone.valid = true;
         zone.symbol = symbol;
         zone.direction = direction;
         zone.left_time = older.time;
         zone.right_time = newer.time;
         zone.lower = lower;
         zone.upper = upper;
         zone.mitigated = IsRetested(symbol, zone);

         if(m_log != NULL)
            m_log.Decision("FVGEngine", symbol, "FVG", "ACCEPT", 10.0,
                           MEMO_DirectionText(direction) + " FVG " + DoubleToString(lower, 2) + "-" + DoubleToString(upper, 2));

         return true;
      }

      if(m_log != NULL)
         m_log.Decision("FVGEngine", symbol, "FVG", "REJECT", 0.0, "No valid FVG in setup direction");

      return false;
   }

   bool IsRetested(const string symbol, const MEMO_FVGZone &zone) const
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
