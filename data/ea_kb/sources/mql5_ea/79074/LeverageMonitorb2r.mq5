//+------------------------------------------------------------------+
//|                                              LeverageMonitor.mq5 |
//|  Expert Advisor (non-trading). Shows the leverage of every       |
//|  Market Watch symbol from its specification, incl. floating      |
//|  (tiered) margin rates, plus a leverage history chart.           |
//|                                                                  |
//|  Must be an EA: OrderCalcMargin() is prohibited in indicators    |
//|  (error 4014). Attach it to its own chart; it never trades.      |
//+------------------------------------------------------------------+
#property copyright   "Leverage Monitor"
#property version     "4.30"
#property description "Spec-based, tier-aware leverage per Market Watch symbol + history. Non-trading EA."

#include <Canvas\Canvas.mqh>

//--- layout (base values at zoom 100 %; use the A- / A+ buttons and the corner grip at runtime)
input int      InpCornerX     = 10;             // Panel X offset (px)
input int      InpCornerY     = 20;             // Panel Y offset (px)
input int      InpRowHeight   = 18;             // Row height (px) at base font
input int      InpMaxRows     = 0;              // Initial visible rows (0 = fit chart height)
input int      InpFontSize    = 8;              // Base font size (pt)
input int      InpSymbolColW  = 92;             // Symbol column width
input int      InpTypeColW    = 50;             // Type column width
input int      InpLevColW     = 66;             // Leverage column width
input int      InpTiersColW   = 180;            // Tiers column width
input int      InpSwapColW    = 118;            // Swap column width
input int      InpCommColW    = 76;             // Commission column width
input int      InpSpreadColW  = 120;            // Spread column width
input int      InpGraphW      = 200;            // History chart width (resizable)
input bool     InpChartSpread = false;          // History chart shows spread instead of leverage (button in title bar)

//--- data
input int      InpRecordSec   = 60;             // History sample interval (s)
input int      InpRefreshSec  = 5;              // Spec re-check interval (s)
input int      InpTierRefresh = 600;            // Tier re-scan interval (s)
input int      InpProbePerSec = 3;              // Symbols tier-scanned per second
input int      InpMaxPoints   = 1440;           // Max history points / symbol
input bool     InpSaveHistory = true;           // Persist history between sessions

//--- colors (all drawn fully opaque)
input color    InpBgColor     = C'20,24,32';    // Background
input color    InpTitleColor  = C'28,34,46';    // Title bar / footer
input color    InpHeaderColor = C'33,40,54';    // Column header
input color    InpBorderColor = C'58,67,86';    // Borders
input color    InpTextColor   = C'226,230,238'; // Text
input color    InpFootColor   = clrWhite;       // Bottom info line text
input color    InpDimColor    = C'128,138,158'; // Secondary text
input color    InpAccentColor = C'64,156,255';  // Chart line
input color    InpUpColor     = C'66,201,120';  // Rise
input color    InpDownColor   = C'240,92,92';   // Fall

//+------------------------------------------------------------------+
class CSymData
  {
public:
   string            name;
   string            tag;        // calc-mode label
   string            why;        // reason if the tier scan failed
   double            cur;        // headline (first tier) leverage, 0 = n/a
   datetime          t[];
   double            v[];
   double            tLots[];    // tier start volume (lots)
   double            tLev[];     // marginal leverage within the tier
   ulong             probeAt;    // GetTickCount64 of last tier scan (0 = never)
   double            probeCur;   // leverage the tier scan was made for
   //--- swap
   bool              swapOk;
   double            swapL, swapS;
   long              swapMode, swap3;
   //--- commission (from SymbolInfoCommissions)
   string            commTxt, commTip;
   //--- spread (points): current + 60 one-minute buckets for the 1 h average
   double            spr, sprAvg;
   int               sprCnt, sprMin;
   double            recSum;     // spread samples since the last history point
   int               recCnt;
   double            sv[];       // spread history (points)
   datetime          sT[];
   long              bMin[60];
   double            bSum[60];
   int               bCnt[60];
                     CSymData()
     {
      cur = 0; tag = ""; why = ""; probeAt = 0; probeCur = 0; commTxt = "-"; commTip = "";
      recSum = 0; recCnt = 0;
      swapOk = false; swapL = 0; swapS = 0; swapMode = 0; swap3 = 0;
      spr = -1; sprAvg = -1; sprCnt = 0; sprMin = 0;
      ArrayInitialize(bMin, -1);
      ArrayInitialize(bSum, 0);
      ArrayInitialize(bCnt, 0);
     }
  };

CCanvas   g_canvas;
CSymData *g_sym[];
int       g_order[];
string    g_obj = "LevMon_Canvas";

//--- GUI state
int       g_font = 8;               // current font size (zoom)
int       g_graphBase = 200;        // history chart width at zoom 100 %
int       g_rowsSet = 0;            // wanted visible rows (0 = fit chart)
int       g_sort = 0;               // 0 = market watch, 1 = name, 2 = leverage desc
bool      g_collapsed = false;
int       g_scroll = 0;
int       g_hover = -1;
bool      g_prevDown = false;
bool      g_resizing = false;
int       g_rsX = 0, g_rsY = 0, g_rsW = 0, g_rsH = 0;
bool      g_locked = false;
bool      g_origScroll = true;

//--- derived layout (see Layout())
double    g_scale = 1.0;
int       g_rowH = 18, g_titleH = 24, g_hdrH = 18, g_footH = 18, g_bodyTop = 42;
int       g_xType = 0, g_xLev = 0, g_xTier = 0, g_xSwap = 0, g_xComm = 0, g_xSpr = 0, g_xGr = 0, g_xEnd = 0, g_wPx = 0;
int       g_w = 0, g_h = 0;

//--- tooltip support (filled by Draw, used by the mouse handler)
string    g_hdr[8];                 // header texts per column
string    g_infoFull = "";          // title-bar info text (untruncated)
bool      g_infoCut = false;
int       g_infoX0 = 0;
string    g_footFull = "";          // bottom line (untruncated)
bool      g_footCut = false;
string    g_tip = "";               // tooltip currently set on the canvas object
int       g_colW[7];                // base column widths (Symbol,Type,Lev,Tiers,Swap,Comm,Spread)
bool      g_chartSpread = false;    // history column shows spread instead of leverage
int       g_colDrag = -1, g_cdX = 0, g_cdW = 0;

ulong     g_lastRec = 0, g_lastRef = 0;
datetime  g_lastUpd = 0;
long      g_accLev = 0;
int       g_recCount = 0;
int       g_errPrinted = 0;
string    g_file;

//+------------------------------------------------------------------+
//| Colour helpers: everything is opaque (canvas primitives do not   |
//| blend, a low alpha would make the chart show through)            |
//+------------------------------------------------------------------+
uint Op(const color c)
  {
   return ColorToARGB(c, 255);
  }

uint Mix(const color a, const color b, const double t)
  {
   int r1 = (int)(a & 0xFF), g1 = (int)((a >> 8) & 0xFF), b1 = (int)((a >> 16) & 0xFF);
   int r2 = (int)(b & 0xFF), g2 = (int)((b >> 8) & 0xFF), b2 = (int)((b >> 16) & 0xFF);
   int r = (int)MathRound(r1 + (r2 - r1) * t);
   int g = (int)MathRound(g1 + (g2 - g1) * t);
   int bl = (int)MathRound(b1 + (b2 - b1) * t);
   return ColorToARGB((color)(r | (g << 8) | (bl << 16)), 255);
  }

int Sc(const int x)
  {
   return (int)MathRound(x * g_scale);
  }

//+------------------------------------------------------------------+
//| Shorten text with "..." so it never exceeds maxW pixels          |
//| (uses the canvas' current font). cut = true if it was shortened. |
//+------------------------------------------------------------------+
string FitText(const string text, const int maxW, bool &cut)
  {
   cut = false;
   if(text == "") return "";
   if(maxW <= 0)
     {
      cut = true;
      return "";
     }
   if(g_canvas.TextWidth(text) <= maxW) return text;
   cut = true;
   const string ell = "...";
   if(g_canvas.TextWidth(ell) > maxW) return "";
   int lo = 0, hi = StringLen(text);          // largest n with text[0..n) + "..." fitting
   while(lo < hi)
     {
      int mid = (lo + hi + 1) / 2;
      if(g_canvas.TextWidth(StringSubstr(text, 0, mid) + ell) <= maxW) lo = mid;
      else hi = mid - 1;
     }
   string head = StringSubstr(text, 0, lo);
   StringTrimRight(head);
   return head + ell;
  }

//+------------------------------------------------------------------+
//| Symbol list                                                      |
//+------------------------------------------------------------------+
int FindSym(const string name)
  {
   for(int i = 0; i < ArraySize(g_sym); i++)
      if(g_sym[i] != NULL && g_sym[i].name == name)
         return i;
   return -1;
  }

void SyncSymbols()
  {
   int total = SymbolsTotal(true);
   CSymData *fresh[];
   ArrayResize(fresh, total);
   for(int i = 0; i < total; i++)
     {
      string nm = SymbolName(i, true);
      int idx = FindSym(nm);
      if(idx >= 0)
        {
         fresh[i] = g_sym[idx];
         g_sym[idx] = NULL;
        }
      else
        {
         fresh[i] = new CSymData();
         fresh[i].name = nm;
        }
     }
   for(int i = 0; i < ArraySize(g_sym); i++)
      if(g_sym[i] != NULL)
         delete g_sym[i];
   ArrayResize(g_sym, total);
   for(int i = 0; i < total; i++)
      g_sym[i] = fresh[i];
  }

//+------------------------------------------------------------------+
//| Headline leverage from the symbol specification                  |
//|   FOREX          lots*Contract/AccLeverage*Rate  -> AccLev/Rate  |
//|                  (SYMBOL_MARGIN_INITIAL is NOT used: many        |
//|                   brokers store the contract size there)         |
//|   FOREX_NO_LEV   lots*Contract*Rate              -> 1/Rate       |
//|   CFD / INDEX    lots*Contract*Price(*..)*Rate   -> 1/Rate       |
//|   CFDLEVERAGE    lots*Contract*Price/AccLev*Rate -> AccLev/Rate  |
//|   EXCH_STOCKS    lots*Contract*Price*Rate        -> 1/Rate       |
//|   FUTURES        lots*InitialMargin*Rate         -> Notional/Marg|
//+------------------------------------------------------------------+
string ModeTag(const long m)
  {
   switch((int)m)
     {
      case SYMBOL_CALC_MODE_FOREX:             return "FX";
      case SYMBOL_CALC_MODE_FOREX_NO_LEVERAGE: return "FX 1:1";
      case SYMBOL_CALC_MODE_CFD:               return "CFD";
      case SYMBOL_CALC_MODE_CFDINDEX:          return "INDEX";
      case SYMBOL_CALC_MODE_CFDLEVERAGE:       return "CFD-L";
      case SYMBOL_CALC_MODE_FUTURES:
      case SYMBOL_CALC_MODE_EXCH_FUTURES:
      case SYMBOL_CALC_MODE_EXCH_FUTURES_FORTS: return "FUT";
      case SYMBOL_CALC_MODE_EXCH_STOCKS:
      case SYMBOL_CALC_MODE_EXCH_STOCKS_MOEX:  return "STOCK";
     }
   return "?";
  }

double GetPrice(const string sym)
  {
   double p = SymbolInfoDouble(sym, SYMBOL_ASK);
   if(p <= 0) p = SymbolInfoDouble(sym, SYMBOL_BID);
   if(p <= 0) p = SymbolInfoDouble(sym, SYMBOL_LAST);
   return p;
  }

bool CalcLeverage(const string sym, double &lev, string &tag)
  {
   lev = 0;
   tag = "";
   long mode = 0;
   if(!SymbolInfoInteger(sym, SYMBOL_TRADE_CALC_MODE, mode))
      return false;
   tag = ModeTag(mode);

   double rateInit = 0, rateMaint = 0;
   if(!SymbolInfoMarginRate(sym, ORDER_TYPE_BUY, rateInit, rateMaint) || rateInit <= 0)
      return false;

   double accLev   = (double)AccountInfoInteger(ACCOUNT_LEVERAGE);
   double contract = SymbolInfoDouble(sym, SYMBOL_TRADE_CONTRACT_SIZE);
   double initial  = SymbolInfoDouble(sym, SYMBOL_MARGIN_INITIAL);

   switch((int)mode)
     {
      case SYMBOL_CALC_MODE_FOREX:
      case SYMBOL_CALC_MODE_CFDLEVERAGE:
         if(accLev > 0)
            lev = accLev / rateInit;
         break;

      case SYMBOL_CALC_MODE_FOREX_NO_LEVERAGE:
      case SYMBOL_CALC_MODE_CFD:
      case SYMBOL_CALC_MODE_CFDINDEX:
      case SYMBOL_CALC_MODE_EXCH_STOCKS:
      case SYMBOL_CALC_MODE_EXCH_STOCKS_MOEX:
         lev = 1.0 / rateInit;
         break;

      case SYMBOL_CALC_MODE_FUTURES:
      case SYMBOL_CALC_MODE_EXCH_FUTURES:
      case SYMBOL_CALC_MODE_EXCH_FUTURES_FORTS:
        {
         if(initial <= 0 || contract <= 0) return false;
         double price = GetPrice(sym);
         if(price <= 0) return false;
         double margin = initial * rateInit;
         string mc = SymbolInfoString(sym, SYMBOL_CURRENCY_MARGIN);
         string pc = SymbolInfoString(sym, SYMBOL_CURRENCY_PROFIT);
         string ac = AccountInfoString(ACCOUNT_CURRENCY);
         double notional = 0;
         if(mc == pc)
            notional = contract * price;
         else if(mc == ac)
           {
            double ts = SymbolInfoDouble(sym, SYMBOL_TRADE_TICK_SIZE);
            double tv = SymbolInfoDouble(sym, SYMBOL_TRADE_TICK_VALUE_PROFIT);
            if(ts <= 0 || tv <= 0) return false;
            notional = price * tv / ts;
           }
         else
            return false;
         lev = notional / margin;
         break;
        }

      default:
         return false;
     }
   return (lev > 0);
  }

//+------------------------------------------------------------------+
//| Tier detection (floating margin rates)                           |
//| The symbol specification holds a rate table by volume/notional;  |
//| MQL5 has no call that returns the table itself, so the terminal  |
//| margin engine (OrderCalcMargin, which applies that same table) is|
//| sampled at growing volumes. The marginal margin per lot of each  |
//| tier, compared with tier 1, gives that tier's leverage.          |
//+------------------------------------------------------------------+
bool MarginOf(const string sym, const double vol, const double price, double &m)
  {
   m = 0;
   ResetLastError();
   return (OrderCalcMargin(ORDER_TYPE_BUY, sym, vol, price, m) && m > 0);
  }

void AddTier(CSymData *s, const double from, const double lev)
  {
   int n = ArraySize(s.tLots);
   ArrayResize(s.tLots, n + 1);
   ArrayResize(s.tLev, n + 1);
   s.tLots[n] = from;
   s.tLev[n] = lev;
  }

double StepVol(const double v, const double step, const double vmax)
  {
   double r = MathRound(v / step) * step;
   return MathMin(vmax, MathMax(step, r));
  }

void ProbeTiers(CSymData *s)
  {
   ArrayResize(s.tLots, 0);
   ArrayResize(s.tLev, 0);
   s.why = "";
   if(s.cur <= 0) { s.why = "no leverage value"; return; }

   string sym = s.name;
   double vmin  = SymbolInfoDouble(sym, SYMBOL_VOLUME_MIN);
   double vmax  = SymbolInfoDouble(sym, SYMBOL_VOLUME_MAX);
   double vstep = SymbolInfoDouble(sym, SYMBOL_VOLUME_STEP);
   if(vmin <= 0 || vmax <= 0) { s.why = "no volume limits in specification"; return; }
   if(vstep <= 0) vstep = vmin;
   double price = GetPrice(sym);
   if(price <= 0) { s.why = "no price yet"; return; }

   double v0 = MathMax(vmin, MathMin(1.0, vmax));
   double m0 = 0;
   if(!MarginOf(sym, v0, price, m0))
     {
      int e = GetLastError();
      s.why = StringFormat("OrderCalcMargin failed (error %d)", e);
      if(g_errPrinted < 5)
        {
         g_errPrinted++;
         PrintFormat("LeverageMonitor: %s - %s", sym, s.why);
        }
      return;
     }
   double ref = m0 / v0;                       // tier-1 margin per lot

   AddTier(s, 0.0, s.cur);
   double lineV = 0, lineM = 0, lineS = ref;   // M(V) = lineM + lineS*(V-lineV)
   double v = v0;

   for(int guard = 0; guard < 120 && v < vmax; guard++)
     {
      double nv = StepVol(v * 1.3, vstep, vmax);
      if(nv <= v) nv = MathMin(vmax, v + vstep);
      if(nv <= v) break;
      double m = 0;
      if(!MarginOf(sym, nv, price, m)) break;

      double line = lineM + lineS * (nv - lineV);
      double tol  = 0.05 + 1e-4 * line;
      if(MathAbs(m - line) > tol)
        {
         // a tier boundary lies between v and nv: bisect
         double lo = v, hi = nv;
         for(int it = 0; it < 30 && (hi - lo) > vstep * 0.5; it++)
           {
            double mid = 0.5 * (lo + hi);
            double mm = 0;
            if(!MarginOf(sym, mid, price, mm)) break;
            if(MathAbs(mm - (lineM + lineS * (mid - lineV))) > tol) hi = mid;
            else lo = mid;
           }
         double d = MathMax(vstep, hi * 0.01);
         double mh = 0, mh2 = 0;
         if(!MarginOf(sym, hi, price, mh) || !MarginOf(sym, hi + d, price, mh2)) break;
         double ns = (mh2 - mh) / d;             // marginal margin per lot in the new tier
         if(ns <= 0 || ArraySize(s.tLev) >= 8) break;
         AddTier(s, hi, s.cur / (ns / ref));
         lineV = hi;
         lineM = mh;
         lineS = ns;
         v = hi + d;
         continue;
        }
      v = nv;
     }
  }

//--- schedule: a few symbols per second, re-scanned every InpTierRefresh seconds
bool ProbeSome()
  {
   ulong now = GetTickCount64();
   int done = 0;
   for(int i = 0; i < ArraySize(g_sym) && done < InpProbePerSec; i++)
     {
      CSymData *s = g_sym[i];
      if(s.cur <= 0) continue;
      if(!SymbolIsSynchronized(s.name)) continue;
      if(s.probeAt != 0 && now - s.probeAt < (ulong)InpTierRefresh * 1000 &&
         MathAbs(s.cur - s.probeCur) <= 0.25 * s.probeCur) continue;
      ProbeTiers(s);
      s.probeAt = now;
      s.probeCur = s.cur;
      done++;
     }
   return (done > 0);
  }

//+------------------------------------------------------------------+
//| Spread (points), 1 h average from 60 one-minute buckets          |
//+------------------------------------------------------------------+
double SpreadPts(const string sym)
  {
   double bid = SymbolInfoDouble(sym, SYMBOL_BID);
   double ask = SymbolInfoDouble(sym, SYMBOL_ASK);
   double pt  = SymbolInfoDouble(sym, SYMBOL_POINT);
   if(bid > 0 && ask > 0 && pt > 0 && ask >= bid)
      return (ask - bid) / pt;
   long sp = SymbolInfoInteger(sym, SYMBOL_SPREAD);
   if(sp > 0) return (double)sp;
   return -1;
  }

void SampleSpreads()                       // called every second
  {
   long minId = (long)TimeLocal() / 60;
   int  idx = (int)(minId % 60);
   for(int i = 0; i < ArraySize(g_sym); i++)
     {
      CSymData *s = g_sym[i];
      if(s == NULL) continue;
      double sp = SpreadPts(s.name);
      s.spr = sp;
      if(sp < 0) continue;
      s.recSum += sp;
      s.recCnt++;
      if(s.bMin[idx] != minId)
        {
         s.bMin[idx] = minId;
         s.bSum[idx] = 0;
         s.bCnt[idx] = 0;
        }
      s.bSum[idx] += sp;
      s.bCnt[idx]++;
     }
  }

void SpreadStats(CSymData *s)
  {
   long minId = (long)TimeLocal() / 60;
   double sum = 0;
   int cnt = 0, mins = 0;
   for(int i = 0; i < 60; i++)
      if(s.bMin[i] >= 0 && minId - s.bMin[i] < 60 && s.bCnt[i] > 0)
        {
         sum += s.bSum[i];
         cnt += s.bCnt[i];
         mins++;
        }
   s.sprCnt = cnt;
   s.sprMin = mins;
   s.sprAvg = (cnt > 0) ? sum / cnt : -1;
  }

//--- defined in the formatting section (reads the commission rules of a symbol)
void ReadCommission(CSymData *s);

//+------------------------------------------------------------------+
void AddPoint(CSymData *s, const datetime now)
  {
   int n = ArraySize(s.v);
   ArrayResize(s.v, n + 1);
   ArrayResize(s.t, n + 1);
   s.v[n] = s.cur;
   s.t[n] = now;
   if(n + 1 > InpMaxPoints)
     {
      int cut = n + 1 - InpMaxPoints;
      ArrayRemove(s.v, 0, cut);
      ArrayRemove(s.t, 0, cut);
     }
  }

void AddSprPoint(CSymData *s, const datetime now)
  {
   if(s.recCnt <= 0) return;
   double val = s.recSum / s.recCnt;
   s.recSum = 0;
   s.recCnt = 0;
   int n = ArraySize(s.sv);
   ArrayResize(s.sv, n + 1);
   ArrayResize(s.sT, n + 1);
   s.sv[n] = val;
   s.sT[n] = now;
   if(n + 1 > InpMaxPoints)
     {
      int cut = n + 1 - InpMaxPoints;
      ArrayRemove(s.sv, 0, cut);
      ArrayRemove(s.sT, 0, cut);
     }
  }

void UpdateAll(const bool record)
  {
   datetime now = TimeLocal();
   g_lastUpd = now;

   long al = AccountInfoInteger(ACCOUNT_LEVERAGE);
   bool accChanged = (al != g_accLev);
   g_accLev = al;

   for(int i = 0; i < ArraySize(g_sym); i++)
     {
      CSymData *s = g_sym[i];
      double lv = 0;
      string tg = "";
      if(CalcLeverage(s.name, lv, tg))
         s.cur = lv;
      else
         s.cur = 0;
      s.tag = tg;
      if(accChanged) s.probeAt = 0;
      if(record && s.cur > 0 && SymbolIsSynchronized(s.name))
         AddPoint(s, now);
      if(record)
         AddSprPoint(s, now);

      s.swapL    = SymbolInfoDouble(s.name, SYMBOL_SWAP_LONG);
      s.swapS    = SymbolInfoDouble(s.name, SYMBOL_SWAP_SHORT);
      s.swapMode = SymbolInfoInteger(s.name, SYMBOL_SWAP_MODE);
      s.swap3    = SymbolInfoInteger(s.name, SYMBOL_SWAP_ROLLOVER3DAYS);
      s.swapOk   = true;
      SpreadStats(s);
      ReadCommission(s);
     }
  }

bool RetryFailed()
  {
   bool changed = false;
   datetime now = TimeLocal();
   for(int i = 0; i < ArraySize(g_sym); i++)
     {
      CSymData *s = g_sym[i];
      if(s.cur > 0) continue;
      double lv = 0;
      string tg = "";
      if(CalcLeverage(s.name, lv, tg))
        {
         s.cur = lv;
         s.tag = tg;
         if(ArraySize(s.v) == 0 && SymbolIsSynchronized(s.name)) AddPoint(s, now);
         changed = true;
        }
     }
   return changed;
  }

//+------------------------------------------------------------------+
//| Formatting                                                       |
//+------------------------------------------------------------------+
string FmtNum(const double x)
  {
   if(x <= 0) return "n/a";
   if(MathAbs(x - MathRound(x)) < 0.05) return DoubleToString(MathRound(x), 0);
   return DoubleToString(x, 1);
  }

string FmtLots(const double x)
  {
   if(x >= 1000) return DoubleToString(x, 0);
   if(x >= 10)   return DoubleToString(x, 1);
   return DoubleToString(x, 2);
  }

string TierChain(CSymData *s)
  {
   int n = ArraySize(s.tLev);
   if(s.cur <= 0) return "-";
   if(s.probeAt == 0) return "...";
   if(n == 0) return "n/a";
   if(n == 1) return "single tier";
   string r = "";
   for(int k = 0; k < n; k++)
      r += (k > 0 ? " > " : "") + FmtNum(s.tLev[k]);
   return r;
  }

string TierDetail(CSymData *s)
  {
   int n = ArraySize(s.tLev);
   if(s.cur <= 0) return s.name + ":  leverage not available";
   if(s.probeAt == 0) return s.name + ":  scanning margin tiers...";
   if(n == 0) return s.name + ":  margin tiers could not be read - " + s.why;
   if(n == 1) return s.name + ":  1:" + FmtNum(s.tLev[0]) + " at any volume (no floating margin rates)";
   string r = s.name + ":  ";
   for(int k = 0; k < n; k++)
     {
      if(k > 0) r += "   ";
      r += "1:" + FmtNum(s.tLev[k]);
      if(k < n - 1)
         r += " up to " + FmtLots(s.tLots[k + 1]) + " lots";
      else
         r += " above";
     }
   return r;
  }

//--- number without trailing zeros ("12.50" -> "12.5", "7.00" -> "7")
string TrimNum(const double x, const int dec)
  {
   string r = DoubleToString(x, dec);
   if(StringFind(r, ".") >= 0)
     {
      int n = StringLen(r);
      while(n > 0 && StringGetCharacter(r, n - 1) == '0') n--;
      if(n > 0 && StringGetCharacter(r, n - 1) == '.') n--;
      r = StringSubstr(r, 0, n);
     }
   if(r == "-0" || r == "") r = "0";
   return r;
  }

string FmtSigned(const double x)
  {
   string r = TrimNum(x, 2);
   if(x > 0 && r != "0") r = "+" + r;
   return r;
  }

string SwapModeName(const long m)
  {
   switch((int)m)
     {
      case 0: return "disabled";
      case 1: return "in points";
      case 2: return "in base currency of the symbol";
      case 3: return "in margin currency";
      case 4: return "in deposit currency";
      case 5: return "as annual interest (% of current price)";
      case 6: return "as annual interest (% of open price)";
      case 7: return "in points (position reopened at current price)";
      case 8: return "in points (position reopened at Bid price)";
     }
   return "swap mode " + IntegerToString(m);
  }

string DayName(const long d)
  {
   string n[] = {"Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"};
   if(d < 0 || d > 6) return "-";
   return n[(int)d];
  }

string SwapText(CSymData *s)
  {
   if(!s.swapOk) return "-";
   if(s.swapMode == 0) return "none";
   string u = (s.swapMode == 5 || s.swapMode == 6) ? "%" : "";
   return FmtSigned(s.swapL) + u + " / " + FmtSigned(s.swapS) + u;
  }

//+------------------------------------------------------------------+
//| Commission rules from the symbol specification                   |
//+------------------------------------------------------------------+
string CommCurrency(const int mode, const string tierCur, const string ruleCur, const string sym)
  {
   switch(mode)
     {
      case SYMBOL_COMMISSION_MONEY_DEPOSIT:       return AccountInfoString(ACCOUNT_CURRENCY);
      case SYMBOL_COMMISSION_MONEY_SYMBOL_BASE:   return SymbolInfoString(sym, SYMBOL_CURRENCY_BASE);
      case SYMBOL_COMMISSION_MONEY_SYMBOL_PROFIT: return SymbolInfoString(sym, SYMBOL_CURRENCY_PROFIT);
      case SYMBOL_COMMISSION_MONEY_SYMBOL_MARGIN: return SymbolInfoString(sym, SYMBOL_CURRENCY_MARGIN);
      case SYMBOL_COMMISSION_MONEY_SPECIFIED:     return (tierCur != "" ? tierCur : ruleCur);
     }
   return "";
  }

//--- one tier as text, e.g. "3.5/lot", "0.0035%", "2 pts/deal" (full = always name the currency)
string CommTierText(const MqlCommissionTier &t, const string ruleCur, const string sym, const bool full)
  {
   int m = (int)t.mode;
   string v = TrimNum(t.value, 5);
   if(m == SYMBOL_COMMISSION_PERCENT)
      return v + "%";
   if(m == SYMBOL_COMMISSION_PERCENT_PROFIT)
      return v + "% of profit";
   if(m == SYMBOL_COMMISSION_PIPS)
      v += " pts";
   else
     {
      string c = CommCurrency(m, t.currency, ruleCur, sym);
      if(c != "" && (full || m != SYMBOL_COMMISSION_MONEY_DEPOSIT))
         v += " " + c;
     }
   switch((int)t.volume_type)
     {
      case SYMBOL_COMMISSION_VOLUME_TYPE_TRADE:    v += "/deal"; break;
      case SYMBOL_COMMISSION_VOLUME_TYPE_VOLUME:   v += "/lot"; break;
      case SYMBOL_COMMISSION_VOLUME_TYPE_TURNOVER: v += "/turnover"; break;
     }
   return v;
  }

string CommRangeUnit(const int mr)
  {
   switch(mr)
     {
      case SYMBOL_COMMISSION_RANGE_VOLUME:          return " lots";
      case SYMBOL_COMMISSION_RANGE_TURNOVER_MONEY:  return " (money turnover)";
      case SYMBOL_COMMISSION_RANGE_TURNOVER_VOLUME: return " lots (turnover)";
      case SYMBOL_COMMISSION_RANGE_VALUE:           return " (trade value)";
      case SYMBOL_COMMISSION_RANGE_PROFIT:          return " (profit)";
     }
   return "";
  }

string CommRuleText(const MqlCommission &r)
  {
   string e = "";
   switch((int)r.mode_entry)
     {
      case SYMBOL_COMMISSION_ENTRY_INOUT: e = "on entry and exit"; break;
      case SYMBOL_COMMISSION_ENTRY_IN:    e = "on entry"; break;
      case SYMBOL_COMMISSION_ENTRY_OUT:   e = "on exit"; break;
     }
   string d = "";
   switch((int)r.mode_direction)
     {
      case SYMBOL_COMMISSION_DIRECTION_BOTH: d = "buy and sell"; break;
      case SYMBOL_COMMISSION_DIRECTION_BUY:  d = "buy only"; break;
      case SYMBOL_COMMISSION_DIRECTION_SELL: d = "sell only"; break;
     }
   string c = "";
   switch((int)r.mode_charge)
     {
      case SYMBOL_COMMISSION_CHARGE_INSTANT: c = "charged instantly"; break;
      case SYMBOL_COMMISSION_CHARGE_DAILY:   c = "charged at end of day"; break;
      case SYMBOL_COMMISSION_CHARGE_MONTHLY: c = "charged at end of month"; break;
     }
   string p = "";
   if((int)r.mode_profit == SYMBOL_COMMISSION_PROFIT_PROFIT) p = ", profitable trades only";
   if((int)r.mode_profit == SYMBOL_COMMISSION_PROFIT_LOSS)   p = ", losing trades only";
   return e + ", " + d + ", " + c + p;
  }

void ReadCommission(CSymData *s)
  {
   MqlCommission rules[];
   ResetLastError();
   int n = SymbolInfoCommissions(s.name, rules);
   if(n < 0)
     {
      s.commTxt = "n/a";
      s.commTip = s.name + " - commission\nNot available (SymbolInfoCommissions error " + IntegerToString(GetLastError()) + ").";
      return;
     }

   string head = "";
   string tip = s.name + " - commission (symbol specification)\n";
   bool multi = false;
   int active = 0;
   for(int i = 0; i < n; i++)
     {
      int nt = ArraySize(rules[i].tiers);
      int first = -1;
      for(int j = 0; j < nt; j++)
         if((int)rules[i].tiers[j].mode != SYMBOL_COMMISSION_DISABLED)
           {
            first = j;
            break;
           }
      if(first < 0) continue;
      active++;
      if(head != "") head += " + ";
      head += CommTierText(rules[i].tiers[first], rules[i].currency, s.name, false);

      tip += "\nRule " + IntegerToString(active) + ": " + CommRuleText(rules[i]) + "\n";
      int shown = 0;
      for(int j = 0; j < nt; j++)
        {
         MqlCommissionTier t = rules[i].tiers[j];
         if((int)t.mode == SYMBOL_COMMISSION_DISABLED) continue;
         shown++;
         string line = "  ";
         bool hasTo = (t.range_to > 0 && t.range_to < 1e15);
         if(t.range_from > 0 || hasTo)
            line += TrimNum(t.range_from, 2) + (hasTo ? " - " + TrimNum(t.range_to, 2) : "+") +
                    CommRangeUnit((int)rules[i].mode_range) + ":  ";
         line += CommTierText(t, rules[i].currency, s.name, true);
         if(t.min_value > 0) line += "   min " + TrimNum(t.min_value, 4);
         if(t.max_value > 0) line += "   max " + TrimNum(t.max_value, 4);
         tip += line + "\n";
        }
      if(shown > 1) multi = true;
     }

   if(active == 0)
     {
      s.commTxt = "none";
      s.commTip = s.name + " - commission\nNo commission is charged on this symbol.";
      return;
     }
   s.commTxt = head + (multi ? "*" : "");
   if(multi) tip += "\n* = several tiers; the column shows the first one.";
   StringTrimRight(tip);
   s.commTip = tip;
  }

string CommText(CSymData *s)
  {
   return s.commTxt;
  }

string SprText(CSymData *s)
  {
   if(s.spr < 0) return "n/a";
   string a = (s.sprAvg >= 0) ? TrimNum(s.sprAvg, 1) : "-";
   return TrimNum(s.spr, 1) + " / " + a;
  }

//--- full text of a body cell (columns 0..6; 7 = history chart)
string CellFull(CSymData *s, const int col)
  {
   switch(col)
     {
      case 0: return s.name;
      case 1: return (s.tag == "" ? "-" : s.tag);
      case 2: return (s.cur > 0 ? "1:" + FmtNum(s.cur) : "n/a");
      case 3: return TierChain(s);
      case 4: return SwapText(s);
      case 5: return CommText(s);
      case 6: return SprText(s);
     }
   return "";
  }

string SwapTip(CSymData *s)
  {
   if(!s.swapOk) return "";
   string r = s.name + " - swap per lot per night\n";
   if(s.swapMode == 0) return r + "Swap is disabled for this symbol.";
   r += "Long:   " + FmtSigned(s.swapL) + "\n";
   r += "Short:  " + FmtSigned(s.swapS) + "\n";
   r += "Charged " + SwapModeName(s.swapMode) + "\n";
   r += "Triple swap on " + DayName(s.swap3);
   return r;
  }

string CommTip(CSymData *s)
  {
   return s.commTip;
  }

string SprTip(CSymData *s)
  {
   if(s.spr < 0) return s.name + " - spread\nNo quote available.";
   string r = s.name + " - spread (points)\n";
   r += "Current: " + TrimNum(s.spr, 1) + "\n";
   if(s.sprAvg >= 0)
      r += "Average, last hour: " + TrimNum(s.sprAvg, 1) + "  (" + IntegerToString(s.sprCnt) +
           " samples, " + IntegerToString(s.sprMin) + " min of data)";
   else
      r += "Average, last hour: collecting...";
   return r;
  }

string HistTip(CSymData *s)
  {
   if(g_chartSpread)
     {
      int m = ArraySize(s.sv);
      if(m < 1) return s.name + ": no spread history yet (1 point per " + IntegerToString(InpRecordSec) + " s)";
      double mn = s.sv[0], mx = s.sv[0], sum = 0;
      for(int i = 0; i < m; i++)
        {
         mn = MathMin(mn, s.sv[i]);
         mx = MathMax(mx, s.sv[i]);
         sum += s.sv[i];
        }
      string rs = s.name + " - spread history (points)\n" + IntegerToString(m) + " points since this EA was attached\n";
      rs += TimeToString(s.sT[0], TIME_DATE | TIME_MINUTES) + "  to  " + TimeToString(s.sT[m - 1], TIME_DATE | TIME_MINUTES) + "\n";
      rs += "Min " + TrimNum(mn, 1) + "     Avg " + TrimNum(sum / m, 1) + "     Max " + TrimNum(mx, 1);
      return rs;
     }
   int n = ArraySize(s.v);
   if(n < 1) return s.name + ": no leverage history yet";
   double mn2 = s.v[ArrayMinimum(s.v)];
   double mx2 = s.v[ArrayMaximum(s.v)];
   string r = s.name + " - leverage history\n" + IntegerToString(n) + " points\n";
   r += TimeToString(s.t[0], TIME_DATE | TIME_MINUTES) + "  to  " + TimeToString(s.t[n - 1], TIME_DATE | TIME_MINUTES) + "\n";
   r += "Min 1:" + FmtNum(mn2) + "     Max 1:" + FmtNum(mx2);
   return r;
  }

//+------------------------------------------------------------------+
//| Sorting                                                          |
//+------------------------------------------------------------------+
bool Before(const int a, const int b)
  {
   if(g_sort == 1)
      return StringCompare(g_sym[a].name, g_sym[b].name) < 0;
   double la = g_sym[a].cur, lb = g_sym[b].cur;
   if(la != lb) return la > lb;
   return StringCompare(g_sym[a].name, g_sym[b].name) < 0;
  }

void BuildOrder()
  {
   int n = ArraySize(g_sym);
   ArrayResize(g_order, n);
   for(int i = 0; i < n; i++) g_order[i] = i;
   if(g_sort == 0) return;
   for(int i = 1; i < n; i++)
     {
      int key = g_order[i];
      int j = i - 1;
      while(j >= 0 && Before(key, g_order[j]))
        {
         g_order[j + 1] = g_order[j];
         j--;
        }
      g_order[j + 1] = key;
     }
  }

//+------------------------------------------------------------------+
//| Layout / zoom                                                    |
//+------------------------------------------------------------------+
void Layout()
  {
   g_scale  = (double)g_font / (double)MathMax(1, InpFontSize);
   g_rowH   = MathMax(12, Sc(InpRowHeight));
   g_titleH = g_rowH + 6;
   g_hdrH   = g_rowH;
   g_footH  = g_rowH;
   g_bodyTop = g_titleH + g_hdrH;

   g_xType = Sc(g_colW[0]);
   g_xLev  = g_xType + Sc(g_colW[1]);
   g_xTier = g_xLev + Sc(g_colW[2]);
   g_xSwap = g_xTier + Sc(g_colW[3]);
   g_xComm = g_xSwap + Sc(g_colW[4]);
   g_xSpr  = g_xComm + Sc(g_colW[5]);
   g_xGr   = g_xSpr + Sc(g_colW[6]);
   g_xEnd  = g_xGr + Sc(g_graphBase);
   g_wPx   = g_xEnd + 9;                       // 9 px gutter for the scrollbar
  }

int VisibleRows(const int total)
  {
   int rows;
   if(g_rowsSet > 0)
      rows = g_rowsSet;
   else
     {
      int ch = (int)ChartGetInteger(0, CHART_HEIGHT_IN_PIXELS, 0);
      rows = (ch - InpCornerY - g_bodyTop - g_footH - 8) / g_rowH;
     }
   rows = MathMax(1, rows);
   return MathMin(rows, MathMax(1, total));
  }

//+------------------------------------------------------------------+
//| Column geometry, truncated cell drawing, tooltips                |
//+------------------------------------------------------------------+
int ColAt(const int px)
  {
   if(px < g_xType) return 0;
   if(px < g_xLev)  return 1;
   if(px < g_xTier) return 2;
   if(px < g_xSwap) return 3;
   if(px < g_xComm) return 4;
   if(px < g_xSpr)  return 5;
   if(px < g_xGr)   return 6;
   return 7;
  }

void ColSpan(const int col, int &x0, int &x1)
  {
   int e[9];
   e[0] = 0;       e[1] = g_xType; e[2] = g_xLev;  e[3] = g_xTier; e[4] = g_xSwap;
   e[5] = g_xComm; e[6] = g_xSpr;  e[7] = g_xGr;   e[8] = g_xEnd;
   int c = MathMax(0, MathMin(7, col));
   x0 = e[c];
   x1 = e[c + 1];
  }

//--- column separator under the pointer (index of the column to its left), -1 = none
int SepAt(const int px)
  {
   for(int c = 0; c < 7; c++)
     {
      int x0, x1;
      ColSpan(c, x0, x1);
      if(MathAbs(px - x1) <= 4) return c;
     }
   return -1;
  }

//--- anchor x, max text width and alignment of a column's text
void CellGeom(const int col, int &ax, int &maxW, uint &align)
  {
   int x0, x1;
   ColSpan(col, x0, x1);
   if(col == 1)
     {
      ax = (x0 + x1) / 2;
      maxW = x1 - x0 - 8;
      align = TA_CENTER | TA_VCENTER;
     }
   else if(col == 2)
     {
      ax = x1 - 8;
      maxW = x1 - x0 - 16;
      align = TA_RIGHT | TA_VCENTER;
     }
   else
     {
      ax = x0 + 8;
      maxW = x1 - x0 - 16;
      align = TA_LEFT | TA_VCENTER;
     }
  }

//--- text that is shortened with "..." instead of running into the next column
void DrawCell(const int col, const int cy, const string text, const uint clr)
  {
   int ax, mw;
   uint al;
   CellGeom(col, ax, mw, al);
   bool cut;
   string t = FitText(text, mw, cut);
   g_canvas.TextOut(ax, cy, t, clr, al);
  }

bool IsCut(const string text, const int col)
  {
   int ax, mw;
   uint al;
   CellGeom(col, ax, mw, al);
   return g_canvas.TextWidth(text) > mw;
  }

string HdrTip(const int col)
  {
   string base = g_hdr[col];
   bool cut = IsCut(base, col);
   string extra = "";
   switch(col)
     {
      case 4: extra = "Overnight swap per lot for a long / short position.\nThe unit depends on the symbol's swap mode (hover a cell)."; break;
      case 5: extra = "Commission rule from the symbol specification (per charge: entry and/or exit).\n* = several tiers. Hover a cell for the full rules."; break;
      case 6: extra = "Spread in points: current value / average of the last hour."; break;
     }
   if(extra != "")
      return (cut ? base + "\n\n" : "") + extra;
   return cut ? base : "";
  }

string CellTip(CSymData *s, const int col)
  {
   switch(col)
     {
      case 3: return IsCut(CellFull(s, 3), 3) ? TierDetail(s) : "";
      case 4: return SwapTip(s);
      case 5: return CommTip(s);
      case 6: return SprTip(s);
      case 7: return HistTip(s);
     }
   string t = CellFull(s, col);
   return IsCut(t, col) ? t : "";
  }

string TipAt(const int px, const int py)
  {
   if(px < 0 || px >= g_w || py < 0 || py >= g_h) return "";
   if(py < g_titleH)
     {
      if(px >= g_w - 24) return g_collapsed ? "Expand panel" : "Collapse panel";
      if(px >= g_w - 116 && px < g_w - 82)
         return g_chartSpread ? "History chart shows spread - click to show leverage"
                              : "History chart shows leverage - click to show spread";
      if(px >= g_w - 50 && px < g_w - 28) return "Zoom in (larger text)";
      if(px >= g_w - 76 && px < g_w - 54) return "Zoom out (smaller text)";
      if(g_infoCut && px >= g_infoX0 && px < g_w - 122) return g_infoFull;
      return "";
     }
   if(g_collapsed) return "";

   int total = ArraySize(g_sym);
   int rows = VisibleRows(total);
   int yb = g_bodyTop + rows * g_rowH;
   if(py < yb && SepAt(px) >= 0) return "Drag to change the column width";
   int col = ColAt(px);
   if(py < g_bodyTop) return HdrTip(col);
   if(py >= yb)
     {
      if(px >= g_w - 16 && py >= g_h - 16) return "Drag to resize";
      return g_footCut ? g_footFull : "";
     }
   int pos = g_scroll + (py - g_bodyTop) / g_rowH;
   if(pos < 0 || pos >= total || pos >= ArraySize(g_order)) return "";
   int gi = g_order[pos];
   if(gi < 0 || gi >= total || g_sym[gi] == NULL) return "";
   return CellTip(g_sym[gi], col);
  }

void SetTip(const string tip)
  {
   string t = (tip == "") ? "\n" : tip;      // "\n" switches the tooltip off
   if(t == g_tip) return;
   g_tip = t;
   ObjectSetString(0, g_obj, OBJPROP_TOOLTIP, t);
   ChartRedraw(0);
  }

void SaveGui()
  {
   GlobalVariableSet("LevMon_font", g_font);
   GlobalVariableSet("LevMon_graph", g_graphBase);
   GlobalVariableSet("LevMon_rows", g_rowsSet);
   GlobalVariableSet("LevMon_sort", g_sort);
   GlobalVariableSet("LevMon_spr", g_chartSpread ? 1 : 0);
   for(int i = 0; i < 7; i++)
      GlobalVariableSet("LevMon_cw" + IntegerToString(i), g_colW[i]);
  }

void LoadGui()
  {
   if(GlobalVariableCheck("LevMon_font"))  g_font = (int)GlobalVariableGet("LevMon_font");
   if(GlobalVariableCheck("LevMon_graph")) g_graphBase = (int)GlobalVariableGet("LevMon_graph");
   if(GlobalVariableCheck("LevMon_rows"))  g_rowsSet = (int)GlobalVariableGet("LevMon_rows");
   if(GlobalVariableCheck("LevMon_sort"))  g_sort = (int)GlobalVariableGet("LevMon_sort");
   if(GlobalVariableCheck("LevMon_spr"))   g_chartSpread = (GlobalVariableGet("LevMon_spr") > 0.5);
   for(int i = 0; i < 7; i++)
     {
      string key = "LevMon_cw" + IntegerToString(i);
      if(GlobalVariableCheck(key)) g_colW[i] = (int)GlobalVariableGet(key);
      g_colW[i] = MathMax(30, MathMin(600, g_colW[i]));
     }
   g_font = MathMax(6, MathMin(18, g_font));
   g_graphBase = MathMax(80, MathMin(1200, g_graphBase));
   g_rowsSet = MathMax(0, g_rowsSet);
   if(g_sort < 0 || g_sort > 2) g_sort = 0;
  }

void LockChart(const bool lock)
  {
   if(lock == g_locked) return;
   g_locked = lock;
   ChartSetInteger(0, CHART_MOUSE_SCROLL, lock ? false : g_origScroll);
  }

//+------------------------------------------------------------------+
//| Rendering                                                        |
//+------------------------------------------------------------------+
void DrawSpark(const double &v[], const bool invert, const int x0, const int y0,
               const int w, const int h, const uint cBack)
  {
   g_canvas.FillRectangle(x0, y0, x0 + w - 1, y0 + h - 1, cBack);
   int n = ArraySize(v);
   if(n < 1) return;

   double mn = v[ArrayMinimum(v)];
   double mx = v[ArrayMaximum(v)];
   double rng = mx - mn;
   int pad = 3;
   int gw = w - 2 * pad, gh = h - 2 * pad;
   int pts = MathMin(n, gw);

   color cUp = invert ? InpDownColor : InpUpColor;     // for spread a rise is bad
   color cDn = invert ? InpUpColor : InpDownColor;
   color lc = InpAccentColor;
   if(v[n - 1] > v[0] + 1e-9)      lc = cUp;
   else if(v[n - 1] < v[0] - 1e-9) lc = cDn;
   uint col = Op(lc);

   int pxPrev = 0, pyPrev = 0, px = 0, py = 0;
   for(int k = 0; k < pts; k++)
     {
      int idx = (pts == 1) ? n - 1 : (int)MathRound((double)k * (n - 1) / (pts - 1));
      double val = v[idx];
      px = x0 + pad + ((pts == 1) ? gw - 1 : (int)MathRound((double)k * (gw - 1) / (pts - 1)));
      py = (rng <= 0) ? y0 + h / 2 : y0 + pad + (int)MathRound((mx - val) / rng * (gh - 1));
      if(k > 0)
        {
         g_canvas.Line(pxPrev, pyPrev, px, pyPrev, col);
         g_canvas.Line(px, pyPrev, px, py, col);
        }
      pxPrev = px;
      pyPrev = py;
     }
   g_canvas.FillCircle(px, py, 2, col);
  }

void DrawButton(const int x, const int y, const int w, const int h, const string txt,
                const uint cFill, const uint cBord, const uint cTxt)
  {
   g_canvas.FillRectangle(x, y, x + w - 1, y + h - 1, cFill);
   g_canvas.Rectangle(x, y, x + w - 1, y + h - 1, cBord);
   g_canvas.TextOut(x + w / 2, y + h / 2, txt, cTxt, TA_CENTER | TA_VCENTER);
  }

void Draw()
  {
   Layout();
   int total = ArraySize(g_sym);
   BuildOrder();
   int rows = VisibleRows(total);
   g_scroll = MathMax(0, MathMin(g_scroll, MathMax(0, total - rows)));

   int w = g_wPx;
   int h = g_collapsed ? g_titleH : g_bodyTop + rows * g_rowH + g_footH + 2;
   if(w != g_w || h != g_h)
     {
      g_canvas.Resize(w, h);
      g_w = w;
      g_h = h;
     }

   uint cBg    = Op(InpBgColor);
   uint cBord  = Op(InpBorderColor);
   uint cText  = Op(InpTextColor);
   uint cDim   = Op(InpDimColor);
   uint cFoot  = Op(InpFootColor);
   uint cTitle = Op(InpTitleColor);
   uint cHdr   = Op(InpHeaderColor);
   uint cAlt   = Mix(InpBgColor, clrWhite, 0.045);
   uint cHov   = Mix(InpBgColor, InpAccentColor, 0.22);
   uint cSpk   = Mix(InpBgColor, clrBlack, 0.40);
   uint cSep   = Mix(InpBgColor, InpBorderColor, 0.70);
   uint cTrack = Mix(InpBgColor, clrWhite, 0.10);

   g_footFull = "";
   g_footCut = false;

   g_canvas.Erase(cBg);
   g_canvas.FontSet("Segoe UI", -g_font * 10);

   //--- title bar
   g_canvas.FillRectangle(0, 0, w - 1, g_titleH - 1, cTitle);
   g_canvas.FontSet("Segoe UI", -g_font * 10, FW_BOLD);
   string ttl = "LEVERAGE MONITOR";
   g_canvas.TextOut(8, g_titleH / 2, ttl, cText, TA_LEFT | TA_VCENTER);
   int ttlW = g_canvas.TextWidth(ttl);
   g_canvas.FontSet("Segoe UI", -g_font * 10);

   g_infoX0 = 8 + ttlW + 14;
   g_infoFull = StringFormat("Account 1:%d   |   %d symbols   |   %s",
                             (int)g_accLev, total, TimeToString(g_lastUpd, TIME_SECONDS));
   string info = FitText(g_infoFull, (w - 122) - g_infoX0, g_infoCut);
   int by = 3, bh = g_titleH - 6;
   g_canvas.TextOut(w - 122, g_titleH / 2, info, cDim, TA_RIGHT | TA_VCENTER);
   DrawButton(w - 116, by, 34, bh, g_chartSpread ? "Spr" : "Lev", cHdr, cBord, cText);   // chart mode
   DrawButton(w - 76, by, 22, bh, "A-", cHdr, cBord, cText);   // zoom out
   DrawButton(w - 50, by, 22, bh, "A+", cHdr, cBord, cText);   // zoom in
   DrawButton(w - 24, by, 20, bh, g_collapsed ? "+" : "-", cHdr, cBord, cText);

   if(!g_collapsed)
     {
      //--- column header
      g_canvas.FillRectangle(0, g_titleH, w - 1, g_bodyTop - 1, cHdr);
      int hy = g_titleH + g_hdrH / 2;
      string symHdr = "Symbol";
      if(total > rows)
         symHdr += StringFormat("  %d-%d/%d", g_scroll + 1, g_scroll + rows, total);
      if(g_sort == 1) symHdr += " ▲";
      string levHdr = (g_sort == 2) ? "Leverage ▼" : "Leverage";
      string rec = (InpRecordSec % 60 == 0) ? IntegerToString(InpRecordSec / 60) + " min"
                   : IntegerToString(InpRecordSec) + " s";
      g_hdr[0] = symHdr;
      g_hdr[1] = "Type";
      g_hdr[2] = levHdr;
      g_hdr[3] = "Tiers (by volume)";
      g_hdr[4] = "Swap (long / short)";
      g_hdr[5] = "Commission";
      g_hdr[6] = "Spread (now / 1h avg)";
      g_hdr[7] = (g_chartSpread ? "Spread history (1 pt / " : "Leverage history (1 pt / ") + rec + ")";
      for(int c = 0; c < 8; c++)
         DrawCell(c, hy, g_hdr[c], cDim);
      g_canvas.Line(0, g_bodyTop - 1, w - 1, g_bodyTop - 1, cBord);

      //--- rows
      int graphPx = g_xEnd - g_xGr;
      for(int r = 0; r < rows; r++)
        {
         int pos = g_scroll + r;
         if(pos >= total) break;
         CSymData *s = g_sym[g_order[pos]];
         int y  = g_bodyTop + r * g_rowH;
         int cy = y + g_rowH / 2;

         if(r == g_hover)
            g_canvas.FillRectangle(0, y, w - 1, y + g_rowH - 1, cHov);
         else if(r % 2 == 1)
            g_canvas.FillRectangle(0, y, w - 1, y + g_rowH - 1, cAlt);

         DrawCell(0, cy, CellFull(s, 0), cText);
         DrawCell(1, cy, CellFull(s, 1), cDim);

         uint cLev = cText;
         int n = ArraySize(s.v);
         if(s.cur > 0 && n > 0)
           {
            double last = s.v[n - 1];
            if(s.cur > last + 1e-9)      cLev = Op(InpUpColor);
            else if(s.cur < last - 1e-9) cLev = Op(InpDownColor);
           }
         DrawCell(2, cy, CellFull(s, 2), s.cur > 0 ? cLev : cDim);

         DrawCell(3, cy, CellFull(s, 3), cDim);

         for(int c = 4; c <= 6; c++)
           {
            string tx = CellFull(s, c);
            bool dimmed = (tx == "n/a" || tx == "-" || tx == "none");
            DrawCell(c, cy, tx, dimmed ? cDim : cText);
           }

         if(g_chartSpread)
            DrawSpark(s.sv, true, g_xGr + 2, y + 2, graphPx - 4, g_rowH - 4, cSpk);
         else
            DrawSpark(s.v, false, g_xGr + 2, y + 2, graphPx - 4, g_rowH - 4, cSpk);
        }

      //--- column separators (body only)
      int yb = g_bodyTop + rows * g_rowH;
      g_canvas.Line(g_xType, g_titleH, g_xType, yb - 1, cSep);
      g_canvas.Line(g_xLev, g_titleH, g_xLev, yb - 1, cSep);
      g_canvas.Line(g_xTier, g_titleH, g_xTier, yb - 1, cSep);
      g_canvas.Line(g_xSwap, g_titleH, g_xSwap, yb - 1, cSep);
      g_canvas.Line(g_xComm, g_titleH, g_xComm, yb - 1, cSep);
      g_canvas.Line(g_xSpr, g_titleH, g_xSpr, yb - 1, cSep);
      g_canvas.Line(g_xGr, g_titleH, g_xGr, yb - 1, cSep);
      g_canvas.Line(g_xEnd, g_titleH, g_xEnd, yb - 1, cSep);

      //--- scrollbar
      if(total > rows)
        {
         int tx = w - 6;
         int ty0 = g_bodyTop + 2, ty1 = yb - 3;
         int th = ty1 - ty0;
         g_canvas.FillRectangle(tx, ty0, tx + 3, ty1, cTrack);
         int thumbH = MathMax(14, th * rows / total);
         int maxS = total - rows;
         int thumbY = ty0 + (maxS > 0 ? (th - thumbH) * g_scroll / maxS : 0);
         g_canvas.FillRectangle(tx, thumbY, tx + 3, thumbY + thumbH, Op(InpAccentColor));
        }

      //--- footer: tier detail of hovered row (bright white) + resize grip
      g_canvas.FillRectangle(0, yb, w - 1, h - 1, cTitle);
      g_canvas.Line(0, yb, w - 1, yb, cBord);
      string foot = "Hover a row for its margin tiers   |   click Symbol / Leverage header to sort   |   drag the corner to resize";
      if(g_hover >= 0 && g_scroll + g_hover < total)
         foot = TierDetail(g_sym[g_order[g_scroll + g_hover]]);
      g_footFull = foot;
      string footTxt = FitText(foot, w - 8 - 20, g_footCut);
      g_canvas.TextOut(8, yb + (h - yb) / 2, footTxt, cFoot, TA_LEFT | TA_VCENTER);
      for(int i = 0; i < 3; i++)
         g_canvas.Line(w - 5 - i * 4, h - 3, w - 3, h - 5 - i * 4, cDim);
     }

   g_canvas.Rectangle(0, 0, w - 1, h - 1, cBord);
   g_canvas.Update();
  }

//+------------------------------------------------------------------+
//| History persistence                                              |
//+------------------------------------------------------------------+
void SaveHistory()
  {
   if(!InpSaveHistory) return;
   int h = FileOpen(g_file, FILE_WRITE | FILE_BIN | FILE_ANSI);
   if(h == INVALID_HANDLE) return;
   FileWriteInteger(h, 1);
   FileWriteInteger(h, ArraySize(g_sym));
   for(int i = 0; i < ArraySize(g_sym); i++)
     {
      CSymData *s = g_sym[i];
      int n = ArraySize(s.v);
      FileWriteInteger(h, StringLen(s.name));
      FileWriteString(h, s.name, StringLen(s.name));
      FileWriteInteger(h, n);
      if(n > 0)
        {
         FileWriteArray(h, s.t, 0, n);
         FileWriteArray(h, s.v, 0, n);
        }
     }
   FileClose(h);
  }

void SanitizeLev(CSymData *s)
  {
   int n = ArraySize(s.v);
   if(n < 2) return;
   if(s.v[ArrayMaximum(s.v)] <= 1.0 + 1e-9) return;      // genuine 1:1 symbol
   int k = 0;
   for(int i = 0; i < n; i++)
      if(s.v[i] > 1.0 + 1e-9)
        {
         s.v[k] = s.v[i];
         s.t[k] = s.t[i];
         k++;
        }
   ArrayResize(s.v, k);
   ArrayResize(s.t, k);
  }

void LoadHistory()
  {
   if(!InpSaveHistory || !FileIsExist(g_file)) return;
   int h = FileOpen(g_file, FILE_READ | FILE_BIN | FILE_ANSI);
   if(h == INVALID_HANDLE) return;
   if(FileReadInteger(h) != 1) { FileClose(h); return; }
   int count = FileReadInteger(h);
   for(int i = 0; i < count && !FileIsEnding(h); i++)
     {
      int len = FileReadInteger(h);
      string nm = FileReadString(h, len);
      int n = FileReadInteger(h);
      datetime tt[];
      double vv[];
      if(n > 0)
        {
         ArrayResize(tt, n);
         ArrayResize(vv, n);
         FileReadArray(h, tt, 0, n);
         FileReadArray(h, vv, 0, n);
        }
      int idx = FindSym(nm);
      if(idx >= 0 && n > 0)
        {
         int start = MathMax(0, n - InpMaxPoints);
         int m = n - start;
         ArrayResize(g_sym[idx].t, m);
         ArrayResize(g_sym[idx].v, m);
         ArrayCopy(g_sym[idx].t, tt, 0, start, m);
         ArrayCopy(g_sym[idx].v, vv, 0, start, m);
         SanitizeLev(g_sym[idx]);
        }
     }
   FileClose(h);
  }

//+------------------------------------------------------------------+
int OnInit()
  {
   ChartSetInteger(0, CHART_EVENT_MOUSE_WHEEL, true);
   ChartSetInteger(0, CHART_EVENT_MOUSE_MOVE, true);
   g_origScroll = (bool)ChartGetInteger(0, CHART_MOUSE_SCROLL);

   g_font = InpFontSize;
   g_graphBase = InpGraphW;
   g_rowsSet = InpMaxRows;
   g_colW[0] = InpSymbolColW; g_colW[1] = InpTypeColW;  g_colW[2] = InpLevColW;
   g_colW[3] = InpTiersColW;  g_colW[4] = InpSwapColW;  g_colW[5] = InpCommColW;
   g_colW[6] = InpSpreadColW;
   g_chartSpread = InpChartSpread;
   LoadGui();
   Layout();
   g_file = "LeverageMonitor_" + IntegerToString(AccountInfoInteger(ACCOUNT_LOGIN)) + ".bin";

   SyncSymbols();
   LoadHistory();
   SampleSpreads();
   UpdateAll(true);                       // every Market Watch symbol evaluated immediately

   int rows = VisibleRows(ArraySize(g_sym));
   int w = g_wPx;
   int h = g_bodyTop + rows * g_rowH + g_footH + 2;
   if(!g_canvas.CreateBitmapLabel(0, 0, g_obj, InpCornerX, InpCornerY, w, h,
                                  COLOR_FORMAT_ARGB_NORMALIZE))
     {
      Print("LeverageMonitor: cannot create canvas, error ", GetLastError());
      return INIT_FAILED;
     }
   ObjectSetInteger(0, g_obj, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, g_obj, OBJPROP_BACK, false);
   ObjectSetString(0, g_obj, OBJPROP_TOOLTIP, "\n");
   g_tip = "\n";
   g_w = w;
   g_h = h;

   g_lastRec = g_lastRef = GetTickCount64();
   Draw();
   EventSetTimer(1);
   return INIT_SUCCEEDED;
  }

void OnDeinit(const int reason)
  {
   EventKillTimer();
   LockChart(false);
   SaveHistory();
   SaveGui();
   g_canvas.Destroy();
   for(int i = 0; i < ArraySize(g_sym); i++)
      if(g_sym[i] != NULL)
         delete g_sym[i];
   ArrayFree(g_sym);
  }

void OnTick()
  {
  }

//+------------------------------------------------------------------+
void OnTimer()
  {
   ulong now = GetTickCount64();
   bool rec = (now - g_lastRec >= (ulong)InpRecordSec * 1000);
   bool ref = (now - g_lastRef >= (ulong)InpRefreshSec * 1000);
   bool changed = false;

   if(rec)
     {
      SyncSymbols();
      g_lastRec = now;
     }
   SampleSpreads();
   if(rec || ref)
     {
      g_lastRef = now;
      UpdateAll(rec);
      changed = true;
      if(rec && ++g_recCount % 10 == 0)
         SaveHistory();
     }
   else if(RetryFailed())
      changed = true;

   if(ProbeSome())
      changed = true;

   if(changed && !g_resizing && g_colDrag < 0)
      Draw();
  }

//+------------------------------------------------------------------+
//| Mouse handling                                                   |
//+------------------------------------------------------------------+
bool HandleClick(const int px, const int py)
  {
   if(py < g_titleH)
     {
      if(px >= g_w - 116 && px < g_w - 82)     // chart mode: leverage / spread
        {
         g_chartSpread = !g_chartSpread;
         SaveGui();
         return true;
        }
      if(px >= g_w - 24)                       // collapse / expand
        {
         g_collapsed = !g_collapsed;
         return true;
        }
      if(px >= g_w - 50 && px < g_w - 28)      // zoom in
        {
         g_font = MathMin(18, g_font + 1);
         SaveGui();
         return true;
        }
      if(px >= g_w - 76 && px < g_w - 54)      // zoom out
        {
         g_font = MathMax(6, g_font - 1);
         SaveGui();
         return true;
        }
      return false;
     }
   if(g_collapsed) return false;
   if(py < g_bodyTop)
     {
      if(px < g_xType)
        {
         g_sort = (g_sort == 1) ? 0 : 1;
         SaveGui();
         return true;
        }
      if(px >= g_xLev && px < g_xTier)
        {
         g_sort = (g_sort == 2) ? 0 : 2;
         SaveGui();
         return true;
        }
     }
   return false;
  }

void ApplyResize(const int mx, const int my)
  {
   int total = ArraySize(g_sym);
   int newW = MathMax(g_xGr + Sc(80) + 9, g_rsW + (mx - g_rsX));
   int newH = g_rsH + (my - g_rsY);

   // width: the history chart absorbs the change
   int gPx = newW - g_xGr - 9;
   g_graphBase = MathMax(80, MathMin(1200, (int)MathRound(gPx / g_scale)));

   // height: whole rows
   int rows = (newH - g_bodyTop - g_footH - 2) / g_rowH;
   g_rowsSet = MathMax(1, MathMin(rows, MathMax(1, total)));
  }

void OnChartEvent(const int id, const long &lparam, const double &dparam, const string &sparam)
  {
   if(id == CHARTEVENT_CHART_CHANGE)
     {
      Draw();
      return;
     }

   if(id == CHARTEVENT_MOUSE_MOVE)
     {
      int mx = (int)lparam, my = (int)dparam;
      int px = mx - InpCornerX;
      int py = my - InpCornerY;
      bool down = ((uint)StringToInteger(sparam) & 1) != 0;
      bool inside = (px >= 0 && px < g_w && py >= 0 && py < g_h);

      if(g_resizing)
        {
         if(down)
           {
            ApplyResize(mx, my);
            Draw();
            g_prevDown = true;
            return;
           }
         g_resizing = false;                    // released
         SaveGui();
        }

      if(g_colDrag >= 0)
        {
         if(down)
           {
            g_colW[g_colDrag] = MathMax(30, MathMin(600, g_cdW + (int)MathRound((mx - g_cdX) / g_scale)));
            Draw();
            g_prevDown = true;
            return;
           }
         g_colDrag = -1;                        // released
         SaveGui();
        }

      LockChart(inside);                        // stop the chart scrolling under the panel

      int hov = -1;
      if(inside && !g_collapsed && py >= g_bodyTop)
        {
         int nrows = VisibleRows(ArraySize(g_sym));
         int r = (py - g_bodyTop) / g_rowH;
         if(r < nrows && g_scroll + r < ArraySize(g_sym))
            hov = r;
         else if(py >= g_bodyTop + nrows * g_rowH)
            hov = g_hover;                      // pointer on the bottom line: keep the row so its full text stays readable
        }
      bool redraw = false;
      if(hov != g_hover)
        {
         g_hover = hov;
         redraw = true;
        }
      if(down && !g_prevDown && inside)
        {
         int sepc = -1;
         if(!g_collapsed && py >= g_titleH && py < g_bodyTop + VisibleRows(ArraySize(g_sym)) * g_rowH)
            sepc = SepAt(px);
         if(sepc >= 0)
           {
            g_colDrag = sepc;                   // grab a column border
            g_cdX = mx;
            g_cdW = g_colW[sepc];
            LockChart(true);
           }
         else if(!g_collapsed && px >= g_w - 16 && py >= g_h - 16)
           {
            g_resizing = true;                  // grab the corner grip
            g_rsX = mx;
            g_rsY = my;
            g_rsW = g_w;
            g_rsH = g_h;
            LockChart(true);
           }
         else if(HandleClick(px, py))
            redraw = true;
        }
      g_prevDown = down;
      if(redraw) Draw();
      SetTip(inside ? TipAt(px, py) : "");
      return;
     }

   if(id == CHARTEVENT_MOUSE_WHEEL)
     {
      int x = (int)(short)lparam;
      int y = (int)(short)(lparam >> 16);
      int delta = (int)dparam;
      if(!g_collapsed && x >= InpCornerX && x < InpCornerX + g_w &&
         y >= InpCornerY && y < InpCornerY + g_h)
        {
         int total = ArraySize(g_sym);
         if(total > VisibleRows(total))
           {
            g_scroll += (delta > 0) ? -3 : 3;
            Draw();
           }
        }
     }
  }
//+------------------------------------------------------------------+
