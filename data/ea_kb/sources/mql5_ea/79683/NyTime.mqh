//+------------------------------------------------------------------+
//| NyTime.mqh - broker server time <-> UTC <-> New York time        |
//| with US and European daylight saving rules.                      |
//|                                                                  |
//| Why: TimeGMT() returns the server time inside the Strategy       |
//| Tester, so session filters ("trade 09:30-11:00 New York") break  |
//| in backtests. Here the server clock is declared once and every   |
//| conversion is computed from the calendar, live and in the tester.|
//|                                                                  |
//| Usage:                                                           |
//|   #include "NyTime.mqh"                                          |
//|   datetime ny = NyTimeFromServer(TimeCurrent(), CLOCK_NY7);      |
//|   if(NyMinute(ny) >= 9 * 60 + 30) ...                            |
//+------------------------------------------------------------------+
#ifndef NY_TIME_MQH
#define NY_TIME_MQH

enum ENUM_SERVER_CLOCK
  {
   CLOCK_NY7  = 0, // New York + 7 (most brokers: 00:00 server = 17:00 New York)
   CLOCK_EU   = 1, // Central Europe (UTC+1, summer UTC+2)
   CLOCK_EET  = 2, // Eastern Europe (UTC+2, summer UTC+3, European dates)
   CLOCK_UTC  = 3, // UTC
   CLOCK_AUTO = 4  // Automatic from TimeGMT() (live only, not in the tester)
  };

int      NyTimeYear(datetime t)      { MqlDateTime s; TimeToStruct(t, s); return s.year; }
int      NyTimeDayOfWeek(datetime t) { MqlDateTime s; TimeToStruct(t, s); return s.day_of_week; }
datetime NyTimeDate(int y, int m, int d) { MqlDateTime s; ZeroMemory(s); s.year = y; s.mon = m; s.day = d; return StructToTime(s); }

// n-th Sunday of a month (n = 1..5)
datetime NthSunday(int y, int m, int n)
  {
   datetime d = NyTimeDate(y, m, 1);
   while(NyTimeDayOfWeek(d) != 0) d += 86400;
   return d + (n - 1) * 7 * 86400;
  }

// last Sunday of a month with 31 days (March, October)
datetime LastSunday31(int y, int m)
  {
   datetime d = NyTimeDate(y, m, 31);
   while(NyTimeDayOfWeek(d) != 0) d -= 86400;
   return d;
  }

// US summer time: 2nd Sunday of March 02:00 local -> 1st Sunday of November 02:00 local (rules since 2007)
bool IsUsSummer(datetime utc)
  {
   int y = NyTimeYear(utc);
   return utc >= NthSunday(y, 3, 2) + 7 * 3600 && utc < NthSunday(y, 11, 1) + 6 * 3600;
  }

// EU summer time: last Sunday of March 01:00 UTC -> last Sunday of October 01:00 UTC
bool IsEuSummer(datetime utc)
  {
   int y = NyTimeYear(utc);
   return utc >= LastSunday31(y, 3) + 3600 && utc < LastSunday31(y, 10) + 3600;
  }

datetime UtcToNy(datetime utc) { return utc - (IsUsSummer(utc) ? 4 : 5) * 3600; }

datetime NyToUtc(datetime ny)
  {
   datetime u = ny + 4 * 3600;
   return IsUsSummer(u) ? u : ny + 5 * 3600;
  }

datetime ServerToUtc(datetime srv, ENUM_SERVER_CLOCK clock)
  {
   switch(clock)
     {
      case CLOCK_NY7: return NyToUtc(srv - 7 * 3600);
      case CLOCK_EU:  { datetime u = srv - 2 * 3600; return IsEuSummer(u) ? u : srv - 3600; }
      case CLOCK_EET: { datetime u = srv - 3 * 3600; return IsEuSummer(u) ? u : srv - 2 * 3600; }
      case CLOCK_UTC: return srv;
      default:
        {
         long off = (long)MathRound((double)(TimeTradeServer() - TimeGMT()) / 900.0) * 900;
         return (datetime)(srv - off);
        }
     }
  }

datetime UtcToServer(datetime utc, ENUM_SERVER_CLOCK clock)
  {
   // the offset is constant within a few hours of the given moment, so one correction step is enough
   datetime guess = utc + (utc - ServerToUtc(utc, clock));
   return guess + (utc - ServerToUtc(guess, clock));
  }

datetime NyTimeFromServer(datetime srv, ENUM_SERVER_CLOCK clock) { return UtcToNy(ServerToUtc(srv, clock)); }
datetime ServerTimeFromNy(datetime ny, ENUM_SERVER_CLOCK clock)  { return UtcToServer(NyToUtc(ny), clock); }

int  NyMinute(datetime ny)          { return (int)((ny % 86400) / 60); }   // minutes after 00:00 New York
long NyDayNumber(datetime ny)       { return (long)ny / 86400; }           // same number for the whole New York day
bool NyIsWeekday(datetime ny)       { int d = NyTimeDayOfWeek(ny); return d >= 1 && d <= 5; }

// minutes after 00:00 New York of the current server time, e.g. NyMinuteNow(CLOCK_NY7) >= 570 -> after 09:30 New York
int NyMinuteNow(ENUM_SERVER_CLOCK clock) { return NyMinute(NyTimeFromServer(TimeCurrent(), clock)); }

#endif
