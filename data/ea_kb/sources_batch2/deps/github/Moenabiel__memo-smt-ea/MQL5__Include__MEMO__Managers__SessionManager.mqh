#ifndef MEMO_MANAGERS_SESSION_MANAGER_MQH
#define MEMO_MANAGERS_SESSION_MANAGER_MQH

#include <MEMO\Core\Settings.mqh>

class CSessionManager
{
private:
   MEMO_Settings m_settings;

public:
   void Init(const MEMO_Settings &settings)
   {
      m_settings = settings;
   }

   MEMO_SessionId CurrentSession(const datetime now) const
   {
      const int minute = MEMO_MinutesOfDay(now);

      if(MEMO_InMinuteWindow(minute, m_settings.newyork_start_minute, m_settings.newyork_end_minute))
         return MEMO_SESSION_NEWYORK;
      if(MEMO_InMinuteWindow(minute, m_settings.london_start_minute, m_settings.london_end_minute))
         return MEMO_SESSION_LONDON;
      if(MEMO_InMinuteWindow(minute, m_settings.asia_start_minute, m_settings.asia_end_minute))
         return MEMO_SESSION_ASIA;

      return MEMO_SESSION_NONE;
   }

   bool CanTradeNow(const datetime now, string &reason) const
   {
      const MEMO_SessionId session = CurrentSession(now);
      if(session == MEMO_SESSION_ASIA && m_settings.trade_asia)
         return true;
      if(session == MEMO_SESSION_LONDON && m_settings.trade_london)
         return true;
      if(session == MEMO_SESSION_NEWYORK && m_settings.trade_newyork)
         return true;

      reason = "Trading disabled for current session: " + MEMO_SessionText(session);
      return false;
   }

   bool WindowForSession(const MEMO_SessionId session, int &start_minute, int &end_minute) const
   {
      if(session == MEMO_SESSION_ASIA)
      {
         start_minute = m_settings.asia_start_minute;
         end_minute = m_settings.asia_end_minute;
         return true;
      }
      if(session == MEMO_SESSION_LONDON)
      {
         start_minute = m_settings.london_start_minute;
         end_minute = m_settings.london_end_minute;
         return true;
      }
      if(session == MEMO_SESSION_NEWYORK)
      {
         start_minute = m_settings.newyork_start_minute;
         end_minute = m_settings.newyork_end_minute;
         return true;
      }
      return false;
   }

   int NewYorkOpeningRangeMinutes() const
   {
      return m_settings.ny_opening_range_minutes;
   }

   bool IsMajorLiquidityWindow(const datetime now) const
   {
      const int minute = MEMO_MinutesOfDay(now);
      const int london_end = m_settings.london_start_minute + 180;
      const int newyork_end = m_settings.newyork_start_minute + 180;
      return MEMO_InMinuteWindow(minute, m_settings.london_start_minute, london_end % 1440)
          || MEMO_InMinuteWindow(minute, m_settings.newyork_start_minute, newyork_end % 1440);
   }
};

#endif
