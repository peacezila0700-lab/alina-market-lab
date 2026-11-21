//+------------------------------------------------------------------+
//|                                                     TradePad.mq5 |
//|                                                       Eudora Lab |
//|                                            https://eudora-ea.com |
//+------------------------------------------------------------------+
#property copyright "Eudora Lab"
#property link      "https://eudora-ea.com"
#property version   "1.00"
#property description "A manual trading pad for the chart symbol: BUY and SELL with the live prices and spread,"
#property description "a lot stepper with margin and point value, optional stop loss and take profit,"
#property description "CLOSE ALL, CLOSE PROFIT, CLOSE LOSS and BREAKEVEN, live positions, lots and floating result."
#property description "Drag it by the header, collapse it to a bar. Practice mode animates everything and sends nothing."

//--- uncomment to print, every 5 seconds, the frames drawn and the time spent in Render()
//#define ETP_PROFILE

#include <Canvas\Canvas.mqh>
#include <Trade\Trade.mqh>

//--- Orders are sent only as the direct result of a click on the pad (CHARTEVENT_OBJECT_CLICK
//--- on the pad object) or of a scripted press, never from OnInit, OnTick or OnTimer.
//---
//--- Scripted control (for automated tests) is OFF by default. With InpScripted = true,
//--- a program on the same chart presses a button with
//---    EventChartCustom(chart_id, (ushort)(7700 + n), 0, 0.0, "ETP:" + IntegerToString(chart_id));
//--- which arrives in OnChartEvent as CHARTEVENT_CUSTOM + 7700 + n:
//---    1 BUY, 2 SELL, 3 lot minus, 4 lot plus, 5 CLOSE ALL, 6 CLOSE PROFIT, 7 CLOSE LOSS,
//---    8 BREAKEVEN, 9 collapse / expand.
//--- Any other custom event, or a different sparam, is ignored. A scripted press of CLOSE ALL
//--- or CLOSE LOSS only arms the confirmation; a second scripted press, 400 ms to 3 seconds
//--- later, confirms it only when InpScriptedConfirm = true.

//--- positions the pad closes and modifies
enum ENUM_PAD_SCOPE
  {
   SCOPE_MANUAL_AND_PAD = 0, // Manual trades and trades opened by this pad
   SCOPE_PAD_ONLY       = 1, // Only trades opened by this pad
   SCOPE_ALL            = 2  // Every position on the symbol, other robots included
  };

input group "Panel"
input int            InpX               = 12;                   // Distance from the left edge, pixels
input int            InpY               = 40;                   // Distance from the top edge, pixels
input int            InpScale           = 100;                  // Panel size, percent
input color          InpAccent          = C'77,163,255';        // Accent color
input group "Orders"
input double         InpLot             = 0.0;                  // Starting lot (0 = symbol minimum)
input int            InpSL              = 0;                    // Stop loss, points (0 = none)
input int            InpTP              = 0;                    // Take profit, points (0 = none)
input int            InpSlippage        = 10;                   // Maximum slippage, points
input long           InpMagic           = 202611;               // Magic number
input ENUM_PAD_SCOPE InpScope           = SCOPE_MANUAL_AND_PAD; // Positions the pad manages
input group "Practice"
input bool           InpPractice        = false;                // Practice mode (no orders are sent)
input group "Automation"
input bool           InpScripted        = false;                // Allow other programs to press the buttons
input bool           InpScriptedConfirm = false;                // Scripted presses may also confirm CLOSE ALL / CLOSE LOSS

//--- palette, ARGB
#define C_TOP    0xFF141D36
#define C_BOT    0xFF0A1020
#define C_EDGE   0xFF2B3B66
#define C_TILE   0xFF18233F
#define C_TRACK  0xFF1D2A4A
#define C_INK    0xFFEEF3FF
#define C_DIM    0xFF8D9DC2
#define C_UP     0xFF3DDC97
#define C_MID    0xFFF5B94A
#define C_DOWN   0xFFFF6B6B

//--- buttons, same numbers as the scripted control
#define B_BUY     1
#define B_SELL    2
#define B_MINUS   3
#define B_PLUS    4
#define B_ALL     5
#define B_PROFIT  6
#define B_LOSS    7
#define B_BE      8
#define B_TOGGLE  9
#define BTN       10

//--- scripted control: custom event offset and timings, milliseconds
#define SCRIPT_BASE   7700
#define CONFIRM_MS    3000
#define CONFIRM_MIN   400
#define TRADE_GAP     300
#define DRAG_GAP      300

//+------------------------------------------------------------------+
//| Canvas with alpha blending and antialiased primitives            |
//+------------------------------------------------------------------+
class CPanel : public CCanvas
  {
public:
   void              Save(uint &dst[]);
   void              Load(const uint &src[]);
   void              Bl(const int x, const int y, const uint rgb, double a);
   static double     Sd(const double px, const double py, const double cx, const double cy, const double hw, const double hh, const double r);
   void              Background(const double r, const uint cTop, const uint cBot, const uint cEdge, const uint accent, const int gradH = 0);
   static uint       Mix(const uint a, const uint b, double t);
   void              RRect(const double x, const double y, const double w, const double h, const double r, const uint rgb, const double alpha);
   void              Halo(const double x, const double y, const double w, const double h, const double r, const double g, const uint rgb, const double alpha);
   void              Ripple(const double x, const double y, const double w, const double h, const double r,
                            const double px, const double py, const double rad, const uint rgb, const double alpha);
   void              Disc(const double cx, const double cy, const double r, const uint rgb, const double alpha, const double glow = 0.0);
   void              Arc(const double cx, const double cy, const double r, const double th, const double a0, const double sweep,
                         const uint rgb, const double alpha, const double glow = 0.0);
   void              Line(const double x1, const double y1, const double x2, const double y2, const double th, const uint rgb, const double alpha);
   void              Text(const int x, const int y, const string s, const uint argb, const int px, const bool bold, const uint align);
   int               TextW(const string s, const int px, const bool bold);
   int               TextH(const string s, const int px, const bool bold);
  };

//+------------------------------------------------------------------+
//| Copies the pixels into an array                                  |
//+------------------------------------------------------------------+
void CPanel::Save(uint &dst[])
  {
   ArrayResize(dst, ArraySize(m_pixels));
   ArrayCopy(dst, m_pixels);
  }

//+------------------------------------------------------------------+
//| Restores the pixels saved with Save, when the size matches       |
//+------------------------------------------------------------------+
void CPanel::Load(const uint &src[])
  {
   if(ArraySize(src) == ArraySize(m_pixels))
      ArrayCopy(m_pixels, src);
  }

//+------------------------------------------------------------------+
//| Blends a color over an opaque pixel; transparent pixels stay     |
//+------------------------------------------------------------------+
void CPanel::Bl(const int x, const int y, const uint rgb, double a)
  {
   if(x < 0 || y < 0 || x >= m_width || y >= m_height || a <= 0.0)
      return;
   int  i = y * m_width + x;
   uint d = m_pixels[i];
   if((d >> 24) == 0)
      return;
   if(a > 1.0)
      a = 1.0;
   int k  = (int)(a * 256.0);
   int dr = (int)((d >> 16) & 255), dg = (int)((d >> 8) & 255), db = (int)(d & 255);
   int sr = (int)((rgb >> 16) & 255), sg = (int)((rgb >> 8) & 255), sb = (int)(rgb & 255);
   dr = (dr * (256 - k) + sr * k) >> 8;
   dg = (dg * (256 - k) + sg * k) >> 8;
   db = (db * (256 - k) + sb * k) >> 8;
   m_pixels[i] = (d & 0xFF000000) | ((uint)dr << 16) | ((uint)dg << 8) | (uint)db;
  }

//+------------------------------------------------------------------+
//| Signed distance from a point to a rounded rectangle              |
//+------------------------------------------------------------------+
double CPanel::Sd(const double px, const double py, const double cx, const double cy, const double hw, const double hh, const double r)
  {
   double qx = MathAbs(px - cx) - (hw - r), qy = MathAbs(py - cy) - (hh - r);
   double ox = MathMax(qx, 0.0), oy = MathMax(qy, 0.0);
   return(MathSqrt(ox * ox + oy * oy) + MathMin(MathMax(qx, qy), 0.0) - r);
  }

//+------------------------------------------------------------------+
//| Rounded background, gradient over gradH pixels, light, thin edge |
//+------------------------------------------------------------------+
void CPanel::Background(const double r, const uint cTop, const uint cBot, const uint cEdge, const uint accent, const int gradH)
  {
   double hw = m_width / 2.0, hh = m_height / 2.0;
   int    gh = gradH > 0 ? gradH : m_height;
   for(int y = 0; y < m_height; y++)
     {
      double t = (double)y / MathMax(gh - 1, 1);
      for(int x = 0; x < m_width; x++)
        {
         int    i = y * m_width + x;
         double d = Sd(x + 0.5, y + 0.5, hw, hh, hw, hh, r);
         double cov = d <= -0.5 ? 1.0 : (d < 0.5 ? 0.5 - d : 0.0);
         if(cov <= 0.0)
           {
            m_pixels[i] = 0;
            continue;
           }
         m_pixels[i] = Mix(cTop, cBot, t);
         double lx = x - m_width * 0.18, ly = (double)y;
         double g = 1.0 - MathSqrt(lx * lx + ly * ly) / (m_width * 0.95);
         if(g > 0)
            Bl(x, y, accent, 0.16 * g * g);
         if(d > -1.6)
            Bl(x, y, cEdge, MathMin(1.0, (d + 1.6) / 1.1));
         m_pixels[i] = (m_pixels[i] & 0x00FFFFFF) | ((uint)(cov * 255.0) << 24);
        }
     }
  }

//+------------------------------------------------------------------+
//| Opaque color between a and b, t from 0 to 1                      |
//+------------------------------------------------------------------+
uint CPanel::Mix(const uint a, const uint b, double t)
  {
   if(t < 0)
      t = 0;
   if(t > 1)
      t = 1;
   int ar = (int)((a >> 16) & 255), ag = (int)((a >> 8) & 255), ab = (int)(a & 255);
   int br = (int)((b >> 16) & 255), bg = (int)((b >> 8) & 255), bb = (int)(b & 255);
   return(0xFF000000 | ((uint)(ar + (br - ar) * t) << 16) | ((uint)(ag + (bg - ag) * t) << 8) | (uint)(ab + (bb - ab) * t));
  }

//+------------------------------------------------------------------+
//| Filled antialiased rounded rectangle                             |
//+------------------------------------------------------------------+
void CPanel::RRect(const double x, const double y, const double w, const double h, const double r, const uint rgb, const double alpha)
  {
   double cx = x + w / 2.0, cy = y + h / 2.0;
   for(int yy = (int)MathFloor(y); yy <= (int)MathCeil(y + h); yy++)
      for(int xx = (int)MathFloor(x); xx <= (int)MathCeil(x + w); xx++)
        {
         double d = Sd(xx + 0.5, yy + 0.5, cx, cy, w / 2.0, h / 2.0, r);
         if(d < 0.5)
            Bl(xx, yy, rgb, alpha * (d <= -0.5 ? 1.0 : 0.5 - d));
        }
  }

//+------------------------------------------------------------------+
//| Soft glow outside a rounded rectangle, g pixels wide             |
//+------------------------------------------------------------------+
void CPanel::Halo(const double x, const double y, const double w, const double h, const double r, const double g, const uint rgb, const double alpha)
  {
   if(g <= 0.0 || alpha <= 0.0)
      return;
   double cx = x + w / 2.0, cy = y + h / 2.0;
   for(int yy = (int)MathFloor(y - g); yy <= (int)MathCeil(y + h + g); yy++)
      for(int xx = (int)MathFloor(x - g); xx <= (int)MathCeil(x + w + g); xx++)
        {
         double d = Sd(xx + 0.5, yy + 0.5, cx, cy, w / 2.0, h / 2.0, r);
         if(d <= 0.0 || d >= g)
            continue;
         double k = 1.0 - d / g;
         Bl(xx, yy, rgb, alpha * k * k);
        }
  }

//+------------------------------------------------------------------+
//| Disc of radius rad clipped to a rounded rectangle: click ripple  |
//+------------------------------------------------------------------+
void CPanel::Ripple(const double x, const double y, const double w, const double h, const double r,
                    const double px, const double py, const double rad, const uint rgb, const double alpha)
  {
   if(rad <= 0.0 || alpha <= 0.0)
      return;
   double cx = x + w / 2.0, cy = y + h / 2.0;
   for(int yy = (int)MathFloor(y); yy <= (int)MathCeil(y + h); yy++)
      for(int xx = (int)MathFloor(x); xx <= (int)MathCeil(x + w); xx++)
        {
         double d = Sd(xx + 0.5, yy + 0.5, cx, cy, w / 2.0, h / 2.0, r);
         if(d >= 0.5)
            continue;
         double inner = d <= -0.5 ? 1.0 : 0.5 - d;
         double dx = xx + 0.5 - px, dy = yy + 0.5 - py;
         double e = MathSqrt(dx * dx + dy * dy) - rad;
         double cov = e <= -0.5 ? 1.0 : (e < 0.5 ? 0.5 - e : 0.0);
         if(cov > 0)
            Bl(xx, yy, rgb, alpha * cov * inner);
        }
  }

//+------------------------------------------------------------------+
//| Disc with an optional soft halo                                  |
//+------------------------------------------------------------------+
void CPanel::Disc(const double cx, const double cy, const double r, const uint rgb, const double alpha, const double glow)
  {
   double R = r + glow + 1.5;
   for(int y = (int)MathFloor(cy - R); y <= (int)MathCeil(cy + R); y++)
      for(int x = (int)MathFloor(cx - R); x <= (int)MathCeil(cx + R); x++)
        {
         double dx = x + 0.5 - cx, dy = y + 0.5 - cy;
         double e = MathSqrt(dx * dx + dy * dy) - r;
         double cov = e <= -0.5 ? 1.0 : (e < 0.5 ? 0.5 - e : 0.0);
         if(glow > 0 && e > -0.5 && e < glow)
            cov = MathMax(cov, 0.5 * (1.0 - e / glow) * (1.0 - e / glow));
         if(cov > 0)
            Bl(x, y, rgb, cov * alpha);
        }
  }

//+------------------------------------------------------------------+
//| Arc with round ends; degrees, clockwise on screen, 0 = right     |
//+------------------------------------------------------------------+
void CPanel::Arc(const double cx, const double cy, const double r, const double th, const double a0, const double sweep,
                 const uint rgb, const double alpha, const double glow)
  {
   if(sweep <= 0.0)
      return;
   double R  = r + th / 2.0 + glow + 1.5;
   double r0 = a0 * M_PI / 180.0, r1 = (a0 + sweep) * M_PI / 180.0;
   double p0x = cx + r * MathCos(r0), p0y = cy + r * MathSin(r0);
   double p1x = cx + r * MathCos(r1), p1y = cy + r * MathSin(r1);
   for(int y = (int)MathFloor(cy - R); y <= (int)MathCeil(cy + R); y++)
      for(int x = (int)MathFloor(cx - R); x <= (int)MathCeil(cx + R); x++)
        {
         double dx = x + 0.5 - cx, dy = y + 0.5 - cy;
         double e = MathAbs(MathSqrt(dx * dx + dy * dy) - r) - th / 2.0;
         double t = MathArctan2(dy, dx) * 180.0 / M_PI - a0;
         while(t < 0.0)
            t += 360.0;
         while(t >= 360.0)
            t -= 360.0;
         if(t > sweep)
           {
            double ax = x + 0.5 - p0x, ay = y + 0.5 - p0y, bx = x + 0.5 - p1x, by = y + 0.5 - p1y;
            e = MathSqrt(MathMin(ax * ax + ay * ay, bx * bx + by * by)) - th / 2.0;
           }
         if(e > glow + 0.5)
            continue;
         double cov = e <= -0.5 ? 1.0 : (e < 0.5 ? 0.5 - e : 0.0);
         if(glow > 0 && e > -0.5 && e < glow)
            cov = MathMax(cov, 0.45 * (1.0 - e / glow) * (1.0 - e / glow));
         if(cov > 0)
            Bl(x, y, rgb, cov * alpha);
        }
  }

//+------------------------------------------------------------------+
//| Antialiased segment with round ends, th pixels thick             |
//+------------------------------------------------------------------+
void CPanel::Line(const double x1, const double y1, const double x2, const double y2, const double th, const uint rgb, const double alpha)
  {
   double R = th / 2.0 + 1.5;
   double vx = x2 - x1, vy = y2 - y1, len2 = vx * vx + vy * vy;
   for(int y = (int)MathFloor(MathMin(y1, y2) - R); y <= (int)MathCeil(MathMax(y1, y2) + R); y++)
      for(int x = (int)MathFloor(MathMin(x1, x2) - R); x <= (int)MathCeil(MathMax(x1, x2) + R); x++)
        {
         double px = x + 0.5 - x1, py = y + 0.5 - y1;
         double u = len2 > 0 ? (px * vx + py * vy) / len2 : 0.0;
         u = MathMax(0.0, MathMin(1.0, u));
         double dx = px - u * vx, dy = py - u * vy;
         double e = MathSqrt(dx * dx + dy * dy) - th / 2.0;
         if(e < 0.5)
            Bl(x, y, rgb, alpha * (e <= -0.5 ? 1.0 : 0.5 - e));
        }
  }

//+------------------------------------------------------------------+
//| Text in Segoe UI, px pixels high, normal or bold                 |
//+------------------------------------------------------------------+
void CPanel::Text(const int x, const int y, const string s, const uint argb, const int px, const bool bold, const uint align)
  {
   FontSet("Segoe UI", px, bold ? FW_BOLD : FW_NORMAL);
   TextOut(x, y, s, argb, align);
  }

//+------------------------------------------------------------------+
//| Width of a text in pixels                                        |
//+------------------------------------------------------------------+
int CPanel::TextW(const string s, const int px, const bool bold)
  {
   FontSet("Segoe UI", px, bold ? FW_BOLD : FW_NORMAL);
   return(TextWidth(s));
  }

//+------------------------------------------------------------------+
//| Height of a text in pixels                                       |
//+------------------------------------------------------------------+
int CPanel::TextH(const string s, const int px, const bool bold)
  {
   FontSet("Segoe UI", px, bold ? FW_BOLD : FW_NORMAL);
   return(TextHeight(s));
  }

const string PFX = "ETP_";
CPanel   g_cv;
CTrade   g_trade;
uint     g_bg[];
string   g_obj, g_gv, g_cur, g_tag;
double   g_s = 1.0;
int      g_w = 0, g_h = 0, g_hFull = 0, g_hBar = 0;
int      g_px = 0, g_py = 0, g_cw = 0, g_ch = 0;
bool     g_ready = false, g_headless = false;
uint     g_accent = 0xFF4DA3FF;
ulong    g_lastData = 0, g_lastDraw = 0;

//--- symbol; g_symOk = the properties were read from a connected terminal
int      g_digits = 5, g_ldig = 2, g_spread = 0;
double   g_point = 0, g_bid = 0, g_ask = 0;
double   g_lot = 0, g_lotWant = 0, g_vmin = 0, g_vmax = 0, g_vstep = 0;
double   g_margin = -1, g_pointValue = 0;
bool     g_tickOk = false, g_symOk = false;

//--- positions the pad manages: count, lots, floating result and its eased copy for the tone
int      g_count = 0;
double   g_lots = 0, g_float = 0, g_floatEase = 0;

//--- buttons: hover glow, press flash, ripple start and origin, reason why the button is disabled ("" = enabled)
double   g_hov[BTN], g_prs[BTN], g_ripX[BTN], g_ripY[BTN];
ulong    g_ripT[BTN];
string   g_block[BTN];
int      g_hover = 0;

//--- collapse animation, 1 = expanded; g_userOpen = what the user chose, g_wantOpen = what is shown
double   g_open = 1.0;
bool     g_wantOpen = true, g_userOpen = true;

//--- mouse: chart settings taken over while the cursor is on the panel, drag, last press
bool     g_lmb = false, g_drag = false, g_capture = false, g_scrollWas = true, g_levelsWas = true;
int      g_dx = 0, g_dy = 0, g_pressBtn = -1;
bool     g_pressLive = false;
ulong    g_pressT = 0, g_releaseT = 0, g_clickT = 0, g_dragEndT = 0;

//--- confirmations (deadline, time armed), end of the last trade request, status line
ulong    g_confAll = 0, g_armAll = 0, g_confLoss = 0, g_armLoss = 0, g_tradeEnd = 0, g_statusT = 0;
string   g_status = "";
uint     g_statusCol = C_DIM;

#ifdef ETP_PROFILE
ulong    g_prfT = 0, g_prfFrames = 0, g_prfSum = 0, g_prfMax = 0;
#endif

//+------------------------------------------------------------------+
//| Scales a size to the screen DPI and to the panel size input      |
//+------------------------------------------------------------------+
int S(const double v) { return((int)MathRound(v * g_s)); }

//+------------------------------------------------------------------+
//| Same scaling, without rounding, for antialiased shapes           |
//+------------------------------------------------------------------+
double Sf(const double v) { return(v * g_s); }

//+------------------------------------------------------------------+
//| Number of decimals in the textual form of a value: 0.25 -> 2     |
//+------------------------------------------------------------------+
int Decimals(const double v)
  {
   string s = DoubleToString(v, 8);
   int dot = StringFind(s, ".");
   if(dot < 0)
      return(0);
   int n = StringLen(s);
   while(n > dot + 1 && StringGetCharacter(s, n - 1) == '0')
      n--;
   return(n - dot - 1);
  }

//+------------------------------------------------------------------+
//| Reads digits, point, volume limits and the account currency      |
//+------------------------------------------------------------------+
void LoadSymbol()
  {
   g_digits = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   g_point  = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   double vmin  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double vmax  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double vstep = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   g_symOk  = g_point > 0 && vmin > 0 && vstep > 0;
   g_vmin   = vmin;
   g_vmax   = vmax;
   g_vstep  = vstep;
   if(g_vstep <= 0)
      g_vstep = g_vmin > 0 ? g_vmin : 0.01;
   if(g_vmin <= 0)
      g_vmin = g_vstep;
   if(g_vmax < g_vmin)
      g_vmax = g_vmin;
   g_ldig = MathMax(Decimals(g_vstep), Decimals(g_vmin));
   if(g_cur == "")
      g_cur = AccountInfoString(ACCOUNT_CURRENCY);
  }

//+------------------------------------------------------------------+
//| Expert initialization                                            |
//+------------------------------------------------------------------+
int OnInit()
  {
   g_headless = MQLInfoInteger(MQL_TESTER) && !MQLInfoInteger(MQL_VISUAL_MODE);
   g_cur      = "";
   LoadSymbol();
   g_trade.SetExpertMagicNumber((ulong)InpMagic);
   g_trade.SetDeviationInPoints((ulong)MathMax(0, InpSlippage));
   g_trade.SetTypeFilling(Filling());
   g_trade.SetMarginMode();
//--- strategy tester without visualization: no panel, no timer, nothing to do
   if(g_headless)
      return(INIT_SUCCEEDED);

   double s = TerminalInfoInteger(TERMINAL_SCREEN_DPI) / 96.0 * MathMax(50, MathMin(300, InpScale)) / 100.0;
   g_s      = MathMax(0.25, MathMin(s, MathMin(3.0, 4000.0 / 430.0)));
   g_accent = ColorToARGB(InpAccent, 255);
   g_w      = S(340);
   g_hFull  = S(430);
   g_hBar   = S(44);
   g_h      = 0;
   g_obj    = PFX + "panel";
   g_gv     = PFX + IntegerToString(ChartID()) + "_";
   g_tag    = "ETP:" + IntegerToString(ChartID());
   g_ready  = false;

//--- stale data from a previous run is never shown
   g_bid        = 0;
   g_ask        = 0;
   g_spread     = 0;
   g_margin     = -1;
   g_pointValue = 0;
   g_tickOk     = false;
   g_count      = 0;
   g_lots       = 0;
   g_float      = 0;
   g_floatEase  = 0;

//--- state of the animations and of the mouse
   ArrayInitialize(g_hov, 0.0);
   ArrayInitialize(g_prs, 0.0);
   ArrayInitialize(g_ripX, 0.0);
   ArrayInitialize(g_ripY, 0.0);
   ArrayInitialize(g_ripT, 0);
   for(int i = 0; i < BTN; i++)
      g_block[i] = "";
   g_hover     = 0;
   g_lmb       = false;
   g_drag      = false;
   g_capture   = false;
   g_pressBtn  = -1;
   g_pressLive = false;
   g_pressT    = 0;
   g_releaseT  = 0;
   g_clickT    = 0;
   g_dragEndT  = 0;
   g_confAll   = 0;
   g_confLoss  = 0;
   g_armAll    = 0;
   g_armLoss   = 0;
   g_tradeEnd  = 0;
   g_lastDraw  = 0;

//--- position, collapsed state and lot remembered for this chart; changed inputs win
   bool params = UninitializeReason() == REASON_PARAMETERS;
   g_px = InpX;
   g_py = InpY;
   if(!params && GlobalVariableCheck(g_gv + "X") && GlobalVariableCheck(g_gv + "Y"))
     {
      g_px = (int)GlobalVariableGet(g_gv + "X");
      g_py = (int)GlobalVariableGet(g_gv + "Y");
     }
   g_userOpen = !(GlobalVariableCheck(g_gv + "COLLAPSED") && GlobalVariableGet(g_gv + "COLLAPSED") > 0.5);
   g_lotWant  = InpLot > 0 ? InpLot : 0.0;
   string lk  = g_gv + "LOT_" + _Symbol;
   if(GlobalVariableCheck(lk) && !(params && InpLot > 0))
      g_lotWant = GlobalVariableGet(lk);
   g_lot = NormLot(g_lotWant > 0 ? g_lotWant : g_vmin);
   ClampPosition();
   g_open = g_wantOpen ? 1.0 : 0.0;

   g_scrollWas = (bool)ChartGetInteger(0, CHART_MOUSE_SCROLL);
   g_levelsWas = (bool)ChartGetInteger(0, CHART_DRAG_TRADE_LEVELS);
   ChartSetInteger(0, CHART_EVENT_MOUSE_MOVE, true);

   if(InpPractice)
      SetStatus("Practice mode: no orders are sent", g_accent);
   else
      SetStatus("Ready", C_DIM);
   EventSetMillisecondTimer(60);
   Refresh();
   Render();
   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
//| Expert deinitialization                                          |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   if(g_headless)
      return;
   EventKillTimer();
   ReleaseMouse();
   if(reason == REASON_REMOVE || reason == REASON_CHARTCLOSE)
      GlobalVariablesDeleteAll(g_gv);
   else
      SaveState();
   g_cv.Destroy();
   ObjectDelete(0, g_obj);
   ChartRedraw();
  }

//+------------------------------------------------------------------+
//| New tick: only the figures are read, nothing is ever sent here   |
//+------------------------------------------------------------------+
void OnTick()
  {
   if(g_headless)
      return;
   Refresh();
  }

//+------------------------------------------------------------------+
//| Eases the figures and the buttons and draws the next frame       |
//+------------------------------------------------------------------+
void OnTimer()
  {
   ulong ms = GetTickCount64();
#ifdef ETP_PROFILE
   if(g_prfT == 0)
      g_prfT = ms;
   if(ms - g_prfT >= 5000)
     {
      double avg = g_prfFrames > 0 ? (double)g_prfSum / (double)g_prfFrames : 0.0;
      Print("Trade Pad profile: ", g_prfFrames, " frames in ", ms - g_prfT, " ms, Render() average ",
            DoubleToString(avg, 0), " us, maximum ", g_prfMax, " us");
      g_prfT      = ms;
      g_prfFrames = 0;
      g_prfSum    = 0;
      g_prfMax    = 0;
     }
#endif
   if(ms - g_lastData >= 250)
      Refresh();
   bool moving = g_drag;
//--- only the tone of the floating result eases; it settles within 0.5%
   double diff = g_float - g_floatEase;
   if(MathAbs(diff) <= MathMax(0.005, MathAbs(g_float) * 0.005))
      g_floatEase = g_float;
   else
     {
      g_floatEase += diff * 0.18;
      moving = true;
     }
   for(int b = 1; b < BTN; b++)
     {
      double want = (b == g_hover && g_block[b] == "" && !g_drag) ? 1.0 : 0.0;
      double d = want - g_hov[b];
      if(MathAbs(d) <= 0.005)
         g_hov[b] = want;
      else
        {
         g_hov[b] += d * 0.25;
         moving = true;
        }
      if(g_prs[b] > 0.005)
        {
         g_prs[b] *= 0.80;
         moving = true;
        }
      else
         g_prs[b] = 0.0;
      if(g_ripT[b] > 0 && ms - g_ripT[b] < 560)
         moving = true;
     }
   double target = g_wantOpen ? 1.0 : 0.0;
   if(MathAbs(target - g_open) <= 0.005)
      g_open = target;
   else
     {
      g_open += (target - g_open) * 0.24;
      moving = true;
     }
   if(g_confAll > 0)
     {
      if(ms > g_confAll)
         g_confAll = 0;
      moving = true;
     }
   if(g_confLoss > 0)
     {
      if(ms > g_confLoss)
         g_confLoss = 0;
      moving = true;
     }
   if(g_statusT > 0 && ms - g_statusT >= 4000 && ms - g_statusT < 5600)
      moving = true;
//--- nothing is drawn while the chart cannot be seen
   if(!ChartVisible())
      return;
//--- while something moves every frame is drawn; at rest 4 frames a second, 1 when collapsed
   ulong period = g_open > 0.0 ? 250 : 1000;
   if(moving || ms - g_lastDraw >= period)
      Render();
  }

//+------------------------------------------------------------------+
//| Clicks, scripted presses, chart changes, hover and drag          |
//+------------------------------------------------------------------+
void OnChartEvent(const int id, const long &lparam, const double &dparam, const string &sparam)
  {
   if(g_headless)
      return;
//--- scripted control: CHARTEVENT_CUSTOM + 7701..7709 with the chart tag, only when allowed
   if(id >= CHARTEVENT_CUSTOM)
     {
      if(!InpScripted)
         return;
      int n = id - CHARTEVENT_CUSTOM - SCRIPT_BASE;
      if(n < 1 || n >= BTN || sparam != g_tag)
         return;
      int x = 0, y = 0, w = 0, h = 0;
      if(ButtonRect(n, x, y, w, h) && g_block[n] == "")
         StartRipple(n, x + w / 2.0, y + h / 2.0);
      Press(n, true);
      return;
     }
   if(id == CHARTEVENT_CHART_CHANGE)
     {
      if(ClampPosition())
         MovePanel();
      return;
     }
   if(id == CHARTEVENT_OBJECT_CLICK)
     {
      if(sparam == g_obj)
         OnPadClick((int)lparam, (int)dparam);
      return;
     }
   if(id == CHARTEVENT_MOUSE_MOVE)
      OnMouse((int)lparam, (int)dparam, ((int)StringToInteger(sparam) & 1) == 1);
  }

//+------------------------------------------------------------------+
//| Genuine click on the pad object: the only way a click acts       |
//+------------------------------------------------------------------+
void OnPadClick(const int mx, const int my)
  {
   if(!g_ready)
      return;
   ulong ms = GetTickCount64();
//--- the object was deleted, moved or replaced by another program: rebuild it, ignore the click
   if(!PadIntact())
     {
      Render();
      return;
     }
//--- the end of a drag is never a click
   if(g_drag || (g_dragEndT > 0 && ms - g_dragEndT < DRAG_GAP))
      return;
   ReadChartSize();
   int hit = HitTest(mx - g_px, my - g_py);
   if(hit == 0)
      return;
//--- a button hidden under an object of another program must not act
   if(Covered(mx, my))
     {
      SetStatus("Another object covers the pad here: move the pad", C_MID);
      return;
     }
//--- when the press was seen, the click must belong to it and land on the same button
   bool pressSeen = g_lmb || (g_releaseT > 0 && ms - g_releaseT <= 300 && g_pressT <= g_releaseT);
   if(pressSeen && (!g_pressLive || g_pressBtn != hit))
      return;
   g_pressLive = false;
   g_clickT    = ms;
   Press(hit, false);
  }

//+------------------------------------------------------------------+
//| True when another pixel-placed object lies over the chart point  |
//+------------------------------------------------------------------+
bool Covered(const int mx, const int my)
  {
   int cw = (int)ChartGetInteger(0, CHART_WIDTH_IN_PIXELS);
   int ch = (int)ChartGetInteger(0, CHART_HEIGHT_IN_PIXELS, 0);
   for(int i = ObjectsTotal(0, 0, -1) - 1; i >= 0; i--)
     {
      string name = ObjectName(0, i, 0, -1);
      if(name == "" || name == g_obj)
         continue;
      ENUM_OBJECT type = (ENUM_OBJECT)ObjectGetInteger(0, name, OBJPROP_TYPE);
      bool boxed = (type == OBJ_RECTANGLE_LABEL || type == OBJ_BUTTON || type == OBJ_EDIT || type == OBJ_CHART);
      bool anchored = (type == OBJ_LABEL || type == OBJ_BITMAP_LABEL);
      if(!boxed && !anchored)
         continue;
      //--- objects drawn in the background or hidden on this timeframe cover nothing
      if(ObjectGetInteger(0, name, OBJPROP_BACK) != 0)
         continue;
      if(ObjectGetInteger(0, name, OBJPROP_TIMEFRAMES) == OBJ_NO_PERIODS)
         continue;
      int xs = (int)MathMax(ObjectGetInteger(0, name, OBJPROP_XSIZE), 1);
      int ys = (int)MathMax(ObjectGetInteger(0, name, OBJPROP_YSIZE), 1);
      int xd = (int)ObjectGetInteger(0, name, OBJPROP_XDISTANCE);
      int yd = (int)ObjectGetInteger(0, name, OBJPROP_YDISTANCE);
      ENUM_BASE_CORNER corner = (ENUM_BASE_CORNER)ObjectGetInteger(0, name, OBJPROP_CORNER);
      int left = (corner == CORNER_RIGHT_UPPER || corner == CORNER_RIGHT_LOWER) ? cw - xd : xd;
      int top  = (corner == CORNER_LEFT_LOWER || corner == CORNER_RIGHT_LOWER) ? ch - yd : yd;
      if(anchored)
        {
         ENUM_ANCHOR_POINT a = (ENUM_ANCHOR_POINT)ObjectGetInteger(0, name, OBJPROP_ANCHOR);
         if(a == ANCHOR_RIGHT_UPPER || a == ANCHOR_RIGHT || a == ANCHOR_RIGHT_LOWER)
            left -= xs;
         if(a == ANCHOR_UPPER || a == ANCHOR_CENTER || a == ANCHOR_LOWER)
            left -= xs / 2;
         if(a == ANCHOR_LEFT_LOWER || a == ANCHOR_LOWER || a == ANCHOR_RIGHT_LOWER)
            top -= ys;
         if(a == ANCHOR_LEFT || a == ANCHOR_CENTER || a == ANCHOR_RIGHT)
            top -= ys / 2;
        }
      if(mx >= left && mx < left + xs && my >= top && my < top + ys)
         return(true);
     }
   return(false);
  }

//+------------------------------------------------------------------+
//| Mouse move: hover, press look, ripple and drag by the header     |
//+------------------------------------------------------------------+
void OnMouse(const int mx, const int my, const bool lmb)
  {
   ulong ms = GetTickCount64();
   if(lmb && !g_lmb && g_ready && !PadIntact())
     {
      Render();
      g_lmb = lmb;
      return;
     }
   int  lx = mx - g_px, ly = my - g_py;
   bool inside = g_ready && lx >= 0 && ly >= 0 && lx < g_w && ly < g_h;

//--- the chart does not scroll and trade levels cannot be dragged under the panel
   if(inside || g_drag)
      CaptureMouse();
   else
      ReleaseMouse();

//--- dragging the panel by its header
   if(g_drag)
     {
      if(lmb)
        {
         g_px = mx - g_dx;
         g_py = my - g_dy;
         ClampPosition();
         if(ObjectGetInteger(0, g_obj, OBJPROP_XDISTANCE) != g_px || ObjectGetInteger(0, g_obj, OBJPROP_YDISTANCE) != g_py)
            MovePanel();
        }
      else
        {
         g_drag     = false;
         g_dragEndT = ms;
         g_releaseT = ms;
         SaveState();
         if(!inside)
            ReleaseMouse();
        }
      g_lmb = lmb;
      return;
     }

   ReadChartSize();
   int hit = inside ? HitTest(lx, ly) : 0;
   g_hover = hit;
   if(lmb && !g_lmb)
     {
      g_pressT    = ms;
      g_pressBtn  = inside ? hit : -1;
      g_pressLive = !(g_clickT > 0 && ms - g_clickT < 200);
      if(inside)
        {
         if(hit > 0)
           {
            if(g_block[hit] == "")
              {
               g_prs[hit] = 1.0;
               StartRipple(hit, lx, ly);
              }
           }
         else
            if(ly < g_hBar)
              {
               g_drag      = true;
               g_pressLive = false;
               g_dx        = mx - g_px;
               g_dy        = my - g_py;
              }
        }
     }
   else
      if(!lmb && g_lmb)
         g_releaseT = ms;
   g_lmb = lmb;
  }

//+------------------------------------------------------------------+
//| True when the pad object is ours and in place; otherwise fixes   |
//+------------------------------------------------------------------+
bool PadIntact()
  {
   if(!g_ready)
      return(false);
   bool there = ObjectFind(0, g_obj) >= 0 && ObjectGetInteger(0, g_obj, OBJPROP_TYPE) == OBJ_BITMAP_LABEL;
   if(there)
     {
      string bmp = ObjectGetString(0, g_obj, OBJPROP_BMPFILE);
      int    p   = StringFind(bmp, "::");
      there = p >= 0 && StringSubstr(bmp, p) == g_cv.ResourceName();
     }
   if(!there)
     {
      //--- deleted or replaced: build it again at the next Render()
      g_cv.Destroy();
      ObjectDelete(0, g_obj);
      g_ready = false;
      g_h     = 0;
      return(false);
     }
   bool ok = ObjectGetInteger(0, g_obj, OBJPROP_XDISTANCE) == g_px &&
             ObjectGetInteger(0, g_obj, OBJPROP_YDISTANCE) == g_py &&
             ObjectGetInteger(0, g_obj, OBJPROP_CORNER) == CORNER_LEFT_UPPER &&
             ObjectGetInteger(0, g_obj, OBJPROP_ANCHOR) == ANCHOR_LEFT_UPPER;
   if(!ok)
     {
      ObjectSetInteger(0, g_obj, OBJPROP_CORNER, CORNER_LEFT_UPPER);
      ObjectSetInteger(0, g_obj, OBJPROP_ANCHOR, ANCHOR_LEFT_UPPER);
      ObjectSetInteger(0, g_obj, OBJPROP_XDISTANCE, g_px);
      ObjectSetInteger(0, g_obj, OBJPROP_YDISTANCE, g_py);
      ChartRedraw();
     }
   return(ok);
  }

//+------------------------------------------------------------------+
//| Takes the chart scroll and the trade level drag off              |
//+------------------------------------------------------------------+
void CaptureMouse()
  {
   if(g_capture)
      return;
   ChartSetInteger(0, CHART_MOUSE_SCROLL, false);
   ChartSetInteger(0, CHART_DRAG_TRADE_LEVELS, false);
   g_capture = true;
  }

//+------------------------------------------------------------------+
//| Gives the chart scroll and the trade level drag back             |
//+------------------------------------------------------------------+
void ReleaseMouse()
  {
   if(!g_capture)
      return;
   ChartSetInteger(0, CHART_MOUSE_SCROLL, g_scrollWas);
   ChartSetInteger(0, CHART_DRAG_TRADE_LEVELS, g_levelsWas);
   g_capture = false;
  }

//+------------------------------------------------------------------+
//| Stores the position, collapsed state and lot for this chart      |
//+------------------------------------------------------------------+
void SaveState()
  {
   GlobalVariableSet(g_gv + "X", g_px);
   GlobalVariableSet(g_gv + "Y", g_py);
   GlobalVariableSet(g_gv + "COLLAPSED", g_userOpen ? 0.0 : 1.0);
   GlobalVariableSet(g_gv + "LOT_" + _Symbol, g_lot);
  }

//+------------------------------------------------------------------+
//| Width of the chart and height of its main window, pixels         |
//+------------------------------------------------------------------+
void ReadChartSize()
  {
   g_cw = (int)ChartGetInteger(0, CHART_WIDTH_IN_PIXELS);
   g_ch = (int)ChartGetInteger(0, CHART_HEIGHT_IN_PIXELS, 0);
  }

//+------------------------------------------------------------------+
//| False when the chart window is minimized or has no size          |
//+------------------------------------------------------------------+
bool ChartVisible()
  {
   if((bool)ChartGetInteger(0, CHART_IS_MINIMIZED))
      return(false);
   ReadChartSize();
   return(g_cw > 0 && g_ch > 0);
  }

//+------------------------------------------------------------------+
//| Keeps the panel inside the main window; true when it changed     |
//+------------------------------------------------------------------+
bool ClampPosition()
  {
   int  ox = g_px, oy = g_py;
   bool oo = g_wantOpen;
   ReadChartSize();
//--- a main window shorter than the panel shows only the collapsed bar
   bool fits = g_ch <= 0 || g_ch >= g_hFull;
   g_wantOpen = g_userOpen && fits;
   int hh = g_wantOpen ? g_hFull : g_hBar;
   if(g_cw > 0)
      g_px = MathMin(g_px, g_cw - g_w);
   if(g_ch > 0)
      g_py = MathMin(g_py, g_ch - hh);
   g_px = MathMax(0, g_px);
   g_py = MathMax(0, g_py);
   return(g_px != ox || g_py != oy || g_wantOpen != oo);
  }

//+------------------------------------------------------------------+
//| Moves the panel object to the current position                   |
//+------------------------------------------------------------------+
void MovePanel()
  {
   if(!g_ready)
      return;
   ObjectSetInteger(0, g_obj, OBJPROP_XDISTANCE, g_px);
   ObjectSetInteger(0, g_obj, OBJPROP_YDISTANCE, g_py);
   ChartRedraw();
  }

//+------------------------------------------------------------------+
//| Rectangle of a button inside the panel, scaled pixels            |
//+------------------------------------------------------------------+
bool ButtonRect(const int b, int &x, int &y, int &w, int &h)
  {
   int bx[BTN] = {0, 192, 18, 18, 278, 18, 174, 18, 174, 299};
   int by[BTN] = {0, 52, 52, 138, 138, 232, 232, 274, 274, 10};
   int bw[BTN] = {0, 130, 130, 44, 44, 148, 148, 148, 148, 24};
   int bh[BTN] = {0, 70, 70, 40, 40, 34, 34, 34, 34, 24};
   if(b < 1 || b >= BTN)
      return(false);
   x = S(bx[b]);
   y = S(by[b]);
   w = S(bw[b]);
   h = S(bh[b]);
   return(true);
  }

//+------------------------------------------------------------------+
//| Button under a point of the panel, 0 = none                      |
//+------------------------------------------------------------------+
int HitTest(const int lx, const int ly)
  {
   for(int b = 1; b < BTN; b++)
     {
      int x = 0, y = 0, w = 0, h = 0;
      if(!ButtonRect(b, x, y, w, h))
         continue;
      //--- only a button fully drawn and fully inside the main chart window is active
      if(y + h > g_h)
         continue;
      if(g_px + x < 0 || g_py + y < 0)
         continue;
      if(g_cw > 0 && g_px + x + w > g_cw)
         continue;
      if(g_ch > 0 && g_py + y + h > g_ch)
         continue;
      if(lx >= x && lx < x + w && ly >= y && ly < y + h)
         return(b);
     }
   return(0);
  }

//+------------------------------------------------------------------+
//| Starts the click ripple of a button from a point of the panel    |
//+------------------------------------------------------------------+
void StartRipple(const int b, const double px, const double py)
  {
   if(b < 1 || b >= BTN)
      return;
   g_ripT[b] = GetTickCount64();
   g_ripX[b] = px;
   g_ripY[b] = py;
  }

//+------------------------------------------------------------------+
//| Lot rounded to the volume step, inside the symbol limits         |
//+------------------------------------------------------------------+
double NormLot(const double v)
  {
   double lot = MathMax(g_vmin, MathMin(g_vmax, v));
   lot = g_vmin + MathRound((lot - g_vmin) / g_vstep) * g_vstep;
   lot = NormalizeDouble(lot, g_ldig);
   if(lot > g_vmax)
      lot = NormalizeDouble(lot - g_vstep, g_ldig);
   return(MathMax(g_vmin, lot));
  }

//+------------------------------------------------------------------+
//| Filling mode allowed by the symbol                               |
//+------------------------------------------------------------------+
ENUM_ORDER_TYPE_FILLING Filling()
  {
   long fm = SymbolInfoInteger(_Symbol, SYMBOL_FILLING_MODE);
   if((fm & SYMBOL_FILLING_FOK) == SYMBOL_FILLING_FOK)
      return(ORDER_FILLING_FOK);
   if((fm & SYMBOL_FILLING_IOC) == SYMBOL_FILLING_IOC)
      return(ORDER_FILLING_IOC);
   return(ORDER_FILLING_RETURN);
  }

//+------------------------------------------------------------------+
//| True when the symbol allows neither FOK nor IOC                  |
//+------------------------------------------------------------------+
bool ReturnOnly()
  {
   long fm = SymbolInfoInteger(_Symbol, SYMBOL_FILLING_MODE);
   return((fm & (SYMBOL_FILLING_FOK | SYMBOL_FILLING_IOC)) == 0);
  }

//+------------------------------------------------------------------+
//| True when the symbol uses exchange execution                     |
//+------------------------------------------------------------------+
bool Exchange()
  {
   return(SymbolInfoInteger(_Symbol, SYMBOL_TRADE_EXEMODE) == SYMBOL_TRADE_EXECUTION_EXCHANGE);
  }

//+------------------------------------------------------------------+
//| Reason trading is blocked; side 0 close, 1 buy, 2 sell           |
//+------------------------------------------------------------------+
string TradeBlock(const int side)
  {
   if(InpPractice)
      return("");
   if(!TerminalInfoInteger(TERMINAL_TRADE_ALLOWED))
      return("Algo Trading is off in the terminal");
   if(!MQLInfoInteger(MQL_TRADE_ALLOWED))
      return("Algo trading is not allowed for this Expert Advisor");
   if(!AccountInfoInteger(ACCOUNT_TRADE_ALLOWED))
      return("Trading is not allowed on this account");
   if(!AccountInfoInteger(ACCOUNT_TRADE_EXPERT))
      return("Expert Advisors cannot trade on this account");
   long mode = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_MODE);
   if(mode == SYMBOL_TRADE_MODE_DISABLED)
      return("Trading is disabled for " + _Symbol);
   if(side != 0 && mode == SYMBOL_TRADE_MODE_CLOSEONLY)
      return(_Symbol + " is in close only mode");
   if(side == 1 && mode == SYMBOL_TRADE_MODE_SHORTONLY)
      return(_Symbol + " allows sell orders only");
   if(side == 2 && mode == SYMBOL_TRADE_MODE_LONGONLY)
      return(_Symbol + " allows buy orders only");
   return("");
  }

//+------------------------------------------------------------------+
//| True when the selected position is one this pad manages          |
//+------------------------------------------------------------------+
bool Mine()
  {
   if(PositionGetString(POSITION_SYMBOL) != _Symbol)
      return(false);
   long m = PositionGetInteger(POSITION_MAGIC);
   if(InpScope == SCOPE_PAD_ONLY)
      return(m == InpMagic);
   if(InpScope == SCOPE_MANUAL_AND_PAD)
      return(m == 0 || m == InpMagic);
   return(true);
  }

//+------------------------------------------------------------------+
//| Short name of the positions the pad manages                      |
//+------------------------------------------------------------------+
string ScopeName()
  {
   if(InpScope == SCOPE_PAD_ONLY)
      return("pad only");
   if(InpScope == SCOPE_ALL)
      return("all positions");
   return("manual + pad");
  }

//+------------------------------------------------------------------+
//| Reads prices, margin, point value and the positions              |
//+------------------------------------------------------------------+
void Refresh()
  {
   g_lastData = GetTickCount64();
//--- terminal started before the connection: read the symbol again until it is known
   if(!g_symOk || g_cur == "")
     {
      bool was = g_symOk;
      LoadSymbol();
      if(!was && g_symOk)
         g_lot = NormLot(g_lotWant > 0 ? g_lotWant : g_vmin);
     }
   MqlTick t;
   g_tickOk = SymbolInfoTick(_Symbol, t) && t.bid > 0 && t.ask > 0;
   if(g_tickOk)
     {
      g_bid    = t.bid;
      g_ask    = t.ask;
      g_spread = g_point > 0 ? (int)MathRound((g_ask - g_bid) / g_point) : 0;
     }
   else
     {
      g_bid    = 0;
      g_ask    = 0;
      g_spread = 0;
     }
   double m = 0;
   g_margin = -1;
   if(g_tickOk && OrderCalcMargin(ORDER_TYPE_BUY, _Symbol, g_lot, g_ask, m))
      g_margin = m;
   double tv = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double ts = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   g_pointValue = g_tickOk && ts > 0 ? tv / ts * g_point * g_lot : 0;

   int    n = 0;
   double lots = 0, fl = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong tk = PositionGetTicket(i);
      if(tk == 0 || !Mine())
         continue;
      n++;
      lots += PositionGetDouble(POSITION_VOLUME);
      fl   += PositionGetDouble(POSITION_PROFIT) + PositionGetDouble(POSITION_SWAP);
     }
   g_count = n;
   g_lots  = lots;
   g_float = fl;

   g_block[B_BUY]  = TradeBlock(1);
   g_block[B_SELL] = TradeBlock(2);
   string c = TradeBlock(0);
   g_block[B_ALL]    = c;
   g_block[B_PROFIT] = c;
   g_block[B_LOSS]   = c;
   g_block[B_BE]     = c;
  }

//+------------------------------------------------------------------+
//| Shows a message on the status line and in the journal            |
//+------------------------------------------------------------------+
void SetStatus(const string s, const uint col)
  {
   g_status    = s;
   g_statusCol = col;
   g_statusT   = GetTickCount64();
   Print("Trade Pad: ", s);
  }

//+------------------------------------------------------------------+
//| Shows "Sending..." at once, before a request that blocks         |
//+------------------------------------------------------------------+
void ShowSending()
  {
   SetStatus("Sending...", C_DIM);
   Render();
  }

//+------------------------------------------------------------------+
//| Price with the digits of the symbol                              |
//+------------------------------------------------------------------+
string Px(const double v)
  {
   return(DoubleToString(v, g_digits));
  }

//+------------------------------------------------------------------+
//| Price on the tick grid; dir -1 down, 0 nearest, +1 up; 0 = none  |
//+------------------------------------------------------------------+
double TickPrice(const double p, const int dir)
  {
   if(p <= 0)
      return(0.0);
   double ts = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(ts <= 0)
      ts = g_point;
   if(ts <= 0)
      return(NormalizeDouble(p, g_digits));
   double k = p / ts;
   double r = dir < 0 ? MathFloor(k + 1e-7) : (dir > 0 ? MathCeil(k - 1e-7) : MathRound(k));
   double v = NormalizeDouble(r * ts, g_digits);
   return(v > 0 ? v : 0.0);
  }

//+------------------------------------------------------------------+
//| Sends a market deal; RETURN filling by hand when CTrade cannot   |
//+------------------------------------------------------------------+
bool SendDeal(const ENUM_ORDER_TYPE type, const double vol, const double price, const double sl, const double tp,
              const ulong position, const long magic, MqlTradeResult &res, string &err)
  {
   ZeroMemory(res);
   err = "";
   if(ReturnOnly())
     {
      MqlTradeRequest rq;
      ZeroMemory(rq);
      rq.action       = TRADE_ACTION_DEAL;
      rq.symbol       = _Symbol;
      rq.volume       = vol;
      rq.type         = type;
      rq.price        = price;
      rq.sl           = sl;
      rq.tp           = tp;
      rq.deviation    = (ulong)MathMax(0, InpSlippage);
      rq.magic        = (ulong)magic;
      rq.position     = position;
      rq.type_filling = ORDER_FILLING_RETURN;
      rq.type_time    = ORDER_TIME_GTC;
      rq.comment      = position == 0 ? "Trade Pad" : "";
      ResetLastError();
      bool sent = OrderSend(rq, res);
      err = res.comment != "" ? res.comment : StringFormat("retcode %u, error %d", res.retcode, GetLastError());
      return(sent);
     }
   g_trade.SetExpertMagicNumber((ulong)magic);
   bool ok = false;
   if(position > 0)
      ok = g_trade.PositionClose(position);
   else
      if(type == ORDER_TYPE_BUY)
         ok = g_trade.Buy(vol, _Symbol, price, sl, tp, "Trade Pad");
      else
         ok = g_trade.Sell(vol, _Symbol, price, sl, tp, "Trade Pad");
   g_trade.Result(res);
   err = g_trade.ResultRetcodeDescription();
   g_trade.SetExpertMagicNumber((ulong)InpMagic);
   return(ok);
  }

//+------------------------------------------------------------------+
//| 0 failed, 1 filled, 2 partially filled, 3 placed on the exchange |
//+------------------------------------------------------------------+
int DealOutcome(const bool sent, const MqlTradeResult &res, const double vol)
  {
   uint rc = res.retcode;
   if(sent && (rc == TRADE_RETCODE_DONE || rc == TRADE_RETCODE_DONE_PARTIAL) && res.deal > 0)
     {
      if(rc == TRADE_RETCODE_DONE_PARTIAL || (res.volume > 0 && res.volume < vol - g_vstep / 2.0))
         return(2);
      return(1);
     }
   if(sent && Exchange() && res.order > 0 &&
      (rc == TRADE_RETCODE_DONE || rc == TRADE_RETCODE_DONE_PARTIAL || rc == TRADE_RETCODE_PLACED))
      return(3);
   return(0);
  }

//+------------------------------------------------------------------+
//| Stop loss and take profit of the position opened by a deal       |
//+------------------------------------------------------------------+
string ActualStops(const ulong deal, double sl, double tp)
  {
   string tag = " (requested)";
   if(deal > 0 && HistoryDealSelect(deal))
     {
      long pid = HistoryDealGetInteger(deal, DEAL_POSITION_ID);
      if(pid > 0 && PositionSelectByTicket((ulong)pid))
        {
         sl  = PositionGetDouble(POSITION_SL);
         tp  = PositionGetDouble(POSITION_TP);
         tag = "";
        }
     }
   return(", SL " + (sl > 0 ? Px(sl) : "none") + ", TP " + (tp > 0 ? Px(tp) : "none") + tag);
  }

//+------------------------------------------------------------------+
//| Arms or confirms CLOSE ALL / CLOSE LOSS; true = act now          |
//+------------------------------------------------------------------+
bool Confirmed(ulong &deadline, ulong &armed, const bool scripted, const string what)
  {
   ulong ms = GetTickCount64();
   if(deadline == 0 || ms > deadline)
     {
      deadline = ms + CONFIRM_MS;
      armed    = ms;
      SetStatus("Click CONFIRM within 3 seconds to " + what, C_MID);
      return(false);
     }
   if(scripted && !InpScriptedConfirm)
     {
      SetStatus("A scripted press cannot confirm: click CONFIRM", C_MID);
      return(false);
     }
//--- the second click of an accidental double click is ignored
   if(ms - armed < CONFIRM_MIN)
      return(false);
   deadline = 0;
   return(true);
  }

//+------------------------------------------------------------------+
//| A button was clicked, or pressed by the scripted control         |
//+------------------------------------------------------------------+
void Press(const int b, const bool scripted)
  {
   if(b < 1 || b >= BTN)
      return;
   g_prs[b] = 1.0;
   if(b == B_TOGGLE)
     {
      //--- collapsed (by choice or because the chart is short): expand only when it fits
      bool expand = !g_wantOpen;
      if(expand)
        {
         ReadChartSize();
         if(g_ch > 0 && g_ch < g_hFull)
           {
            SetStatus("The chart is too short to expand the pad", C_MID);
            return;
           }
        }
      g_userOpen = expand;
      if(ClampPosition())
         MovePanel();
      SaveState();
      return;
     }
   if(b == B_MINUS || b == B_PLUS)
     {
      g_lot     = NormLot(g_lot + (b == B_PLUS ? g_vstep : -g_vstep));
      g_lotWant = g_lot;
      SaveState();
      Refresh();
      return;
     }
   if(g_block[b] != "")
     {
      SetStatus(g_block[b], C_MID);
      return;
     }
//--- a click right after a trade request is the tail of a double click
   if(g_tradeEnd > 0 && GetTickCount64() - g_tradeEnd < TRADE_GAP)
      return;
   if(b == B_BUY || b == B_SELL)
     {
      OpenOrder(b == B_BUY);
      return;
     }
   if(b == B_ALL)
     {
      if(Confirmed(g_confAll, g_armAll, scripted, "close all"))
         CloseWhere(0);
      return;
     }
   if(b == B_LOSS)
     {
      if(Confirmed(g_confLoss, g_armLoss, scripted, "close the losses"))
         CloseWhere(2);
      return;
     }
   if(b == B_PROFIT)
      CloseWhere(1);
   if(b == B_BE)
      Breakeven();
  }

//+------------------------------------------------------------------+
//| Sends a market order with the lot, stop loss and take profit     |
//+------------------------------------------------------------------+
void OpenOrder(const bool buy)
  {
   Refresh();
   double price = buy ? g_ask : g_bid;
   string side  = buy ? "Buy" : "Sell";
   string lots  = DoubleToString(g_lot, g_ldig);
   if(!g_tickOk || price <= 0 || g_point <= 0)
     {
      SetStatus("No price for " + _Symbol + " yet", C_DOWN);
      return;
     }
//--- stops closer than the broker allows are refused, never widened
   int lvl = (int)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
   if(InpSL > 0 && lvl > 0 && InpSL < lvl + g_spread)
     {
      SetStatus(StringFormat("Stop loss %d points is below the minimum of %d (stops level %d + spread %d)", InpSL, lvl + g_spread, lvl, g_spread), C_DOWN);
      return;
     }
   if(InpTP > 0 && lvl > 0 && InpTP < lvl)
     {
      SetStatus(StringFormat("Take profit %d points is below the minimum of %d points", InpTP, lvl), C_DOWN);
      return;
     }
   double sl = 0, tp = 0;
   if(InpSL > 0)
      sl = buy ? TickPrice(price - InpSL * g_point, -1) : TickPrice(price + InpSL * g_point, 1);
   if(InpTP > 0)
      tp = buy ? TickPrice(price + InpTP * g_point, 1) : TickPrice(price - InpTP * g_point, -1);
   string stops = (sl > 0 ? ", SL " + Px(sl) : "") + (tp > 0 ? ", TP " + Px(tp) : "");
   if(InpPractice)
     {
      SetStatus("Practice: " + side + " " + lots + " at " + Px(price) + stops, g_accent);
      g_tradeEnd = GetTickCount64();
      return;
     }
   ShowSending();
   MqlTradeResult res;
   string err = "";
   bool   sent = SendDeal(buy ? ORDER_TYPE_BUY : ORDER_TYPE_SELL, g_lot, price, sl, tp, 0, InpMagic, res, err);
   int    out  = DealOutcome(sent, res, g_lot);
   double fill = res.price > 0 ? res.price : price;
   if(out == 1)
      SetStatus(side + " " + lots + " filled at " + Px(fill) + ActualStops(res.deal, sl, tp), C_UP);
   else
      if(out == 2)
         SetStatus(side + " partially filled: " + DoubleToString(res.volume, g_ldig) + " of " + lots + " at " + Px(fill) + ActualStops(res.deal, sl, tp), C_MID);
      else
         if(out == 3)
            SetStatus(side + " " + lots + " placed, order #" + IntegerToString((long)res.order), C_UP);
         else
            SetStatus(side + " " + lots + " failed: " + err, C_DOWN);
   g_tradeEnd = GetTickCount64();
   Refresh();
  }

//+------------------------------------------------------------------+
//| Closes the positions: mode 0 all, 1 in profit, 2 at a loss       |
//+------------------------------------------------------------------+
void CloseWhere(const int mode)
  {
   Refresh();
   ulong tickets[];
   int   n = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong tk = PositionGetTicket(i);
      if(tk == 0 || !Mine())
         continue;
      double p = PositionGetDouble(POSITION_PROFIT) + PositionGetDouble(POSITION_SWAP);
      if(mode == 1 && p <= 0)
         continue;
      if(mode == 2 && p >= 0)
         continue;
      ArrayResize(tickets, n + 1);
      tickets[n++] = tk;
     }
   string what = mode == 1 ? " in profit" : (mode == 2 ? " at a loss" : "");
   string plur = n == 1 ? "" : "s";
   if(n == 0)
     {
      SetStatus("No position" + what + " to close", C_DIM);
      return;
     }
   if(InpPractice)
     {
      SetStatus(StringFormat("Practice: would close %d position%s%s", n, plur, what), g_accent);
      g_tradeEnd = GetTickCount64();
      return;
     }
   if(!g_tickOk)
     {
      SetStatus("No price for " + _Symbol + " yet", C_DOWN);
      return;
     }
   ShowSending();
   int    ok = 0, part = 0, placed = 0, gone = 0, bad = 0;
   string err = "";
   for(int i = 0; i < n; i++)
     {
      //--- a position that is not there any more was closed meanwhile
      if(!PositionSelectByTicket(tickets[i]))
        {
         gone++;
         continue;
        }
      bool   buy   = PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY;
      double vol   = PositionGetDouble(POSITION_VOLUME);
      long   magic = PositionGetInteger(POSITION_MAGIC);
      MqlTick t;
      if(!SymbolInfoTick(_Symbol, t) || t.bid <= 0 || t.ask <= 0)
        {
         bad++;
         err = "no price";
         continue;
        }
      MqlTradeResult res;
      string e = "";
      bool   sent = SendDeal(buy ? ORDER_TYPE_SELL : ORDER_TYPE_BUY, vol, buy ? t.bid : t.ask, 0, 0, tickets[i], magic, res, e);
      int    out  = DealOutcome(sent, res, vol);
      if(out == 1)
         ok++;
      else
         if(out == 2)
            part++;
         else
            if(out == 3)
               placed++;
            else
               if(!PositionSelectByTicket(tickets[i]))
                  gone++;
               else
                 {
                  bad++;
                  err = e;
                 }
     }
   string s = StringFormat("Closed %d position%s%s", ok, ok == 1 ? "" : "s", what);
   if(part > 0)
      s += StringFormat(", %d partially", part);
   if(placed > 0)
      s += StringFormat(", %d placed", placed);
   if(gone > 0)
      s += StringFormat(", %d already closed", gone);
   if(bad > 0)
      s += StringFormat(", %d failed: %s", bad, err);
   SetStatus(s, bad > 0 ? C_DOWN : (part > 0 ? C_MID : C_UP));
   g_tradeEnd = GetTickCount64();
   Refresh();
  }

//+------------------------------------------------------------------+
//| Moves the stop loss to the open price of positions in profit     |
//+------------------------------------------------------------------+
void Breakeven()
  {
   Refresh();
   if(!g_tickOk || g_point <= 0)
     {
      SetStatus("No price for " + _Symbol + " yet", C_DOWN);
      return;
     }
   double lvl = (double)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL) * g_point;
   ulong  tickets[];
   double opens[], tps[];
   int    n = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong tk = PositionGetTicket(i);
      if(tk == 0 || !Mine())
         continue;
      bool   buy  = PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY;
      double open = TickPrice(PositionGetDouble(POSITION_PRICE_OPEN), 0);
      double sl   = PositionGetDouble(POSITION_SL);
      if(open <= 0)
         continue;
      //--- in profit by at least the stops level, and the stop is not already at or beyond the open price
      double dist = buy ? g_bid - open : open - g_ask;
      if(dist <= 0 || dist < lvl)
         continue;
      if(buy && sl >= open - g_point / 2.0)
         continue;
      if(!buy && sl > 0 && sl <= open + g_point / 2.0)
         continue;
      ArrayResize(tickets, n + 1);
      ArrayResize(opens, n + 1);
      ArrayResize(tps, n + 1);
      tickets[n] = tk;
      opens[n]   = open;
      tps[n]     = PositionGetDouble(POSITION_TP);
      n++;
     }
   string plur = n == 1 ? "" : "s";
   if(n == 0)
     {
      SetStatus("No position in profit eligible for breakeven", C_DIM);
      return;
     }
   if(InpPractice)
     {
      SetStatus(StringFormat("Practice: would move %d stop%s to breakeven", n, plur), g_accent);
      g_tradeEnd = GetTickCount64();
      return;
     }
   ShowSending();
   int    ok = 0, gone = 0, bad = 0;
   string err = "";
   for(int i = 0; i < n; i++)
     {
      if(!PositionSelectByTicket(tickets[i]))
        {
         gone++;
         continue;
        }
      g_trade.SetExpertMagicNumber((ulong)PositionGetInteger(POSITION_MAGIC));
      bool sent = g_trade.PositionModify(tickets[i], opens[i], tps[i]);
      uint rc   = g_trade.ResultRetcode();
      g_trade.SetExpertMagicNumber((ulong)InpMagic);
      if(sent && (rc == TRADE_RETCODE_DONE || rc == TRADE_RETCODE_NO_CHANGES))
         ok++;
      else
         if(!PositionSelectByTicket(tickets[i]))
            gone++;
         else
           {
            bad++;
            err = g_trade.ResultRetcodeDescription();
           }
     }
   string s = StringFormat("Breakeven set on %d position%s", ok, ok == 1 ? "" : "s");
   if(gone > 0)
      s += StringFormat(", %d already closed", gone);
   if(bad > 0)
      s += StringFormat(", %d failed: %s", bad, err);
   SetStatus(s, bad > 0 ? C_DOWN : C_UP);
   g_tradeEnd = GetTickCount64();
   Refresh();
  }

//+------------------------------------------------------------------+
//| 1234567.8 -> "1,234,567.80", with a plus sign on request         |
//+------------------------------------------------------------------+
string Num(const double v, const bool sign = false, const int dec = 2)
  {
   double lim = dec > 0 ? 0.5 * MathPow(10, -dec) : 0.5;
   if(MathAbs(v) < lim)
      return(dec > 0 ? DoubleToString(0.0, dec) : "0");
   string s = DoubleToString(MathAbs(v), dec);
   int dot = StringFind(s, ".");
   if(dot < 0)
      dot = StringLen(s);
   string ip = StringSubstr(s, 0, dot), out = "";
   int n = StringLen(ip);
   for(int i = 0; i < n; i++)
     {
      out += StringSubstr(ip, i, 1);
      int rem = n - 1 - i;
      if(rem > 0 && rem % 3 == 0)
         out += ",";
     }
   if(dot < StringLen(s))
      out += StringSubstr(s, dot);
   if(v < 0)
      return("-" + out);
   return(sign ? "+" + out : out);
  }

//+------------------------------------------------------------------+
//| Green for a gain, red for a loss, white for zero                 |
//+------------------------------------------------------------------+
uint Tone(const double v)
  {
   if(v > 0.004)
      return(C_UP);
   if(v < -0.004)
      return(C_DOWN);
   return(C_INK);
  }

//+------------------------------------------------------------------+
//| Shrinks the font from px0 down to pxMin until the text fits      |
//+------------------------------------------------------------------+
bool FitPx(const string s, const int maxW, const int px0, const int pxMin, const bool bold, int &px)
  {
   px = px0;
   while(px > pxMin && g_cv.TextW(s, px, bold) > maxW)
      px--;
   return(g_cv.TextW(s, px, bold) <= maxW);
  }

//+------------------------------------------------------------------+
//| Cuts a text and ends it with ".." so that it fits maxW           |
//+------------------------------------------------------------------+
string Clip(const string s, const int maxW, const int px, const bool bold)
  {
   if(g_cv.TextW(s, px, bold) <= maxW)
      return(s);
   string b = s;
   while(StringLen(b) > 1 && g_cv.TextW(b + "..", px, bold) > maxW)
      b = StringSubstr(b, 0, StringLen(b) - 1);
   return(b + "..");
  }

//+------------------------------------------------------------------+
//| Floating result that fits maxW: smaller, shorter, then clipped   |
//+------------------------------------------------------------------+
string FitMoney(const double v, const string suffix, const int maxW, const int px0, int &px)
  {
   string full = Num(v, true) + suffix;
   if(FitPx(full, maxW, px0, S(8), true, px))
      return(full);
   string bare = Num(v, true);
   if(suffix != "" && FitPx(bare, maxW, px0, S(8), true, px))
      return(bare);
   string whole = Num(v, true, 0);
   if(FitPx(whole, maxW, px0, S(7), true, px))
      return(whole);
   return(Clip(whole, maxW, px, true));
  }

//+------------------------------------------------------------------+
//| Account mode shown in the header                                 |
//+------------------------------------------------------------------+
string ModeText(const bool online)
  {
   if(InpPractice)
      return("PRACTICE");
   if(!online)
      return("OFFLINE");
   long tm = AccountInfoInteger(ACCOUNT_TRADE_MODE);
   if(tm == ACCOUNT_TRADE_MODE_DEMO)
      return("DEMO");
   if(tm == ACCOUNT_TRADE_MODE_CONTEST)
      return("CONTEST");
   return("REAL");
  }

//+------------------------------------------------------------------+
//| Creates or resizes the canvas and paints the static background   |
//+------------------------------------------------------------------+
bool Prepare(const int h)
  {
   if(g_ready && h == g_h)
      return(true);
   if(!g_ready)
     {
      if(!g_cv.CreateBitmapLabel(0, 0, g_obj, g_px, g_py, g_w, h, COLOR_FORMAT_ARGB_NORMALIZE))
         return(false);
      //--- not selectable (cannot be dragged or deleted by mistake), hidden from the object list,
      //--- above other objects so that it wins the click
      ObjectSetInteger(0, g_obj, OBJPROP_CORNER, CORNER_LEFT_UPPER);
      ObjectSetInteger(0, g_obj, OBJPROP_ANCHOR, ANCHOR_LEFT_UPPER);
      ObjectSetInteger(0, g_obj, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, g_obj, OBJPROP_SELECTED, false);
      ObjectSetInteger(0, g_obj, OBJPROP_HIDDEN, true);
      ObjectSetInteger(0, g_obj, OBJPROP_BACK, false);
      ObjectSetInteger(0, g_obj, OBJPROP_ZORDER, 1000);
      g_ready = true;
     }
   else
      g_cv.Resize(g_w, h);
   g_h = h;
   g_cv.Background(S(14), C_TOP, C_BOT, C_EDGE, g_accent, g_hFull);
   g_cv.Save(g_bg);
   return(true);
  }

//+------------------------------------------------------------------+
//| Ripple of a click, clipped to the button                         |
//+------------------------------------------------------------------+
void DrawRipple(const int b, const double x, const double y, const double w, const double h, const double r, const ulong ms)
  {
   if(g_ripT[b] == 0 || ms - g_ripT[b] >= 520)
      return;
   double t = (double)(ms - g_ripT[b]) / 520.0;
   double e = 1.0 - (1.0 - t) * (1.0 - t) * (1.0 - t);
   g_cv.Ripple(x, y, w, h, r, g_ripX[b], g_ripY[b], MathMax(w, h) * 1.15 * e, C_INK, 0.30 * (1.0 - t));
  }

//+------------------------------------------------------------------+
//| Price with the pips large: 1.10|54|2                             |
//+------------------------------------------------------------------+
void DrawPrice(const int cx, const int base, const double price, const uint col)
  {
   string s = price > 0 ? Px(price) : "-";
   int    len = StringLen(s), nt = 0, nb = 0;
   if(price > 0 && (g_digits == 3 || g_digits == 5) && len > 3)
     {
      nt = 1;
      nb = 2;
     }
   else
      if(price > 0 && len > 2)
         nb = 2;
      else
         nb = len;
   string head = StringSubstr(s, 0, len - nb - nt);
   string big  = StringSubstr(s, len - nb - nt, nb);
   string tail = nt > 0 ? StringSubstr(s, len - nt) : "";
   int ph = S(15), pb = S(27), pt = S(13);
   int wh = head != "" ? g_cv.TextW(head, ph, true) : 0;
   int wb = g_cv.TextW(big, pb, true);
   int wt = tail != "" ? g_cv.TextW(tail, pt, true) : 0;
   int x0 = cx - (wh + wb + wt) / 2;
   if(head != "")
      g_cv.Text(x0, base - S(2), head, CPanel::Mix(C_TILE, col, 0.78), ph, true, TA_LEFT | TA_BOTTOM);
   g_cv.Text(x0 + wh, base, big, col, pb, true, TA_LEFT | TA_BOTTOM);
   if(tail != "")
      g_cv.Text(x0 + wh + wb + S(1), base - g_cv.TextH(big, pb, true) + S(5), tail, col, pt, true, TA_LEFT | TA_TOP);
  }

//+------------------------------------------------------------------+
//| BUY or SELL button with the live price                           |
//+------------------------------------------------------------------+
void DrawTradeButton(const int b, const string label, const double price, const uint col, const ulong ms)
  {
   int x = 0, y = 0, w = 0, h = 0;
   ButtonRect(b, x, y, w, h);
   bool   on = g_block[b] == "";
   double hv = g_hov[b], pr = g_prs[b];
   double ins = Sf(2.5) * pr;
   double fx = x + ins, fy = y + ins, fw = w - 2 * ins, fh = h - 2 * ins, r = Sf(11);
   if(on && hv > 0.01)
      g_cv.Halo(fx, fy, fw, fh, r, Sf(11), col, 0.32 * hv);
   uint base = on ? CPanel::Mix(C_TILE, col, 0.14 + 0.10 * hv + 0.30 * pr) : C_TILE;
   g_cv.RRect(fx, fy, fw, fh, r, base, 1.0);
   g_cv.RRect(fx + 1, fy + 1, fw - 2, fh * 0.46, r - 1, C_INK, 0.03 + 0.03 * hv);
   if(on)
      DrawRipple(b, fx, fy, fw, fh, r, ms);
   g_cv.RRect(fx + S(14), fy + fh - S(7), fw - S(28), S(2), S(1), on ? col : C_DIM, on ? 0.55 + 0.45 * hv : 0.35);
   g_cv.Text(x + w / 2, y + S(10), label, on ? col : C_DIM, S(10), true, TA_CENTER | TA_TOP);
   DrawPrice(x + w / 2, y + S(58), price, on ? C_INK : C_DIM);
  }

//+------------------------------------------------------------------+
//| Lot minus or plus, with the sign drawn as antialiased lines      |
//+------------------------------------------------------------------+
void DrawStepper(const int b, const ulong ms)
  {
   int x = 0, y = 0, w = 0, h = 0;
   ButtonRect(b, x, y, w, h);
   bool   edge = b == B_MINUS ? g_lot <= g_vmin + g_vstep / 2.0 : g_lot >= g_vmax - g_vstep / 2.0;
   double hv = g_hov[b], pr = g_prs[b];
   double ins = Sf(2) * pr;
   double fx = x + ins, fy = y + ins, fw = w - 2 * ins, fh = h - 2 * ins, r = Sf(10);
   if(hv > 0.01)
      g_cv.Halo(fx, fy, fw, fh, r, Sf(9), g_accent, 0.28 * hv);
   g_cv.RRect(fx, fy, fw, fh, r, CPanel::Mix(C_TILE, g_accent, 0.06 + 0.14 * hv + 0.35 * pr), 1.0);
   DrawRipple(b, fx, fy, fw, fh, r, ms);
   double cx = x + w / 2.0, cy = y + h / 2.0, k = Sf(6.5);
   uint   ink = edge ? C_DIM : C_INK;
   g_cv.Line(cx - k, cy, cx + k, cy, Sf(2.2), ink, 1.0);
   if(b == B_PLUS)
      g_cv.Line(cx, cy - k, cx, cy + k, Sf(2.2), ink, 1.0);
  }

//+------------------------------------------------------------------+
//| One of the four action buttons                                   |
//+------------------------------------------------------------------+
void DrawAction(const int b, const string label, const uint acc, const ulong ms)
  {
   int x = 0, y = 0, w = 0, h = 0;
   ButtonRect(b, x, y, w, h);
   ulong  dl   = b == B_ALL ? g_confAll : (b == B_LOSS ? g_confLoss : 0);
   bool   on   = g_block[b] == "";
   bool   conf = dl > ms;
   double hv = g_hov[b], pr = g_prs[b];
   double ins = Sf(2) * pr;
   double fx = x + ins, fy = y + ins, fw = w - 2 * ins, fh = h - 2 * ins, r = Sf(9);
   if(conf)
     {
      double beat = 0.5 + 0.5 * MathSin((double)ms / 140.0);
      g_cv.Halo(fx, fy, fw, fh, r, Sf(10), C_MID, 0.20 + 0.25 * beat);
     }
   else
      if(on && hv > 0.01)
         g_cv.Halo(fx, fy, fw, fh, r, Sf(9), acc, 0.26 * hv);
   uint base = on ? CPanel::Mix(C_TILE, conf ? C_MID : acc, 0.05 + 0.12 * hv + 0.30 * pr + (conf ? 0.22 : 0.0)) : C_TILE;
   g_cv.RRect(fx, fy, fw, fh, r, base, 1.0);
   if(on)
      DrawRipple(b, fx, fy, fw, fh, r, ms);
   g_cv.Disc(x + S(16), y + h / 2.0, Sf(3.2), conf ? C_MID : acc, on ? 1.0 : 0.35, on ? Sf(3) * hv : 0.0);
   g_cv.Text(x + w / 2 + S(6), y + h / 2, conf ? "CONFIRM" : label, on ? (conf ? C_MID : C_INK) : C_DIM, S(11), true, TA_CENTER | TA_VCENTER);
   if(conf)
     {
      double frac = (double)(dl - ms) / (double)CONFIRM_MS;
      g_cv.RRect(fx + S(10), fy + fh - S(5), (fw - S(20)) * frac, S(2), S(1), C_MID, 1.0);
     }
  }

//+------------------------------------------------------------------+
//| Round collapse button, the chevron turns with the animation      |
//+------------------------------------------------------------------+
void DrawToggle(const double f)
  {
   int x = 0, y = 0, w = 0, h = 0;
   ButtonRect(B_TOGGLE, x, y, w, h);
   double cx = x + w / 2.0, cy = y + h / 2.0, r = w / 2.0;
   double hv = g_hov[B_TOGGLE], pr = g_prs[B_TOGGLE];
   if(hv > 0.01)
      g_cv.Disc(cx, cy, r, g_accent, 0.30 * hv, Sf(7));
   g_cv.Disc(cx, cy, r - Sf(1.5) * pr, CPanel::Mix(C_TILE, g_accent, 0.10 + 0.22 * hv + 0.35 * pr), 1.0);
   g_cv.Arc(cx, cy, r - Sf(1.5) * pr - 0.5, 1.0, 0.0, 360.0, C_EDGE, 1.0);
//--- "^" when expanded (click to collapse), "v" when collapsed
   double a = M_PI * (1.0 - f), ca = MathCos(a), sa = MathSin(a);
   double px[3], py[3];
   px[0] = -Sf(4.5);
   py[0] = Sf(2.2);
   px[1] = 0.0;
   py[1] = -Sf(2.3);
   px[2] = Sf(4.5);
   py[2] = Sf(2.2);
   double qx[3], qy[3];
   for(int i = 0; i < 3; i++)
     {
      qx[i] = cx + px[i] * ca - py[i] * sa;
      qy[i] = cy + px[i] * sa + py[i] * ca;
     }
   g_cv.Line(qx[0], qy[0], qx[1], qy[1], Sf(1.8), C_INK, 1.0);
   g_cv.Line(qx[1], qy[1], qx[2], qy[2], Sf(1.8), C_INK, 1.0);
  }

//+------------------------------------------------------------------+
//| One frame, timed when ETP_PROFILE is defined                     |
//+------------------------------------------------------------------+
void Render()
  {
#ifdef ETP_PROFILE
   ulong t0 = GetMicrosecondCount();
#endif
   g_lastDraw = GetTickCount64();
   if(g_ready)
      PadIntact();
   Paint();
#ifdef ETP_PROFILE
   ulong dt = GetMicrosecondCount() - t0;
   g_prfFrames++;
   g_prfSum += dt;
   if(dt > g_prfMax)
      g_prfMax = dt;
#endif
  }

//+------------------------------------------------------------------+
//| Draws the whole panel                                            |
//+------------------------------------------------------------------+
void Paint()
  {
   double f = g_open * g_open * (3.0 - 2.0 * g_open);
   int    h = g_hBar + (int)MathRound((g_hFull - g_hBar) * f);
   if(!Prepare(h))
      return;
   g_cv.Load(g_bg);

   ulong  ms  = GetTickCount64();
   double pul = (double)(ms % 1600) / 1600.0;
   int    xl  = S(18), xr = g_w - S(18), cx = g_w / 2;

//--- light running along the top edge
   double sx = (double)(ms % 5200) / 5200.0 * (g_w + S(240)) - S(120);
   for(int x = (int)(sx - S(110)); x <= (int)(sx + S(110)); x++)
     {
      double k = 1.0 - MathAbs(x - sx) / S(110);
      g_cv.Bl(x, 1, g_accent, 0.9 * k * k);
      g_cv.Bl(x, 2, g_accent, 0.35 * k * k);
     }

//--- header: title, symbol, live dot, mode or floating result, collapse button
   int    hy     = S(22);
   bool   online = (bool)TerminalInfoInteger(TERMINAL_CONNECTED);
   uint   dot    = online ? (InpPractice ? g_accent : C_UP) : C_DIM;
   double dx     = g_w - S(56);
   string mode   = ModeText(online);
   int    right  = (int)dx - S(10);
   int    symX   = xl + g_cv.TextW("TRADE PAD", S(11), true) + S(8);
   int    symMax = right - MathMax(g_cv.TextW(mode, S(11), true), S(60)) - S(8) - symX;
   int    spx    = S(11);
   string sym    = _Symbol;
   if(!FitPx(sym, symMax, S(11), S(8), true, spx))
      sym = Clip(sym, symMax, spx, true);
   g_cv.Text(xl, hy, "TRADE PAD", C_DIM, S(11), true, TA_LEFT | TA_VCENTER);
   g_cv.Text(symX, hy, sym, g_accent, spx, true, TA_LEFT | TA_VCENTER);
   DrawToggle(f);
   if(online)
      g_cv.Disc(dx, hy, Sf(3) + Sf(7) * pul, dot, 0.35 * (1.0 - pul));
   g_cv.Disc(dx, hy, Sf(3), dot, 1.0);
   if(f > 0.02)
      g_cv.Text(right, hy, mode, CPanel::Mix(C_TOP, C_DIM, f), S(11), true, TA_RIGHT | TA_VCENTER);
   if(f < 0.98)
     {
      int    fpx  = S(13);
      int    room = right - (symX + g_cv.TextW(sym, spx, true) + S(10));
      string fl   = FitMoney(g_float, " " + g_cur, room, S(13), fpx);
      g_cv.Text(right, hy, fl, CPanel::Mix(C_TOP, Tone(g_float), 1.0 - f), fpx, true, TA_RIGHT | TA_VCENTER);
     }
   if(f > 0.02)
      g_cv.RRect(xl, S(43), xr - xl, 1, 0, C_TRACK, f);

   if(h > g_hBar + 1)
     {
      //--- SELL and BUY with the spread between them
      DrawTradeButton(B_SELL, "SELL", g_bid, C_DOWN, ms);
      DrawTradeButton(B_BUY, "BUY", g_ask, C_UP, ms);
      g_cv.Text(cx, S(64), "SPREAD", C_DIM, S(8), true, TA_CENTER | TA_TOP);
      g_cv.RRect(cx - S(19), S(78), S(38), S(26), S(13), C_BOT, 0.85);
      g_cv.RRect(cx - S(19), S(78), S(38), S(26), S(13), g_accent, 0.10);
      string sp  = g_tickOk ? IntegerToString(g_spread) : "-";
      int    ppx = S(12);
      if(!FitPx(sp, S(32), S(12), S(7), true, ppx))
         sp = Clip(sp, S(32), ppx, true);
      g_cv.Text(cx, S(91), sp, C_INK, ppx, true, TA_CENTER | TA_VCENTER);

      //--- lot stepper
      double pop = MathMax(g_prs[B_MINUS], g_prs[B_PLUS]);
      DrawStepper(B_MINUS, ms);
      DrawStepper(B_PLUS, ms);
      g_cv.Text(cx, S(136), "LOT", C_DIM, S(9), true, TA_CENTER | TA_TOP);
      g_cv.Text(cx, S(165), DoubleToString(g_lot, g_ldig), CPanel::Mix(C_INK, g_accent, pop), S(24 + 4 * pop), true, TA_CENTER | TA_VCENTER);

      //--- margin, stops, point value
      int iy = S(192), vy = S(205);
      string pv = g_pointValue <= 0 ? "-" : (g_pointValue < 0.01 ? DoubleToString(g_pointValue, 4) : (g_pointValue < 1 ? DoubleToString(g_pointValue, 3) : Num(g_pointValue)));
      string st = (InpSL > 0 ? IntegerToString(InpSL) : "off") + " / " + (InpTP > 0 ? IntegerToString(InpTP) : "off");
      g_cv.Text(xl, iy, "MARGIN", C_DIM, S(9), true, TA_LEFT | TA_TOP);
      g_cv.Text(xl, vy, g_margin < 0 ? "-" : Num(g_margin) + " " + g_cur, C_INK, S(12), true, TA_LEFT | TA_TOP);
      g_cv.Text(cx, iy, "SL / TP POINTS", C_DIM, S(9), true, TA_CENTER | TA_TOP);
      g_cv.Text(cx, vy, st, C_INK, S(12), true, TA_CENTER | TA_TOP);
      g_cv.Text(xr, iy, "1 POINT", C_DIM, S(9), true, TA_RIGHT | TA_TOP);
      g_cv.Text(xr, vy, g_pointValue <= 0 ? "-" : pv + " " + g_cur, C_INK, S(12), true, TA_RIGHT | TA_TOP);

      //--- actions
      DrawAction(B_ALL, "CLOSE ALL", C_MID, ms);
      DrawAction(B_PROFIT, "CLOSE PROFIT", C_UP, ms);
      DrawAction(B_LOSS, "CLOSE LOSS", C_DOWN, ms);
      DrawAction(B_BE, "BREAKEVEN", g_accent, ms);

      //--- positions, lots, floating: real values; only the bar of the floating tile eases
      string names[3] = {"POSITIONS", "LOTS", "FLOATING"};
      int ty = S(320), th = S(48), gap = S(8);
      int tw = (xr - xl - 2 * gap) / 3;
      string vals[3];
      int    pxs[3];
      vals[0] = IntegerToString(g_count);
      vals[1] = DoubleToString(g_lots, g_ldig);
      pxs[0]  = S(14);
      pxs[1]  = S(14);
      vals[2] = FitMoney(g_float, "", tw - S(20), S(14), pxs[2]);
      uint tones[3];
      tones[0] = C_INK;
      tones[1] = C_INK;
      tones[2] = Tone(g_float);
      uint ease = Tone(g_floatEase);
      for(int k = 0; k < 3; k++)
        {
         int tx = xl + k * (tw + gap);
         uint bar = k == 2 ? (ease == C_INK ? C_DIM : ease) : g_accent;
         g_cv.RRect(tx, ty, tw, th, S(9), C_TILE, 1.0);
         g_cv.RRect(tx + S(10), ty + th - S(5), tw - S(20), S(2), S(1), bar, k == 2 ? 0.85 : 0.45);
         g_cv.Text(tx + S(10), ty + S(8), names[k], C_DIM, S(9), true, TA_LEFT | TA_TOP);
         g_cv.Text(tx + S(10), ty + S(20) + (S(14) - pxs[k]) / 2, vals[k], tones[k], pxs[k], true, TA_LEFT | TA_TOP);
        }

      //--- status of the last action, fading out; at rest the scope of the pad
      double a = 0.0;
      if(g_status != "" && g_statusT > 0)
        {
         double age = (double)(ms - g_statusT);
         a = age < 4000 ? 1.0 : 1.0 - (age - 4000) / 1500.0;
        }
      if(a > 0)
        {
         string s = Clip(g_status, xr - xl, S(11), false);
         g_cv.Text(cx, S(386), s, CPanel::Mix(C_BOT, g_statusCol, a), S(11), false, TA_CENTER | TA_VCENTER);
        }
      else
         g_cv.Text(cx, S(386), "manages " + ScopeName(), CPanel::Mix(C_BOT, C_DIM, 0.75), S(10), false, TA_CENTER | TA_VCENTER);

      //--- signature
      g_cv.RRect(xl, g_hFull - S(31), xr - xl, 1, 0, C_TRACK, 1.0);
      g_cv.Text(cx, g_hFull - S(24), "E U D O R A   L A B", C_DIM, S(9), true, TA_CENTER | TA_TOP);
     }

   g_cv.Update();
  }
//+------------------------------------------------------------------+
