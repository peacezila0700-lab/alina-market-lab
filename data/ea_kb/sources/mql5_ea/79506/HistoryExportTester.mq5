//+------------------------------------------------------------------+
//|                                          HistoryExportTester.mq5 |
//|                                   Copyright 2026, Robit Napit    |
//|                                                                  |
//|  Exports price history from the Strategy Tester to CSV files:    |
//|  - closed bars of any timeframe (time, OHLC, tick volume,        |
//|    real volume, spread);                                         |
//|  - optionally every tick the tester delivers (time in ms, bid,   |
//|    ask, last, volume, flags).                                    |
//|  The tester is not limited by the chart's "Max bars in chart"    |
//|  setting, so years of M1 bars or real ticks can be exported in   |
//|  one run. At the end the EA reports the first and last bar, the  |
//|  number of rows and the largest gaps inside trading sessions.    |
//|                                                                  |
//|  Read-only: the EA never sends, modifies or closes an order.     |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, Robit Napit"
#property version   "1.00"
#property description "Exports bars of any timeframe and, optionally, every tick from the Strategy Tester to CSV."
#property description "Not limited by the chart's maximum number of bars. Reports gaps in the data. Places no orders."

input ENUM_TIMEFRAMES InpTimeframe   = PERIOD_M1; // Bars to export
input bool            InpExportTicks = false;     // Also export every tick (use the real-ticks model)
input string          InpPrefix      = "";        // File name prefix (empty = symbol name)
input bool            InpCommonDir   = true;      // Write to the common folder (Terminal\Common\Files)
input int             InpGapBars     = 5;         // Report gaps longer than this many bars (inside trading sessions)

#define TOP_GAPS 10

int      g_bars  = INVALID_HANDLE;
int      g_ticks = INVALID_HANDLE;
datetime g_lastBar = 0;
datetime g_prevBarTime = 0;
datetime g_firstBar = 0;
long     g_barRows = 0;
long     g_tickRows = 0;
long     g_gapCount = 0;
datetime g_gapFrom[TOP_GAPS];
datetime g_gapTo[TOP_GAPS];
int      g_gapBars[TOP_GAPS];

//+------------------------------------------------------------------+
string BaseName(void)
  {
   string p = InpPrefix == "" ? _Symbol : InpPrefix;
   StringReplace(p, "\\", "_");
   StringReplace(p, "/", "_");
   return p;
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
int OpenCsv(const string name)
  {
   int flags = FILE_WRITE | FILE_CSV | FILE_ANSI;
   if(InpCommonDir)
      flags |= FILE_COMMON;
   return FileOpen(name, flags, ',');
  }

//--- true if the time falls inside one of the symbol's trading sessions
bool InSession(const datetime t)
  {
   MqlDateTime dt;
   TimeToStruct(t, dt);
   uint sec = (uint)(dt.hour * 3600 + dt.min * 60 + dt.sec);
   datetime from, to;
   for(uint k = 0; SymbolInfoSessionTrade(_Symbol, (ENUM_DAY_OF_WEEK)dt.day_of_week, k, from, to); k++)
     {
      uint f = (uint)(from % 86400), e = (uint)(to % 86400);
      if(e == 0)
         e = 86400;
      if(sec >= f && sec < e)
         return true;
     }
   return false;
  }

//--- counts the bars missing between two bars that fall inside trading sessions;
//--- weekends and daily breaks are therefore not gaps, holidays are
void CheckGap(const datetime prev, const datetime cur)
  {
   int  step    = PeriodSeconds(InpTimeframe);
   long missing = 0;
   for(datetime t = prev + step; t < cur && missing <= 100000; t += step)
      if(InSession(t))
         missing++;
   if(missing <= InpGapBars)
      return;
   g_gapCount++;
//--- keep the TOP_GAPS largest gaps
   int k = -1;
   for(int i = 0; i < TOP_GAPS; i++)
      if(g_gapBars[i] < missing && (k < 0 || g_gapBars[i] < g_gapBars[k]))
         k = i;
   if(k >= 0)
     {
      g_gapFrom[k] = prev;
      g_gapTo[k]   = cur;
      g_gapBars[k] = (int)missing;
     }
  }

//+------------------------------------------------------------------+
int OnInit()
  {
   if(!MQLInfoInteger(MQL_TESTER))
      Print("HistoryExportTester is meant for the Strategy Tester; on a chart it only exports bars that close while it runs.");
   ArrayInitialize(g_gapBars, 0);
   string tf = StringSubstr(EnumToString(InpTimeframe), 7);
   string barsName = BaseName() + "_" + tf + "_bars.csv";
   g_bars = OpenCsv(barsName);
   if(g_bars == INVALID_HANDLE)
     {
      PrintFormat("cannot open %s, error %d", barsName, GetLastError());
      return INIT_FAILED;
     }
   FileWrite(g_bars, "time", "open", "high", "low", "close", "tick_volume", "real_volume", "spread");
   if(InpExportTicks)
     {
      string ticksName = BaseName() + "_ticks.csv";
      g_ticks = OpenCsv(ticksName);
      if(g_ticks == INVALID_HANDLE)
        {
         PrintFormat("cannot open %s, error %d", ticksName, GetLastError());
         return INIT_FAILED;
        }
      FileWrite(g_ticks, "time_msc", "time", "bid", "ask", "last", "volume", "flags");
     }
   PrintFormat("[Export] %s %s bars%s -> %s", _Symbol, tf, InpExportTicks ? " + ticks" : "",
               InpCommonDir ? "Common\\Files" : "MQL5\\Files (tester agent)");
   return INIT_SUCCEEDED;
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
void OnTick()
  {
   if(g_ticks != INVALID_HANDLE)
     {
      MqlTick t;
      if(SymbolInfoTick(_Symbol, t))
        {
         FileWrite(g_ticks, IntegerToString(t.time_msc), TimeToString(t.time, TIME_DATE | TIME_SECONDS),
                   DoubleToString(t.bid, _Digits), DoubleToString(t.ask, _Digits), DoubleToString(t.last, _Digits),
                   (string)t.volume, (string)t.flags);
         g_tickRows++;
        }
     }

   datetime t0 = iTime(_Symbol, InpTimeframe, 0);
   if(t0 == 0 || t0 == g_lastBar)
      return;
   if(g_lastBar != 0)
     {
      //--- a new bar has opened: every bar before it is complete
      MqlRates r[];
      int n = CopyRates(_Symbol, InpTimeframe, g_lastBar, t0 - 1, r);
      for(int i = 0; i < n; i++)
        {
         if(r[i].time <= g_prevBarTime)
            continue;
         if(g_prevBarTime > 0)
            CheckGap(g_prevBarTime, r[i].time);
         else
            g_firstBar = r[i].time;
         FileWrite(g_bars, TimeToString(r[i].time, TIME_DATE | TIME_SECONDS),
                   DoubleToString(r[i].open, _Digits), DoubleToString(r[i].high, _Digits),
                   DoubleToString(r[i].low, _Digits), DoubleToString(r[i].close, _Digits),
                   (string)r[i].tick_volume, (string)r[i].real_volume, (string)r[i].spread);
         g_prevBarTime = r[i].time;
         g_barRows++;
        }
     }
   g_lastBar = t0;
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   if(g_bars != INVALID_HANDLE)
      FileClose(g_bars);
   if(g_ticks != INVALID_HANDLE)
      FileClose(g_ticks);
   PrintFormat("[Export] bars written: %I64d (%s to %s); ticks written: %I64d",
               g_barRows, TimeToString(g_firstBar), TimeToString(g_prevBarTime), g_tickRows);
   PrintFormat("[Export] gaps of more than %d bars inside trading sessions: %I64d", InpGapBars, g_gapCount);
   for(int i = 0; i < TOP_GAPS; i++)
      if(g_gapBars[i] > 0)
         PrintFormat("[Export]   %s -> %s: %d session bars missing", TimeToString(g_gapFrom[i]), TimeToString(g_gapTo[i]), g_gapBars[i]);
  }
//+------------------------------------------------------------------+
