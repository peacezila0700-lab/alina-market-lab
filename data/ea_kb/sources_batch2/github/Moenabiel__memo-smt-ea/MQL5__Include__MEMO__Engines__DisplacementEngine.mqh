#ifndef MEMO_ENGINES_DISPLACEMENT_ENGINE_MQH
#define MEMO_ENGINES_DISPLACEMENT_ENGINE_MQH

#include <MEMO\Core\Settings.mqh>
#include <MEMO\Core\MarketData.mqh>
#include <MEMO\Managers\LoggingManager.mqh>

class CDisplacementEngine
{
private:
   MEMO_Settings m_settings;
   CLoggingManager *m_log;

   bool CreatesFVG(const MqlRates &rates[], const MEMO_Direction direction) const
   {
      if(ArraySize(rates) < 4)
         return false;

      if(direction == MEMO_DIR_BUY)
         return rates[3].high < rates[1].low;
      if(direction == MEMO_DIR_SELL)
         return rates[3].low > rates[1].high;
      return false;
   }

   int ConsecutiveImbalanceCount(const MqlRates &rates[], const MEMO_Direction direction) const
   {
      int count = 0;
      for(int i = 1; i < ArraySize(rates); i++)
      {
         const double range = rates[i].high - rates[i].low;
         if(range <= 0.0)
            break;

         const double body = MathAbs(rates[i].close - rates[i].open);
         const double ratio = body / range;
         const bool bullish = rates[i].close > rates[i].open;
         const bool bearish = rates[i].close < rates[i].open;

         if(direction == MEMO_DIR_BUY && bullish && ratio >= m_settings.minimum_body_ratio)
            count++;
         else if(direction == MEMO_DIR_SELL && bearish && ratio >= m_settings.minimum_body_ratio)
            count++;
         else
            break;
      }
      return count;
   }

public:
   CDisplacementEngine()
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
               MEMO_DisplacementSignal &signal) const
   {
      signal.Reset();

      MqlRates rates[];
      if(!MEMO_CopyRatesSeries(symbol, m_settings.execution_tf, 0, 10, rates))
         return false;

      const MqlRates bar = rates[1];
      const double point = SymbolInfoDouble(symbol, SYMBOL_POINT);
      if(point <= 0.0)
         return false;

      const double range = bar.high - bar.low;
      const double body = MathAbs(bar.close - bar.open);
      if(range <= 0.0)
         return false;

      const bool direction_ok = (direction == MEMO_DIR_BUY && bar.close > bar.open)
                             || (direction == MEMO_DIR_SELL && bar.close < bar.open);
      const double body_points = body / point;
      const double atr_points = MEMO_ATRPoints(symbol, m_settings.execution_tf, m_settings.atr_period, 1);
      const double body_ratio = body / range;
      const bool fvg_created = CreatesFVG(rates, direction);
      const int imbalance_count = ConsecutiveImbalanceCount(rates, direction);

      const bool size_ok = body_points >= m_settings.minimum_displacement_points
                        || (atr_points > 0.0 && body_points >= atr_points * m_settings.displacement_atr_multiple);

      const bool valid = direction_ok
                      && size_ok
                      && body_ratio >= m_settings.minimum_body_ratio
                      && imbalance_count >= MathMax(1, m_settings.consecutive_imbalance_candles)
                      && fvg_created;

      signal.valid = valid;
      signal.symbol = symbol;
      signal.direction = direction;
      signal.bar_time = bar.time;
      signal.body_points = body_points;
      signal.atr_points = atr_points;
      signal.body_ratio = body_ratio;
      signal.created_fvg = fvg_created;

      if(m_log != NULL)
      {
         const string verdict = valid ? "ACCEPT" : "REJECT";
         m_log.Decision("DisplacementEngine", symbol, "Displacement", verdict, valid ? 15.0 : 0.0,
                        "body=" + DoubleToString(body_points, 1)
                        + " atr=" + DoubleToString(atr_points, 1)
                        + " ratio=" + DoubleToString(body_ratio, 2)
                        + " fvg=" + (fvg_created ? "yes" : "no"));
      }

      return valid;
   }
};

#endif
