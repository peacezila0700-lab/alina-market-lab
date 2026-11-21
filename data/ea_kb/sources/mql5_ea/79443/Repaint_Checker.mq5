//+------------------------------------------------------------------+
//|                                             Repaint_Checker.mq5   |
//|  Finds out whether an indicator repaints.                        |
//|  When each bar closes it records what every buffer of the tested |
//|  indicator showed at that moment. Later it reads the same bars   |
//|  again and reports values that changed, signals that appeared    |
//|  late (empty at the close, filled in later) and signals that     |
//|  vanished. Best run in the Strategy Tester; also works live.     |
//|  Places no trades.                                               |
//+------------------------------------------------------------------+
#property copyright   "Desmond Obafemi"
#property link        "https://www.mql5.com/en/users/478847"
#property version     "1.01"
#property description "Checks any indicator for repainting: values that change after the bar closed,"
#property description "signals that appear late and signals that vanish. Run it in the Strategy Tester."

#include <Canvas\Canvas.mqh>

input string InpIndicator = "";                  // Indicator to test (path in MQL5\Indicators, empty = built-in Fractals demo)
input string InpParams    = "";                  // Its inputs, comma separated (empty = its defaults)
input int    InpMaxBuffers = 0;                  // Buffers to check (0 = all it has, up to 32)
input double InpTolerance = 0.0000001;           // Ignore changes smaller than this (relative)
input bool   InpShowPanel = true;                // Show the result panel
input bool   InpWriteCsv  = true;                // Write a CSV report (Common\Files)

#define MAXB 32

int      g_h = INVALID_HANDLE;
string   g_name = "";              // name shown in reports
int      g_nb = 0;                 // buffers found
datetime g_last = 0;
datetime g_t[];                    // closed-bar times
double   g_v[];                    // values at the close, g_v[i * MAXB + b]
int      g_n = 0;

// results per buffer
long     r_checked[MAXB], r_changed[MAXB], r_late[MAXB], r_gone[MAXB];
double   r_maxdiff[MAXB];
string   r_example[MAXB];
bool     g_done = false;
datetime g_lastCompare = 0;

CCanvas  g_cv;
bool     g_cvOk = false;
string   PFX;
double   g_s = 1.0;

//+------------------------------------------------------------------+
bool IsNumber(const string s, bool &isInt)
{
   const int n = StringLen(s);
   if(n == 0) return(false);
   bool dot = false, digit = false;
   for(int i = 0; i < n; i++)
   {
      const ushort c = StringGetCharacter(s, i);
      if(c >= '0' && c <= '9') { digit = true; continue; }
      if(c == '.' && !dot) { dot = true; continue; }
      if((c == '-' || c == '+') && i == 0) continue;
      return(false);
   }
   isInt = !dot;
   return(digit);
}

int CreateHandle()
{
   // empty name: demo on the terminal's built-in Fractals (always available, and it repaints)
   if(StringLen(InpIndicator) == 0) return(iFractals(_Symbol, _Period));
   MqlParam p[];
   ArrayResize(p, 1);
   p[0].type = TYPE_STRING;
   p[0].string_value = InpIndicator;
   string parts[];
   const int k = (StringLen(InpParams) > 0) ? StringSplit(InpParams, ',', parts) : 0;
   for(int i = 0; i < k; i++)
   {
      string s = parts[i];
      StringTrimLeft(s); StringTrimRight(s);
      const int j = ArraySize(p);
      ArrayResize(p, j + 1);
      bool isInt;
      string low = s; StringToLower(low);
      if(low == "true" || low == "false") { p[j].type = TYPE_BOOL; p[j].integer_value = (low == "true"); }
      else if(IsNumber(s, isInt))
      {
         if(isInt) { p[j].type = TYPE_INT; p[j].integer_value = StringToInteger(s); }
         else      { p[j].type = TYPE_DOUBLE; p[j].double_value = StringToDouble(s); }
      }
      else
      {
         StringReplace(s, "\"", "");
         p[j].type = TYPE_STRING; p[j].string_value = s;
      }
   }
   return(IndicatorCreate(_Symbol, _Period, IND_CUSTOM, ArraySize(p), p));
}

int OnInit()
{
   ArrayInitialize(r_checked, 0); ArrayInitialize(r_changed, 0); ArrayInitialize(r_late, 0);
   ArrayInitialize(r_gone, 0); ArrayInitialize(r_maxdiff, 0);
   for(int b = 0; b < MAXB; b++) r_example[b] = "";
   PFX = "RPC" + IntegerToString((long)(GetMicrosecondCount() % 1000000)) + "_";
   g_s = MathMax(1.0, MathMin(2.0, TerminalInfoInteger(TERMINAL_SCREEN_DPI) / 96.0));
   g_name = (StringLen(InpIndicator) == 0) ? "Fractals (built-in demo)" : InpIndicator;
   g_h = CreateHandle();
   if(g_h == INVALID_HANDLE)
   {
      PrintFormat("Repaint Checker: cannot load indicator '%s' (error %d). Check the name and the inputs.", g_name, GetLastError());
      return(INIT_FAILED);
   }
   if(!MQLInfoInteger(MQL_TESTER) || MQLInfoInteger(MQL_VISUAL_MODE)) ChartIndicatorAdd(0, 0, g_h);
   EventSetTimer(2);
   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason)
{
   EventKillTimer();
   if(!g_done && g_n > 0) { Compare(); Report(); }
   if(g_cvOk) { g_cv.Destroy(); g_cvOk = false; }
   ObjectsDeleteAll(0, PFX);
   if(g_h != INVALID_HANDLE) IndicatorRelease(g_h);
}

double OnTester()
{
   Compare();
   Report();
   g_done = true;
   long total = 0;
   for(int b = 0; b < g_nb; b++) total += r_changed[b] + r_late[b] + r_gone[b];
   return((double)total);
}

void OnTimer()
{
   if(MQLInfoInteger(MQL_TESTER)) return;
   Compare();              // live: keep the verdict up to date
   DrawPanel();
}

int DetectBuffers()
{
   const int lim = (InpMaxBuffers > 0) ? MathMin(InpMaxBuffers, MAXB) : MAXB;
   double v[1];
   int n = 0;
   for(int b = 0; b < lim; b++)
   {
      ResetLastError();
      if(CopyBuffer(g_h, b, 1, 1, v) != 1) break;
      n++;
   }
   return(n);
}

void OnTick()
{
   const datetime t = iTime(_Symbol, _Period, 0);
   if(t == g_last) return;
   if(BarsCalculated(g_h) <= 0) return;
   g_last = t;
   if(g_nb == 0)
   {
      g_nb = DetectBuffers();
      if(g_nb == 0) return;
      PrintFormat("Repaint Checker: testing '%s' on %s %s, %d buffers", g_name, _Symbol, EnumToString(_Period), g_nb);
   }
   //--- record what every buffer shows for the bar that just closed
   const datetime bt = iTime(_Symbol, _Period, 1);
   if(g_n > 0 && g_t[g_n - 1] == bt) return;
   if(g_n % 1024 == 0) { ArrayResize(g_t, g_n + 1024); ArrayResize(g_v, (g_n + 1024) * MAXB); }
   g_t[g_n] = bt;
   double v[1];
   for(int b = 0; b < g_nb; b++)
      g_v[g_n * MAXB + b] = (CopyBuffer(g_h, b, 1, 1, v) == 1) ? v[0] : EMPTY_VALUE;
   g_n++;
   if(MQLInfoInteger(MQL_VISUAL_MODE) && t - g_lastCompare >= 50 * PeriodSeconds(_Period))
   {
      g_lastCompare = t;
      Compare();
      DrawPanel();
   }
}

bool IsEmptyVal(const double x) { return(x == EMPTY_VALUE || x == 0.0 || !MathIsValidNumber(x)); }

void Compare()
{
   if(g_n < 2 || g_nb == 0) return;
   ArrayInitialize(r_checked, 0); ArrayInitialize(r_changed, 0); ArrayInitialize(r_late, 0);
   ArrayInitialize(r_gone, 0); ArrayInitialize(r_maxdiff, 0);
   for(int b = 0; b < MAXB; b++) r_example[b] = "";
   // read all buffers over the recorded period once
   const int cnt = Bars(_Symbol, _Period, g_t[0], g_t[g_n - 1]);
   for(int b = 0; b < g_nb; b++)
   {
      double now[]; datetime tm[];
      ArraySetAsSeries(now, false); ArraySetAsSeries(tm, false);
      const int got = CopyBuffer(g_h, b, g_t[0], g_t[g_n - 1], now);
      const int gt  = CopyTime(_Symbol, _Period, g_t[0], g_t[g_n - 1], tm);
      if(got <= 0 || gt != got) continue;
      int j = 0;
      for(int i = 0; i < g_n; i++)
      {
         while(j < gt && tm[j] < g_t[i]) j++;
         if(j >= gt || tm[j] != g_t[i]) continue;
         const double a = g_v[i * MAXB + b], c = now[j];
         r_checked[b]++;
         const bool ea = IsEmptyVal(a), ec = IsEmptyVal(c);
         string kind = "";
         if(ea && !ec)       { r_late[b]++; kind = "appeared late"; }
         else if(!ea && ec)  { r_gone[b]++; kind = "vanished"; }
         else if(!ea && !ec)
         {
            const double d = MathAbs(a - c);
            if(d > InpTolerance * MathMax(1.0, MathAbs(a)))
            {
               r_changed[b]++; kind = "changed";
               if(d > r_maxdiff[b]) r_maxdiff[b] = d;
            }
         }
         if(kind != "" && StringLen(r_example[b]) < 120)
            r_example[b] += StringFormat("%s%s %s (%s -> %s)", r_example[b] == "" ? "" : "; ", TimeToString(g_t[i], TIME_DATE | TIME_MINUTES),
                                         kind, ea ? "empty" : DoubleToString(a, _Digits), ec ? "empty" : DoubleToString(c, _Digits));
      }
   }
}

void Report()
{
   long total = 0;
   for(int b = 0; b < g_nb; b++) total += r_changed[b] + r_late[b] + r_gone[b];
   PrintFormat("Repaint Checker: '%s' %s %s, %d closed bars, %d buffers -> %s",
               g_name, _Symbol, EnumToString(_Period), g_n, g_nb, total == 0 ? "NO REPAINTING FOUND" : "REPAINTS");
   for(int b = 0; b < g_nb; b++)
      PrintFormat("  buffer %d: checked %I64d, changed %I64d, appeared late %I64d, vanished %I64d%s",
                  b, r_checked[b], r_changed[b], r_late[b], r_gone[b], r_example[b] == "" ? "" : "  e.g. " + r_example[b]);
   if(InpWriteCsv)
   {
      string name = (StringLen(InpIndicator) == 0) ? "Fractals" : InpIndicator;
      StringReplace(name, "\\", "_"); StringReplace(name, "/", "_");
      const string fn = StringFormat("RepaintChecker_%s_%s_%s.csv", name, _Symbol, StringSubstr(EnumToString(_Period), 7));
      const int fh = FileOpen(fn, FILE_WRITE | FILE_CSV | FILE_COMMON | FILE_ANSI, ',');
      if(fh != INVALID_HANDLE)
      {
         FileWrite(fh, "indicator", "symbol", "timeframe", "buffer", "checked", "changed", "appeared_late", "vanished", "max_change", "examples");
         for(int b = 0; b < g_nb; b++)
            FileWrite(fh, g_name, _Symbol, StringSubstr(EnumToString(_Period), 7), b, r_checked[b], r_changed[b],
                      r_late[b], r_gone[b], DoubleToString(r_maxdiff[b], 8), r_example[b]);
         FileClose(fh);
         PrintFormat("Repaint Checker: report written to Common\\Files\\%s", fn);
      }
   }
   DrawPanel();
}

//+------------------------------------------------------------------+
//| Panel                                                            |
//+------------------------------------------------------------------+
uint Clr(const color c, const uchar a) { return(ColorToARGB(c, a)); }
int  S(const double v) { return((int)MathRound(v * g_s)); }

void RRect(const int x1, const int y1, const int x2, const int y2, const int r, const uint clr)
{
   if(r <= 0 || x2 - x1 < 2 * r || y2 - y1 < 2 * r) { g_cv.FillRectangle(x1, y1, x2, y2, clr); return; }
   g_cv.FillRectangle(x1 + r, y1, x2 - r, y2, clr);
   g_cv.FillRectangle(x1, y1 + r, x1 + r + 1, y2 - r, clr);
   g_cv.FillRectangle(x2 - r - 1, y1 + r, x2, y2 - r, clr);
   g_cv.FillCircle(x1 + r, y1 + r, r, clr);
   g_cv.FillCircle(x2 - r, y1 + r, r, clr);
   g_cv.FillCircle(x1 + r, y2 - r, r, clr);
   g_cv.FillCircle(x2 - r, y2 - r, r, clr);
}

void Txt(const int x, const int y, const string s, const uint clr, const int size10, const bool bold = false,
         const uint align = TA_LEFT | TA_TOP)
{
   g_cv.FontSet("Segoe UI", -size10, bold ? FW_SEMIBOLD : FW_NORMAL);
   g_cv.TextOut(x, y, s, clr, align);
}

int TW(const string s, const int size10, const bool bold = false)
{
   g_cv.FontSet("Segoe UI", -size10, bold ? FW_SEMIBOLD : FW_NORMAL);
   return(g_cv.TextWidth(s));
}

void DrawPanel()
{
   if(!InpShowPanel) return;
   if(MQLInfoInteger(MQL_TESTER) && !MQLInfoInteger(MQL_VISUAL_MODE)) return;
   const color bgc = (color)ChartGetInteger(0, CHART_COLOR_BACKGROUND);
   const bool dark = (0.299 * (bgc & 0xFF) + 0.587 * ((bgc >> 8) & 0xFF) + 0.114 * ((bgc >> 16) & 0xFF)) < 128;
   const uint cBg     = dark ? Clr(C'21,24,31', 255)  : Clr(C'252,252,253', 255);
   const uint cBorder = dark ? Clr(C'52,58,70', 255)  : Clr(C'214,218,226', 255);
   const uint cText   = dark ? Clr(C'236,239,244', 255) : Clr(C'28,32,40', 255);
   const uint cDim    = dark ? Clr(C'138,146,160', 255) : Clr(C'110,118,132', 255);
   const uint cTrack  = dark ? Clr(C'46,52,64', 255)  : Clr(C'228,231,237', 255);

   long total = 0;
   int bad = 0;
   for(int b = 0; b < g_nb; b++) { const long x = r_changed[b] + r_late[b] + r_gone[b]; total += x; if(x > 0) bad++; }
   const bool ready = (g_nb > 0 && g_n > 10);
   const color sc = !ready ? C'140,148,160' : (total == 0 ? C'38,194,129' : C'235,77,75');
   const string verdict = !ready ? "COLLECTING BARS..." : (total == 0 ? "NO REPAINTING FOUND" : "REPAINTS");

   const int rows = MathMin(g_nb, 8);
   const int W = S(320), pad = S(14);
   const int H = S(118) + rows * S(20) + S(10);
   const string nm = PFX + "panel";
   if(!g_cvOk)
   {
      if(!g_cv.CreateBitmapLabel(0, 0, nm, 0, 0, W, H, COLOR_FORMAT_ARGB_NORMALIZE)) return;
      g_cvOk = true;
      ObjectSetInteger(0, nm, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, nm, OBJPROP_HIDDEN, true);
      ObjectSetInteger(0, nm, OBJPROP_CORNER, CORNER_RIGHT_UPPER);
      ObjectSetInteger(0, nm, OBJPROP_ANCHOR, ANCHOR_RIGHT_UPPER);
      ObjectSetInteger(0, nm, OBJPROP_XDISTANCE, 12);
      ObjectSetInteger(0, nm, OBJPROP_YDISTANCE, 28);
   }
   else if(g_cv.Width() != W || g_cv.Height() != H) g_cv.Resize(W, H);

   g_cv.Erase(0);
   RRect(0, 0, W - 1, H - 1, S(10), cBorder);
   RRect(1, 1, W - 2, H - 2, S(9), cBg);
   RRect(1, 1, S(5), H - 2, S(2), Clr(sc, 255));
   int y = S(12);
   Txt(pad, y, "Repaint Checker", cText, 100, true);
   Txt(W - pad, y + S(1), _Symbol + "  \x00B7  " + StringSubstr(EnumToString(_Period), 7), cDim, 80, false, TA_RIGHT | TA_TOP);
   y += S(22);
   string ind = g_name;
   if(StringLen(ind) > 40) ind = "..." + StringSubstr(ind, StringLen(ind) - 38);
   Txt(pad, y, ind, cDim, 80);
   y += S(20);
   const string badge = (total == 0 && ready ? "\x2714  " : (ready ? "\x2716  " : "")) + verdict;
   const int bw = TW(badge, 95, true) + S(24);
   RRect(pad, y, pad + bw, y + S(26), S(13), Clr(sc, 255));
   Txt(pad + bw / 2, y + S(13), badge, Clr(clrWhite, 255), 95, true, TA_CENTER | TA_VCENTER);
   y += S(34);
   Txt(pad, y, StringFormat("%d closed bars recorded  \x00B7  %d buffers  \x00B7  %d repaint", g_n, g_nb, bad), cDim, 75);
   y += S(20);
   g_cv.FillRectangle(pad, y, W - pad, y, cTrack);
   y += S(6);
   for(int b = 0; b < rows; b++)
   {
      const long x = r_changed[b] + r_late[b] + r_gone[b];
      Txt(pad, y + S(2), StringFormat("Buffer %d", b), cText, 80, true);
      string d = (x == 0) ? "no change" : "";
      if(r_changed[b] > 0) d += StringFormat("%I64d changed ", r_changed[b]);
      if(r_late[b] > 0)    d += StringFormat("%I64d late ", r_late[b]);
      if(r_gone[b] > 0)    d += StringFormat("%I64d vanished", r_gone[b]);
      Txt(W - pad, y + S(2), d, x == 0 ? Clr(C'38,194,129', 255) : Clr(C'235,77,75', 255), 80, false, TA_RIGHT | TA_TOP);
      y += S(20);
   }
   g_cv.Update();
}
//+------------------------------------------------------------------+
