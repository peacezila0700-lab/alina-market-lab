//+------------------------------------------------------------------+
//|                                  New Bar Connection Event Logger |
//|                            Copyright 2026, Savia Forex Solutions |
//|                                       https://www.saviaforex.com |
//+------------------------------------------------------------------+
#property copyright "Savia Forex Software Solutions"
#property link      "https://www.saviaforex.com/"
#property version   "1.00"
#property description "Logs observed bar and terminal connection events to a local CSV."
#property indicator_chart_window
#property indicator_plots 0

input int PollSeconds = 2;

enum BarEvent
  {
   BAR_NONE = 0,
   BAR_BASELINE,
   BAR_NEW,
   BAR_RESYNC
  };

// This pure function is also exercised by the private deterministic QA harness.
BarEvent ClassifyBar(const datetime previous,const datetime current,
                     const datetime immediately_prior)
  {
   if(current <= 0 || current == previous)
      return BAR_NONE;
   if(previous == 0)
      return BAR_BASELINE;
   if(current < previous || immediately_prior != previous)
      return BAR_RESYNC;
   return BAR_NEW;
  }

int      log_file = INVALID_HANDLE;
bool     connection_known = false;
bool     connected_before = false;
bool     tester = false;
datetime last_bar = 0;
datetime bars[2];

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
string Timestamp(const datetime value)
  {
   if(value <= 0)
      return "";
   return TimeToString(value,TIME_DATE|TIME_SECONDS);
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
bool LogEvent(const string event,const datetime previous,const datetime current,
              const string note)
  {
// TimeGMT is simulated in the Strategy Tester, not actual wall-clock UTC.
   ResetLastError();
   if(FileWrite(log_file,Timestamp(TimeGMT()),tester ? "tester" : "live_terminal",
                _Symbol,EnumToString(_Period),event,Timestamp(previous),
                Timestamp(current),note)==0)
     {
      PrintFormat("New-Bar & Connection Logger: CSV write failed (%d); logging stopped.",
                  GetLastError());
      EventKillTimer();
      FileClose(log_file);
      log_file=INVALID_HANDLE;
      return false;
     }
   FileFlush(log_file);
   return true;
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
int OnInit()
  {
   if(PollSeconds<1 || PollSeconds>60)
     {
      Print("New-Bar & Connection Logger: PollSeconds must be 1 through 60.");
      return INIT_PARAMETERS_INCORRECT;
     }
   tester=(bool)MQLInfoInteger(MQL_TESTER);
   string name=StringFormat("NewBarConnection_%I64d_%I64d_%I64u.csv",
                            ChartID(),(long)TimeGMT(),GetTickCount64());
// A fresh file per attachment. Never overwrite, append to, or read someone else's CSV.
   if(FileIsExist(name))
     {
      Print("New-Bar & Connection Logger: CSV name already exists; retry attachment.");
      return INIT_FAILED;
     }
   ResetLastError();
   log_file=FileOpen(name,FILE_WRITE|FILE_CSV|FILE_ANSI|FILE_SHARE_READ,',',CP_UTF8);
   if(log_file==INVALID_HANDLE)
     {
      PrintFormat("New-Bar & Connection Logger: could not open CSV (%d).",GetLastError());
      return INIT_FAILED;
     }
   if(FileWrite(log_file,"observed_time","clock_mode","symbol","timeframe","event",
                "previous_bar_open_server_time","bar_open_server_time","detail")==0)
     {
      PrintFormat("New-Bar & Connection Logger: could not write CSV header (%d).",GetLastError());
      FileClose(log_file);
      log_file=INVALID_HANDLE;
      return INIT_FAILED;
     }
   FileFlush(log_file);
   if(!EventSetTimer(PollSeconds))
     {
      PrintFormat("New-Bar & Connection Logger: could not start timer (%d).",GetLastError());
      FileClose(log_file);
      log_file=INVALID_HANDLE;
      return INIT_FAILED;
     }
   PrintFormat("New-Bar & Connection Logger: logging to MQL5\\Files\\%s",name);
   return INIT_SUCCEEDED;
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
void OnTimer()
  {
   if(log_file==INVALID_HANDLE)
      return;

// The Strategy Tester cannot demonstrate real terminal connection transitions.
   if(!tester)
     {
      bool connected=(bool)TerminalInfoInteger(TERMINAL_CONNECTED);
      if(!connection_known || connected!=connected_before)
        {
         bool was_known=connection_known;
         connection_known=true;
         connected_before=connected;
         last_bar=0;
         string event=was_known ? (connected ? "RECONNECTED" : "DISCONNECTED")
                      : "CONNECTION_BASELINE";
         if(!LogEvent(event,0,0,connected ? "connected" : "disconnected"))
            return;
        }
      if(!connected)
         return;
     }

   if(!SeriesInfoInteger(_Symbol,_Period,SERIES_SYNCHRONIZED))
     {
      last_bar=0;
      return;
     }

// CopyTime stores the oldest element first regardless of array indexing.
// Require two open times to establish whether the observed advance is adjacent.
   if(CopyTime(_Symbol,_Period,0,2,bars)!=2)
     {
      last_bar=0;
      return;
     }
   datetime current=bars[1];
   datetime prior=bars[0];
   if(prior<=0 || current<=prior)
     {
      last_bar=0;
      return;
     }
   BarEvent bar_event=ClassifyBar(last_bar,current,prior);
   if(bar_event==BAR_BASELINE)
      LogEvent("BAR_BASELINE",0,current,"baseline_only");
   else
      if(bar_event==BAR_NEW)
         LogEvent("NEW_BAR",last_bar,current,"adjacent_observed_advance");
      else
         if(bar_event==BAR_RESYNC)
            LogEvent("BAR_RESYNC",last_bar,current,"skipped_or_revised_series_no_backfill");
   last_bar=current;
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
int OnCalculate(const int rates_total,const int prev_calculated,const int begin,
                const double &price[])
  {
// Indicator calculation does not log. The timer is the sole sampling source.
   return rates_total;
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   EventKillTimer();
   if(log_file!=INVALID_HANDLE)
     {
      FileFlush(log_file);
      FileClose(log_file);
      log_file=INVALID_HANDLE;
     }
  }

//+------------------------------------------------------------------+
