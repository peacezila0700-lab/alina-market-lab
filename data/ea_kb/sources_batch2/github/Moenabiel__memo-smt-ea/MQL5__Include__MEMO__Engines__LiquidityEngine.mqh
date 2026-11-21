#ifndef MEMO_ENGINES_LIQUIDITY_ENGINE_MQH
#define MEMO_ENGINES_LIQUIDITY_ENGINE_MQH

#include <MEMO\Core\Settings.mqh>
#include <MEMO\Core\MarketData.mqh>
#include <MEMO\Managers\LoggingManager.mqh>
#include <MEMO\Managers\SessionManager.mqh>

class CLiquidityEngine
{
private:
   MEMO_Settings m_settings;
   CLoggingManager *m_log;
   CSessionManager *m_sessions;

   bool BuildPreviousRange(const string symbol,
                           const ENUM_TIMEFRAMES timeframe,
                           const string name,
                           MEMO_PriceRange &range)
   {
      range.Reset(name);

      MqlRates rates[];
      if(!MEMO_CopyRatesSeries(symbol, timeframe, 1, 1, rates))
         return false;

      range.high = rates[0].high;
      range.low = rates[0].low;
      range.start_time = rates[0].time;
      range.end_time = rates[0].time + PeriodSeconds(timeframe);
      range.valid = range.high > range.low;
      return range.valid;
   }

   bool BuildSessionRange(const string symbol,
                          const MEMO_SessionId session,
                          const ENUM_TIMEFRAMES timeframe,
                          const datetime now,
                          MEMO_PriceRange &range)
   {
      range.Reset(MEMO_SessionText(session) + " Session");

      int start_minute = 0;
      int end_minute = 0;
      if(m_sessions == NULL || !m_sessions.WindowForSession(session, start_minute, end_minute))
         return false;

      datetime session_start = MEMO_StartOfDay(now) + start_minute * 60;
      datetime session_end = MEMO_StartOfDay(now) + end_minute * 60;
      if(session_end <= session_start)
         session_end += 86400;
      if(now < session_start)
      {
         session_start -= 86400;
         session_end -= 86400;
      }

      MqlRates rates[];
      const int bars = MathMax(300, (int)(172800 / PeriodSeconds(timeframe)));
      if(!MEMO_CopyRatesSeries(symbol, timeframe, 0, bars, rates))
         return false;

      bool seeded = false;
      for(int i = 1; i < ArraySize(rates); i++)
      {
         if(rates[i].time < session_start || rates[i].time >= session_end)
            continue;

         if(!seeded)
         {
            range.high = rates[i].high;
            range.low = rates[i].low;
            range.start_time = session_start;
            range.end_time = session_end;
            seeded = true;
         }
         else
         {
            range.high = MathMax(range.high, rates[i].high);
            range.low = MathMin(range.low, rates[i].low);
         }
      }

      range.valid = seeded && range.high > range.low;
      return range.valid;
   }

   bool BuildOpeningRange(const string symbol, const datetime now, MEMO_PriceRange &range)
   {
      range.Reset("New York Opening Range");
      if(m_sessions == NULL)
         return false;

      int ny_start = 0;
      int ny_end = 0;
      if(!m_sessions.WindowForSession(MEMO_SESSION_NEWYORK, ny_start, ny_end))
         return false;

      datetime start_time = MEMO_StartOfDay(now) + ny_start * 60;
      datetime end_time = start_time + MathMax(1, m_sessions.NewYorkOpeningRangeMinutes()) * 60;
      if(now < start_time)
      {
         start_time -= 86400;
         end_time -= 86400;
      }

      MqlRates rates[];
      if(!MEMO_CopyRatesSeries(symbol, PERIOD_M1, 0, 2880, rates))
         return false;

      bool seeded = false;
      for(int i = 1; i < ArraySize(rates); i++)
      {
         if(rates[i].time < start_time || rates[i].time >= end_time)
            continue;

         if(!seeded)
         {
            range.high = rates[i].high;
            range.low = rates[i].low;
            range.start_time = start_time;
            range.end_time = end_time;
            seeded = true;
         }
         else
         {
            range.high = MathMax(range.high, rates[i].high);
            range.low = MathMin(range.low, rates[i].low);
         }
      }

      range.valid = seeded && range.high > range.low;
      return range.valid;
   }

   bool ScanRangeSweep(const string symbol,
                       const MEMO_PriceRange &range,
                       const ENUM_TIMEFRAMES timeframe,
                       const MEMO_Direction direction,
                       const MEMO_SmtTier tier,
                       MEMO_LiquidityEvent &event) const
   {
      if(!range.valid)
         return false;

      MqlRates rates[];
      if(!MEMO_CopyRatesSeries(symbol, timeframe, 0, m_settings.sweep_lookback_bars + 5, rates))
         return false;

      const double point = SymbolInfoDouble(symbol, SYMBOL_POINT);
      const double buffer = m_settings.sweep_buffer_points * point;

      for(int i = 1; i <= m_settings.sweep_lookback_bars && i < ArraySize(rates); i++)
      {
         if(direction == MEMO_DIR_BUY)
         {
            const bool swept = rates[i].low < range.low - buffer;
            const bool reclaimed = rates[i].close > range.low;
            if(swept && reclaimed)
            {
               event.Reset();
               event.valid = true;
               event.symbol = symbol;
               event.direction = MEMO_DIR_BUY;
               event.tier = tier;
               event.level_name = range.name + " Low";
               event.level_price = range.low;
               event.event_time = rates[i].time;
               event.sweep_extreme = rates[i].low;
               event.close_price = rates[i].close;
               event.reclaimed = reclaimed;
               event.distance_points = MathAbs(range.low - rates[i].low) / point;
               return true;
            }
         }
         else if(direction == MEMO_DIR_SELL)
         {
            const bool swept = rates[i].high > range.high + buffer;
            const bool reclaimed = rates[i].close < range.high;
            if(swept && reclaimed)
            {
               event.Reset();
               event.valid = true;
               event.symbol = symbol;
               event.direction = MEMO_DIR_SELL;
               event.tier = tier;
               event.level_name = range.name + " High";
               event.level_price = range.high;
               event.event_time = rates[i].time;
               event.sweep_extreme = rates[i].high;
               event.close_price = rates[i].close;
               event.reclaimed = reclaimed;
               event.distance_points = MathAbs(rates[i].high - range.high) / point;
               return true;
            }
         }
      }

      return false;
   }

public:
   CLiquidityEngine()
   {
      m_log = NULL;
      m_sessions = NULL;
   }

   void Init(const MEMO_Settings &settings, CLoggingManager *logger, CSessionManager *session_manager)
   {
      m_settings = settings;
      m_log = logger;
      m_sessions = session_manager;
   }

   bool Update(const string symbol, MEMO_LiquidityMap &map)
   {
      map.Reset(symbol);
      const datetime now = TimeCurrent();

      const bool pd = BuildPreviousRange(symbol, PERIOD_D1, "Previous Day", map.previous_day);
      const bool pw = BuildPreviousRange(symbol, PERIOD_W1, "Previous Week", map.previous_week);
      BuildSessionRange(symbol, MEMO_SESSION_ASIA, PERIOD_M5, now, map.asia);
      BuildSessionRange(symbol, MEMO_SESSION_LONDON, PERIOD_M5, now, map.london);
      BuildSessionRange(symbol, MEMO_SESSION_NEWYORK, PERIOD_M5, now, map.newyork);
      BuildOpeningRange(symbol, now, map.ny_opening_range);

      map.updated_at = now;
      map.valid = pd && pw;

      if(m_log != NULL && map.valid)
         m_log.Debug("LiquidityEngine", symbol + " PDH/PDL=" + DoubleToString(map.previous_day.high, 2) + "/" + DoubleToString(map.previous_day.low, 2));

      return map.valid;
   }

   bool DetectSweep(const string symbol,
                    const MEMO_LiquidityMap &map,
                    const ENUM_TIMEFRAMES timeframe,
                    const MEMO_Direction direction,
                    const MEMO_SmtTier max_tier,
                    MEMO_LiquidityEvent &event) const
   {
      event.Reset();

      if(max_tier >= MEMO_TIER_1)
      {
         if(ScanRangeSweep(symbol, map.previous_day, timeframe, direction, MEMO_TIER_1, event))
            return true;
         if(ScanRangeSweep(symbol, map.previous_week, timeframe, direction, MEMO_TIER_1, event))
            return true;
      }

      if(max_tier >= MEMO_TIER_2)
      {
         if(ScanRangeSweep(symbol, map.asia, timeframe, direction, MEMO_TIER_2, event))
            return true;
         if(ScanRangeSweep(symbol, map.london, timeframe, direction, MEMO_TIER_2, event))
            return true;
         if(ScanRangeSweep(symbol, map.newyork, timeframe, direction, MEMO_TIER_2, event))
            return true;
         if(ScanRangeSweep(symbol, map.ny_opening_range, timeframe, direction, MEMO_TIER_2, event))
            return true;
      }

      if(max_tier >= MEMO_TIER_3)
         return DetectSwingSweep(symbol, timeframe, direction, event);

      return false;
   }

   bool DetectSwingSweep(const string symbol,
                         const ENUM_TIMEFRAMES timeframe,
                         const MEMO_Direction direction,
                         MEMO_LiquidityEvent &event) const
   {
      event.Reset();

      MqlRates rates[];
      const int lookback = MathMax(m_settings.sweep_lookback_bars + m_settings.swing_depth + 5, 20);
      if(!MEMO_CopyRatesSeries(symbol, timeframe, 0, lookback, rates))
         return false;

      const double point = SymbolInfoDouble(symbol, SYMBOL_POINT);
      const double buffer = m_settings.sweep_buffer_points * point;
      double swing = 0.0;
      bool seeded = false;

      for(int i = 2; i < ArraySize(rates); i++)
      {
         if(!seeded)
         {
            swing = direction == MEMO_DIR_BUY ? rates[i].low : rates[i].high;
            seeded = true;
         }
         else if(direction == MEMO_DIR_BUY)
            swing = MathMin(swing, rates[i].low);
         else if(direction == MEMO_DIR_SELL)
            swing = MathMax(swing, rates[i].high);
      }

      if(!seeded)
         return false;

      const MqlRates bar = rates[1];
      if(direction == MEMO_DIR_BUY && bar.low < swing - buffer && bar.close > swing)
      {
         event.valid = true;
         event.symbol = symbol;
         event.direction = MEMO_DIR_BUY;
         event.tier = MEMO_TIER_3;
         event.level_name = "Execution Swing Low";
         event.level_price = swing;
         event.event_time = bar.time;
         event.sweep_extreme = bar.low;
         event.close_price = bar.close;
         event.reclaimed = true;
         event.distance_points = MathAbs(swing - bar.low) / point;
         return true;
      }

      if(direction == MEMO_DIR_SELL && bar.high > swing + buffer && bar.close < swing)
      {
         event.valid = true;
         event.symbol = symbol;
         event.direction = MEMO_DIR_SELL;
         event.tier = MEMO_TIER_3;
         event.level_name = "Execution Swing High";
         event.level_price = swing;
         event.event_time = bar.time;
         event.sweep_extreme = bar.high;
         event.close_price = bar.close;
         event.reclaimed = true;
         event.distance_points = MathAbs(bar.high - swing) / point;
         return true;
      }

      return false;
   }
};

#endif
