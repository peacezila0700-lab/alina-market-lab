//+------------------------------------------------------------------+
//|                                                  GoldLevelMap.mq5 |
//|                                      Copyright 2026, Pavel Polikarpov |
//|                          https://www.mql5.com/en/users/krechet233 |
//+------------------------------------------------------------------+
#property copyright "Pavel Polikarpov"
#property link      "https://www.mql5.com/en/users/krechet233"
#property version   "1.10"
#property description "Gold Level Map: psychological round numbers with reaction statistics,"
#property description "prior day/week extremes and an ADR range budget."
#property description "Display only. It does not place, modify or close orders and it is not a trade signal."
#property indicator_chart_window
#property indicator_plots   0
#property indicator_buffers 0

//+------------------------------------------------------------------+
//| Inputs                                                             |
//+------------------------------------------------------------------+
input group "1. Round numbers"
input double InpMajorStep       = 0;      // Major step (0 = auto, typically 100 on gold)
input int    InpLevelsEachSide  = 4;      // Major levels drawn on each side of price
input bool   InpShowMidLevels   = true;   // Show mid levels (half of the major step, typically 50)
input bool   InpShowMinorLevels = false;  // Show minor levels (1/10 of the major step, typically 10)

input group "2. Prior extremes"
input bool   InpShowPDH         = true;   // Previous day high
input bool   InpShowPDL         = true;   // Previous day low
input bool   InpShowDayOpen     = true;   // Current day open
input bool   InpShowPWH         = true;   // Previous week high
input bool   InpShowPWL         = true;   // Previous week low
input bool   InpShowWeekOpen    = false;  // Current week open
input bool   InpShowPMH         = false;  // Previous month high
input bool   InpShowPML         = false;  // Previous month low

input group "3. Average daily range"
input int    InpAdrDays         = 14;     // ADR lookback, completed daily bars
input bool   InpShowAdrProjections = true; // Projected high/low = day open +/- ADR

input group "4. Reaction statistics"
input int    InpLookbackDays    = 60;     // Lookback for touch / bounce / break counts
input int    InpEpisodeBars     = 24;     // Max H1 bars to wait for a bounce or a break
input double InpBufferAtr       = 0.20;   // Decision buffer in H1 ATR units
input bool   InpShowReactionPanel = true; // Show the reaction table in the panel
input int    InpReactionRows    = 6;      // Rows in the reaction table

input group "5. Alerts (closed bar only)"
input bool   InpAlertMajor      = false;  // Alert when a closed bar touches a major level
input bool   InpAlertMid        = false;  // Alert when a closed bar touches a mid level
input bool   InpAlertPdhPdl     = false;  // Alert when a closed bar touches PDH or PDL
input bool   InpAlertPopup      = true;   // Terminal pop-up
input bool   InpAlertPush       = false;  // Push notification
input bool   InpAlertSound      = false;  // Sound
input string InpAlertSoundName  = "alert.wav"; // Sound file

input group "6. Display"
input bool   InpShowPanel       = true;   // Show the information panel
input bool   InpShowDistance    = true;   // Show price and distance on chart labels
input bool   InpAutoScale       = true;   // Scale panel font and width to the chart size
input ENUM_BASE_CORNER InpPanelCorner = CORNER_LEFT_UPPER; // Panel corner
input int    InpPanelX          = 12;     // Panel X offset, pixels
input int    InpPanelY          = 24;     // Panel Y offset, pixels
input int    InpPanelWidth      = 0;      // Panel width, pixels (0 = auto)
input int    InpFontSize        = 8;      // Base font size (auto-scale starts from this)
input string InpFontName        = "Consolas"; // Font
input int    InpLabelShiftBars  = 0;      // Label shift to the right, bars (0 = auto)
input int    InpLineWidthMajor  = 2;      // Major line width
input int    InpLineWidthMid    = 1;      // Mid line width
input int    InpLineWidthMinor  = 1;      // Minor line width

input group "7. Colors"
input color  InpColMajor        = C'232,196,86';   // Major level
input color  InpColMid          = C'88,168,214';   // Mid level
input color  InpColMinor        = C'62,68,80';     // Minor level
input color  InpColPdh          = C'224,98,92';    // PDH / PWH / PMH
input color  InpColPdl          = C'46,186,150';   // PDL / PWL / PML
input color  InpColOpen         = C'168,176,188';  // Day / week open
input color  InpColAdr          = C'148,136,200';  // ADR projections
input color  InpColPanelBg      = C'18,22,30';     // Panel background
input color  InpColPanelBd      = C'52,60,74';     // Panel border
input color  InpColHeaderBg     = C'28,34,46';     // Panel header background
input color  InpColPanelTx      = C'220,224,230';  // Panel text
input color  InpColPanelDim     = C'130,138,150';  // Panel secondary text
input color  InpColPanelAcc     = C'232,196,86';   // Panel accent

//+------------------------------------------------------------------+
//| Internal types                                                     |
//+------------------------------------------------------------------+
enum ELevelKind
  {
   KIND_MINOR = 0,
   KIND_MID   = 1,
   KIND_MAJOR = 2,
   KIND_PDH   = 3,
   KIND_PDL   = 4,
   KIND_DO    = 5,
   KIND_PWH   = 6,
   KIND_PWL   = 7,
   KIND_WO    = 8,
   KIND_PMH   = 9,
   KIND_PML   = 10,
   KIND_ADRH  = 11,
   KIND_ADRL  = 12
  };

struct SLevel
  {
   string     id;
   string     tag;
   double     price;
   ELevelKind kind;
   color      clr;
   int        width;
   ENUM_LINE_STYLE style;
  };

struct SReaction
  {
   double price;
   int    tests;
   int    bounces;
   int    breaks;
   int    open_ep;
  };

struct SExtremes
  {
   double   pdh, pdl, day_open;
   double   pwh, pwl, week_open;
   double   pmh, pml;
   double   adr;
   double   today_high, today_low, today_range;
   datetime day_start;
   bool     ready;
  };

//+------------------------------------------------------------------+
//| Globals                                                            |
//+------------------------------------------------------------------+
const string PREFIX    = "GLM_";
const string PANEL_BD  = "GLM_PANEL_BD";
const string PANEL_BG  = "GLM_PANEL_BG";
const string PANEL_HD  = "GLM_PANEL_HD";
const string PANEL_AC  = "GLM_PANEL_AC";
const int    MAX_LEVELS = 80;
const int    MAX_REACT  = 24;
const int    MAX_ROWS   = 36;

SLevel     g_levels[];
int        g_nlevels = 0;
SReaction  g_react[];
int        g_nreact  = 0;
SExtremes  g_ext;
double     g_major = 100.0;
double     g_mid   = 50.0;
double     g_minor = 10.0;
double     g_base  = 0.0;
int        g_hAtrH1 = INVALID_HANDLE;
datetime   g_last_h1 = 0;
datetime   g_last_d1 = 0;
datetime   g_last_tf = 0;
datetime   g_last_alert_day = 0;
double     g_last_bid = -1.0;
int        g_last_w = -1;
int        g_last_h = -1;
int        g_last_vis = -1;
int        g_font = 8;
int        g_label_font = 7;
int        g_line_h = 14;
int        g_panel_w = 308;
int        g_digits = 2;
double     g_point  = 0.01;
bool       g_inited = false;
string     g_alerted[];
int        g_nalerted = 0;

//+------------------------------------------------------------------+
int OnInit()
  {
   g_digits = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   g_point  = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   if(g_point <= 0.0)
      g_point = _Point;
   if(InpAdrDays < 2 || InpLookbackDays < 5 || InpLevelsEachSide < 1)
     {
      Print("Gold Level Map: ADR days must be >= 2, lookback days >= 5, levels each side >= 1.");
      return(INIT_PARAMETERS_INCORRECT);
     }
   if(InpFontSize < 6 || InpFontSize > 20)
     {
      Print("Gold Level Map: font size must be between 6 and 20.");
      return(INIT_PARAMETERS_INCORRECT);
     }

   g_hAtrH1 = iATR(_Symbol, PERIOD_H1, 14);
   if(g_hAtrH1 == INVALID_HANDLE)
     {
      Print("Gold Level Map: failed to create the H1 ATR handle.");
      return(INIT_FAILED);
     }

   ArrayResize(g_levels, MAX_LEVELS);
   ArrayResize(g_react, MAX_REACT);
   ArrayResize(g_alerted, 64);
   ZeroMemory(g_ext);
   g_inited = false;
   g_last_bid = -1.0;
   g_last_w = -1;
   IndicatorSetString(INDICATOR_SHORTNAME, "Gold Level Map");
   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   ObjectsDeleteAll(0, PREFIX);
   if(g_hAtrH1 != INVALID_HANDLE)
     {
      IndicatorRelease(g_hAtrH1);
      g_hAtrH1 = INVALID_HANDLE;
     }
   g_inited = false;
   ChartRedraw(0);
  }

//+------------------------------------------------------------------+
void OnChartEvent(const int id, const long &lparam, const double &dparam, const string &sparam)
  {
   if(id != CHARTEVENT_CHART_CHANGE || !g_inited || !g_ext.ready)
      return;
   const int w = (int)ChartGetInteger(0, CHART_WIDTH_IN_PIXELS);
   const int h = (int)ChartGetInteger(0, CHART_HEIGHT_IN_PIXELS);
   const int v = (int)ChartGetInteger(0, CHART_VISIBLE_BARS);
   if(w == g_last_w && h == g_last_h && v == g_last_vis)
      return;
   g_last_w = w;
   g_last_h = h;
   g_last_vis = v;
   UpdateScale();
   UpdateLevelLabels();
   if(InpShowPanel)
      DrawPanel();
   else
      ChartRedraw(0);
  }

//+------------------------------------------------------------------+
int OnCalculate(const int rates_total,
                const int prev_calculated,
                const datetime &time[],
                const double &open[],
                const double &high[],
                const double &low[],
                const double &close[],
                const long &tick_volume[],
                const long &volume[],
                const int &spread[])
  {
   if(rates_total < 3)
      return(0);

   const datetime t_h1 = iTime(_Symbol, PERIOD_H1, 0);
   const datetime t_d1 = iTime(_Symbol, PERIOD_D1, 0);
   const datetime t_tf = time[rates_total - 1];
   const double bid = NormalizeDouble(BidSafe(), g_digits);
   const int chart_w = (int)ChartGetInteger(0, CHART_WIDTH_IN_PIXELS);
   const int chart_h = (int)ChartGetInteger(0, CHART_HEIGHT_IN_PIXELS);
   const int vis = (int)ChartGetInteger(0, CHART_VISIBLE_BARS);

   const bool first = (prev_calculated == 0 || !g_inited);
   const bool new_h1 = (t_h1 != 0 && t_h1 != g_last_h1);
   const bool new_d1 = (t_d1 != 0 && t_d1 != g_last_d1);
   const bool new_tf = (t_tf != 0 && t_tf != g_last_tf);
   const bool bid_changed = (bid > 0.0 && bid != g_last_bid);
   const bool layout_changed = (chart_w != g_last_w || chart_h != g_last_h || vis != g_last_vis);

   if(!first && !new_h1 && !new_d1 && !new_tf && !bid_changed && !layout_changed)
      return(rates_total);

   if(first || layout_changed)
      UpdateScale();

   if(first || new_d1)
      ResolveSteps();

   if(first || new_d1)
      BuildExtremes();
   else if(bid_changed || new_tf)
      RefreshTodayRange();

   bool window_changed = false;
   if(g_major > 0.0 && bid > 0.0)
     {
      const double base = MathFloor(bid / g_major) * g_major;
      if(first || base != g_base)
        {
         g_base = base;
         window_changed = !first;
        }
     }

   if(g_ext.ready && (first || new_d1 || window_changed))
      BuildLevels();

   if(g_ext.ready && (first || new_h1 || new_d1 || window_changed))
      BuildReactions();

   const bool rebuild_objects = (first || new_d1 || window_changed);
   const bool refresh_labels  = (rebuild_objects || bid_changed || layout_changed || new_tf);
   const bool refresh_panel   = (InpShowPanel && (refresh_labels || new_h1 || new_d1));

   if(g_ext.ready)
     {
      if(rebuild_objects)
         SyncLevelObjects();
      if(refresh_labels)
         UpdateLevelLabels();
      if(refresh_panel)
         DrawPanel();
      else if(refresh_labels)
         ChartRedraw(0);
      if(first || new_tf)
         CheckAlerts();
     }

   if(t_h1 != 0) g_last_h1 = t_h1;
   if(t_d1 != 0) g_last_d1 = t_d1;
   if(t_tf != 0) g_last_tf = t_tf;
   if(bid  > 0.0) g_last_bid = bid;
   g_last_w = chart_w;
   g_last_h = chart_h;
   g_last_vis = vis;
   g_inited = true;
   return(rates_total);
  }

//+------------------------------------------------------------------+
void UpdateScale()
  {
   int base = InpFontSize;
   if(base < 6)  base = 6;
   if(base > 20) base = 20;
   if(InpAutoScale)
     {
      const int cw = (int)ChartGetInteger(0, CHART_WIDTH_IN_PIXELS);
      if(cw > 0)
        {
         const double sc = MathMax(0.85, MathMin(1.35, cw / 1280.0));
         base = (int)MathRound(base * sc);
         if(base < 7)  base = 7;
         if(base > 14) base = 14;
        }
     }
   g_font = base;
   g_label_font = MathMax(7, g_font - 1);
   g_line_h = g_font + 6;
   if(InpPanelWidth > 80)
      g_panel_w = InpPanelWidth;
   else
      g_panel_w = 16 + 44 * MathMax(6, (int)MathRound(g_font * 0.62));
  }

//+------------------------------------------------------------------+
double NiceStep(const double raw)
  {
   if(raw <= 0.0)
      return(1.0);
   const double e = MathPow(10.0, MathFloor(MathLog10(raw)));
   const double m = raw / e;
   if(m < 1.5) return(e);
   if(m < 3.5) return(2.0 * e);
   if(m < 7.5) return(5.0 * e);
   return(10.0 * e);
  }

void ResolveSteps()
  {
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   if(bid <= 0.0)
      bid = iClose(_Symbol, PERIOD_D1, 0);
   if(bid <= 0.0)
      bid = 1000.0;

   if(InpMajorStep > 0.0)
      g_major = InpMajorStep;
   else
      g_major = NiceStep(bid * 0.025);

   g_mid   = g_major / 2.0;
   g_minor = g_major / 10.0;
   if(g_point > 0.0)
     {
      g_major = MathMax(g_point, NormalizeDouble(g_major, g_digits));
      g_mid   = MathMax(g_point, NormalizeDouble(g_mid,   g_digits));
      g_minor = MathMax(g_point, NormalizeDouble(g_minor, g_digits));
     }
  }

//+------------------------------------------------------------------+
double CompletedAdr()
  {
   const int need = InpAdrDays + 1;
   if(iBars(_Symbol, PERIOD_D1) < need)
      return(0.0);
   double sum = 0.0;
   int    n   = 0;
   for(int i = 1; i <= InpAdrDays; i++)
     {
      const double h = iHigh(_Symbol, PERIOD_D1, i);
      const double l = iLow (_Symbol, PERIOD_D1, i);
      if(h > 0.0 && l > 0.0 && h >= l)
        {
         sum += (h - l);
         n++;
        }
     }
   if(n == 0)
      return(0.0);
   return(sum / n);
  }

void BuildExtremes()
  {
   ZeroMemory(g_ext);
   if(iBars(_Symbol, PERIOD_D1) < InpAdrDays + 2)
      return;

   g_ext.pdh        = iHigh(_Symbol, PERIOD_D1, 1);
   g_ext.pdl        = iLow (_Symbol, PERIOD_D1, 1);
   g_ext.day_open   = iOpen(_Symbol, PERIOD_D1, 0);
   g_ext.today_high = iHigh(_Symbol, PERIOD_D1, 0);
   g_ext.today_low  = iLow (_Symbol, PERIOD_D1, 0);
   g_ext.day_start  = iTime(_Symbol, PERIOD_D1, 0);
   if(g_ext.today_high > 0.0 && g_ext.today_low > 0.0)
      g_ext.today_range = g_ext.today_high - g_ext.today_low;

   if(iBars(_Symbol, PERIOD_W1) >= 2)
     {
      g_ext.pwh       = iHigh(_Symbol, PERIOD_W1, 1);
      g_ext.pwl       = iLow (_Symbol, PERIOD_W1, 1);
      g_ext.week_open = iOpen(_Symbol, PERIOD_W1, 0);
     }
   if(iBars(_Symbol, PERIOD_MN1) >= 2)
     {
      g_ext.pmh = iHigh(_Symbol, PERIOD_MN1, 1);
      g_ext.pml = iLow (_Symbol, PERIOD_MN1, 1);
     }
   g_ext.adr   = CompletedAdr();
   g_ext.ready = (g_ext.day_open > 0.0 && g_ext.adr > 0.0);
  }

void RefreshTodayRange()
  {
   const double h = iHigh(_Symbol, PERIOD_D1, 0);
   const double l = iLow (_Symbol, PERIOD_D1, 0);
   if(h > 0.0 && l > 0.0)
     {
      g_ext.today_high  = h;
      g_ext.today_low   = l;
      g_ext.today_range = h - l;
     }
  }

//+------------------------------------------------------------------+
void AddLevel(const string id, const string tag, const double price,
              const ELevelKind kind, const color clr, const int width,
              const ENUM_LINE_STYLE style)
  {
   if(g_nlevels >= MAX_LEVELS || price <= 0.0)
      return;
   for(int i = 0; i < g_nlevels; i++)
     {
      if(MathAbs(g_levels[i].price - price) < g_point * 0.5)
         return;
     }
   SLevel z;
   z.id    = id;
   z.tag   = tag;
   z.price = NormalizeDouble(price, g_digits);
   z.kind  = kind;
   z.clr   = clr;
   z.width = width;
   z.style = style;
   g_levels[g_nlevels++] = z;
  }

void BuildLevels()
  {
   g_nlevels = 0;
   const double bid = (BidSafe() > 0.0 ? BidSafe() : g_ext.day_open);
   if(bid <= 0.0 || g_major <= 0.0)
      return;

   const double base = MathFloor(bid / g_major) * g_major;
   const int side = MathMax(1, InpLevelsEachSide);

   for(int k = -side; k <= side; k++)
     {
      const double major = base + k * g_major;
      if(major <= 0.0)
         continue;
      AddLevel("MAJ_"+DoubleToString(major, g_digits),
               "00", major, KIND_MAJOR, InpColMajor, InpLineWidthMajor, STYLE_SOLID);

      if(InpShowMidLevels && k < side)
        {
         const double mid = major + g_mid;
         if(mid > 0.0)
            AddLevel("MID_"+DoubleToString(mid, g_digits),
                     "50", mid, KIND_MID, InpColMid, InpLineWidthMid, STYLE_SOLID);
        }
      if(InpShowMidLevels && k == -side)
        {
         const double mid_below = major - g_mid;
         if(mid_below > 0.0)
            AddLevel("MID_"+DoubleToString(mid_below, g_digits),
                     "50", mid_below, KIND_MID, InpColMid, InpLineWidthMid, STYLE_SOLID);
        }

      if(InpShowMinorLevels)
        {
         for(int m = 1; m <= 9; m++)
           {
            const double minor = major + m * g_minor;
            if(minor <= 0.0)
               continue;
            if(InpShowMidLevels && MathAbs(minor - (major + g_mid)) < g_point * 0.5)
               continue;
            AddLevel("MIN_"+DoubleToString(minor, g_digits),
                     "", minor, KIND_MINOR, InpColMinor, InpLineWidthMinor, STYLE_DOT);
           }
        }
     }

   AttachOrMerge("PDH", "PDH", g_ext.pdh, KIND_PDH, InpColPdh, 2, STYLE_SOLID, InpShowPDH);
   AttachOrMerge("PDL", "PDL", g_ext.pdl, KIND_PDL, InpColPdl, 2, STYLE_SOLID, InpShowPDL);
   AttachOrMerge("DO",  "Open", g_ext.day_open, KIND_DO, InpColOpen, 1, STYLE_DASH, InpShowDayOpen);
   AttachOrMerge("PWH", "PWH", g_ext.pwh, KIND_PWH, InpColPdh, 1, STYLE_DASHDOT, InpShowPWH);
   AttachOrMerge("PWL", "PWL", g_ext.pwl, KIND_PWL, InpColPdl, 1, STYLE_DASHDOT, InpShowPWL);
   AttachOrMerge("WO",  "WOpen", g_ext.week_open, KIND_WO, InpColOpen, 1, STYLE_DOT, InpShowWeekOpen);
   AttachOrMerge("PMH", "PMH", g_ext.pmh, KIND_PMH, InpColPdh, 1, STYLE_DASHDOTDOT, InpShowPMH);
   AttachOrMerge("PML", "PML", g_ext.pml, KIND_PML, InpColPdl, 1, STYLE_DASHDOTDOT, InpShowPML);

   if(InpShowAdrProjections && g_ext.adr > 0.0 && g_ext.day_open > 0.0)
     {
      AttachOrMerge("ADRH", "ADR H", g_ext.day_open + g_ext.adr, KIND_ADRH, InpColAdr, 1, STYLE_DOT, true);
      AttachOrMerge("ADRL", "ADR L", g_ext.day_open - g_ext.adr, KIND_ADRL, InpColAdr, 1, STYLE_DOT, true);
     }
  }

void AttachOrMerge(const string id, const string tag, const double price,
                   const ELevelKind kind, const color clr, const int width,
                   const ENUM_LINE_STYLE style, const bool enabled)
  {
   if(!enabled || price <= 0.0)
      return;
   for(int i = 0; i < g_nlevels; i++)
     {
      if(MathAbs(g_levels[i].price - price) < g_point * 0.5)
        {
         if(StringLen(g_levels[i].tag) > 0)
            g_levels[i].tag = tag + "/" + g_levels[i].tag;
         else
            g_levels[i].tag = tag;
         if(kind == KIND_PDH || kind == KIND_PDL || kind == KIND_PWH || kind == KIND_PWL)
           {
            g_levels[i].clr   = clr;
            g_levels[i].width = MathMax(g_levels[i].width, width);
            g_levels[i].kind  = kind;
           }
         return;
        }
     }
   AddLevel(id, tag, price, kind, clr, width, style);
  }

//+------------------------------------------------------------------+
//| Reaction statistics on closed H1 bars only.                        |
//| A test starts when a closed H1 bar first trades through the level  |
//| after price has been away from it. Then:                           |
//|   bounce — close back on the approach side by the ATR buffer;      |
//|   break  — close through the level by the ATR buffer;              |
//|   open   — the bar budget ran out. Open episodes are excluded      |
//|            from the bounce rate.                                   |
//+------------------------------------------------------------------+
double CurrentAtrH1()
  {
   double buf[];
   ArraySetAsSeries(buf, true);
   if(CopyBuffer(g_hAtrH1, 0, 1, 1, buf) < 1)
      return(0.0);
   return(buf[0]);
  }

void BuildReactions()
  {
   g_nreact = 0;
   if(!InpShowReactionPanel || !InpShowPanel)
      return;

   const int days = MathMax(5, InpLookbackDays);
   const int need = days * 28 + InpEpisodeBars + 5;
   const int bars = iBars(_Symbol, PERIOD_H1);
   if(bars < 30)
      return;

   const datetime now_h1 = iTime(_Symbol, PERIOD_H1, 0);
   if(now_h1 == 0)
      return;
   const datetime from = now_h1 - (datetime)days * 86400;
   int shift_from = bars - 1;
   for(int s = 1; s < bars; s++)
     {
      const datetime t = iTime(_Symbol, PERIOD_H1, s);
      if(t == 0)
         continue;
      if(t < from)
        {
         shift_from = s - 1;
         break;
        }
      shift_from = s;
     }
   shift_from = MathMin(shift_from, MathMin(bars - 2, need));
   if(shift_from < 10)
      return;

   const double atr = CurrentAtrH1();
   const double buf = MathMax(g_point, InpBufferAtr * (atr > 0.0 ? atr : g_major * 0.02));

   double prices[];
   ArrayResize(prices, 0);
   for(int i = 0; i < g_nlevels; i++)
     {
      if(g_levels[i].kind != KIND_MAJOR && g_levels[i].kind != KIND_MID)
         continue;
      const int m = ArraySize(prices);
      ArrayResize(prices, m + 1);
      prices[m] = g_levels[i].price;
     }
   if(ArraySize(prices) == 0)
      return;

   for(int p = 0; p < ArraySize(prices) && g_nreact < MAX_REACT; p++)
     {
      SReaction r;
      r.price   = prices[p];
      r.tests   = 0;
      r.bounces = 0;
      r.breaks  = 0;
      r.open_ep = 0;
      ScoreLevel(r, shift_from, buf);
      g_react[g_nreact++] = r;
     }
  }

void ScoreLevel(SReaction &r, const int shift_from, const double buf)
  {
   const double L = r.price;
   const int max_wait = MathMax(3, InpEpisodeBars);
   int s = shift_from;

   while(s >= 2)
     {
      const double hi = iHigh(_Symbol, PERIOD_H1, s);
      const double lo = iLow (_Symbol, PERIOD_H1, s);
      const double cl = iClose(_Symbol, PERIOD_H1, s + 1);
      if(hi <= 0.0 || lo <= 0.0)
        {
         s--;
         continue;
        }
      const bool touched = (hi >= L && lo <= L);
      if(!touched)
        {
         s--;
         continue;
        }

      int approach = 0;
      if(cl > 0.0 && cl < L - buf * 0.25)
         approach = -1;
      else if(cl > L + buf * 0.25)
         approach = +1;
      else
        {
         s--;
         continue;
        }

      r.tests++;
      int decision = 0;
      int waited   = 0;
      int k        = s;
      while(k >= 1 && waited <= max_wait)
        {
         const double ck = iClose(_Symbol, PERIOD_H1, k);
         if(ck > 0.0)
           {
            if(approach < 0)
              {
               if(ck >= L + buf) { decision = -1; break; }
               if(ck <= L - buf) { decision = +1; break; }
              }
            else
              {
               if(ck <= L - buf) { decision = -1; break; }
               if(ck >= L + buf) { decision = +1; break; }
              }
           }
         waited++;
         k--;
        }

      if(decision > 0)      r.bounces++;
      else if(decision < 0) r.breaks++;
      else                  r.open_ep++;

      s = (k >= 1 ? k - 1 : 0);
     }
  }

//+------------------------------------------------------------------+
string LineName(const SLevel &z) { return(PREFIX + "L_" + z.id); }
string TextName(const SLevel &z) { return(PREFIX + "T_" + z.id); }

string LevelCaption(const SLevel &z, const double bid)
  {
   string tag = z.tag;
   if(StringLen(tag) == 0)
      tag = DoubleToString(z.price, g_digits);
   string s = " " + tag + "  " + DoubleToString(z.price, g_digits);
   if(InpShowDistance && bid > 0.0 && z.kind != KIND_MINOR)
      s += "  " + SignedPrice(z.price - bid);
   return(s);
  }

void SyncLevelObjects()
  {
   const int total = ObjectsTotal(0, -1, -1);
   for(int i = total - 1; i >= 0; i--)
     {
      const string name = ObjectName(0, i, -1, -1);
      if(StringFind(name, PREFIX + "L_") != 0 && StringFind(name, PREFIX + "T_") != 0)
         continue;
      bool keep = false;
      for(int k = 0; k < g_nlevels; k++)
        {
         if(name == LineName(g_levels[k]) || name == TextName(g_levels[k]))
           {
            keep = true;
            break;
           }
        }
      if(!keep)
         ObjectDelete(0, name);
     }

   for(int i = 0; i < g_nlevels; i++)
     {
      const SLevel z = g_levels[i];
      const string ln = LineName(z);
      if(ObjectFind(0, ln) < 0)
        {
         ObjectCreate(0, ln, OBJ_HLINE, 0, 0, z.price);
         ObjectSetInteger(0, ln, OBJPROP_SELECTABLE, false);
         ObjectSetInteger(0, ln, OBJPROP_HIDDEN, true);
         ObjectSetInteger(0, ln, OBJPROP_BACK, true);
         ObjectSetInteger(0, ln, OBJPROP_ZORDER, 0);
        }
      ObjectSetDouble (0, ln, OBJPROP_PRICE, z.price);
      ObjectSetInteger(0, ln, OBJPROP_COLOR, z.clr);
      ObjectSetInteger(0, ln, OBJPROP_STYLE, z.style);
      ObjectSetInteger(0, ln, OBJPROP_WIDTH, z.width);
      ObjectSetString (0, ln, OBJPROP_TOOLTIP, LevelCaption(z, BidSafe()));

      const string tn = TextName(z);
      if(ObjectFind(0, tn) < 0)
        {
         ObjectCreate(0, tn, OBJ_TEXT, 0, TimeCurrent(), z.price);
         ObjectSetInteger(0, tn, OBJPROP_SELECTABLE, false);
         ObjectSetInteger(0, tn, OBJPROP_HIDDEN, true);
         ObjectSetInteger(0, tn, OBJPROP_ANCHOR, ANCHOR_LEFT_LOWER);
         ObjectSetInteger(0, tn, OBJPROP_BACK, false);
         ObjectSetInteger(0, tn, OBJPROP_ZORDER, 1);
        }
     }
  }

datetime LabelTime()
  {
   datetime t0 = iTime(_Symbol, _Period, 0);
   if(t0 == 0)
      t0 = TimeCurrent();
   const int sec = PeriodSeconds(_Period);
   if(sec <= 0)
      return(t0);
   int shift = InpLabelShiftBars;
   if(shift <= 0)
     {
      const int vis = (int)ChartGetInteger(0, CHART_VISIBLE_BARS);
      shift = MathMax(6, vis / 16);
     }
   return(t0 + (datetime)sec * shift);
  }

void UpdateLevelLabels()
  {
   const double bid = BidSafe();
   const datetime tlab = LabelTime();
   for(int i = 0; i < g_nlevels; i++)
     {
      const SLevel z = g_levels[i];
      const string tn = TextName(z);
      const string cap = LevelCaption(z, bid);
      if(ObjectFind(0, tn) < 0)
         continue;
      ObjectSetInteger(0, tn, OBJPROP_TIME, tlab);
      ObjectSetDouble (0, tn, OBJPROP_PRICE, z.price);
      ObjectSetInteger(0, tn, OBJPROP_COLOR, z.clr);
      ObjectSetInteger(0, tn, OBJPROP_FONTSIZE, g_label_font);
      ObjectSetString (0, tn, OBJPROP_FONT, InpFontName);
      ObjectSetString (0, tn, OBJPROP_TEXT, cap);
      ObjectSetString (0, LineName(z), OBJPROP_TOOLTIP, cap);
     }
  }

//+------------------------------------------------------------------+
string PadR(string s, const int width)
  {
   while(StringLen(s) < width)
      s += " ";
   return(s);
  }

string PadL(string s, const int width)
  {
   while(StringLen(s) < width)
      s = " " + s;
   return(s);
  }

string SignedPrice(const double v)
  {
   const string s = DoubleToString(MathAbs(v), g_digits);
   if(v > 0.0) return("+" + s);
   if(v < 0.0) return("-" + s);
   return(s);
  }

string Pct(const int num, const int den)
  {
   if(den <= 0)
      return("  n/a");
   return(PadL(IntegerToString((int)MathRound(100.0 * num / den)), 3) + "%");
  }

double BidSafe()
  {
   double b = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   if(b <= 0.0)
      b = iClose(_Symbol, _Period, 0);
   return(b);
  }

int NearestIndex(const ELevelKind kind_a, const ELevelKind kind_b, const double bid)
  {
   int best = -1;
   double best_d = 1.0e100;
   for(int i = 0; i < g_nlevels; i++)
     {
      if(g_levels[i].kind != kind_a && g_levels[i].kind != kind_b)
         continue;
      const double d = MathAbs(g_levels[i].price - bid);
      if(d < best_d)
        {
         best_d = d;
         best = i;
        }
     }
   return(best);
  }

string LineDist(const string name, const double price, const double bid, const double atr)
  {
   if(price <= 0.0)
      return(PadR(name, 11) + "  n/a");
   string s = PadR(name, 11) +
              PadL(DoubleToString(price, g_digits), 10) + "  " +
              PadL(SignedPrice(price - bid), 10);
   if(atr > 0.0)
      s += "  " + DoubleToString(MathAbs(price - bid) / atr, 1) + " ATR";
   return(s);
  }

string Tfs()
  {
   switch(_Period)
     {
      case PERIOD_M1:  return("M1");
      case PERIOD_M5:  return("M5");
      case PERIOD_M15: return("M15");
      case PERIOD_M30: return("M30");
      case PERIOD_H1:  return("H1");
      case PERIOD_H4:  return("H4");
      case PERIOD_D1:  return("D1");
      case PERIOD_W1:  return("W1");
      case PERIOD_MN1: return("MN1");
      default:         return(EnumToString(_Period));
     }
  }

string Rule(const int n)
  {
   string s = "";
   for(int i = 0; i < n; i++)
      s += "-";
   return(s);
  }

//+------------------------------------------------------------------+
void DrawPanel()
  {
   const double bid = BidSafe();
   const double atr = CurrentAtrH1();

   string row[];
   color  col[];
   ArrayResize(row, MAX_ROWS);
   ArrayResize(col, MAX_ROWS);
   int n = 0;

   const int i00 = NearestIndex(KIND_MAJOR, KIND_MAJOR, bid);
   const int i50 = NearestIndex(KIND_MID,   KIND_MID,   bid);
   if(i00 >= 0)
     { row[n] = LineDist("Nearest 00", g_levels[i00].price, bid, atr); col[n] = InpColMajor; n++; }
   if(i50 >= 0)
     { row[n] = LineDist("Nearest 50", g_levels[i50].price, bid, atr); col[n] = InpColMid; n++; }

   row[n] = Rule(42);
   col[n] = InpColPanelBd; n++;

   const double used = (g_ext.adr > 0.0 ? 100.0 * g_ext.today_range / g_ext.adr : 0.0);
   const double left = MathMax(0.0, g_ext.adr - g_ext.today_range);
   row[n] = "ADR(" + IntegerToString(InpAdrDays) + ")   " +
            DoubleToString(g_ext.adr, g_digits) +
            "   used " + DoubleToString(used, 0) + "%" +
            "   left " + DoubleToString(left, g_digits);
   col[n] = InpColPanelTx; n++;
   row[n] = "Today      H " + DoubleToString(g_ext.today_high, g_digits) +
            "  L " + DoubleToString(g_ext.today_low, g_digits) +
            "  R " + DoubleToString(g_ext.today_range, g_digits);
   col[n] = InpColPanelDim; n++;
   if(InpShowAdrProjections && g_ext.day_open > 0.0)
     {
      row[n] = "ADR band   " + DoubleToString(g_ext.day_open - g_ext.adr, g_digits) +
               "  ..  " + DoubleToString(g_ext.day_open + g_ext.adr, g_digits);
      col[n] = InpColAdr; n++;
     }

   row[n] = Rule(42);
   col[n] = InpColPanelBd; n++;

   if(InpShowPDH)
     { row[n] = LineDist("PDH", g_ext.pdh, bid, atr); col[n] = InpColPdh; n++; }
   if(InpShowPDL)
     { row[n] = LineDist("PDL", g_ext.pdl, bid, atr); col[n] = InpColPdl; n++; }
   if(InpShowPWH)
     { row[n] = LineDist("PWH", g_ext.pwh, bid, atr); col[n] = InpColPdh; n++; }
   if(InpShowPWL)
     { row[n] = LineDist("PWL", g_ext.pwl, bid, atr); col[n] = InpColPdl; n++; }

   if(InpShowReactionPanel)
     {
      row[n] = Rule(42);
      col[n] = InpColPanelBd; n++;
      row[n] = "Reactions  last " + IntegerToString(InpLookbackDays) + " days, H1";
      col[n] = InpColPanelAcc; n++;
      row[n] = "Level        Tests  Bounce  Break  Rate";
      col[n] = InpColPanelDim; n++;

      int order[];
      ArrayResize(order, g_nreact);
      for(int i = 0; i < g_nreact; i++)
         order[i] = i;
      for(int a = 0; a < g_nreact; a++)
         for(int b = a + 1; b < g_nreact; b++)
            if(MathAbs(g_react[order[b]].price - bid) < MathAbs(g_react[order[a]].price - bid))
              {
               const int tmp = order[a];
               order[a] = order[b];
               order[b] = tmp;
              }

      const int take = MathMin(MathMax(1, InpReactionRows), g_nreact);
      for(int i = 0; i < take && n < MAX_ROWS - 1; i++)
        {
         const SReaction r = g_react[order[i]];
         const int decided = r.bounces + r.breaks;
         row[n] = PadR(DoubleToString(r.price, g_digits), 11) +
                  PadL(IntegerToString(r.tests), 7) +
                  PadL(IntegerToString(r.bounces), 8) +
                  PadL(IntegerToString(r.breaks), 7) + "  " +
                  Pct(r.bounces, decided);
         col[n] = InpColPanelTx; n++;
        }
     }

   row[n] = "Display only. Not a trade signal.";
   col[n] = InpColPanelDim; n++;

   const int header_h = g_line_h + 8;
   const int body_h   = 8 + n * g_line_h + 8;
   const int panel_h  = header_h + body_h;
   const int x = InpPanelX;
   const int y = InpPanelY;

   EnsureRect(PANEL_BD, x - 1, y - 1, g_panel_w + 2, panel_h + 2, InpColPanelBd, 50);
   EnsureRect(PANEL_BG, x, y, g_panel_w, panel_h, InpColPanelBg, 51);
   EnsureRect(PANEL_HD, x, y, g_panel_w, header_h, InpColHeaderBg, 52);
   EnsureRect(PANEL_AC, x, y + header_h - 1, g_panel_w, 1, InpColPanelAcc, 53);

   const string title = "GOLD LEVEL MAP";
   const string sub   = _Symbol + "  " + Tfs() + "   " + DoubleToString(bid, g_digits);
   PutLabel(PREFIX + "P_TITLE", x + 10, y + 4, title, InpColPanelAcc, g_font);
   PutLabel(PREFIX + "P_PRICE", x + 10, y + 4 + g_font + 1, sub, InpColPanelTx, g_font);

   const int body_y = y + header_h + 6;
   for(int i = 0; i < n; i++)
      PutLabel(PREFIX + "P_" + IntegerToString(i),
               x + 10,
               body_y + i * g_line_h,
               row[i], col[i], g_font);

   for(int i = n; i < MAX_ROWS; i++)
      ObjectDelete(0, PREFIX + "P_" + IntegerToString(i));

   ChartRedraw(0);
  }

void EnsureRect(const string name, const int x, const int y, const int w, const int h,
                const color clr, const int zorder)
  {
   if(ObjectFind(0, name) < 0)
     {
      ObjectCreate(0, name, OBJ_RECTANGLE_LABEL, 0, 0, 0);
      ObjectSetInteger(0, name, OBJPROP_BORDER_TYPE, BORDER_FLAT);
      ObjectSetInteger(0, name, OBJPROP_BACK, false);
      ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
     }
   ObjectSetInteger(0, name, OBJPROP_CORNER, InpPanelCorner);
   ObjectSetInteger(0, name, OBJPROP_XDISTANCE, x);
   ObjectSetInteger(0, name, OBJPROP_YDISTANCE, y);
   ObjectSetInteger(0, name, OBJPROP_XSIZE, w);
   ObjectSetInteger(0, name, OBJPROP_YSIZE, MathMax(1, h));
   ObjectSetInteger(0, name, OBJPROP_BGCOLOR, clr);
   ObjectSetInteger(0, name, OBJPROP_BORDER_COLOR, clr);
   ObjectSetInteger(0, name, OBJPROP_ZORDER, zorder);
  }

void PutLabel(const string name, const int x, const int y, const string text,
              const color clr, const int font_size)
  {
   if(ObjectFind(0, name) < 0)
     {
      ObjectCreate(0, name, OBJ_LABEL, 0, 0, 0);
      ObjectSetInteger(0, name, OBJPROP_ANCHOR, ANCHOR_LEFT_UPPER);
      ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
      ObjectSetInteger(0, name, OBJPROP_ZORDER, 60);
     }
   ObjectSetInteger(0, name, OBJPROP_CORNER, InpPanelCorner);
   ObjectSetInteger(0, name, OBJPROP_XDISTANCE, x);
   ObjectSetInteger(0, name, OBJPROP_YDISTANCE, y);
   ObjectSetInteger(0, name, OBJPROP_COLOR, clr);
   ObjectSetInteger(0, name, OBJPROP_FONTSIZE, font_size);
   ObjectSetString (0, name, OBJPROP_FONT, InpFontName);
   ObjectSetString (0, name, OBJPROP_TEXT, text);
  }

//+------------------------------------------------------------------+
void CheckAlerts()
  {
   if(!InpAlertMajor && !InpAlertMid && !InpAlertPdhPdl)
      return;
   if(iBars(_Symbol, _Period) < 3)
      return;

   const datetime bar_t = iTime(_Symbol, _Period, 1);
   const datetime day_t = iTime(_Symbol, PERIOD_D1, 0);
   if(bar_t == 0)
      return;
   if(day_t != g_last_alert_day)
     {
      g_nalerted = 0;
      g_last_alert_day = day_t;
     }

   const double hi = iHigh(_Symbol, _Period, 1);
   const double lo = iLow (_Symbol, _Period, 1);
   if(hi <= 0.0 || lo <= 0.0)
      return;

   for(int i = 0; i < g_nlevels; i++)
     {
      const SLevel z = g_levels[i];
      bool wanted = false;
      if((z.kind == KIND_MAJOR) && InpAlertMajor) wanted = true;
      if((z.kind == KIND_MID)   && InpAlertMid)   wanted = true;
      if((z.kind == KIND_PDH || z.kind == KIND_PDL) && InpAlertPdhPdl) wanted = true;
      if(!wanted)
         continue;
      if(!(hi >= z.price && lo <= z.price))
         continue;
      if(AlreadyAlerted(z.id))
         continue;
      RememberAlert(z.id);
      const string msg = "Gold Level Map " + _Symbol + " touched " + z.tag +
                         " at " + DoubleToString(z.price, g_digits) +
                         " on the closed " + Tfs() + " bar.";
      if(InpAlertPopup) Alert(msg);
      else              Print(msg);
      if(InpAlertPush)  SendNotification(msg);
      if(InpAlertSound) PlaySound(InpAlertSoundName);
     }
  }

bool AlreadyAlerted(const string id)
  {
   for(int i = 0; i < g_nalerted; i++)
      if(g_alerted[i] == id)
         return(true);
   return(false);
  }

void RememberAlert(const string id)
  {
   if(g_nalerted >= ArraySize(g_alerted))
      ArrayResize(g_alerted, g_nalerted + 16);
   g_alerted[g_nalerted++] = id;
  }

//+------------------------------------------------------------------+
