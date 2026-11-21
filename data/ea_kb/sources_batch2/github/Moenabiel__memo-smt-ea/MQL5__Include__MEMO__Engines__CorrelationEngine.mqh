#ifndef MEMO_ENGINES_CORRELATION_ENGINE_MQH
#define MEMO_ENGINES_CORRELATION_ENGINE_MQH

#include <MEMO\Core\Settings.mqh>
#include <MEMO\Managers\LoggingManager.mqh>

class CCorrelationEngine
{
private:
   MEMO_Settings m_settings;
   CLoggingManager *m_log;

public:
   CCorrelationEngine()
   {
      m_log = NULL;
   }

   void Init(const MEMO_Settings &settings, CLoggingManager *logger)
   {
      m_settings = settings;
      m_log = logger;
   }

   double Calculate(const string symbol_a, const string symbol_b, bool &ok) const
   {
      ok = false;
      const int count = m_settings.correlation_lookback + 1;

      double close_a[];
      double close_b[];
      if(CopyClose(symbol_a, m_settings.correlation_tf, 1, count, close_a) < count)
         return 0.0;
      if(CopyClose(symbol_b, m_settings.correlation_tf, 1, count, close_b) < count)
         return 0.0;

      ArraySetAsSeries(close_a, true);
      ArraySetAsSeries(close_b, true);

      double sum_x = 0.0;
      double sum_y = 0.0;
      double sum_x2 = 0.0;
      double sum_y2 = 0.0;
      double sum_xy = 0.0;
      int n = 0;

      for(int i = 0; i < m_settings.correlation_lookback; i++)
      {
         if(close_a[i + 1] == 0.0 || close_b[i + 1] == 0.0)
            continue;

         const double x = (close_a[i] - close_a[i + 1]) / close_a[i + 1];
         const double y = (close_b[i] - close_b[i + 1]) / close_b[i + 1];
         sum_x += x;
         sum_y += y;
         sum_x2 += x * x;
         sum_y2 += y * y;
         sum_xy += x * y;
         n++;
      }

      if(n < 10)
         return 0.0;

      const double numerator = n * sum_xy - sum_x * sum_y;
      const double denom_x = n * sum_x2 - sum_x * sum_x;
      const double denom_y = n * sum_y2 - sum_y * sum_y;
      if(denom_x <= 0.0 || denom_y <= 0.0)
         return 0.0;

      ok = true;
      return numerator / MathSqrt(denom_x * denom_y);
   }

   bool IsValid(const string symbol_a, const string symbol_b, double &correlation, string &reason) const
   {
      bool ok = false;
      correlation = Calculate(symbol_a, symbol_b, ok);

      if(!ok)
      {
         reason = "Correlation unavailable";
         return false;
      }

      if(correlation < m_settings.minimum_correlation)
      {
         reason = "Correlation below threshold: " + DoubleToString(correlation, 3);
         if(m_log != NULL)
            m_log.Decision("CorrelationEngine", symbol_a + "/" + symbol_b, "Correlation", "REJECT", correlation, reason);
         return false;
      }

      reason = "Correlation accepted: " + DoubleToString(correlation, 3);
      return true;
   }

   int Score(const double correlation) const
   {
      if(correlation >= 0.90)
         return 10;
      if(correlation >= m_settings.minimum_correlation)
         return 7;
      return 0;
   }
};

#endif
