#ifndef MEMO_MANAGERS_NEWS_FILTER_MQH
#define MEMO_MANAGERS_NEWS_FILTER_MQH

#include <MEMO\Core\Settings.mqh>
#include <MEMO\Managers\LoggingManager.mqh>

struct MEMO_NewsBlackout
{
   datetime start_time;
   datetime end_time;
   string impact;
   string currency;
   string title;
   bool valid;

   void Reset()
   {
      start_time = 0;
      end_time = 0;
      impact = "";
      currency = "";
      title = "";
      valid = false;
   }
};

class CNewsFilter
{
private:
   MEMO_Settings m_settings;
   MEMO_NewsBlackout m_events[];
   datetime m_last_load;
   CLoggingManager *m_log;

   bool ImpactBlocked(const string impact) const
   {
      const bool high = StringFind(impact, "High") >= 0 || StringFind(impact, "HIGH") >= 0 || StringFind(impact, "high") >= 0;
      const bool medium = StringFind(impact, "Medium") >= 0 || StringFind(impact, "MEDIUM") >= 0 || StringFind(impact, "medium") >= 0;
      if(high && m_settings.block_high_impact_news)
         return true;
      if(medium && m_settings.block_medium_impact_news)
         return true;
      return impact == "";
   }

   bool CurrencyMatches(const string symbol, const string currency) const
   {
      if(currency == "" || currency == "*")
         return true;
      if(StringFind(symbol, currency) >= 0)
         return true;
      if(currency == "USD" || currency == "usd")
         return true;
      return false;
   }

public:
   CNewsFilter()
   {
      m_last_load = 0;
      m_log = NULL;
      ArrayResize(m_events, 0);
   }

   void Init(const MEMO_Settings &settings, CLoggingManager *logger)
   {
      m_settings = settings;
      m_log = logger;
      Load();
   }

   void Load()
   {
      ArrayResize(m_events, 0);
      m_last_load = TimeCurrent();

      if(!m_settings.enable_news_filter || m_settings.news_blackout_file == "")
         return;

      const int handle = FileOpen(m_settings.news_blackout_file, FILE_READ | FILE_CSV | FILE_ANSI | FILE_SHARE_READ, ',');
      if(handle == INVALID_HANDLE)
      {
         if(m_log != NULL)
            m_log.Debug("NewsFilter", "No blackout file found: " + m_settings.news_blackout_file);
         return;
      }

      while(!FileIsEnding(handle))
      {
         const string start_raw = FileReadString(handle);
         if(FileIsEnding(handle))
            break;
         const string end_raw = FileReadString(handle);
         const string impact = FileReadString(handle);
         const string currency = FileReadString(handle);
         const string title = FileReadString(handle);

         if(start_raw == "start" || start_raw == "Start" || start_raw == "")
            continue;

         MEMO_NewsBlackout event;
         event.Reset();
         event.start_time = StringToTime(start_raw);
         event.end_time = StringToTime(end_raw);
         event.impact = impact;
         event.currency = currency;
         event.title = title;
         event.valid = event.start_time > 0 && event.end_time >= event.start_time;

         if(event.valid)
         {
            const int size = ArraySize(m_events);
            ArrayResize(m_events, size + 1);
            m_events[size] = event;
         }
      }

      FileClose(handle);

      if(m_log != NULL)
         m_log.Info("NewsFilter", "Loaded blackout events: " + IntegerToString(ArraySize(m_events)));
   }

   bool IsBlocked(const string symbol, const datetime now, string &reason)
   {
      if(!m_settings.enable_news_filter)
         return false;

      if(m_last_load == 0 || now - m_last_load > 60)
         Load();

      for(int i = 0; i < ArraySize(m_events); i++)
      {
         if(!m_events[i].valid)
            continue;
         if(!ImpactBlocked(m_events[i].impact))
            continue;
         if(!CurrencyMatches(symbol, m_events[i].currency))
            continue;

         const datetime blocked_start = m_events[i].start_time - m_settings.news_minutes_before * 60;
         const datetime blocked_end = m_events[i].end_time + m_settings.news_minutes_after * 60;
         if(now >= blocked_start && now <= blocked_end)
         {
            reason = "News blackout: " + m_events[i].impact + " " + m_events[i].currency + " " + m_events[i].title;
            return true;
         }
      }

      return false;
   }
};

#endif
