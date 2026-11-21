//+------------------------------------------------------------------+
//|  TickScalper v2.6                                                |
//|  Tick chart (canvas) + one-click scalping panel + live DOM       |
//|                                                                  |
//|  CHANGELOG                                                       |
//|  v2.6  - After a manual Y zoom/pan the chart returns to Auto Y   |
//|          by itself as soon as a DOM line reaches the top or      |
//|          bottom of the screen (input InpDomAutoResume)          |
//|  v2.5  - The terminal's own trade history (deal arrows and      |
//|          lines) is hidden while the EA runs and restored on exit |
//|  v2.4  - BID line and label have their own fixed colour (green,  |
//|          input InpColBid) and never turn red; ASK stays red      |
//|  v2.3  - DOM is ON at every start (the old on/off state is no    |
//|          longer remembered between sessions)                     |
//|        - Auto Y scale now follows the DOM: it covers the        |
//|          furthest displayed DOM ask and bid lines (default on)   |
//|        - ASK line and ASK price label are red                    |
//|        - DOM lines sit exactly on their price on the chart axis  |
//|          (axis ticks added); levels outside the view get no      |
//|          fake fan from the chart edge                            |
//|  v2.2  - DOM filter fixed. The feed reports 100 units = 1 lot,   |
//|          so the volume divisor now defaults to 100 (0 = use the  |
//|          symbol's contract size). Filter levels (button cycles): |
//|            default : 1-10 lots,    max 10 rows                   |
//|            1st click: 10-100 lots, up to 20 rows (detailed)      |
//|            2nd click: 1-100 lots,  up to 20 rows                 |
//|            3rd click: 10-100 lots, max 10 rows                   |
//|        - DOM level lines and diagonals thicker and brighter;     |
//|          live BID/ASK lines thicker (inputs for both widths)     |
//|        - Panel: Lots has its own row; the - / + buttons moved to |
//|          a labelled "Ticks/bar" row                              |
//|  v2.1  - Compact panel (about 45% shorter)                       |
//|        - Panel and its title are drawn ABOVE all chart text      |
//|        - DOM failure (no feed / no data) hides the DOM and shows |
//|          a notification banner; it returns when data arrives     |
//|        - DOM shows small positions: default level = from 1 lot   |
//|        - DOM show/hide button and detail-level button            |
//|          (>=1 lot, >=10 lots, >=100 lots, 1-10 lots only);       |
//|          default view = 20 rows, filtered views = 10 rows        |
//|        - DOM is part of the chart: every DOM level is a thin     |
//|          line across the chart (moves with price scale / zoom)   |
//|          joined by diagonals to its thick DOM bar (prism look)   |
//|  v2.0  - Draggable GUI: drag the panel's title bar anywhere on   |
//|          the chart (position is remembered)                      |
//|        - DOM (depth of market) from the broker's live book feed  |
//|          (MarketBookAdd / OnBookEvent) in the far right of the   |
//|          chart, default 20% of the width. Adjust with the input  |
//|          or by dragging the DOM's left edge. Two views:          |
//|            Ladder  = rows of price + volume around the spread   |
//|            Aligned = volume bars on the tick chart's price scale |
//|          Panel button cycles Off / Ladder / Aligned.             |
//|        - Chart now uses the full width; the panel floats on top  |
//|  v1.7  - FIX: closing positions inside the freeze level          |
//|  v1.6  - Backtesting (Strategy Tester), stats, Market hardening  |
//|  v1.5  - GUI text explanations moved into an "Info" hover tip    |
//|  v1.4  - Draggable Y zoom, pending orders at clicked price       |
//|  v1.3  - Vertical zoom fits visible ticks only                   |
//|  v1.2  - Live BID and ASK lines                                  |
//|  v1.1  - Order result checks, compact ticks, time mode, levels   |
//|  v1.0  - Initial release                                         |
//+------------------------------------------------------------------+
#property copyright "Tick Scalper Helper"
#property version   "2.60"
#property description "TickScalper v2.6 - tick chart + quick trade panel + DOM with lot-band filter (1-10 / 10-100 lots). Attach to the symbol you trade."

#include <Canvas\Canvas.mqh>

//--- inputs --------------------------------------------------------
input group "=== Trading ==="
input double InpLots          = 0.01;   // Default lot size
input int    InpDeviation     = 30;     // Max slippage (points)
input ulong  InpMagic         = 0;      // Magic number
input bool   InpTPOn          = false;  // Take profit enabled at start
input int    InpTPPoints      = 50;     // Take profit distance (points)
input bool   InpSLOn          = false;  // Stop loss enabled at start
input int    InpSLPoints      = 50;     // Stop loss distance (points)
input bool   InpPendingClick  = true;   // Ctrl/Shift+click places pending orders

input group "=== Tick chart ==="
input int    InpTicksPerBar   = 1;      // Ticks per bar at start
input int    InpMaxTicksPerBar= 4096;   // Maximum ticks per bar (+ button)
input int    InpBarWidth      = 2;      // Width of each tick/bar (px)
input int    InpLineWidth     = 2;      // Line thickness (px)
input bool   InpTimeMode      = false;  // Time-scaled x axis at start
input double InpPxPerSecond   = 10.0;   // Time mode: pixels per second
input double InpPadPercent    = 5.0;    // Vertical padding of auto zoom (%)
input bool   InpSkipUnchanged = true;   // Ignore ticks where BID did not change
input int    InpPreloadTicks  = 10000;  // Ticks loaded from history at start

input group "=== DOM (needs the broker's depth-of-market feed) ==="
input bool   InpDomShow       = true;   // Show DOM at start
input int    InpDomWidthPct   = 20;     // DOM width (% of chart width, 8-50)
input int    InpDomRowsDefault= 10;     // Rows (asks+bids) in the default and compact views
input int    InpDomRowsDetail = 20;     // Rows (asks+bids) in the detailed views
input double InpDomLowLots    = 1.0;    // Band lower limit (lots)
input double InpDomMidLots    = 10.0;   // Band middle limit (lots)
input double InpDomHighLots   = 100.0;  // Band upper limit (lots)
input double InpDomVolDivisor = 100.0;  // Feed volume units per lot (100 = 100 units is 1 lot; 0 = use contract size)
input int    InpDomLineWidth  = 2;      // Thickness of the DOM level lines and diagonals (px)
input bool   InpDomAutoResume  = true;   // After a manual Y change, return to Auto Y when a DOM line reaches the screen edge
input bool   InpDomFitScale   = true;   // Auto zoom covers the furthest displayed DOM lines

input group "=== Display ==="
input bool   InpDarkMode      = true;   // Dark mode at start
input bool   InpShowBidAsk    = true;   // Show BID / ASK lines
input int    InpBidAskWidth   = 2;      // BID / ASK line thickness (px)
input bool   InpShowLevels    = true;   // Show positions, pending orders, SL, TP
input color  InpColUp         = C'38,166,91';    // Up colour (also DOM bids)
input color  InpColDown       = C'229,57,53';    // Down colour (also DOM asks)
input color  InpColBid        = C'38,166,91';    // BID line and label colour (fixed, green)
input color  InpColAsk        = C'214,32,32';    // ASK line and label colour (red)
input color  InpColBuyLevel   = C'41,121,255';   // Buy position / pending colour
input color  InpColSellLevel  = C'255,145,0';    // Sell position / pending colour
input int    InpRenderMs      = 15;     // Chart refresh interval (ms)

input group "=== Backtest (Strategy Tester only) ==="
input bool   InpBtAuto        = true;   // Run built-in demo rule in tester (never active on live charts)
input int    InpBtTicks       = 4;      // Entry: consecutive ticks in one direction
input int    InpBtTP          = 40;     // Take profit (points)
input int    InpBtSL          = 60;     // Stop loss (points)
input int    InpBtMaxSpread   = 0;      // Max spread to enter (points, 0 = off)
input int    InpBtMaxHoldSec  = 60;     // Close position after N seconds (0 = off)
input int    InpBtCooldownSec = 10;     // Pause after each entry (seconds)

//--- layout
#define CAP      262144          // tick ring buffer (power of 2)
#define MASK     262143
#define MAXPTS   32768           // max points drawn
#define MAXLV    128             // max trade levels tracked
#define MAXDOM   128             // max DOM levels per side
#define MAXOBJ   32              // max panel objects
#define PANEL_W  196
#define PANEL_H  268
#define TITLE_H  18
#define AXIS_W   70
#define STRIP_H  36

//--- panel: position of the "Info" word (relative to the panel's top-left)
#define IX_INFO  118
#define IY_INFO  242

//--- object names
#define N_BUY   "TS_buy"
#define N_SELL  "TS_sell"
#define N_LOTS  "TS_lots"
#define N_TPT   "TS_tp_toggle"
#define N_TPE   "TS_tp_edit"
#define N_SLT   "TS_sl_toggle"
#define N_SLE   "TS_sl_edit"
#define N_CB    "TS_close_buy"
#define N_CS    "TS_close_sell"
#define N_CP    "TS_close_profit"
#define N_CA    "TS_close_all"
#define N_MINUS "TS_minus"
#define N_PLUS  "TS_plus"
#define N_TIMET "TS_time_toggle"
#define N_TIMEE "TS_time_edit"
#define N_AUTOY "TS_auto_y"
#define N_THEME "TS_theme"
#define N_DOMB  "TS_dom_btn"
#define N_DOML  "TS_dom_level"
#define N_CV    "TS_canvas"

//--- DOM level
struct DomLv { double p; double v; };

//--- state
CCanvas  g_cv;
double   g_ring[CAP];
long     g_tms[CAP];              // tick time (msc) ring
long     g_n = 0;                 // total ticks stored
double   g_lastP = 0;
double   g_bid = 0, g_ask = 0;
double   g_spreadPts = 0;
double   g_cl[MAXPTS];            // scratch: visible closes (0 = newest)
int      g_off[MAXPTS];           // scratch: x offset from newest point
long     g_tpb = 1;               // ticks per bar
bool     g_dark = true;
bool     g_dirty = true;
int      g_w = 0, g_h = 0;
string   g_status = "";

double   g_lots = 0.01;
int      g_lotDigits = 2;
bool     g_tpOn = false, g_slOn = false;
int      g_tpPts = 50, g_slPts = 50;
bool     g_timeMode = false;
double   g_pxPerSec = 10.0;

//--- trade levels (0 buy pos, 1 sell pos, 2 SL, 3 TP, 4 buy pending, 5 sell pending)
double   g_lvP[MAXLV];
int      g_lvK[MAXLV];
double   g_lvV[MAXLV];
string   g_lvT[MAXLV];
int      g_nlv = 0;

MqlTradeRequest g_req;
MqlTradeResult  g_res;
ENUM_ORDER_TYPE_FILLING g_fill = ORDER_FILLING_IOC;

//--- price<->pixel mapping (set in DrawChart)
double   g_pmax = 0, g_pscale = 0;
int      g_yT = 0;
double   g_vMax = 0, g_vMin = 0;          // currently displayed range

//--- chart area (set in Render, used for mouse hit-testing)
int      g_xL = 0, g_xR = 0, g_yTc = 0, g_yBc = 0;
int      g_xDom = 0, g_domW = 0;

//--- vertical zoom
bool     g_autoY = true;
double   g_manMax = 0, g_manMin = 0;
int      g_dragY = 0;
int      g_domOutPrev = -1;               // DOM lines touching/outside the manual view in the previous frame (-1 = unknown)
double   g_dragMax = 0, g_dragMin = 0;
uint     g_lastAxisPress = 0;

//--- drag state: 0 none, 1 zoom (axis), 2 pan (chart), 3 DOM width, 4 panel move
int      g_drag = 0;
int      g_dragDX = 0, g_dragDY = 0;

//--- floating panel
int      g_px = 8, g_py = 44;
bool     g_panelMoved = true;
string   g_oN[MAXOBJ];
int      g_oRX[MAXOBJ], g_oRY[MAXOBJ];
int      g_nObj = 0;

//--- DOM
bool     g_domShow = true;                // user switch (button)
int      g_domLevel = 0;                  // 0 >=min, 1 >=mid, 2 >=big, 3 band min..mid
double   g_domPct = 20.0;
bool     g_domOK = false;                 // subscribed to the book
bool     g_domFailed = false;             // no feed / no data: DOM is hidden
bool     g_gotBook = false;               // at least one level was received
uint     g_domSubMs = 0;                  // when we subscribed (for the no-data timeout)
bool     g_bookDirty = false;
DomLv    g_dAsk[MAXDOM], g_dBid[MAXDOM];  // full book: asks ascending, bids descending (volumes in lots)
int      g_nAsk = 0, g_nBid = 0;
DomLv    g_rAsk[MAXDOM], g_rBid[MAXDOM];  // rows selected for display (nearest first)
int      g_nrA = 0, g_nrB = 0;
double   g_rMax = 0;
int      g_domRh = 16, g_domYm = 0;       // row height and spread position of the DOM ladder
string   g_note = "";                     // notification banner
uint     g_noteMs = 0;

//--- mouse
bool     g_prevL = false, g_prevR = false;
int      g_mx = 0, g_my = 0;
uint     g_mfl = 0;
bool     g_cross = false;
bool     g_info = false;
uint     g_lastMouseMs = 0;

//--- run environment
bool     g_isTester = false, g_visual = false, g_gui = true;

//--- session statistics
datetime g_t0 = 0;
int      g_stN = 0, g_stW = 0;
double   g_stNet = 0;

//--- backtest engine state
double   g_btPrev = 0;
int      g_btRun = 0;
datetime g_btLast = 0;
datetime g_btRetry = 0;

//--- native chart scale sync (so the right-click trading menu uses our scale)
double   g_synMax = 0, g_synMin = 0;
uint     g_lastSync = 0;
bool     g_needSync = false;

//--- original chart settings (restored on exit)
long     g_oMode, g_oGrid, g_oDate, g_oPrice, g_oScroll, g_oFix, g_oLine, g_oBack, g_oMouseEv, g_oOhlc, g_oHist;

//+------------------------------------------------------------------+
//| Small helpers                                                    |
//+------------------------------------------------------------------+
int ClampI(int v, int lo, int hi) { return v < lo ? lo : (v > hi ? hi : v); }

color Mix(color a, color b, double t)       // t = 0 -> b, t = 1 -> a
{
   uint ca = (uint)a, cb = (uint)b;
   int ar = (int)(ca & 0xFF), ag = (int)((ca >> 8) & 0xFF), ab = (int)((ca >> 16) & 0xFF);
   int br = (int)(cb & 0xFF), bg = (int)((cb >> 8) & 0xFF), bb = (int)((cb >> 16) & 0xFF);
   int r = (int)(br + (ar - br) * t), g = (int)(bg + (ag - bg) * t), bl = (int)(bb + (ab - bb) * t);
   return (color)(r | (g << 8) | (bl << 16));
}

string VolStr(double v)
{
   if(v >= 1000000.0) return StringFormat("%.1fM", v / 1000000.0);
   if(v >= 10000.0)   return StringFormat("%.1fK", v / 1000.0);
   if(MathAbs(v - MathRound(v)) < 1e-9) return StringFormat("%.0f", v);
   return StringFormat("%.2f", v);
}

//+------------------------------------------------------------------+
//| Theme helpers                                                    |
//+------------------------------------------------------------------+
color cBg()      { return g_dark ? C'16,18,22'    : C'255,255,255'; }
color cPanel()   { return g_dark ? C'24,27,32'    : C'240,242,245'; }
color cGrid()    { return g_dark ? C'42,46,54'    : C'225,228,232'; }
color cBorder()  { return g_dark ? C'80,86,98'    : C'170,175,185'; }
color cTxt()     { return g_dark ? C'165,171,182' : C'70,75,85';    }
color cBtnBg()   { return g_dark ? C'48,52,61'    : C'222,226,232'; }
color cBtnFg()   { return g_dark ? C'225,228,234' : C'30,34,40';    }
color cEdBg()    { return g_dark ? C'32,35,42'    : C'255,255,255'; }
color cDomBg()   { return g_dark ? C'20,23,28'    : C'247,248,250'; }
color cUp()      { return InpColUp;        }
color cDn()      { return InpColDown;      }
color cFlat()    { return g_dark ? C'120,125,135' : C'150,155,165'; }
color cBuyLv()   { return InpColBuyLevel;  }
color cSellLv()  { return InpColSellLevel; }
color cAskLn()   { return InpColAsk;       }

//+------------------------------------------------------------------+
//| DOM helpers                                                      |
//+------------------------------------------------------------------+
bool DomActive() { return g_domShow && g_domOK && !g_domFailed && !g_isTester; }

// band and row count of the current filter level
void DomBand(double &lo, double &hi, int &rows)
{
   int rd = MathMax(2, InpDomRowsDefault), rx = MathMax(2, InpDomRowsDetail);
   switch(g_domLevel)
   {
      case 0:  lo = InpDomLowLots; hi = InpDomMidLots;  rows = rd; break;   // default: 1-10 lots, 10 rows
      case 1:  lo = InpDomMidLots; hi = InpDomHighLots; rows = rx; break;   // 1st click: 10-100 lots, 20 rows
      case 2:  lo = InpDomLowLots; hi = InpDomHighLots; rows = rx; break;   // 2nd click: 1-100 lots, 20 rows
      default: lo = InpDomMidLots; hi = InpDomHighLots; rows = rd; break;   // 3rd click: 10-100 lots, 10 rows
   }
}

string DomLevelLabel()
{
   double lo, hi; int rows;
   DomBand(lo, hi, rows);
   return VolStr(lo) + "-" + VolStr(hi) + " lots";
}

bool DomPass(double v)
{
   double lo, hi; int rows;
   DomBand(lo, hi, rows);
   return (v >= lo - 1e-9 && v <= hi + 1e-9);
}

// rows per side = half of the rows of the current level
int DomRowsPerSide()
{
   double lo, hi; int rows;
   DomBand(lo, hi, rows);
   return MathMax(1, rows / 2);
}

// feed volume units per lot
double DomDivisor()
{
   if(InpDomVolDivisor > 0) return InpDomVolDivisor;
   double cs = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_CONTRACT_SIZE);
   return (cs > 0) ? cs : 1.0;
}

int DomWidth()
{
   if(!DomActive()) return 0;
   int w = (int)(g_w * g_domPct / 100.0);
   w = MathMax(200, w);
   return MathMin(w, g_w / 2);
}

void DomNote(string msg)
{
   g_note = msg;
   g_noteMs = GetTickCount();
   g_dirty = true;
   Print("TickScalper: ", msg);
}

void DomFail(string reason)
{
   g_domFailed = true;
   DomNote("DOM hidden: " + reason);
}

void DomSubscribe()
{
   if(g_isTester) return;
   if(!g_domOK)
   {
      g_domOK = MarketBookAdd(_Symbol);
      if(!g_domOK)
      {
         DomFail("broker provides no depth of market for " + _Symbol);
         return;
      }
   }
   g_domFailed = false;          // (re)start the wait for data
   g_gotBook = false;
   g_domSubMs = GetTickCount();
   g_bookDirty = true;
   g_dirty = true;
}

void DomInsert(DomLv &arr[], int &n, double p, double v, bool ascending)
{
   if(n >= MAXDOM) return;
   int i = n;
   while(i > 0 && (ascending ? arr[i - 1].p > p : arr[i - 1].p < p))
   {
      arr[i] = arr[i - 1];
      i--;
   }
   arr[i].p = p;
   arr[i].v = v;
   n++;
}

// copies the broker's book into sorted arrays (called from the render timer, not per event)
void FetchBook()
{
   g_bookDirty = false;
   g_nAsk = 0; g_nBid = 0;
   MqlBookInfo bk[];
   if(!MarketBookGet(_Symbol, bk)) return;
   double div = DomDivisor();
   int n = ArraySize(bk);
   for(int i = 0; i < n; i++)
   {
      double pr = bk[i].price;
      double v  = ((bk[i].volume_real > 0) ? bk[i].volume_real : (double)bk[i].volume) / div;
      if(pr <= 0 || v <= 0) continue;
      if(bk[i].type == BOOK_TYPE_SELL || bk[i].type == BOOK_TYPE_SELL_MARKET)
         DomInsert(g_dAsk, g_nAsk, pr, v, true);
      else if(bk[i].type == BOOK_TYPE_BUY || bk[i].type == BOOK_TYPE_BUY_MARKET)
         DomInsert(g_dBid, g_nBid, pr, v, false);
   }
   if(g_nAsk + g_nBid > 0)
   {
      g_gotBook = true;
      if(g_domFailed) { g_domFailed = false; g_note = ""; }   // data arrived: show the DOM again
   }
}

// picks the nearest levels that pass the detail-level filter
void BuildDomRows()
{
   g_nrA = 0; g_nrB = 0; g_rMax = 0;
   int per = DomRowsPerSide();
   for(int k = 0; k < g_nAsk && g_nrA < per; k++)
      if(DomPass(g_dAsk[k].v))
      {
         g_rAsk[g_nrA++] = g_dAsk[k];
         if(g_dAsk[k].v > g_rMax) g_rMax = g_dAsk[k].v;
      }
   for(int k = 0; k < g_nBid && g_nrB < per; k++)
      if(DomPass(g_dBid[k].v))
      {
         g_rBid[g_nrB++] = g_dBid[k];
         if(g_dBid[k].v > g_rMax) g_rMax = g_dBid[k].v;
      }
}

//+------------------------------------------------------------------+
//| UI creation (floating panel; positions relative to g_px/g_py)    |
//+------------------------------------------------------------------+
void Reg(string n, int rx, int ry)
{
   if(g_nObj >= MAXOBJ) return;
   g_oN[g_nObj] = n; g_oRX[g_nObj] = rx; g_oRY[g_nObj] = ry;
   g_nObj++;
}

void PlacePanel()
{
   for(int i = 0; i < g_nObj; i++)
   {
      ObjectSetInteger(0, g_oN[i], OBJPROP_XDISTANCE, g_px + g_oRX[i]);
      ObjectSetInteger(0, g_oN[i], OBJPROP_YDISTANCE, g_py + g_oRY[i]);
   }
}

void ClampPanel()
{
   g_px = ClampI(g_px, 0, MathMax(0, g_w - PANEL_W));
   g_py = ClampI(g_py, 0, MathMax(0, g_h - PANEL_H));
}

void MakeBtn(string n, string txt, int rx, int ry, int w, int h)
{
   ObjectCreate(0, n, OBJ_BUTTON, 0, 0, 0);
   ObjectSetInteger(0, n, OBJPROP_XDISTANCE, g_px + rx);
   ObjectSetInteger(0, n, OBJPROP_YDISTANCE, g_py + ry);
   ObjectSetInteger(0, n, OBJPROP_XSIZE, w);
   ObjectSetInteger(0, n, OBJPROP_YSIZE, h);
   ObjectSetString (0, n, OBJPROP_TEXT, txt);
   ObjectSetString (0, n, OBJPROP_FONT, "Segoe UI");
   ObjectSetInteger(0, n, OBJPROP_FONTSIZE, 9);
   ObjectSetInteger(0, n, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, n, OBJPROP_HIDDEN, true);
   ObjectSetInteger(0, n, OBJPROP_ZORDER, 10);
   Reg(n, rx, ry);
}

void MakeEdit(string n, string txt, int rx, int ry, int w, int h)
{
   ObjectCreate(0, n, OBJ_EDIT, 0, 0, 0);
   ObjectSetInteger(0, n, OBJPROP_XDISTANCE, g_px + rx);
   ObjectSetInteger(0, n, OBJPROP_YDISTANCE, g_py + ry);
   ObjectSetInteger(0, n, OBJPROP_XSIZE, w);
   ObjectSetInteger(0, n, OBJPROP_YSIZE, h);
   ObjectSetString (0, n, OBJPROP_TEXT, txt);
   ObjectSetString (0, n, OBJPROP_FONT, "Segoe UI");
   ObjectSetInteger(0, n, OBJPROP_FONTSIZE, 9);
   ObjectSetInteger(0, n, OBJPROP_ALIGN, ALIGN_CENTER);
   ObjectSetInteger(0, n, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, n, OBJPROP_HIDDEN, true);
   ObjectSetInteger(0, n, OBJPROP_ZORDER, 10);
   Reg(n, rx, ry);
}

void Skin(string n, color bg, color fg)
{
   ObjectSetInteger(0, n, OBJPROP_BGCOLOR, bg);
   ObjectSetInteger(0, n, OBJPROP_COLOR, fg);
   ObjectSetInteger(0, n, OBJPROP_BORDER_COLOR, g_dark ? C'70,75,85' : C'180,185,195');
}

void SetToggle(string n, string label, bool on)
{
   ObjectSetString(0, n, OBJPROP_TEXT, label + (on ? " ON" : " OFF"));
   Skin(n, on ? C'33,111,214' : cBtnBg(), on ? clrWhite : cBtnFg());
}

void DomRefreshButtons()
{
   if(g_isTester)
   {
      ObjectSetString(0, N_DOMB, OBJPROP_TEXT, "DOM n/a");
      Skin(N_DOMB, cBtnBg(), cBtnFg());
   }
   else SetToggle(N_DOMB, "DOM", g_domShow && !g_domFailed);
   ObjectSetString(0, N_DOML, OBJPROP_TEXT, DomLevelLabel());
}

void ApplyTheme()
{
   string neutral[] = {N_CB, N_CS, N_CP, N_CA, N_MINUS, N_PLUS, N_THEME, N_DOML};
   for(int i = 0; i < ArraySize(neutral); i++) Skin(neutral[i], cBtnBg(), cBtnFg());
   Skin(N_BUY,  cUp(), clrWhite);
   Skin(N_SELL, cDn(), clrWhite);
   Skin(N_LOTS,  cEdBg(), cBtnFg());
   Skin(N_TPE,   cEdBg(), cBtnFg());
   Skin(N_SLE,   cEdBg(), cBtnFg());
   Skin(N_TIMEE, cEdBg(), cBtnFg());
   SetToggle(N_TPT,   "TP",     g_tpOn);
   SetToggle(N_SLT,   "SL",     g_slOn);
   SetToggle(N_TIMET, "Time",   g_timeMode);
   SetToggle(N_AUTOY, "Y Auto", g_autoY);
   ObjectSetString(0, N_THEME, OBJPROP_TEXT, g_dark ? "Light mode" : "Dark mode");
   DomRefreshButtons();
   g_dirty = true;
}

void CreateUI()
{
   g_nObj = 0;
   // layout: Lots on its own row, ticks-per-bar (- / +) on a separate labelled row
   MakeBtn (N_BUY,   "BUY",  8,  22, 86, 30);
   MakeBtn (N_SELL,  "SELL", 98, 22, 86, 30);
   MakeEdit(N_LOTS,  DoubleToString(g_lots, g_lotDigits), 62, 56, 122, 22);
   MakeBtn (N_MINUS, "-", 84,  82, 24, 22);
   MakeBtn (N_PLUS,  "+", 160, 82, 24, 22);
   MakeBtn (N_TPT,   "TP OFF", 8,  108, 52, 22);
   MakeEdit(N_TPE,   IntegerToString(g_tpPts), 62, 108, 32, 22);
   MakeBtn (N_SLT,   "SL OFF", 98, 108, 52, 22);
   MakeEdit(N_SLE,   IntegerToString(g_slPts), 152, 108, 32, 22);
   MakeBtn (N_CB,    "Close Buy",    8,  134, 86, 24);
   MakeBtn (N_CS,    "Close Sell",   98, 134, 86, 24);
   MakeBtn (N_CP,    "Close Profit", 8,  160, 86, 24);
   MakeBtn (N_CA,    "Close All",    98, 160, 86, 24);
   MakeBtn (N_TIMET, "Time OFF", 8,  188, 52, 22);
   MakeEdit(N_TIMEE, DoubleToString(g_pxPerSec, 1), 62, 188, 32, 22);
   MakeBtn (N_AUTOY, "Y Auto ON", 98, 188, 86, 22);
   MakeBtn (N_DOMB,  "", 8,  214, 86, 22);
   MakeBtn (N_DOML,  "", 98, 214, 86, 22);
   MakeBtn (N_THEME, "", 8,  240, 86, 22);
   ApplyTheme();
}

// panel position and DOM width are remembered between sessions
void SaveLayout()
{
   if(g_isTester) return;
   GlobalVariableSet("TS_px", g_px);
   GlobalVariableSet("TS_py", g_py);
   GlobalVariableSet("TS_domPct", g_domPct);
}

void LoadLayout()
{
   if(g_isTester) return;
   if(GlobalVariableCheck("TS_px"))     g_px = (int)GlobalVariableGet("TS_px");
   if(GlobalVariableCheck("TS_py"))     g_py = (int)GlobalVariableGet("TS_py");
   if(GlobalVariableCheck("TS_domPct")) g_domPct = MathMax(8.0, MathMin(50.0, GlobalVariableGet("TS_domPct")));
}

//+------------------------------------------------------------------+
//| Lot helpers                                                      |
//+------------------------------------------------------------------+
double NormLots(double v)
{
   double mn = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double mx = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double st = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   if(st <= 0) st = mn;
   if(st <= 0) return v;
   v = MathFloor(v / st + 0.5) * st;
   if(v < mn) v = mn;
   if(v > mx) v = mx;
   return NormalizeDouble(v, g_lotDigits);
}

double SnapPrice(double p)
{
   double ts = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(ts <= 0) ts = _Point;
   return NormalizeDouble(MathRound(p / ts) * ts, _Digits);
}

// SL/TP distance in price units, never below the broker's minimum (stops level + spread)
double StopDist(int pts, double spread)
{
   double md   = (double)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL) * _Point;
   double need = md + spread + _Point;
   double d    = pts * _Point;
   return (d < need) ? need : d;
}

// true when the SELECTED position cannot be closed/modified right now because its SL or TP
// is within the broker's freeze level of the current price
bool PosFrozen(double bid, double ask)
{
   long fl = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_FREEZE_LEVEL);
   if(fl <= 0) return false;
   double fz  = (double)fl * _Point;
   bool   buy = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY);
   double cur = buy ? bid : ask;
   double sl = PositionGetDouble(POSITION_SL), tp = PositionGetDouble(POSITION_TP);
   if(tp > 0 && MathAbs(tp - cur) <= fz) return true;
   if(sl > 0 && MathAbs(sl - cur) <= fz) return true;
   return false;
}

double PriceAt(int y)
{
   if(g_pscale <= 0) return 0;
   return g_pmax - (double)(y - g_yT) / g_pscale;
}

//+------------------------------------------------------------------+
//| Trading - hot path. Pre-built request, async send.               |
//+------------------------------------------------------------------+
void SendMarket(ENUM_ORDER_TYPE type)
{
   MqlTick t;
   if(!SymbolInfoTick(_Symbol, t)) return;
   bool   buy = (type == ORDER_TYPE_BUY);
   double p   = buy ? t.ask : t.bid;

   g_req.action       = TRADE_ACTION_DEAL;
   g_req.position     = 0;
   g_req.type         = type;
   g_req.type_filling = g_fill;
   g_req.volume       = g_lots;
   g_req.price        = p;
   g_req.sl           = 0;
   g_req.tp           = 0;
   double spr = t.ask - t.bid;
   if(g_slOn) { double d = StopDist(g_slPts, spr); g_req.sl = NormalizeDouble(buy ? p - d : p + d, _Digits); }
   if(g_tpOn) { double d = StopDist(g_tpPts, spr); g_req.tp = NormalizeDouble(buy ? p + d : p - d, _Digits); }

   if(!OrderSendAsync(g_req, g_res))
   {
      int err = GetLastError();
      g_status = StringFormat("Send failed: err %d, ret %u", err, g_res.retcode);
      Print("TickScalper: OrderSendAsync failed. error=", err, " retcode=", g_res.retcode);
      g_dirty = true;
   }
}

// pending order at an exact price (limit/stop chosen automatically)
ENUM_ORDER_TYPE PendingTypeFor(bool buy, double price)
{
   if(buy) return (price < g_ask) ? ORDER_TYPE_BUY_LIMIT  : ORDER_TYPE_BUY_STOP;
   else    return (price > g_bid) ? ORDER_TYPE_SELL_LIMIT : ORDER_TYPE_SELL_STOP;
}

string PendingText(bool buy, double price)
{
   string nm;
   if(buy) nm = (price < g_ask) ? "BUY LIMIT"  : "BUY STOP";
   else    nm = (price > g_bid) ? "SELL LIMIT" : "SELL STOP";
   return nm + " @" + DoubleToString(price, _Digits);
}

void PlacePending(bool buy, double price)
{
   if(price <= 0 || g_ask <= 0 || g_bid <= 0) return;
   price = SnapPrice(price);

   // price must respect the broker's minimum distance from the market
   double md = (double)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL) * _Point;
   ENUM_ORDER_TYPE ot = PendingTypeFor(buy, price);
   bool tooClose = (ot == ORDER_TYPE_BUY_LIMIT  && price > g_ask - md) ||
                   (ot == ORDER_TYPE_BUY_STOP   && price < g_ask + md) ||
                   (ot == ORDER_TYPE_SELL_LIMIT && price < g_bid + md) ||
                   (ot == ORDER_TYPE_SELL_STOP  && price > g_bid - md);
   if(tooClose)
   {
      g_status = "Pending price too close to market (stops level)";
      g_dirty = true;
      return;
   }

   g_req.action       = TRADE_ACTION_PENDING;
   g_req.position     = 0;
   g_req.type         = ot;
   g_req.type_filling = ORDER_FILLING_RETURN;
   g_req.type_time    = ORDER_TIME_GTC;
   g_req.volume       = g_lots;
   g_req.price        = price;
   g_req.sl           = 0;
   g_req.tp           = 0;
   double spr = g_ask - g_bid;
   if(g_slOn) { double d = StopDist(g_slPts, spr); g_req.sl = NormalizeDouble(buy ? price - d : price + d, _Digits); }
   if(g_tpOn) { double d = StopDist(g_tpPts, spr); g_req.tp = NormalizeDouble(buy ? price + d : price - d, _Digits); }

   if(!OrderSendAsync(g_req, g_res))
   {
      int err = GetLastError();
      g_status = StringFormat("Pending failed: err %d, ret %u", err, g_res.retcode);
      Print("TickScalper: pending OrderSendAsync failed. error=", err, " retcode=", g_res.retcode);
      g_dirty = true;
   }
   g_req.type_filling = g_fill;   // restore for market orders
}

// mode: 0 = all, 1 = buys, 2 = sells, 3 = profitable only
void ClosePositions(int mode)
{
   MqlTick t;
   if(!SymbolInfoTick(_Symbol, t)) return;

   g_req.action       = TRADE_ACTION_DEAL;
   g_req.type_filling = g_fill;
   g_req.sl = 0;
   g_req.tp = 0;
   int failed = 0, lastErr = 0, frozen = 0;

   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i);
      if(tk == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      long pt = PositionGetInteger(POSITION_TYPE);
      if(mode == 1 && pt != POSITION_TYPE_BUY)  continue;
      if(mode == 2 && pt != POSITION_TYPE_SELL) continue;
      if(mode == 3 && PositionGetDouble(POSITION_PROFIT) <= 0) continue;
      if(PosFrozen(t.bid, t.ask)) { frozen++; continue; }   // server would reject: freeze level

      g_req.position = tk;
      g_req.volume   = PositionGetDouble(POSITION_VOLUME);
      if(pt == POSITION_TYPE_BUY) { g_req.type = ORDER_TYPE_SELL; g_req.price = t.bid; }
      else                        { g_req.type = ORDER_TYPE_BUY;  g_req.price = t.ask; }

      if(!OrderSendAsync(g_req, g_res))
      {
         failed++;
         lastErr = GetLastError();
         Print("TickScalper: close failed. ticket=", tk, " error=", lastErr, " retcode=", g_res.retcode);
      }
   }
   g_req.position = 0;

   if(failed > 0)
   {
      g_status = StringFormat("Close failed x%d: err %d", failed, lastErr);
      g_dirty = true;
   }
   else if(frozen > 0)
   {
      g_status = StringFormat("%d position(s) inside freeze level - press again", frozen);
      g_dirty = true;
   }
}

//+------------------------------------------------------------------+
//| Backtest engine: simple tick-momentum demo rule.                 |
//| Runs ONLY inside the Strategy Tester (g_isTester). Never active  |
//| on live charts. Synchronous OrderSend with full pre-checks.      |
//+------------------------------------------------------------------+
bool BtFindPos(ulong &ticket, datetime &opened)
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i);
      if(tk == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if((ulong)PositionGetInteger(POSITION_MAGIC) != InpMagic + 1) continue;
      ticket = tk;
      opened = (datetime)PositionGetInteger(POSITION_TIME);
      return true;
   }
   return false;
}

void BtClose(ulong ticket)
{
   if(TimeCurrent() < g_btRetry) return;                 // back off after a failed attempt
   if(!PositionSelectByTicket(ticket)) return;
   MqlTick t;
   if(!SymbolInfoTick(_Symbol, t)) return;
   if(PosFrozen(t.bid, t.ask)) return;                   // inside freeze level: try again on a later tick
   long pt = PositionGetInteger(POSITION_TYPE);

   MqlTradeRequest rq; MqlTradeResult rs;
   ZeroMemory(rq); ZeroMemory(rs);
   rq.action       = TRADE_ACTION_DEAL;
   rq.symbol       = _Symbol;
   rq.position     = ticket;
   rq.volume       = PositionGetDouble(POSITION_VOLUME);
   rq.type         = (pt == POSITION_TYPE_BUY) ? ORDER_TYPE_SELL : ORDER_TYPE_BUY;
   rq.price        = (pt == POSITION_TYPE_BUY) ? t.bid : t.ask;
   rq.deviation    = InpDeviation;
   rq.magic        = InpMagic + 1;
   rq.type_filling = g_fill;
   if(!OrderSend(rq, rs) || (rs.retcode != TRADE_RETCODE_DONE && rs.retcode != TRADE_RETCODE_PLACED))
   {
      g_btRetry = TimeCurrent() + 1;
      Print("TickScalper[backtest]: close failed, retcode=", rs.retcode);
   }
}

void BtOpen(bool buy, const MqlTick &t)
{
   if((ENUM_SYMBOL_TRADE_MODE)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_MODE) != SYMBOL_TRADE_MODE_FULL) return;

   ENUM_ORDER_TYPE ot = buy ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
   double p   = buy ? t.ask : t.bid;
   double vol = NormLots(g_lots);
   double lim = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_LIMIT);
   if(vol <= 0 || (lim > 0 && vol > lim)) return;

   // margin check: never send an order the account cannot afford
   double margin = 0;
   if(!OrderCalcMargin(ot, _Symbol, vol, p, margin)) return;
   if(margin <= 0 || margin > AccountInfoDouble(ACCOUNT_MARGIN_FREE) * 0.9) return;

   double spr = t.ask - t.bid;
   double sld = StopDist(InpBtSL, spr);
   double tpd = StopDist(InpBtTP, spr);

   MqlTradeRequest rq; MqlTradeResult rs;
   ZeroMemory(rq); ZeroMemory(rs);
   rq.action       = TRADE_ACTION_DEAL;
   rq.symbol       = _Symbol;
   rq.volume       = vol;
   rq.type         = ot;
   rq.price        = p;
   rq.sl           = NormalizeDouble(buy ? p - sld : p + sld, _Digits);
   rq.tp           = NormalizeDouble(buy ? p + tpd : p - tpd, _Digits);
   rq.deviation    = InpDeviation;
   rq.magic        = InpMagic + 1;
   rq.type_filling = g_fill;
   rq.comment      = "TS backtest";

   g_btLast = TimeCurrent();
   if(!OrderSend(rq, rs) || (rs.retcode != TRADE_RETCODE_DONE && rs.retcode != TRADE_RETCODE_PLACED))
      Print("TickScalper[backtest]: open failed, retcode=", rs.retcode);
}

void BtOnTick(const MqlTick &t)
{
   if(t.bid <= 0 || t.ask <= 0) return;

   // run of consecutive ticks in one direction (+up / -down)
   if(g_btPrev > 0)
   {
      if(t.bid > g_btPrev)      g_btRun = (g_btRun > 0) ? g_btRun + 1 : 1;
      else if(t.bid < g_btPrev) g_btRun = (g_btRun < 0) ? g_btRun - 1 : -1;
   }
   g_btPrev = t.bid;

   ulong tk; datetime opened;
   if(BtFindPos(tk, opened))
   {
      if(InpBtMaxHoldSec > 0 && TimeCurrent() - opened >= InpBtMaxHoldSec) BtClose(tk);
      return;
   }
   if(MathAbs(g_btRun) < MathMax(1, InpBtTicks)) return;
   if(TimeCurrent() - g_btLast < InpBtCooldownSec) return;
   if(InpBtMaxSpread > 0 && (t.ask - t.bid) / _Point > InpBtMaxSpread) return;

   BtOpen(g_btRun > 0, t);
   g_btRun = 0;
}

//+------------------------------------------------------------------+
//| Session statistics (shown on the chart header)                   |
//+------------------------------------------------------------------+
void UpdateStats()
{
   g_stN = 0; g_stW = 0; g_stNet = 0;
   if(!HistorySelect(g_t0, TimeCurrent() + 86400)) return;
   int n = HistoryDealsTotal();
   for(int i = 0; i < n; i++)
   {
      ulong tk = HistoryDealGetTicket(i);
      if(tk == 0) continue;
      if(HistoryDealGetString(tk, DEAL_SYMBOL) != _Symbol) continue;
      long ty = HistoryDealGetInteger(tk, DEAL_TYPE);
      if(ty != DEAL_TYPE_BUY && ty != DEAL_TYPE_SELL) continue;
      double p = HistoryDealGetDouble(tk, DEAL_PROFIT) + HistoryDealGetDouble(tk, DEAL_COMMISSION)
               + HistoryDealGetDouble(tk, DEAL_SWAP)   + HistoryDealGetDouble(tk, DEAL_FEE);
      g_stNet += p;
      long en = HistoryDealGetInteger(tk, DEAL_ENTRY);
      if(en == DEAL_ENTRY_OUT || en == DEAL_ENTRY_INOUT || en == DEAL_ENTRY_OUT_BY)
      {
         g_stN++;
         if(p > 0) g_stW++;
      }
   }
   g_dirty = true;
}

//+------------------------------------------------------------------+
//| Trade levels (positions + pending orders)                        |
//+------------------------------------------------------------------+
void AddLv(double p, int k, double v, string t)
{
   if(g_nlv >= MAXLV || p <= 0) return;
   g_lvP[g_nlv] = p;
   g_lvK[g_nlv] = k;
   g_lvV[g_nlv] = v;
   g_lvT[g_nlv] = t;
   g_nlv++;
}

string PendingName(ENUM_ORDER_TYPE ot, bool &buy)
{
   buy = false;
   switch(ot)
   {
      case ORDER_TYPE_BUY_LIMIT:       buy = true;  return "BUY LIMIT";
      case ORDER_TYPE_SELL_LIMIT:                   return "SELL LIMIT";
      case ORDER_TYPE_BUY_STOP:        buy = true;  return "BUY STOP";
      case ORDER_TYPE_SELL_STOP:                    return "SELL STOP";
      case ORDER_TYPE_BUY_STOP_LIMIT:  buy = true;  return "BUY STOP LMT";
      case ORDER_TYPE_SELL_STOP_LIMIT:              return "SELL STOP LMT";
   }
   return "";
}

void RefreshLevels()
{
   g_nlv = 0;

   for(int i = 0; i < PositionsTotal(); i++)
   {
      ulong tk = PositionGetTicket(i);
      if(tk == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      bool buy = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY);
      AddLv(PositionGetDouble(POSITION_PRICE_OPEN), buy ? 0 : 1, PositionGetDouble(POSITION_VOLUME), "");
      double sl = PositionGetDouble(POSITION_SL), tp = PositionGetDouble(POSITION_TP);
      if(sl > 0) AddLv(sl, 2, 0, "SL " + DoubleToString(sl, _Digits));
      if(tp > 0) AddLv(tp, 3, 0, "TP " + DoubleToString(tp, _Digits));
   }

   for(int i = 0; i < OrdersTotal(); i++)
   {
      ulong tk = OrderGetTicket(i);
      if(tk == 0) continue;
      if(OrderGetString(ORDER_SYMBOL) != _Symbol) continue;
      bool buy;
      string nm = PendingName((ENUM_ORDER_TYPE)OrderGetInteger(ORDER_TYPE), buy);
      if(nm == "") continue;
      double pr  = OrderGetDouble(ORDER_PRICE_OPEN);
      double vol = OrderGetDouble(ORDER_VOLUME_CURRENT);
      AddLv(pr, buy ? 4 : 5, vol,
            StringFormat("%s %s @%s", nm, DoubleToString(vol, g_lotDigits), DoubleToString(pr, _Digits)));
      double sl = OrderGetDouble(ORDER_SL), tp = OrderGetDouble(ORDER_TP);
      if(sl > 0) AddLv(sl, 2, 0, "SL " + DoubleToString(sl, _Digits));
      if(tp > 0) AddLv(tp, 3, 0, "TP " + DoubleToString(tp, _Digits));
   }
   g_dirty = true;
}

//+------------------------------------------------------------------+
//| Tick storage                                                     |
//+------------------------------------------------------------------+
void AddTick(double p, long msc)
{
   if(p <= 0) return;
   if(InpSkipUnchanged && p == g_lastP) return;
   long i = g_n & MASK;
   g_ring[i] = p;
   g_tms[i]  = msc;
   g_n++;
   g_lastP = p;
   g_dirty = true;
}

//+------------------------------------------------------------------+
//| Rendering                                                        |
//+------------------------------------------------------------------+
int Y(double p)
{
   double v = g_yT + (g_pmax - p) * g_pscale;
   if(v < -10000) v = -10000;
   if(v > 10000)  v = 10000;
   return (int)v;
}

void ThickLine(int x1, int y1, int x2, int y2, uint c)
{
   bool steep = MathAbs(y2 - y1) > MathAbs(x2 - x1);
   for(int k = 0; k < InpLineWidth; k++)
   {
      if(steep) g_cv.Line(x1 + k, y1, x2 + k, y2, c);
      else      g_cv.Line(x1, y1 + k, x2, y2 + k, c);
   }
}

// horizontal line w px thick, centred on y
void HLine(int x1, int x2, int y, int w, uint c)
{
   w = MathMax(1, w);
   for(int k = 0; k < w; k++)
      g_cv.Line(x1, y + k - w / 2, x2, y + k - w / 2, c);
}

void DashLine(int x1, int x2, int y, uint c)
{
   for(int x = x1; x < x2; x += 8)
      g_cv.Line(x, y, MathMin(x + 4, x2), y, c);
}

void DrawLevels(int xL, int xR, int yT, int yB)
{
   for(int k = 0; k < g_nlv; k++)
   {
      int  kind = g_lvK[k];
      int  y = Y(g_lvP[k]);
      string pre = "";
      if(y < yT) { y = yT; pre = "^ "; }
      if(y > yB) { y = yB; pre = "v "; }

      uint c;
      string txt = g_lvT[k];
      switch(kind)
      {
         case 0:
            c = ColorToARGB(cBuyLv());
            txt = StringFormat("BUY %s @%s  %+.0f pts", DoubleToString(g_lvV[k], g_lotDigits),
                               DoubleToString(g_lvP[k], _Digits), (g_bid - g_lvP[k]) / _Point);
            break;
         case 1:
            c = ColorToARGB(cSellLv());
            txt = StringFormat("SELL %s @%s  %+.0f pts", DoubleToString(g_lvV[k], g_lotDigits),
                               DoubleToString(g_lvP[k], _Digits), (g_lvP[k] - g_ask) / _Point);
            break;
         case 2:  c = ColorToARGB(cDn());     break;
         case 3:  c = ColorToARGB(cUp());     break;
         case 4:  c = ColorToARGB(cBuyLv());  break;
         default: c = ColorToARGB(cSellLv()); break;
      }

      if(kind <= 1)
      {
         g_cv.Line(xL, y, xR, y, c);
         g_cv.Line(xL, y + 1, xR, y + 1, c);
      }
      else DashLine(xL, xR, y, c);

      g_cv.TextOut(xR - 4, MathMax(0, y - 15), pre + txt, c, TA_RIGHT);
   }
}

void DrawCrosshair(int xL, int xR, int yT, int yB)
{
   if(!g_cross || g_my < yT || g_my > yB) return;
   double pr = SnapPrice(PriceAt(g_my));
   uint c = ColorToARGB(cTxt());
   DashLine(xL, xR, g_my, c);
   g_cv.FillRectangle(xR + 1, g_my - 9, xR + AXIS_W - 2, g_my + 9, c);
   g_cv.TextOut(xR + 6, g_my - 7, DoubleToString(pr, _Digits), ColorToARGB(cBg()));
   if((g_mfl & 8) != 0)       g_cv.TextOut(g_mx + 12, MathMax(0, g_my - 18), PendingText(true,  pr), ColorToARGB(cBuyLv()));
   else if((g_mfl & 4) != 0)  g_cv.TextOut(g_mx + 12, MathMax(0, g_my - 18), PendingText(false, pr), ColorToARGB(cSellLv()));
}

// ask (red) / bid (green) line per displayed DOM level, brighter for larger volume
void DrawDomLines(int xL, int xR, int xEnd, int yT, int yB)
{
   if(g_rMax <= 0) return;
   color bg = cBg();
   for(int k = 0; k < g_nrA; k++)
   {
      int y = Y(g_rAsk[k].p);
      if(y < yT || y > yB) continue;                 // outside the visible range: not drawn
      double t = 0.55 + 0.45 * (g_rAsk[k].v / g_rMax);
      uint ca = ColorToARGB(Mix(cDn(), bg, MathMin(1.0, t)));
      HLine(xL, xEnd, y, InpDomLineWidth, ca);
      HLine(xR, xR + 7, y, InpDomLineWidth + 1, ColorToARGB(cDn()));      // tick on the price axis
   }
   for(int k = 0; k < g_nrB; k++)
   {
      int y = Y(g_rBid[k].p);
      if(y < yT || y > yB) continue;
      double t = 0.55 + 0.45 * (g_rBid[k].v / g_rMax);
      uint cb = ColorToARGB(Mix(cUp(), bg, MathMin(1.0, t)));
      HLine(xL, xEnd, y, InpDomLineWidth, cb);
      HLine(xR, xR + 7, y, InpDomLineWidth + 1, ColorToARGB(cUp()));      // tick on the price axis
   }
}

void DrawChart(int xL, int xR, int yT, int yB, int yBase)
{
   if(g_n < 2) return;

   int bw   = MathMax(1, InpBarWidth);
   int xNew = xR - 6;
   int span = xNew - xL;
   if(span < 4) return;

   // ---- collect points (index 0 = newest) ----
   int  cap = g_timeMode ? MAXPTS : MathMin(MAXPTS, span / bw + 2);
   long N = g_tpb, lastBar = (g_n - 1) / N;
   long oldest = (g_n > CAP) ? g_n - CAP : 0;
   long tNew = 0;
   int  m = 0;
   for(int j = 0; j < cap; j++)
   {
      long bar = lastBar - j;
      if(bar < 0) break;
      long e = (bar + 1) * N - 1;
      if(e > g_n - 1) e = g_n - 1;
      if(e < oldest) break;
      g_cl[j] = g_ring[e & MASK];
      long tm = g_tms[e & MASK];
      if(j == 0) tNew = tm;
      if(g_timeMode)
      {
         double o = (double)(tNew - tm) * g_pxPerSec / 1000.0;
         g_off[j] = (o > 1000000.0) ? 1000000 : (int)o;
      }
      else g_off[j] = j * bw;
      m++;
      if(g_off[j] > span) break;     // first point past the left edge: keep it, then stop
   }
   if(m < 2) return;

   // ---- price range: auto-fit to visible ticks, or manual (dragged) ----
   double pmin = g_cl[0], pmax = g_cl[0];
   for(int j = 1; j < m; j++)
   {
      if(g_off[j] > span) break;
      if(g_cl[j] < pmin) pmin = g_cl[j];
      if(g_cl[j] > pmax) pmax = g_cl[j];
   }
   if(InpDomFitScale && g_domW > 0)          // optionally include the displayed DOM levels
   {
      for(int k = 0; k < g_nrA; k++) { pmax = MathMax(pmax, g_rAsk[k].p); pmin = MathMin(pmin, g_rAsk[k].p); }
      for(int k = 0; k < g_nrB; k++) { pmax = MathMax(pmax, g_rBid[k].p); pmin = MathMin(pmin, g_rBid[k].p); }
   }
   if(pmax - pmin < _Point * 2) { pmax += _Point; pmin -= _Point; }
   double pad = (pmax - pmin) * MathMax(0.0, InpPadPercent) / 100.0;
   pmax += pad; pmin -= pad;
   // manual Y: go back to automatic as soon as a displayed DOM line reaches the top or bottom edge
   if(g_autoY) g_domOutPrev = -1;
   else if(InpDomAutoResume && InpDomFitScale && g_domW > 0 && g_manMax - g_manMin > _Point * 2)
   {
      double mg = (g_manMax - g_manMin) * 0.01;
      int out = 0;
      for(int k = 0; k < g_nrA; k++) if(g_rAsk[k].p >= g_manMax - mg || g_rAsk[k].p <= g_manMin + mg) out++;
      for(int k = 0; k < g_nrB; k++) if(g_rBid[k].p >= g_manMax - mg || g_rBid[k].p <= g_manMin + mg) out++;
      if(g_drag == 0 && g_domOutPrev >= 0 && out > g_domOutPrev)
      {
         g_autoY = true;                       // pmin/pmax above already include the DOM levels
         SetToggle(N_AUTOY, "Y Auto", true);
         g_domOutPrev = -1;
      }
      else g_domOutPrev = out;
   }
   if(!g_autoY)
   {
      pmax = g_manMax;
      pmin = g_manMin;
      if(pmax - pmin < _Point * 2) { pmax += _Point; pmin -= _Point; }
   }
   g_vMax = pmax; g_vMin = pmin;
   g_yT = yT;
   g_pmax = pmax;
   g_pscale = (double)(yB - yT) / (pmax - pmin);
   g_needSync = true;

   uint uGrid = ColorToARGB(cGrid()), uTxt = ColorToARGB(cTxt());
   uint uUp = ColorToARGB(cUp()), uDn = ColorToARGB(cDn()), uFl = ColorToARGB(cFlat());

   // ---- grid ----
   for(int i = 0; i <= 4; i++)
   {
      double pr = pmax - i * (pmax - pmin) / 4.0;
      int y = Y(pr);
      g_cv.Line(xL, y, xR, y, uGrid);
   }

   // ---- DOM levels as thin lines across the chart (they move with the price scale) ----
   if(g_domW > 0) DrawDomLines(xL, xR, g_xDom, yT, yB);

   // ---- axis labels (after the DOM lines so they stay readable) ----
   for(int i = 0; i <= 4; i++)
   {
      double pr = pmax - i * (pmax - pmin) / 4.0;
      g_cv.TextOut(xR + 6, Y(pr) - 7, DoubleToString(pr, _Digits), uTxt);
   }

   // ---- max |delta| for bottom strip ----
   double maxD = 0;
   for(int j = 0; j < m - 1; j++)
   {
      if(g_off[j] > span) break;
      double d = MathAbs(g_cl[j] - g_cl[j + 1]);
      if(d > maxD) maxD = d;
   }

   // ---- line segments + coloured ticks ----
   for(int j = m - 1; j >= 1; j--)
   {
      int x1 = xNew - g_off[j], x2 = xNew - g_off[j - 1];
      if(x2 < xL) continue;
      int y1 = Y(g_cl[j]), y2 = Y(g_cl[j - 1]);
      if(x1 < xL)
      {
         if(x2 > x1) y1 += (int)((double)(y2 - y1) * (xL - x1) / (x2 - x1));
         x1 = xL;
      }
      y1 = ClampI(y1, yT, yB);
      y2 = ClampI(y2, yT, yB);

      double d = g_cl[j - 1] - g_cl[j];
      uint c = (d > 0) ? uUp : (d < 0 ? uDn : uFl);
      ThickLine(x1, y1, x2, y2, c);

      int h = 2;
      if(maxD > 0 && d != 0) h = 3 + (int)(MathAbs(d) / maxD * (STRIP_H - 6));
      g_cv.FillRectangle(x2 - bw + 1, yBase - h, x2, yBase, c);
   }

   // ---- trade levels ----
   if(InpShowLevels) DrawLevels(xL, xR, yT, yB);

   // ---- live BID / ASK lines + axis tags ----
   if(InpShowBidAsk)
   {
      uint uBid = ColorToARGB(InpColBid);          // fixed colour: BID never turns red like the ASK
      uint uAsk = ColorToARGB(cAskLn());
      uint uWhite = ColorToARGB(clrWhite);
      double bidP = (g_bid > 0) ? g_bid : g_cl[0];
      int yBid = ClampI(Y(bidP), yT, yB);
      HLine(xL, xR, yBid, InpBidAskWidth, uBid);
      g_cv.TextOut(xL + 4, yBid + 2, "BID", uBid);
      int yBidTag = yBid;
      if(g_ask > 0)
      {
         int yAskRaw = Y(g_ask);
         int yAsk = ClampI(yAskRaw, yT, yB);
         HLine(xL, xR, yAsk, InpBidAskWidth, uAsk);
         g_cv.TextOut(xL + 4, MathMax(0, yAsk - 15), (yAskRaw < yT) ? "ASK ^" : "ASK", uAsk);
         int yAskTag = MathMin(yAsk, yBid - 19);      // keep the two tags from overlapping
         if(yAskTag < yT) yAskTag = yT;
         g_cv.FillRectangle(xR + 1, yAskTag - 9, xR + AXIS_W - 2, yAskTag + 9, uAsk);
         g_cv.TextOut(xR + 6, yAskTag - 7, DoubleToString(g_ask, _Digits), uWhite);
         if(yAskTag + 9 >= yBid - 9) yBidTag = yAskTag + 19;
      }
      g_cv.FillRectangle(xR + 1, yBidTag - 9, xR + AXIS_W - 2, yBidTag + 9, uBid);
      g_cv.TextOut(xR + 6, yBidTag - 7, DoubleToString(bidP, _Digits), uWhite);
   }

   // ---- crosshair / pending-order preview ----
   DrawCrosshair(xL, xR, yT, yB);
}

//+------------------------------------------------------------------+
//| DOM drawing                                                      |
//+------------------------------------------------------------------+
//+------------------------------------------------------------------+
//| DOM drawing: thick ladder bars joined to the chart's thin level  |
//| lines by diagonals (prism look)                                  |
//+------------------------------------------------------------------+
void DrawDom(int x0, int yT, int yB)
{
   color bgc = cDomBg();
   uint uT = ColorToARGB(cTxt());
   g_cv.FillRectangle(x0, 0, g_w - 1, g_h - 1, ColorToARGB(bgc));
   { double lo, hi; int rows; DomBand(lo, hi, rows);
     g_cv.TextOut(x0 + 6, 8, StringFormat("DOM  %s  (max %d rows)", DomLevelLabel(), rows), uT); }

   if(g_nrA + g_nrB == 0 || g_rMax <= 0)
   {
      g_cv.TextOut(x0 + 6, yT + 4, (g_nAsk + g_nBid == 0) ? "Waiting for DOM data..." : "No levels in this filter", uT);
      return;
   }

   int connW = ClampI((int)((g_w - x0) * 0.40), 60, 120);    // width of the diagonal "fan" zone
   int xBar  = x0 + connW;                                   // thick bars start here
   int rh = g_domRh, half = rh / 2;
   int bwMax = g_w - xBar - 10;

   for(int side = 0; side < 2; side++)                       // 0 = asks (above), 1 = bids (below)
   {
      int n = (side == 0) ? g_nrA : g_nrB;
      color base = (side == 0) ? cDn() : cUp();
      for(int k = 0; k < n; k++)
      {
         double p = (side == 0) ? g_rAsk[k].p : g_rBid[k].p;
         double v = (side == 0) ? g_rAsk[k].v : g_rBid[k].v;
         double rel = v / g_rMax;
         int yc   = (side == 0) ? g_domYm - 2 - half - k * rh : g_domYm + 2 + half + k * rh;
         int yTop = yc - half + 1, yBot = yc + half - 1;
         int yRaw = Y(p);
         bool onScr = (yRaw >= yT && yRaw <= yB);            // level is inside the visible price range
         int yl   = yRaw;

         // diagonals: from the thin line's end to the corners of the thick bar
         uint uDia = ColorToARGB(Mix(base, bgc, MathMin(1.0, 0.60 + 0.4 * rel)));
         if(onScr)
         for(int w = 0; w < MathMax(1, InpDomLineWidth); w++)
         {
            int o = w - MathMax(1, InpDomLineWidth) / 2;
            g_cv.Line(x0, yl + o, xBar + 2, yTop + o, uDia);
            g_cv.Line(x0, yl + o, xBar + 2, yBot + o, uDia);
         }

         // thick bar, length proportional to volume
         int bwid = MathMax(2, (int)(rel * bwMax));
         g_cv.FillRectangle(xBar + 2, yTop, xBar + 2 + bwid, yBot, ColorToARGB(Mix(base, bgc, 0.35 + 0.5 * rel)));

         g_cv.TextOut(xBar + 6, yc - 6, DoubleToString(p, _Digits), uT);
         g_cv.TextOut(g_w - 6, yc - 6, VolStr(v), uT, TA_RIGHT);
      }
   }
}

//+------------------------------------------------------------------+
//| Floating panel background, title bar and captions                |
//+------------------------------------------------------------------+
void DrawPanel()
{
   int x = g_px, y = g_py;
   uint uBorder = ColorToARGB(cBorder());
   uint uTxt = ColorToARGB(cTxt());
   g_cv.FillRectangle(x, y, x + PANEL_W - 1, y + PANEL_H - 1, ColorToARGB(cPanel()));
   g_cv.FillRectangle(x, y, x + PANEL_W - 1, y + TITLE_H - 1, ColorToARGB(cBtnBg()));
   g_cv.Rectangle(x, y, x + PANEL_W - 1, y + PANEL_H - 1, uBorder);
   g_cv.TextOut(x + 8, y + 2, ":::  TickScalper v2.6", ColorToARGB(cBtnFg()));

   g_cv.TextOut(x + 8, y + 60, "Lots", uTxt);
   g_cv.TextOut(x + 8, y + 86, "Ticks/bar", uTxt);
   g_cv.TextOut(x + 134, y + 86, StringFormat("%d", (int)g_tpb), ColorToARGB(cBtnFg()), TA_CENTER);

   // "Info" word: all explanations live in its hover tooltip
   uint uInfo = ColorToARGB(g_info ? cBtnFg() : cTxt());
   g_cv.TextOut(x + IX_INFO, y + IY_INFO + 2, "Info", uInfo);
   g_cv.Line(x + IX_INFO, y + IY_INFO + 17, x + IX_INFO + 30, y + IY_INFO + 17, uInfo);
}

void DrawInfoTip(uint uTxt)
{
   string lines[];
   int n = 0;
   ArrayResize(lines, 33);
   lines[n++] = "Drag title bar        : move this panel";
   if(InpPendingClick)
   {
      lines[n++] = "Ctrl+click on chart   : pending BUY at that price";
      lines[n++] = "Shift+click on chart  : pending SELL at that price";
   }
   lines[n++] = "Drag price axis       : vertical zoom";
   lines[n++] = "Drag chart            : vertical pan";
   lines[n++] = "Double-click axis     : Y auto-fit (or Y Auto button)";
   lines[n++] = "Lots box              : order size in lots";
   lines[n++] = "TP / SL boxes         : distance in points";
   lines[n++] = "Time box              : pixels per second";
   lines[n++] = "Ticks/bar - / +      : ticks per bar (1, 2, 4, 8 ...)";
   lines[n++] = "DOM button            : show / hide the DOM";
   lines[n++] = "DOM level button      : cycles the volume filter";
   lines[n++] = "                        default 1-10 lots (10 rows)";
   lines[n++] = "                        1st 10-100 lots (20 rows)";
   lines[n++] = "                        2nd 1-100 lots (20 rows)";
   lines[n++] = "                        3rd 10-100 lots (10 rows)";
   lines[n++] = "Drag DOM left edge    : DOM width";
   lines[n++] = "Red/green DOM lines   : asks / bids at their exact price";
   lines[n++] = "Auto Y scale          : follows the furthest DOM lines";
   lines[n++] = "                        after a manual change it returns";
   lines[n++] = "                        when a DOM line reaches the edge";
   lines[n++] = "Diagonals             : join each line to its DOM bar";
   lines[n++] = "Blue/orange line      : buy/sell position or pending";
   lines[n++] = "Red/green dashed      : stop loss / take profit";
   lines[n++] = "Red line/label = ASK, green line/label = BID";
   lines[n++] = "Strategy Tester       : visual mode = manual panel";

   int lh = 16, pad = 8, w = 0;
   for(int i = 0; i < n; i++) w = MathMax(w, StringLen(lines[i]) * 7);
   w += pad * 2;
   int h = n * lh + pad * 2;
   int x1 = g_px + PANEL_W + 8;
   if(x1 + w > g_w - 4) x1 = MathMax(4, g_px - w - 8);   // no room on the right: show on the left
   int y1 = ClampI(g_py + IY_INFO - h + 20, 4, MathMax(4, g_h - h - 4));
   g_cv.FillRectangle(x1, y1, x1 + w, y1 + h, ColorToARGB(cPanel()));
   g_cv.Rectangle(x1, y1, x1 + w, y1 + h, ColorToARGB(cTxt()));
   for(int i = 0; i < n; i++)
      g_cv.TextOut(x1 + pad, y1 + pad + i * lh, lines[i], uTxt);
}

void Render()
{
   if(!g_dirty || g_w <= AXIS_W + 240 || g_h < 160) return;
   g_dirty = false;

   if(g_domOK && g_domShow && g_bookDirty) FetchBook();   // also detects data arriving after a failure
   bool domOn = DomActive();
   if(domOn) BuildDomRows();
   if(g_panelMoved) { ClampPanel(); PlacePanel(); g_panelMoved = false; }

   uint uTxt = ColorToARGB(cTxt());

   g_domW = domOn ? DomWidth() : 0;
   g_xDom = g_w - g_domW;
   int xL = 2, xR = g_xDom - AXIS_W;
   int yT = 38, yB = g_h - STRIP_H - 14, yBase = g_h - 8;
   g_xL = xL; g_xR = xR; g_yTc = yT; g_yBc = yB;

   // DOM ladder geometry (shared by the chart's level lines and the DOM drawing)
   int per = DomRowsPerSide();
   g_domRh = ClampI((yB - yT) / (per * 2 + 2), 12, 24);
   g_domYm = (yT + yB) / 2;

   g_cv.Erase(ColorToARGB(cBg()));

   DrawChart(xL, xR, yT, yB, yBase);
   if(g_domW > 0) DrawDom(g_xDom, yT, yB);

   // header texts first, so the panel (drawn last) is always ABOVE them
   string mode = g_timeMode ? StringFormat("time %.1f px/s", g_pxPerSec) : "compact";
   g_cv.TextOut(xL + 10, 8, StringFormat("TickScalper v2.6   %s   %d tick/bar   %s   spread %.0f pts",
                _Symbol, (int)g_tpb, mode, g_spreadPts), uTxt);
   g_cv.TextOut(xL + 10, 22, StringFormat("%s session: %d trades   win %.0f%%   net %+.2f %s",
                g_isTester ? "Tester" : "Live", g_stN,
                g_stN > 0 ? 100.0 * g_stW / g_stN : 0.0, g_stNet,
                AccountInfoString(ACCOUNT_CURRENCY)), uTxt);
   if(g_status != "")
      g_cv.TextOut(xR, 8, g_status, ColorToARGB(cDn()), TA_RIGHT);

   // notification banner (e.g. DOM could not be loaded)
   if(g_note != "")
   {
      int tw = g_cv.TextWidth(g_note);
      int bx = MathMax(4, g_w - tw - 24), by = 38;
      g_cv.FillRectangle(bx, by, bx + tw + 16, by + 20, ColorToARGB(C'255,193,7'));
      g_cv.TextOut(bx + 8, by + 4, g_note, ColorToARGB(C'30,30,30'));
   }

   DrawPanel();                       // panel above all chart text
   if(g_info) DrawInfoTip(uTxt);      // tooltip above the panel

   g_cv.Update();
}

void ResizeCanvas()
{
   int w = (int)ChartGetInteger(0, CHART_WIDTH_IN_PIXELS);
   int h = (int)ChartGetInteger(0, CHART_HEIGHT_IN_PIXELS);
   if(w <= 0 || h <= 0) return;
   if(w != g_w || h != g_h)
   {
      g_w = w; g_h = h;
      g_cv.Resize(w, h);
      g_synMax = g_synMin = 0;
      g_panelMoved = true;          // keep the panel inside the chart
   }
   g_dirty = true;
}

//+------------------------------------------------------------------+
//| Keep the native chart's price scale identical to ours, so the    |
//| right-click > Trading > Buy Limit / Sell Stop... menu uses the   |
//| price under the cursor.                                          |
//+------------------------------------------------------------------+
void SyncNative(bool force)
{
   if(g_pscale <= 0 || g_h <= 0) return;
   uint now = GetTickCount();
   if(!force && (now - g_lastSync) < 150) return;

   double top = g_pmax + (double)g_yT / g_pscale;              // price at y = 0
   double bot = g_pmax - (double)(g_h - g_yT) / g_pscale;      // price at y = chart height
   if(top <= bot) return;
   if(MathAbs(top - g_synMax) < _Point * 0.01 && MathAbs(bot - g_synMin) < _Point * 0.01)
   {
      g_needSync = false;
      return;
   }

   bool ok;
   if(top > g_synMax) ok = ChartSetDouble(0, CHART_FIXED_MAX, top) && ChartSetDouble(0, CHART_FIXED_MIN, bot);
   else               ok = ChartSetDouble(0, CHART_FIXED_MIN, bot) && ChartSetDouble(0, CHART_FIXED_MAX, top);
   if(!ok)   // order matters when the new window does not overlap the old one: retry once
   {
      ChartSetDouble(0, CHART_FIXED_MAX, top);
      ChartSetDouble(0, CHART_FIXED_MIN, bot);
   }
   g_synMax = top; g_synMin = bot;
   g_lastSync = now;
   g_needSync = false;
}

//+------------------------------------------------------------------+
//| Mouse handling: panel drag, DOM resize, pending clicks, Y zoom   |
//+------------------------------------------------------------------+
void SetManualY(double mx, double mn)
{
   if(g_autoY)
   {
      g_autoY = false;
      SetToggle(N_AUTOY, "Y Auto", false);
   }
   g_manMax = mx; g_manMin = mn;
   g_dirty = true;
}

void OnMouse(int x, int y, uint fl)
{
   g_lastMouseMs = GetTickCount();
   bool left  = (fl & 1) != 0;
   bool right = (fl & 2) != 0;
   bool mod   = (fl & 12) != 0;                       // Shift (4) or Ctrl (8)

   bool inPanel = (x >= g_px && x < g_px + PANEL_W && y >= g_py && y < g_py + PANEL_H);
   bool inTitle = (x >= g_px && x < g_px + PANEL_W && y >= g_py && y < g_py + TITLE_H);
   int  ix = g_px + IX_INFO, iy = g_py + IY_INFO;
   bool onInfo = (x >= ix && x <= ix + 34 && y >= iy && y <= iy + 20);
   if(onInfo != g_info) { g_info = onInfo; g_dirty = true; }

   bool onDomEdge = (g_domW > 0 && MathAbs(x - g_xDom) <= 4);
   bool inChart = (!inPanel && x > g_xL && x < g_xR && y >= g_yTc && y <= g_yBc);
   bool inAxis  = (!inPanel && x >= g_xR && x < g_xR + AXIS_W && y >= g_yTc && y <= g_yBc);

   // right button pressed: make sure the native trading menu sees our scale
   if(right && !g_prevR) SyncNative(true);

   // crosshair preview while Ctrl/Shift is held
   bool wantCross = InpPendingClick && mod && inChart;
   if(wantCross || g_cross)
   {
      g_mx = x; g_my = y; g_mfl = fl;
      g_cross = wantCross;
      g_dirty = true;
   }

   if(left && !g_prevL)                               // left button pressed
   {
      if(inTitle)                                     // start moving the panel
      {
         g_drag = 4; g_dragDX = x - g_px; g_dragDY = y - g_py;
      }
      else if(inPanel) { /* buttons handle their own clicks */ }
      else if(onDomEdge) g_drag = 3;                  // start resizing the DOM
      else if(InpPendingClick && inChart && (fl & 8) != 0)  PlacePending(true,  PriceAt(y));
      else if(InpPendingClick && inChart && (fl & 4) != 0)  PlacePending(false, PriceAt(y));
      else if(inAxis && g_pscale > 0)
      {
         uint now = GetTickCount();
         if(now - g_lastAxisPress < 400)                // double-click on axis -> auto
         {
            g_autoY = true;
            SetToggle(N_AUTOY, "Y Auto", true);
            g_dirty = true;
            g_drag = 0;
         }
         else
         {
            g_drag = 1; g_dragY = y; g_dragMax = g_vMax; g_dragMin = g_vMin;
         }
         g_lastAxisPress = now;
      }
      else if(inChart && g_pscale > 0)
      {
         g_drag = 2; g_dragY = y; g_dragMax = g_vMax; g_dragMin = g_vMin;
      }
   }
   else if(left && g_drag != 0)                       // dragging
   {
      if(g_drag == 4)
      {
         g_px = ClampI(x - g_dragDX, 0, MathMax(0, g_w - PANEL_W));
         g_py = ClampI(y - g_dragDY, 0, MathMax(0, g_h - PANEL_H));
         g_panelMoved = true;
         g_dirty = true;
      }
      else if(g_drag == 3)
      {
         g_domPct = MathMax(8.0, MathMin(50.0, 100.0 * (g_w - x) / (double)MathMax(1, g_w)));
         g_dirty = true;
      }
      else
      {
         double range0 = g_dragMax - g_dragMin;
         if(range0 > 0)
         {
            if(g_drag == 1)                             // zoom around the centre; drag up = zoom in
            {
               double f = MathExp((double)(y - g_dragY) * 0.006);
               double nr = MathMax(range0 * f, _Point * 2);
               double c = (g_dragMax + g_dragMin) / 2.0;
               SetManualY(c + nr / 2.0, c - nr / 2.0);
            }
            else                                        // pan with the cursor
            {
               double scale0 = (double)(g_yBc - g_yTc) / range0;
               double dp = (double)(y - g_dragY) / scale0;
               SetManualY(g_dragMax + dp, g_dragMin + dp);
            }
         }
      }
   }
   if(!left)
   {
      if(g_drag == 3 || g_drag == 4) SaveLayout();
      g_drag = 0;
   }

   g_prevL = left;
   g_prevR = right;
}

//+------------------------------------------------------------------+
//| Init / deinit                                                    |
//+------------------------------------------------------------------+
int OnInit()
{
   g_isTester = (bool)MQLInfoInteger(MQL_TESTER);
   g_visual   = (bool)MQLInfoInteger(MQL_VISUAL_MODE);
   g_gui      = (!g_isTester || g_visual);      // no UI work in non-visual tester runs
   g_t0       = TimeCurrent();
   if(g_t0 == 0) g_t0 = TimeLocal();

   g_dark      = InpDarkMode;
   g_timeMode  = InpTimeMode;
   g_pxPerSec  = MathMax(0.5, MathMin(2000.0, InpPxPerSecond));
   g_tpOn      = InpTPOn;
   g_slOn      = InpSLOn;
   g_tpPts     = MathMax(1, InpTPPoints);
   g_slPts     = MathMax(1, InpSLPoints);
   g_tpb       = MathMax(1, MathMin(InpMaxTicksPerBar, InpTicksPerBar));
   g_domShow   = InpDomShow;
   g_domLevel  = 0;
   g_domPct    = MathMax(8.0, MathMin(50.0, (double)InpDomWidthPct));
   LoadLayout();
   SymbolSelect(_Symbol, true);

   // filling mode
   int fm = (int)SymbolInfoInteger(_Symbol, SYMBOL_FILLING_MODE);
   if((fm & SYMBOL_FILLING_IOC) != 0)      g_fill = ORDER_FILLING_IOC;
   else if((fm & SYMBOL_FILLING_FOK) != 0) g_fill = ORDER_FILLING_FOK;
   else                                    g_fill = ORDER_FILLING_RETURN;

   // lot digits
   double st = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   g_lotDigits = 0;
   while(st > 0 && g_lotDigits < 8 &&
         MathAbs(st * MathPow(10, g_lotDigits) - MathRound(st * MathPow(10, g_lotDigits))) > 1e-9)
      g_lotDigits++;
   g_lots = NormLots(InpLots);

   // static part of the trade request
   ZeroMemory(g_req);
   g_req.symbol       = _Symbol;
   g_req.deviation    = InpDeviation;
   g_req.magic        = InpMagic;
   g_req.type_filling = g_fill;

   if(g_gui)
   {
      // remember the user's chart settings
      g_oMode    = ChartGetInteger(0, CHART_MODE);
      g_oGrid    = ChartGetInteger(0, CHART_SHOW_GRID);
      g_oDate    = ChartGetInteger(0, CHART_SHOW_DATE_SCALE);
      g_oPrice   = ChartGetInteger(0, CHART_SHOW_PRICE_SCALE);
      g_oScroll  = ChartGetInteger(0, CHART_MOUSE_SCROLL);
      g_oFix     = ChartGetInteger(0, CHART_SCALEFIX);
      g_oLine    = ChartGetInteger(0, CHART_COLOR_CHART_LINE);
      g_oBack    = ChartGetInteger(0, CHART_COLOR_BACKGROUND);
      g_oMouseEv = ChartGetInteger(0, CHART_EVENT_MOUSE_MOVE);
      g_oOhlc    = ChartGetInteger(0, CHART_SHOW_OHLC);
      g_oHist    = ChartGetInteger(0, CHART_SHOW_TRADE_HISTORY);

      g_w = (int)ChartGetInteger(0, CHART_WIDTH_IN_PIXELS);
      g_h = (int)ChartGetInteger(0, CHART_HEIGHT_IN_PIXELS);
      if(g_w < 10) g_w = 800;
      if(g_h < 10) g_h = 600;
      if(!g_cv.CreateBitmapLabel(N_CV, 0, 0, g_w, g_h, COLOR_FORMAT_XRGB_NOALPHA))
      {
         Print("TickScalper: canvas creation failed");
         if(!g_isTester) return INIT_FAILED;
         g_gui = false;                          // tester: carry on without GUI
      }
   }

   if(g_gui)
   {
      // native chart stays ON (EA visible) as a silent fixed-scale background whose
      // price scale is kept equal to the tick chart's scale
      ChartSetInteger(0, CHART_SHOW, true);
      ChartSetInteger(0, CHART_MODE, CHART_LINE);
      ChartSetInteger(0, CHART_SHOW_GRID, false);
      ChartSetInteger(0, CHART_SHOW_DATE_SCALE, false);
      ChartSetInteger(0, CHART_SHOW_PRICE_SCALE, false);
      ChartSetInteger(0, CHART_SHOW_OHLC, false);
      ChartSetInteger(0, CHART_SHOW_TRADE_HISTORY, false);   // no deal arrows / history lines on the chart
      ChartSetInteger(0, CHART_MOUSE_SCROLL, false);
      ChartSetInteger(0, CHART_COLOR_BACKGROUND, cBg());
      ChartSetInteger(0, CHART_COLOR_CHART_LINE, cBg());
      ChartSetInteger(0, CHART_SCALEFIX, true);
      ChartSetInteger(0, CHART_EVENT_MOUSE_MOVE, true);

      ObjectSetInteger(0, N_CV, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, N_CV, OBJPROP_HIDDEN, true);
      g_cv.FontSet("Consolas", -90);
      ClampPanel();
      CreateUI();   // created after canvas so it sits on top

      if(g_domShow) DomSubscribe();
   }

   // preload history (live only; the tester feeds its own ticks)
   if(!g_isTester)
   {
      MqlTick tk[];
      int c = CopyTicks(_Symbol, tk, COPY_TICKS_ALL, 0, MathMax(0, InpPreloadTicks));
      for(int i = 0; i < c; i++) AddTick(tk[i].bid > 0 ? tk[i].bid : tk[i].last, tk[i].time_msc);
   }
   MqlTick now;
   if(SymbolInfoTick(_Symbol, now))
   {
      g_bid = now.bid; g_ask = now.ask;
      g_spreadPts = (now.ask - now.bid) / _Point;
   }

   RefreshLevels();
   if(g_gui)
   {
      UpdateStats();
      EventSetMillisecondTimer(MathMax(5, InpRenderMs));
      ChartRedraw();
   }
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   EventKillTimer();
   if(g_domOK) MarketBookRelease(_Symbol);
   if(!g_gui) return;
   SaveLayout();
   g_cv.Destroy();
   ObjectsDeleteAll(0, "TS_");
   // restore the user's chart settings
   ChartSetInteger(0, CHART_SCALEFIX, g_oFix);
   ChartSetInteger(0, CHART_MODE, g_oMode);
   ChartSetInteger(0, CHART_SHOW_GRID, g_oGrid);
   ChartSetInteger(0, CHART_SHOW_DATE_SCALE, g_oDate);
   ChartSetInteger(0, CHART_SHOW_PRICE_SCALE, g_oPrice);
   ChartSetInteger(0, CHART_SHOW_OHLC, g_oOhlc);
   ChartSetInteger(0, CHART_SHOW_TRADE_HISTORY, g_oHist);
   ChartSetInteger(0, CHART_MOUSE_SCROLL, g_oScroll);
   ChartSetInteger(0, CHART_COLOR_CHART_LINE, g_oLine);
   ChartSetInteger(0, CHART_COLOR_BACKGROUND, g_oBack);
   ChartSetInteger(0, CHART_EVENT_MOUSE_MOVE, g_oMouseEv);
   ChartSetInteger(0, CHART_SHOW, true);
   ChartRedraw();
}

//+------------------------------------------------------------------+
//| Events                                                           |
//+------------------------------------------------------------------+
void OnTick()
{
   MqlTick t;
   if(!SymbolInfoTick(_Symbol, t)) return;
   g_bid = t.bid; g_ask = t.ask;
   g_spreadPts = (t.ask - t.bid) / _Point;
   AddTick(t.bid > 0 ? t.bid : t.last, t.time_msc);
   g_dirty = true;   // ask-only ticks must still move the ASK line
   if(g_isTester && InpBtAuto) BtOnTick(t);
}

// depth-of-market update: only set a flag; the book is copied once per render
void OnBookEvent(const string &symbol)
{
   if(symbol != _Symbol) return;
   g_bookDirty = true;
   g_dirty = true;
}

void OnTimer()
{
   uint now = GetTickCount();
   if(g_note != "" && (now - g_noteMs) > 12000) { g_note = ""; g_dirty = true; }       // banner expires
   // subscribed but the broker never sent any levels: hide the DOM and say so
   if(g_domOK && g_domShow && !g_gotBook && !g_domFailed && (now - g_domSubMs) > 6000)
   {
      DomFail("no depth-of-market data received from the broker for " + _Symbol);
      DomRefreshButtons();
   }
   Render();
   // while the mouse is active over the chart, keep the native scale in sync (throttled)
   if(g_needSync && (GetTickCount() - g_lastMouseMs) < 5000) SyncNative(false);
}

// positions / pending orders changed
void OnTrade()
{
   RefreshLevels();
   if(g_gui) UpdateStats();   // skipped in non-visual tester runs (keeps tests fast)
}

// result of every async request arrives here
void OnTradeTransaction(const MqlTradeTransaction &trans,
                        const MqlTradeRequest &request,
                        const MqlTradeResult &result)
{
   if(trans.type != TRADE_TRANSACTION_REQUEST) return;
   uint rc = result.retcode;
   if(rc == TRADE_RETCODE_DONE || rc == TRADE_RETCODE_PLACED || rc == TRADE_RETCODE_DONE_PARTIAL)
      g_status = "";
   else
   {
      g_status = StringFormat("Rejected %u: %s", rc, result.comment);
      Print("TickScalper: request rejected. retcode=", rc, " comment=", result.comment);
   }
   g_dirty = true;
}

void OnChartEvent(const int id, const long &lparam, const double &dparam, const string &sparam)
{
   if(id == CHARTEVENT_MOUSE_MOVE)
   {
      OnMouse((int)lparam, (int)dparam, (uint)StringToInteger(sparam));
      return;
   }

   if(id == CHARTEVENT_OBJECT_CLICK)
   {
      // --- trading first: nothing may delay these ---
      if(sparam == N_BUY)       SendMarket(ORDER_TYPE_BUY);
      else if(sparam == N_SELL) SendMarket(ORDER_TYPE_SELL);
      else if(sparam == N_CB)   ClosePositions(1);
      else if(sparam == N_CS)   ClosePositions(2);
      else if(sparam == N_CP)   ClosePositions(3);
      else if(sparam == N_CA)   ClosePositions(0);
      // --- UI actions ---
      else if(sparam == N_PLUS)   { if(g_tpb * 2 <= InpMaxTicksPerBar) g_tpb *= 2; g_dirty = true; }
      else if(sparam == N_MINUS)  { if(g_tpb > 1) g_tpb /= 2; g_dirty = true; }
      else if(sparam == N_TPT)    { g_tpOn = !g_tpOn; SetToggle(N_TPT, "TP", g_tpOn); }
      else if(sparam == N_SLT)    { g_slOn = !g_slOn; SetToggle(N_SLT, "SL", g_slOn); }
      else if(sparam == N_TIMET)  { g_timeMode = !g_timeMode; SetToggle(N_TIMET, "Time", g_timeMode); g_dirty = true; }
      else if(sparam == N_AUTOY)
      {
         if(g_autoY) { g_manMax = g_vMax; g_manMin = g_vMin; g_autoY = false; }   // freeze current view
         else        g_autoY = true;
         SetToggle(N_AUTOY, "Y Auto", g_autoY);
         g_dirty = true;
      }
      else if(sparam == N_DOMB)                       // quick show / hide (also retries after a failure)
      {
         if(g_domShow && !g_domFailed) g_domShow = false;
         else { g_domShow = true; DomSubscribe(); }
         DomRefreshButtons();
         SaveLayout();
         g_dirty = true;
      }
      else if(sparam == N_DOML)                       // filter level: 1-10, 10-100, 1-100, 10-100 (compact)
      {
         g_domLevel = (g_domLevel + 1) % 4;
         DomRefreshButtons();
         SaveLayout();
         g_dirty = true;
      }
      else if(sparam == N_THEME)  { g_dark = !g_dark; ApplyTheme(); }
      else return;

      ObjectSetInteger(0, sparam, OBJPROP_STATE, false);
      return;
   }

   if(id == CHARTEVENT_OBJECT_ENDEDIT)
   {
      if(sparam == N_LOTS)
      {
         g_lots = NormLots(StringToDouble(ObjectGetString(0, sparam, OBJPROP_TEXT)));
         ObjectSetString(0, sparam, OBJPROP_TEXT, DoubleToString(g_lots, g_lotDigits));
      }
      else if(sparam == N_TPE)
      {
         g_tpPts = (int)MathMax(1, StringToInteger(ObjectGetString(0, sparam, OBJPROP_TEXT)));
         ObjectSetString(0, sparam, OBJPROP_TEXT, IntegerToString(g_tpPts));
      }
      else if(sparam == N_SLE)
      {
         g_slPts = (int)MathMax(1, StringToInteger(ObjectGetString(0, sparam, OBJPROP_TEXT)));
         ObjectSetString(0, sparam, OBJPROP_TEXT, IntegerToString(g_slPts));
      }
      else if(sparam == N_TIMEE)
      {
         g_pxPerSec = MathMax(0.5, MathMin(2000.0, StringToDouble(ObjectGetString(0, sparam, OBJPROP_TEXT))));
         ObjectSetString(0, sparam, OBJPROP_TEXT, DoubleToString(g_pxPerSec, 1));
         g_dirty = true;
      }
      return;
   }

   if(id == CHARTEVENT_CHART_CHANGE) ResizeCanvas();
}

//+------------------------------------------------------------------+
//| Custom optimisation criterion: net profit relative to drawdown   |
//+------------------------------------------------------------------+
double OnTester()
{
   double profit = TesterStatistics(STAT_PROFIT);
   double dd     = TesterStatistics(STAT_EQUITY_DD);
   return (dd > 0) ? profit / dd : profit;
}
//+------------------------------------------------------------------+
