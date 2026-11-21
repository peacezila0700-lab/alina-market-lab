//+------------------------------------------------------------------+
//|                                        SpreadSessionRecorder.mq5 |
//|  Records the spread of one or many symbols to CSV, one row per    |
//|  interval, counting every tick, and keeps per-hour and            |
//|  per-session tables.                                              |
//|                                                                   |
//|  It never opens, closes or modifies a trade.                      |
//+------------------------------------------------------------------+
#property copyright "Amul R"
#property version   "1.00"
#property description "Records the spread of one or many symbols to CSV from a single chart."
#property description "Every tick is counted: each row holds the minimum, time-weighted average and maximum spread of its interval."
#property description "Keeps a table per hour of the day and per session, fills gaps from tick history after a restart. Never trades."

input string InpSymbols        = "";               // Symbols, comma separated (empty = chart symbol, * = Market Watch)
input int    InpRowSeconds     = 60;               // Row length in seconds
input int    InpBackfillHours  = 24;               // On start, fill up to this many hours from tick history
input int    InpStaleSeconds   = 300;              // A quote older than this is not counted (market closed)
input string InpFolder         = "SpreadRecorder"; // Folder inside MQL5\Files
input bool   InpCommonFolder   = false;            // Use the common folder shared by all terminals
input int    InpSummaryMinutes = 5;                // Rewrite the summary tables every N minutes

input group "Sessions (hours in GMT)"
input double InpGmtOffsetHours = 99;               // Server time minus GMT, hours (99 = detect)
input int    InpAsiaStart      = 0;                // Asia start hour
input int    InpAsiaEnd        = 9;                // Asia end hour
input int    InpLondonStart    = 7;                // London start hour
input int    InpLondonEnd      = 16;               // London end hour
input int    InpNewYorkStart   = 12;               // New York start hour
input int    InpNewYorkEnd     = 21;               // New York end hour
input int    InpRollBeforeMin  = 10;               // Rollover window: minutes before server midnight
input int    InpRollAfterMin   = 60;               // Rollover window: minutes after server midnight

input group "Panel"
input bool   InpShowPanel      = true;             // Show the panel
input int    InpPanelX         = 10;               // Panel X
input int    InpPanelY         = 20;               // Panel Y
input int    InpFontSize       = 9;                // Font size
input color  InpTextColor      = clrWhite;         // Text colour
input color  InpBackColor      = C'24,28,36';      // Background colour

input group "Testing"
input bool   InpSelfTest       = false;            // Run the built-in checks and stop
input int    InpTestReloadRows = 0;                // Rebuild the tables from the file every N rows (0 = off)

#define SESS_N    6
#define MAX_SYMS  50
#define PFX       "SSR_"
#define HEADER    "time_server,time_gmt,symbol,session,ticks,covered_s,min_pts,avg_pts,max_pts,bid,ask"
#define SUMHEADER "group,key,rows,hours_covered,ticks,min_pts,avg_pts,avg_row_max_pts,max_pts,max_at_server"

string SESS_NAME[SESS_N] = {"ROLLOVER", "LONDON_NY", "LONDON", "NEWYORK", "ASIA", "OFF"};

//--- running totals of one table line
struct Stat
  {
   long              rows;
   double            covered;    // seconds
   double            sumW;       // sum of avg * covered
   long              ticks;
   double            mn;
   double            mx;
   datetime          mxAt;
   double            sumMax;
  };

//--- one parsed row of the CSV
struct Row
  {
   datetime          t;
   string            sess;
   long              ticks;
   double            cov;
   double            mn;
   double            avg;
   double            mx;
  };

//--- everything kept for one symbol
struct Agg
  {
   string            sym;
   double            point;
   int               digits;
   long              cursorMs;      // ticks up to this server time are processed
   long              skipBefore;    // rows starting before this are warm-up only
   long              lastRowMs;     // start of the last row in the file
   long              rowStartMs;    // 0 = no row open
   bool              have;          // a spread is known
   double            cur;           // current spread, points
   long              lastTickMs;
   long              segMs;         // the current spread is counted from here
   double            sum;           // points * ms
   long              covered;       // ms
   int               ticks;
   double            mn;
   double            mx;
   double            bid;
   double            ask;
   double            nowSpread;     // for the panel
   int               month;         // yyyymm of the tables below
   int               sinceReload;
   Stat              all;
   Stat              hour[24];
   Stat              sess[SESS_N];
   string            pendLine[];
   int               pendYm[];
   long              pendMs[];
  };

Agg    g_a[];
long   g_rowMs   = 60000;
long   g_staleMs = 300000;
long   g_backMs  = 86400000;
int    g_offSec  = 0;
string g_dir     = "SpreadRecorder";
int    g_common  = 0;
long   g_lastSummaryMs = 0;
long   g_lastWarnMs    = 0;
bool   g_closing       = false;   // set in OnDeinit: tick history may be unavailable while MT5 shuts down
bool   g_selfTestOnly  = false;
int    g_panelLines    = 0;

//+------------------------------------------------------------------+
//| Small helpers                                                    |
//+------------------------------------------------------------------+
int YmOf(long ms)
  {
   MqlDateTime d;
   TimeToStruct((datetime)(ms / 1000), d);
   return d.year * 100 + d.mon;
  }

int PrevYm(int ym)
  {
   int y = ym / 100, m = ym % 100 - 1;
   if(m < 1)
     {
      m = 12;
      y--;
     }
   return y * 100 + m;
  }

string SafeName(string s)
  {
   string bad = "\\/:*?\"<>|";
   for(int i = 0; i < StringLen(bad); i++)
      StringReplace(s, StringSubstr(bad, i, 1), "_");
   return s;
  }

string RowFile(string sym, int ym)
  {
   return g_dir + "\\" + SafeName(sym) + "_" + IntegerToString(ym) + ".csv";
  }

string SummaryFile(string sym, int ym)
  {
   return g_dir + "\\" + SafeName(sym) + "_" + IntegerToString(ym) + "_summary.csv";
  }

//--- splits "A, B,,C" into clean names
int SplitList(string text, string &out[])
  {
   string parts[];
   int n = StringSplit(text, ',', parts);
   ArrayResize(out, 0);
   for(int i = 0; i < n; i++)
     {
      string s = parts[i];
      StringTrimLeft(s);
      StringTrimRight(s);
      if(s == "")
         continue;
      int k = ArraySize(out);
      ArrayResize(out, k + 1);
      out[k] = s;
     }
   return ArraySize(out);
  }

bool InHours(int minuteOfDay, int startHour, int endHour)
  {
   int a = startHour * 60, b = endHour * 60;
   if(a == b)
      return false;
   if(a < b)
      return (minuteOfDay >= a && minuteOfDay < b);
   return (minuteOfDay >= a || minuteOfDay < b);      // wraps over midnight
  }

//--- session label of a server time; offSec = server time minus GMT
string SessionLabel(datetime server, int offSec)
  {
   int srvMin = (int)((long)server % 86400) / 60;
   if(InpRollBeforeMin + InpRollAfterMin > 0)
      if(srvMin >= 1440 - InpRollBeforeMin || srvMin < InpRollAfterMin)
         return SESS_NAME[0];
   long g = ((long)server - offSec) % 86400;
   if(g < 0)
      g += 86400;
   int gmtMin = (int)(g / 60);
   bool lon = InHours(gmtMin, InpLondonStart, InpLondonEnd);
   bool ny  = InHours(gmtMin, InpNewYorkStart, InpNewYorkEnd);
   if(lon && ny)
      return SESS_NAME[1];
   if(lon)
      return SESS_NAME[2];
   if(ny)
      return SESS_NAME[3];
   if(InHours(gmtMin, InpAsiaStart, InpAsiaEnd))
      return SESS_NAME[4];
   return SESS_NAME[5];
  }

int SessIndex(string name)
  {
   for(int i = 0; i < SESS_N; i++)
      if(SESS_NAME[i] == name)
         return i;
   return SESS_N - 1;
  }

void UpdateOffset()
  {
   if(InpGmtOffsetHours != 99)
     {
      g_offSec = (int)MathRound(InpGmtOffsetHours * 3600.0);
      return;
     }
   long diff = (long)(TimeTradeServer() - TimeGMT());
   g_offSec = (int)(MathRound(diff / 900.0) * 900);   // zones are multiples of 15 minutes
  }

//+------------------------------------------------------------------+
//| Tables                                                           |
//+------------------------------------------------------------------+
void StatReset(Stat &s)
  {
   s.rows = 0;
   s.covered = 0;
   s.sumW = 0;
   s.ticks = 0;
   s.mn = DBL_MAX;
   s.mx = -1;
   s.mxAt = 0;
   s.sumMax = 0;
  }

void StatAdd(Stat &s, const Row &r)
  {
   s.rows++;
   s.covered += r.cov;
   s.sumW += r.avg * r.cov;
   s.ticks += r.ticks;
   if(r.mn < s.mn)
      s.mn = r.mn;
   if(r.mx > s.mx)
     {
      s.mx = r.mx;
      s.mxAt = r.t;
     }
   s.sumMax += r.mx;
  }

void ResetStats(Agg &a)
  {
   StatReset(a.all);
   for(int i = 0; i < 24; i++)
      StatReset(a.hour[i]);
   for(int i = 0; i < SESS_N; i++)
      StatReset(a.sess[i]);
  }

void AddRowToStats(Agg &a, const Row &r)
  {
   MqlDateTime d;
   TimeToStruct(r.t, d);
   StatAdd(a.all, r);
   StatAdd(a.hour[d.hour], r);
   StatAdd(a.sess[SessIndex(r.sess)], r);
  }

string FormatRow(long rowStartMs, int offSec, string sym, string sess, int ticks, long coveredMs,
                 double mn, double avg, double mx, double bid, double ask, int digits)
  {
   datetime ts = (datetime)(rowStartMs / 1000);
   return TimeToString(ts, TIME_DATE | TIME_SECONDS) + "," +
          TimeToString(ts - offSec, TIME_DATE | TIME_SECONDS) + "," +
          sym + "," + sess + "," + IntegerToString(ticks) + "," +
          DoubleToString(coveredMs / 1000.0, 3) + "," +
          DoubleToString(mn, 1) + "," + DoubleToString(avg, 2) + "," + DoubleToString(mx, 1) + "," +
          DoubleToString(bid, digits) + "," + DoubleToString(ask, digits);
  }

bool ParseRow(string line, Row &r)
  {
   string f[];
   if(StringSplit(line, ',', f) != 11)
      return false;
   if(f[0] == "time_server")
      return false;
   r.t = StringToTime(f[0]);
   if(r.t <= 0)
      return false;
   r.sess  = f[3];
   r.ticks = StringToInteger(f[4]);
   r.cov   = StringToDouble(f[5]);
   r.mn    = StringToDouble(f[6]);
   r.avg   = StringToDouble(f[7]);
   r.mx    = StringToDouble(f[8]);
   return true;
  }

//--- rebuilds the tables of one month from its row file; returns the start of the last row (ms), 0 if none
long LoadMonth(Agg &a, int ym)
  {
   ResetStats(a);
   a.month = ym;
   long last = 0;
   string name = RowFile(a.sym, ym);
   if(!FileIsExist(name, g_common))
      return 0;
   int h = FileOpen(name, FILE_READ | FILE_TXT | FILE_ANSI | FILE_SHARE_READ | FILE_SHARE_WRITE | g_common);
   if(h == INVALID_HANDLE)
      return 0;
   Row r;
   while(!FileIsEnding(h))
     {
      string line = FileReadString(h);
      if(!ParseRow(line, r))
         continue;
      AddRowToStats(a, r);
      long ms = (long)r.t * 1000;
      if(ms > last)
         last = ms;
     }
   FileClose(h);
   return last;
  }

string StatLine(string group, string key, const Stat &s)
  {
   if(s.rows == 0)
      return "";
   double avg = (s.covered > 0) ? s.sumW / s.covered : 0;
   return group + "," + key + "," + IntegerToString(s.rows) + "," + DoubleToString(s.covered / 3600.0, 3) + "," +
          IntegerToString(s.ticks) + "," + DoubleToString(s.mn, 1) + "," + DoubleToString(avg, 2) + "," +
          DoubleToString(s.sumMax / s.rows, 2) + "," + DoubleToString(s.mx, 1) + "," +
          TimeToString(s.mxAt, TIME_DATE | TIME_SECONDS) + "\r\n";
  }

string SummaryText(Agg &a)
  {
   string t = SUMHEADER + "\r\n";
   t += StatLine("ALL", IntegerToString(a.month), a.all);
   for(int i = 0; i < SESS_N; i++)
      t += StatLine("SESSION", SESS_NAME[i], a.sess[i]);
   for(int i = 0; i < 24; i++)
      t += StatLine("HOUR_SERVER", StringFormat("%02d", i), a.hour[i]);
   return t;
  }

void WriteSummary(Agg &a)
  {
   if(a.month == 0 || a.all.rows == 0)
      return;
   int h = FileOpen(SummaryFile(a.sym, a.month), FILE_WRITE | FILE_TXT | FILE_ANSI | FILE_SHARE_READ | g_common);
   if(h == INVALID_HANDLE)
      return;                                   // open in another program: the next pass writes it
   FileWriteString(h, SummaryText(a));
   FileClose(h);
  }

//+------------------------------------------------------------------+
//| Recording                                                        |
//+------------------------------------------------------------------+
void InitAgg(Agg &a, string sym, double point, int digits)
  {
   a.sym = sym;
   a.point = point;
   a.digits = digits;
   a.cursorMs = 0;
   a.skipBefore = 0;
   a.lastRowMs = 0;
   a.rowStartMs = 0;
   a.have = false;
   a.cur = 0;
   a.lastTickMs = 0;
   a.segMs = 0;
   a.sum = 0;
   a.covered = 0;
   a.ticks = 0;
   a.mn = DBL_MAX;
   a.mx = -1;
   a.bid = 0;
   a.ask = 0;
   a.nowSpread = -1;
   a.month = 0;
   a.sinceReload = 0;
   ResetStats(a);
   ArrayResize(a.pendLine, 0);
   ArrayResize(a.pendYm, 0);
   ArrayResize(a.pendMs, 0);
  }

//--- decides where recording continues: right after the last row in the files, or the backfill limit
void ResumeAgg(Agg &a, long nowMs)
  {
   int ym = YmOf(nowMs);
   long last = LoadMonth(a, ym);
   if(last == 0)
     {
      last = LoadMonth(a, PrevYm(ym));
      if(last == 0)
        {
         ResetStats(a);
         a.month = 0;
        }
     }
   a.lastRowMs = last;
   long resume = ((nowMs - g_backMs) / g_rowMs) * g_rowMs;
   if(last > 0)
     {
      long next = (last / g_rowMs + 1) * g_rowMs;       // first row boundary after the last row
      if(next > resume)
         resume = next;
     }
   a.skipBefore = resume;
   a.cursorMs = resume - g_staleMs - 1;                 // read a little earlier so the first row knows its opening spread
  }

//--- counts the current spread from segMs up to upTo
void AddSeg(Agg &a, long upTo)
  {
   if(upTo <= a.segMs)
      return;
   if(a.have)
     {
      long end = MathMin(upTo, a.lastTickMs + g_staleMs);
      if(end > a.segMs)
        {
         long d = end - a.segMs;
         a.sum += a.cur * d;
         a.covered += d;
         if(a.cur < a.mn)
            a.mn = a.cur;
         if(a.cur > a.mx)
            a.mx = a.cur;
        }
     }
   a.segMs = upTo;
  }

void CloseRow(Agg &a)
  {
   long end = a.rowStartMs + g_rowMs;
   AddSeg(a, end);
   if(a.covered > 0 && a.rowStartMs >= a.skipBefore)
     {
      datetime ts = (datetime)(a.rowStartMs / 1000);
      string line = FormatRow(a.rowStartMs, g_offSec, a.sym, SessionLabel(ts, g_offSec), a.ticks, a.covered,
                              a.mn, a.sum / a.covered, a.mx, a.bid, a.ask, a.digits);
      int k = ArraySize(a.pendLine);
      ArrayResize(a.pendLine, k + 1, 64);
      ArrayResize(a.pendYm, k + 1, 64);
      ArrayResize(a.pendMs, k + 1, 64);
      a.pendLine[k] = line;
      a.pendYm[k] = YmOf(a.rowStartMs);
      a.pendMs[k] = a.rowStartMs;
     }
   a.sum = 0;
   a.covered = 0;
   a.ticks = 0;
   a.mn = DBL_MAX;
   a.mx = -1;
  }

//--- closes every row that ended at or before t
void Advance(Agg &a, long t)
  {
   while(a.rowStartMs != 0 && t >= a.rowStartMs + g_rowMs)
     {
      CloseRow(a);
      long end = a.rowStartMs + g_rowMs;
      if(a.have && a.lastTickMs + g_staleMs > end)
         a.rowStartMs = end;                    // the quote is still fresh: the next row starts with it
      else
         a.rowStartMs = 0;
     }
  }

void Feed(Agg &a, long t, double bid, double ask)
  {
   if(bid <= 0 || ask <= 0 || a.point <= 0)
      return;
   if(t < a.lastTickMs)
      return;                                   // out of order: ignore
   Advance(a, t);
   if(a.rowStartMs == 0)
     {
      a.rowStartMs = (t / g_rowMs) * g_rowMs;
      a.segMs = t;
     }
   AddSeg(a, t);
   a.cur = NormalizeDouble((ask - bid) / a.point, 1);
   a.have = true;
   a.lastTickMs = t;
   a.segMs = t;
   a.ticks++;
   if(a.cur < a.mn)
      a.mn = a.cur;
   if(a.cur > a.mx)
      a.mx = a.cur;
   a.bid = bid;
   a.ask = ask;
  }

//--- appends the waiting rows to their month files; a locked file keeps them waiting
void Flush(Agg &a)
  {
   int n = ArraySize(a.pendLine);
   int done = 0;
   while(done < n)
     {
      int ym = a.pendYm[done];
      if(a.month != ym)
        {
         WriteSummary(a);
         long last = LoadMonth(a, ym);
         if(last > a.lastRowMs)
            a.lastRowMs = last;
        }
      string name = RowFile(a.sym, ym);
      int h = FileOpen(name, FILE_READ | FILE_WRITE | FILE_TXT | FILE_ANSI | FILE_SHARE_READ | g_common);
      if(h == INVALID_HANDLE)
        {
         long nowMs = (long)GetTickCount64();
         if(nowMs - g_lastWarnMs > 60000)
           {
            g_lastWarnMs = nowMs;
            Print("SpreadSessionRecorder: cannot open ", name, " (error ", GetLastError(),
                  "). Rows are kept in memory and written when the file is free.");
           }
         break;
        }
      if(FileSize(h) == 0)
         FileWriteString(h, HEADER + "\r\n");
      FileSeek(h, 0, SEEK_END);
      Row r;
      while(done < n && a.pendYm[done] == ym)
        {
         if(a.pendMs[done] > a.lastRowMs && ParseRow(a.pendLine[done], r))
           {
            FileWriteString(h, a.pendLine[done] + "\r\n");
            AddRowToStats(a, r);                // the tables are fed by the written text only
            a.lastRowMs = a.pendMs[done];
            a.sinceReload++;
           }
         done++;
        }
      FileClose(h);
      if(InpTestReloadRows > 0 && a.sinceReload >= InpTestReloadRows)
        {
         a.sinceReload = 0;
         LoadMonth(a, ym);
        }
     }
   if(done >= n)
     {
      ArrayResize(a.pendLine, 0);
      ArrayResize(a.pendYm, 0);
      ArrayResize(a.pendMs, 0);
     }
   else
      if(done > 0)
        {
         ArrayRemove(a.pendLine, 0, done);
         ArrayRemove(a.pendYm, 0, done);
         ArrayRemove(a.pendMs, 0, done);
        }
  }

//--- reads the ticks of a symbol up to endMs from the terminal's tick history
bool Process(Agg &a, long endMs)
  {
   while(a.cursorMs < endMs)
     {
      long from = a.cursorMs + 1;
      long to = MathMin(endMs, from + 4 * 3600000 - 1);
      MqlTick ticks[];
      ResetLastError();
      int n = CopyTicksRange(a.sym, ticks, COPY_TICKS_ALL, (ulong)from, (ulong)to);
      if(n < 0)
        {
         long nowMs = (long)GetTickCount64();
         //--- while closing this is normal; the next start fills these minutes from tick history
         if(!g_closing && nowMs - g_lastWarnMs > 60000)
           {
            g_lastWarnMs = nowMs;
            Print("SpreadSessionRecorder: tick history of ", a.sym, " is not ready (error ", GetLastError(), "), retrying.");
           }
         return false;
        }
      for(int i = 0; i < n; i++)
         Feed(a, ticks[i].time_msc, ticks[i].bid, ticks[i].ask);
      a.cursorMs = to;
      Advance(a, to + 1);
     }
   return true;
  }

void Pump(bool forceSummary)
  {
   UpdateOffset();
   int n = ArraySize(g_a);
   long stamp = 0;
   for(int i = 0; i < n; i++)
     {
      MqlTick t;
      if(SymbolInfoTick(g_a[i].sym, t))
        {
         if(t.time_msc > stamp)
            stamp = t.time_msc;
         if(t.bid > 0 && t.ask > 0 && g_a[i].point > 0)
            g_a[i].nowSpread = (t.ask - t.bid) / g_a[i].point;
        }
     }
   long clock = (long)TimeTradeServer() * 1000;
   //--- stay 3 s behind the newest server stamp so late ticks are not missed;
   //--- when every symbol is quiet, the PC clock closes the rows a minute later
   long endMs = MathMax(stamp - 3000, clock - 60000);
   for(int i = 0; i < n; i++)
     {
      Process(g_a[i], endMs);
      Flush(g_a[i]);
     }
   if(forceSummary || clock - g_lastSummaryMs >= (long)MathMax(1, InpSummaryMinutes) * 60000)
     {
      g_lastSummaryMs = clock;
      for(int i = 0; i < n; i++)
         WriteSummary(g_a[i]);
     }
   if(InpShowPanel)
      DrawPanel(clock);
  }

//+------------------------------------------------------------------+
//| Panel                                                            |
//+------------------------------------------------------------------+
void SetLabel(int line, string text)
  {
   string name = PFX + "L" + IntegerToString(line);
   if(ObjectFind(0, name) < 0)
     {
      ObjectCreate(0, name, OBJ_LABEL, 0, 0, 0);
      ObjectSetInteger(0, name, OBJPROP_CORNER, CORNER_LEFT_UPPER);
      ObjectSetInteger(0, name, OBJPROP_XDISTANCE, InpPanelX + 8);
      ObjectSetInteger(0, name, OBJPROP_YDISTANCE, InpPanelY + 6 + line * (InpFontSize + 7));
      ObjectSetString(0, name, OBJPROP_FONT, "Consolas");
      ObjectSetInteger(0, name, OBJPROP_FONTSIZE, InpFontSize);
      ObjectSetInteger(0, name, OBJPROP_COLOR, InpTextColor);
      ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
     }
   ObjectSetString(0, name, OBJPROP_TEXT, text);
  }

string Num(double v, int decimals)
  {
   return (v < 0 || v == DBL_MAX) ? "-" : DoubleToString(v, decimals);
  }

double StatAvg(const Stat &s)
  {
   return (s.covered > 0) ? s.sumW / s.covered : -1;
  }

//--- MT5 shows at most 63 characters of a chart label, so every panel line is built to fit
#define PANEL_MAX_CHARS 63

string OffText(int offSec)
  {
   string sign = (offSec < 0) ? "-" : "+";
   int a = MathAbs(offSec);
   int h = a / 3600, m = (a % 3600) / 60;
   return sign + IntegerToString(h) + ((m == 0) ? "" : StringFormat(":%02d", m));
  }

string PanelHead(datetime now, string sess, int offSec)
  {
   return StringFormat("Spread recorder  %s server  %s  GMT%s",
                       TimeToString(now, TIME_DATE | TIME_MINUTES), sess, OffText(offSec));
  }

string PanelColumns()
  {
   return StringFormat("%-10s%8s%9s%9s%9s%9s%7s", "symbol", "now", "hour avg", "sess avg", "mon avg", "mon max", "rows");
  }

string PanelRow(string sym, double now, double hourAvg, double sessAvg, double monAvg, double monMax, long rows)
  {
   return StringFormat("%-10s%8s%9s%9s%9s%9s%7s", StringSubstr(sym, 0, 10), Num(now, 1), Num(hourAvg, 2),
                       Num(sessAvg, 2), Num(monAvg, 2), Num(monMax, 1), IntegerToString(rows));
  }

string PanelFoot(string dir, bool common)
  {
   string path = (common ? "Common\\Files\\" : "MQL5\\Files\\") + dir;
   string t = "spread in points  files: " + path;
   if(StringLen(t) > PANEL_MAX_CHARS)
      t = "files: " + path;
   if(StringLen(t) > PANEL_MAX_CHARS)
      t = "files: ..." + StringSubstr(path, StringLen(path) - (PANEL_MAX_CHARS - 10));
   return t;
  }

void DrawPanel(long clockMs)
  {
   int n = MathMin(ArraySize(g_a), 20);
   datetime now = (datetime)(clockMs / 1000);
   MqlDateTime d;
   TimeToStruct(now, d);
   string sess = SessionLabel(now, g_offSec);
   int si = SessIndex(sess);
   int lines = n + 3;
   string back = PFX + "BG";
   if(ObjectFind(0, back) < 0)
     {
      ObjectCreate(0, back, OBJ_RECTANGLE_LABEL, 0, 0, 0);
      ObjectSetInteger(0, back, OBJPROP_CORNER, CORNER_LEFT_UPPER);
      ObjectSetInteger(0, back, OBJPROP_XDISTANCE, InpPanelX);
      ObjectSetInteger(0, back, OBJPROP_YDISTANCE, InpPanelY);
      ObjectSetInteger(0, back, OBJPROP_BGCOLOR, InpBackColor);
      ObjectSetInteger(0, back, OBJPROP_BORDER_TYPE, BORDER_FLAT);
      ObjectSetInteger(0, back, OBJPROP_COLOR, InpBackColor);
      ObjectSetInteger(0, back, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, back, OBJPROP_HIDDEN, true);
     }
   ObjectSetInteger(0, back, OBJPROP_XSIZE, (int)(InpFontSize * 0.78 * PANEL_MAX_CHARS) + 16);
   ObjectSetInteger(0, back, OBJPROP_YSIZE, lines * (InpFontSize + 7) + 12);

   SetLabel(0, PanelHead(now, sess, g_offSec));
   SetLabel(1, PanelColumns());
   for(int i = 0; i < n; i++)
      SetLabel(i + 2, PanelRow(g_a[i].sym, g_a[i].nowSpread, StatAvg(g_a[i].hour[d.hour]),
                               StatAvg(g_a[i].sess[si]), StatAvg(g_a[i].all), g_a[i].all.mx, g_a[i].all.rows));
   SetLabel(n + 2, PanelFoot(g_dir, g_common != 0));
   for(int i = lines; i < g_panelLines; i++)
      ObjectDelete(0, PFX + "L" + IntegerToString(i));
   g_panelLines = lines;
   ChartRedraw(0);
  }

//+------------------------------------------------------------------+
//| Built-in checks                                                  |
//+------------------------------------------------------------------+
int g_pass = 0, g_fail = 0;

void Check(bool ok, string what)
  {
   if(ok)
      g_pass++;
   else
     {
      g_fail++;
      Print("SELFTEST FAIL: ", what);
     }
  }

int ReadRows(string name, Row &rows[])
  {
   ArrayResize(rows, 0);
   int h = FileOpen(name, FILE_READ | FILE_TXT | FILE_ANSI | FILE_SHARE_READ | FILE_SHARE_WRITE | g_common);
   if(h == INVALID_HANDLE)
      return -1;
   Row r;
   while(!FileIsEnding(h))
     {
      string line = FileReadString(h);
      if(!ParseRow(line, r))
         continue;
      int k = ArraySize(rows);
      ArrayResize(rows, k + 1);
      rows[k] = r;
     }
   FileClose(h);
   return ArraySize(rows);
  }

void TestFeed(Agg &a, long t, double bid, double spreadPts)
  {
   Feed(a, t, bid, (bid > 0) ? bid + spreadPts * a.point : 0);
  }

bool Near(double a, double b)
  {
   return MathAbs(a - b) < 0.0000001;
  }

void CleanSelfTest()
  {
   string names[] = {"TEST_A_202001", "TEST_C_202001", "TEST_C_202002"};
   for(int i = 0; i < ArraySize(names); i++)
     {
      FileDelete(g_dir + "\\" + names[i] + ".csv", g_common);
      FileDelete(g_dir + "\\" + names[i] + "_summary.csv", g_common);
     }
  }

void ReplayA(Agg &a, long T0)
  {
   TestFeed(a, T0, 1.10000, 10);
   TestFeed(a, T0 + 30000, 1.10000, 20);
   Advance(a, T0 + 3600000);
   TestFeed(a, T0 + 3615000, 1.10000, 8);
   TestFeed(a, T0 + 3615000, 1.10000, 50);        // same millisecond: lasts 0 ms, still the maximum
   TestFeed(a, T0 + 3615001, 1.10000, 8);
   TestFeed(a, T0 + 3615002, 0, 99);              // bad tick: ignored
   Advance(a, T0 + 3660000);
  }

bool RunSelfTest()
  {
   g_pass = 0;
   g_fail = 0;
   string keepDir = g_dir;
   long keepRow = g_rowMs, keepStale = g_staleMs, keepBack = g_backMs;
   int keepOff = g_offSec;
   g_dir = keepDir + "\\selftest";
   g_rowMs = 60000;
   g_staleMs = 300000;
   g_backMs = 86400000;
   g_offSec = 7200;
   CleanSelfTest();

   long T0 = (long)D'2020.01.15 10:00:00' * 1000;
   Agg a;
   InitAgg(a, "TEST_A", 0.00001, 5);
   ResumeAgg(a, T0);
   Check(a.lastRowMs == 0 && a.skipBefore == T0 - 86400000, "fresh start resumes at the backfill limit");
   ReplayA(a, T0);
   Flush(a);

   Row r[];
   int n = ReadRows(RowFile("TEST_A", 202001), r);
   Check(n == 7, StringFormat("7 rows expected, got %d", n));
   if(n == 7)
     {
      Check(r[0].ticks == 2 && Near(r[0].cov, 60) && Near(r[0].mn, 10) && Near(r[0].avg, 15) && Near(r[0].mx, 20),
            "time-weighted average 10 for 30 s then 20 for 30 s = 15");
      Check(r[1].ticks == 0 && Near(r[1].cov, 60) && Near(r[1].avg, 20) && Near(r[1].mn, 20) && Near(r[1].mx, 20),
            "a row without ticks carries the standing spread");
      Check(r[5].t == (datetime)(T0 / 1000 + 300) && Near(r[5].cov, 30), "stale limit: counting stops 300 s after the last tick");
      Check(r[6].t == (datetime)(T0 / 1000 + 3600) && Near(r[6].cov, 45), "after a gap a row starts at its first tick, no carry");
      Check(r[6].ticks == 3 && Near(r[6].mn, 8) && Near(r[6].mx, 50) && Near(r[6].avg, 8.00),
            "zero-length spike counts in the maximum, bad tick ignored");
      Check(r[0].sess == "LONDON", "row session label");
     }
   datetime day = D'2020.01.15 00:00:00';
   Check(SessionLabel(day + 30 * 60, 7200) == "ROLLOVER" && SessionLabel(day + 23 * 3600 + 55 * 60, 7200) == "ROLLOVER",
         "rollover window around server midnight");
   Check(SessionLabel(day + 15 * 3600, 7200) == "LONDON_NY" && SessionLabel(day + 20 * 3600, 7200) == "NEWYORK",
         "overlap and New York labels");
   Check(SessionLabel(day + 5 * 3600, 7200) == "ASIA" && SessionLabel(day + 23 * 3600 + 30 * 60, 7200) == "OFF",
         "Asia and off-hours labels");

   //--- tables rebuilt from the file must equal the live tables
   string live = SummaryText(a);
   LoadMonth(a, 202001);
   string reloaded = SummaryText(a);
   Check(live == reloaded, "tables rebuilt from the file equal the live tables");
   Check(a.all.rows == 7 && Near(a.all.mx, 50) && a.all.mxAt == (datetime)(T0 / 1000 + 3600), "month table: rows, maximum and its time");
   WriteSummary(a);
   Check(FileIsExist(SummaryFile("TEST_A", 202001), g_common), "summary file written");

   //--- restart: a new instance on the same files, fed the same ticks again, adds nothing
   Agg b;
   InitAgg(b, "TEST_A", 0.00001, 5);
   ResumeAgg(b, T0 + 3660000);
   Check(b.lastRowMs == T0 + 3600000 && b.skipBefore == T0 + 3660000 && b.all.rows == 7, "restart finds the last row and the tables");
   ReplayA(b, T0);
   Flush(b);
   n = ReadRows(RowFile("TEST_A", 202001), r);
   Check(n == 7, StringFormat("restart must not duplicate rows, got %d", n));
   TestFeed(b, T0 + 3670000, 1.10000, 9);
   Advance(b, T0 + 3720000);
   Flush(b);
   n = ReadRows(RowFile("TEST_A", 202001), r);
   Check(n == 8 && b.all.rows == 8, StringFormat("recording continues after restart, got %d rows", n));
   if(n == 8)
      Check(Near(r[7].cov, 60) && Near(r[7].mn, 8) && Near(r[7].mx, 9) && r[7].ticks == 1,
            "first row after restart knows its opening spread");

   //--- month change
   Agg c;
   InitAgg(c, "TEST_C", 0.01, 2);
   long M = (long)D'2020.02.01 00:00:00' * 1000;
   ResumeAgg(c, M);
   TestFeed(c, M - 30000, 1500.00, 5);
   TestFeed(c, M + 10000, 1500.00, 7);
   Advance(c, M + 60000);
   Flush(c);
   Row r1[], r2[];
   int n1 = ReadRows(RowFile("TEST_C", 202001), r1);
   int n2 = ReadRows(RowFile("TEST_C", 202002), r2);
   Check(n1 == 1 && n2 == 1, StringFormat("one row in each month file, got %d and %d", n1, n2));
   if(n2 == 1)
      Check(Near(r2[0].mn, 5) && Near(r2[0].mx, 7) && c.month == 202002 && c.all.rows == 1, "new month starts new tables");
   Check(FileIsExist(SummaryFile("TEST_C", 202001), g_common), "old month summary written at the month change");

   string list[];
   Check(SplitList(" EURUSD, GBPUSD ,,", list) == 2 && list[1] == "GBPUSD", "symbol list parsing");
   Check(SafeName("BTC/USD.a") == "BTC_USD.a", "file name made safe");
   Row p;
   string line = FormatRow(T0, 7200, "X", "ASIA", 3, 59999, 1.5, 2.345, 9.0, 1.2, 1.3, 5);
   Check(ParseRow(line, p) && p.t == (datetime)(T0 / 1000) && p.ticks == 3 && Near(p.cov, 59.999) && Near(p.avg, 2.35) && !ParseRow(HEADER, p),
         "row text round trip");

   //--- panel lines must fit the 63-character label limit even with wide values
   Check(OffText(7200) == "+2" && OffText(19800) == "+5:30" && OffText(-12600) == "-3:30" && OffText(0) == "+0",
         "GMT offset text");
   string head = PanelHead((datetime)(T0 / 1000), "LONDON_NY", 45900);
   string row = PanelRow("BTCUSD.ecnX", 99999.9, 99999.99, 99999.99, 99999.99, 999999.9, 999999);
   string foot1 = PanelFoot("SpreadRecorder", false), foot2 = PanelFoot("A_very_long_folder_name\\with_a_sub_folder_inside_it", true);
   Check(StringLen(head) <= PANEL_MAX_CHARS && StringFind(head, "GMT+12:45") > 0, "panel head fits: " + head);
   Check(StringLen(PanelColumns()) <= PANEL_MAX_CHARS && StringFind(PanelColumns(), "rows") > 0, "panel columns fit: " + PanelColumns());
   Check(StringLen(row) <= PANEL_MAX_CHARS && StringFind(row, "999999", StringLen(row) - 7) > 0, "panel row fits: " + row);
   Check(StringLen(foot1) <= PANEL_MAX_CHARS && foot1 == "spread in points  files: MQL5\\Files\\SpreadRecorder", "panel foot: " + foot1);
   Check(StringLen(foot2) <= PANEL_MAX_CHARS && StringFind(foot2, "inside_it") > 0, "long folder foot fits: " + foot2);

   CleanSelfTest();
   FolderDelete(g_dir, g_common);
   g_dir = keepDir;
   g_rowMs = keepRow;
   g_staleMs = keepStale;
   g_backMs = keepBack;
   g_offSec = keepOff;
   Print(StringFormat("SELFTEST %d/%d passed%s", g_pass, g_pass + g_fail, g_fail == 0 ? "" : "  <-- FAILED"));
   return (g_fail == 0);
  }

//+------------------------------------------------------------------+
//| Events                                                           |
//+------------------------------------------------------------------+
int OnInit()
  {
   g_dir = (InpFolder == "") ? "SpreadRecorder" : InpFolder;
   g_common = InpCommonFolder ? FILE_COMMON : 0;
   g_rowMs = (long)MathMax(1, InpRowSeconds) * 1000;
   g_staleMs = (long)MathMax(1, InpStaleSeconds) * 1000;
   g_backMs = (long)MathMax(0, InpBackfillHours) * 3600000;
   UpdateOffset();

   if(InpSelfTest)
     {
      g_selfTestOnly = true;
      RunSelfTest();
      return INIT_SUCCEEDED;
     }

   string names[];
   if(InpSymbols == "*")
     {
      int total = SymbolsTotal(true);
      for(int i = 0; i < total && ArraySize(names) < MAX_SYMS; i++)
        {
         int k = ArraySize(names);
         ArrayResize(names, k + 1);
         names[k] = SymbolName(i, true);
        }
     }
   else
      SplitList(InpSymbols, names);
   if(ArraySize(names) == 0)
     {
      ArrayResize(names, 1);
      names[0] = _Symbol;
     }

   long nowMs = (long)TimeTradeServer() * 1000;
   ArrayResize(g_a, 0);
   for(int i = 0; i < ArraySize(names) && ArraySize(g_a) < MAX_SYMS; i++)
     {
      if(!SymbolSelect(names[i], true))
        {
         Print("SpreadSessionRecorder: symbol ", names[i], " not found, skipped.");
         continue;
        }
      int k = ArraySize(g_a);
      ArrayResize(g_a, k + 1);
      InitAgg(g_a[k], names[i], SymbolInfoDouble(names[i], SYMBOL_POINT), (int)SymbolInfoInteger(names[i], SYMBOL_DIGITS));
      ResumeAgg(g_a[k], nowMs);
      Print("SpreadSessionRecorder: ", names[i], " rows in the files this month: ", g_a[k].all.rows,
            ", recording from ", TimeToString((datetime)(g_a[k].skipBefore / 1000), TIME_DATE | TIME_SECONDS));
     }
   if(ArraySize(g_a) == 0)
     {
      Print("SpreadSessionRecorder: no valid symbol.");
      return INIT_PARAMETERS_INCORRECT;
     }
   g_lastSummaryMs = nowMs;
   EventSetTimer(1);
   return INIT_SUCCEEDED;
  }

void OnDeinit(const int reason)
  {
   EventKillTimer();
   g_closing = true;
   if(!g_selfTestOnly && ArraySize(g_a) > 0)
      Pump(true);
   ObjectsDeleteAll(0, PFX);
   ChartRedraw(0);
  }

void OnTimer()
  {
   if(!g_selfTestOnly)
      Pump(false);
  }

void OnTick()
  {
  }
//+------------------------------------------------------------------+
