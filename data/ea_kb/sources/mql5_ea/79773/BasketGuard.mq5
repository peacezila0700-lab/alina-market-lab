//+------------------------------------------------------------------+
//|                                                  BasketGuard.mq5 |
//|                          Basket risk limiter for any EA or manual |
//|                                          Roman Zif, profxportal  |
//+------------------------------------------------------------------+
#property copyright "Roman Zif"
#property link      "https://www.mql5.com/en/users/roman_zif/seller"
#property version   "1.00"
#property description "Watches a basket of open positions (all, by Magic number or by symbol)"
#property description "and closes it when floating loss or profit reaches a % of balance."
#property description "Optional: close positions older than N days. Works on hedging and netting accounts."

#include <Trade\Trade.mqh>

//--- inputs
input long   InpMagic         = -1;     // Magic number to watch (-1 = all positions)
input string InpSymbols       = "";     // Symbols to watch, separated by ';' (empty = all)
input double InpLossPercent   = 10.0;   // Close basket at loss, % of balance (0 = off)
input double InpProfitPercent = 0.0;    // Close basket at profit, % of balance (0 = off)
input int    InpMaxAgeDays    = 0;      // Close positions older than N days (0 = off)
input bool   InpLockAfterStop = true;   // After loss stop: close new positions until next day
input int    InpSlippage      = 20;     // Max price deviation, points
input bool   InpShowPanel     = true;   // Show information panel
input color  InpPanelColor    = C'38,110,220'; // Panel accent color
input ENUM_BASE_CORNER InpPanelCorner = CORNER_RIGHT_UPPER; // Panel corner
input int    InpPanelX        = 10;     // Panel offset X, px
input int    InpPanelY        = 20;     // Panel offset Y, px

CTrade   g_trade;
string   g_symbols[];
bool     g_locked      = false;
datetime g_lockDay     = 0;
string   g_status      = "WATCHING";
const string PFX       = "BGuard_";

//--- panel layout and colors
#define PANEL_W   270
#define ROW_H     20
#define PAD       12

color  C_BG     = C'22,27,38';
color  C_BORDER = C'58,68,90';
color  C_LABEL  = C'150,160,180';
color  C_VALUE  = C'235,238,245';
color  C_GREEN  = C'38,190,120';
color  C_ORANGE = C'245,150,50';
color  C_RED    = C'235,70,70';
color  C_TRACK  = C'45,52,68';

double g_k = 1.0;          // DPI scale
int    g_lastCount = 0;
double g_lastFloat = 0.0, g_lastPct = 0.0;


//+------------------------------------------------------------------+
int OnInit()
  {
   if(InpLossPercent < 0 || InpProfitPercent < 0 || InpMaxAgeDays < 0)
     {
      Print("BasketGuard: percent and day values must not be negative");
      return(INIT_PARAMETERS_INCORRECT);
     }
   ParseSymbols();
   g_trade.SetDeviationInPoints(InpSlippage);
   g_trade.SetAsyncMode(false);
   g_k = MathMax(TerminalInfoInteger(TERMINAL_SCREEN_DPI), 96) / 96.0;
   EventSetTimer(1);
   DrawPanel(0, 0, 0);
   return(INIT_SUCCEEDED);
  }
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   EventKillTimer();
   ObjectsDeleteAll(0, PFX);
  }
//+------------------------------------------------------------------+
void OnTick()  { Check(); }
void OnTimer() { Check(); }
//+------------------------------------------------------------------+
void ParseSymbols()
  {
   ArrayResize(g_symbols, 0);
   string s = InpSymbols;
   StringReplace(s, " ", "");
   if(s == "")
      return;
   StringSplit(s, ';', g_symbols);
  }
//+------------------------------------------------------------------+
bool InBasket(const ulong ticket)
  {
   if(!PositionSelectByTicket(ticket))
      return(false);
   if(InpMagic >= 0 && PositionGetInteger(POSITION_MAGIC) != InpMagic)
      return(false);
   int n = ArraySize(g_symbols);
   if(n == 0)
      return(true);
   string sym = PositionGetString(POSITION_SYMBOL);
   for(int i = 0; i < n; i++)
      if(g_symbols[i] != "" && g_symbols[i] == sym)
         return(true);
   return(false);
  }
//+------------------------------------------------------------------+
void Check()
  {
   //--- unlock on a new day
   datetime today = iTime(_Symbol, PERIOD_D1, 0);
   if(g_locked && today != 0 && today != g_lockDay)
     {
      g_locked = false;
      g_status = "WATCHING";
     }

   double balance = AccountInfoDouble(ACCOUNT_BALANCE);
   double floating = 0.0;
   int    count = 0;
   datetime now = TimeCurrent();

   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0 || !InBasket(ticket))
         continue;
      //--- locked after a loss stop: close anything new in the basket
      if(g_locked)
        {
         ClosePosition(ticket);
         continue;
        }
      //--- age limit
      if(InpMaxAgeDays > 0)
        {
         datetime opened = (datetime)PositionGetInteger(POSITION_TIME);
         if(now - opened >= (long)InpMaxAgeDays * 86400)
           {
            PrintFormat("BasketGuard: closing #%I64u, older than %d days", ticket, InpMaxAgeDays);
            ClosePosition(ticket);
            continue;
           }
        }
      floating += PositionGetDouble(POSITION_PROFIT) + PositionGetDouble(POSITION_SWAP);
      count++;
     }

   double pct = (balance > 0.0) ? floating / balance * 100.0 : 0.0;

   if(count > 0 && !g_locked)
     {
      g_status = "WATCHING";
      if(InpLossPercent > 0 && pct <= -InpLossPercent)
        {
         PrintFormat("BasketGuard: loss %.2f%% reached the limit %.2f%%, closing %d positions", pct, InpLossPercent, count);
         CloseBasket();
         g_status = "LOSS STOP - BASKET CLOSED";
         if(InpLockAfterStop)
           {
            g_locked  = true;
            g_lockDay = today;
            g_status  = "LOSS STOP - LOCKED UNTIL NEXT DAY";
           }
        }
      else if(InpProfitPercent > 0 && pct >= InpProfitPercent)
        {
         PrintFormat("BasketGuard: profit %.2f%% reached the target %.2f%%, closing %d positions", pct, InpProfitPercent, count);
         CloseBasket();
         g_status = "PROFIT TARGET - BASKET CLOSED";
        }
     }
   DrawPanel(count, floating, pct);
  }
//+------------------------------------------------------------------+
void CloseBasket()
  {
   //--- several passes: a requote can leave a position open
   for(int pass = 0; pass < 3; pass++)
     {
      int left = 0;
      for(int i = PositionsTotal() - 1; i >= 0; i--)
        {
         ulong ticket = PositionGetTicket(i);
         if(ticket == 0 || !InBasket(ticket))
            continue;
         if(!ClosePosition(ticket))
            left++;
        }
      if(left == 0)
         return;
      Sleep(300);
     }
  }
//+------------------------------------------------------------------+
bool ClosePosition(const ulong ticket)
  {
   if(!g_trade.PositionClose(ticket))
     {
      PrintFormat("BasketGuard: failed to close #%I64u, retcode %u (%s)",
                  ticket, g_trade.ResultRetcode(), g_trade.ResultRetcodeDescription());
      return(false);
     }
   return(true);
  }
//+------------------------------------------------------------------+
//| Panel                                                            |
//+------------------------------------------------------------------+
int Px(const int v) { return (int)MathRound(v * g_k); }

void Rect(const string name, const int x, const int y, const int w, const int h,
          const color bg, const color border)
  {
   string obj = PFX + name;
   if(ObjectFind(0, obj) < 0)
     {
      ObjectCreate(0, obj, OBJ_RECTANGLE_LABEL, 0, 0, 0);
      ObjectSetInteger(0, obj, OBJPROP_CORNER, CORNER_LEFT_UPPER);
      ObjectSetInteger(0, obj, OBJPROP_BORDER_TYPE, BORDER_FLAT);
      ObjectSetInteger(0, obj, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, obj, OBJPROP_HIDDEN, true);
      ObjectSetInteger(0, obj, OBJPROP_BACK, false);
     }
   ObjectSetInteger(0, obj, OBJPROP_XDISTANCE, x);
   ObjectSetInteger(0, obj, OBJPROP_YDISTANCE, y);
   ObjectSetInteger(0, obj, OBJPROP_XSIZE, MathMax(w, 0));
   ObjectSetInteger(0, obj, OBJPROP_YSIZE, h);
   ObjectSetInteger(0, obj, OBJPROP_BGCOLOR, bg);
   ObjectSetInteger(0, obj, OBJPROP_COLOR, border);
  }

void Text(const string name, const int x, const int y, const string text, const color clr,
          const int size = 9, const string font = "Segoe UI",
          const ENUM_ANCHOR_POINT anchor = ANCHOR_LEFT_UPPER)
  {
   string obj = PFX + name;
   if(ObjectFind(0, obj) < 0)
     {
      ObjectCreate(0, obj, OBJ_LABEL, 0, 0, 0);
      ObjectSetInteger(0, obj, OBJPROP_CORNER, CORNER_LEFT_UPPER);
      ObjectSetInteger(0, obj, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, obj, OBJPROP_HIDDEN, true);
      ObjectSetInteger(0, obj, OBJPROP_BACK, false);
     }
   ObjectSetInteger(0, obj, OBJPROP_XDISTANCE, x);
   ObjectSetInteger(0, obj, OBJPROP_YDISTANCE, y);
   ObjectSetInteger(0, obj, OBJPROP_ANCHOR, anchor);
   ObjectSetInteger(0, obj, OBJPROP_FONTSIZE, size);
   ObjectSetString(0, obj, OBJPROP_FONT, font);
   ObjectSetInteger(0, obj, OBJPROP_COLOR, clr);
   ObjectSetString(0, obj, OBJPROP_TEXT, text);
  }

string Shorten(const string s, const int maxLen)
  {
   if(StringLen(s) <= maxLen)
      return(s);
   return(StringSubstr(s, 0, maxLen - 3) + "...");
  }

void Row(const int i, const int x0, const int y, const string label, const string value, const color clr)
  {
   Text("l" + IntegerToString(i), x0 + Px(PAD), y, label, C_LABEL);
   Text("v" + IntegerToString(i), x0 + Px(PANEL_W - PAD), y, value, clr, 9, "Segoe UI Semibold", ANCHOR_RIGHT_UPPER);
  }

//+------------------------------------------------------------------+
void DrawPanel(const int count, const double floating, const double pct)
  {
   g_lastCount = count;
   g_lastFloat = floating;
   g_lastPct   = pct;
   if(!InpShowPanel)
      return;

   string cur  = AccountInfoString(ACCOUNT_CURRENCY);
   int    W    = Px(PANEL_W);
   int    rows = 7;
   int    H    = Px(30 + 8 + rows * ROW_H + 8 + 38 + 8 + 28 + PAD);

   //--- panel position from the chosen corner
   int cw = (int)ChartGetInteger(0, CHART_WIDTH_IN_PIXELS);
   int ch = (int)ChartGetInteger(0, CHART_HEIGHT_IN_PIXELS);
   int x0 = Px(InpPanelX), y0 = Px(InpPanelY);
   if(InpPanelCorner == CORNER_RIGHT_UPPER || InpPanelCorner == CORNER_RIGHT_LOWER)
      x0 = cw - W - Px(InpPanelX);
   if(InpPanelCorner == CORNER_LEFT_LOWER || InpPanelCorner == CORNER_RIGHT_LOWER)
      y0 = ch - H - Px(InpPanelY);
   x0 = MathMax(x0, 0);
   y0 = MathMax(y0, 0);

   //--- frame and header (created first, so they stay under the text)
   Rect("bg", x0, y0, W, H, C_BG, C_BORDER);
   Rect("hdr", x0, y0, W, Px(30), InpPanelColor, InpPanelColor);
   Text("title", x0 + Px(PAD), y0 + Px(6), "BASKET GUARD", clrWhite, 10, "Segoe UI Semibold");
   Text("ver", x0 + W - Px(PAD), y0 + Px(8), "v1.00", clrWhite, 8, "Segoe UI", ANCHOR_RIGHT_UPPER);

   //--- rows
   int y = y0 + Px(38);
   int step = Px(ROW_H);
   string magic = (InpMagic >= 0) ? IntegerToString(InpMagic) : "all";
   string syms  = (ArraySize(g_symbols) > 0) ? Shorten(InpSymbols, 24) : "all";
   color  fc    = (floating > 0.0) ? C_GREEN : (floating < 0.0 ? C_RED : C_VALUE);

   Row(0, x0, y, "Magic",     magic, C_VALUE);                              y += step;
   Row(1, x0, y, "Symbols",   syms, C_VALUE);                               y += step;
   Row(2, x0, y, "Positions", IntegerToString(count), C_VALUE);             y += step;
   Row(3, x0, y, "Floating",  StringFormat("%+.2f %s", floating, cur), fc); y += step;
   Row(4, x0, y, "Floating, % of balance", StringFormat("%+.2f%%", pct), fc); y += step;
   Row(5, x0, y, "Loss stop / Profit target",
       (InpLossPercent > 0 ? "-" + DoubleToString(InpLossPercent, 1) + "%" : "off") + " / " +
       (InpProfitPercent > 0 ? "+" + DoubleToString(InpProfitPercent, 1) + "%" : "off"), C_VALUE); y += step;
   Row(6, x0, y, "Max position age",
       InpMaxAgeDays > 0 ? IntegerToString(InpMaxAgeDays) + " days" : "off", C_VALUE); y += step;

   //--- risk bar: how much of the loss stop is used
   y += Px(8);
   double used = 0.0;
   string usedTxt = "loss stop off";
   if(InpLossPercent > 0)
     {
      used = MathMin(MathMax(-pct, 0.0) / InpLossPercent, 1.0);
      usedTxt = StringFormat("%.0f%% of loss stop", used * 100.0);
     }
   color bc = (used < 0.5) ? C_GREEN : (used < 0.8 ? C_ORANGE : C_RED);
   Text("risk_l", x0 + Px(PAD), y, "Risk used", C_LABEL);
   Text("risk_v", x0 + W - Px(PAD), y, usedTxt, (InpLossPercent > 0 ? bc : C_LABEL), 9, "Segoe UI Semibold", ANCHOR_RIGHT_UPPER);
   int barW = W - Px(2 * PAD);
   Rect("bar_bg", x0 + Px(PAD), y + Px(22), barW, Px(10), C_TRACK, C_TRACK);
   int fillW = (int)MathRound(barW * used);
   color fillC = (fillW > 0) ? bc : C_TRACK;
   Rect("bar_fg", x0 + Px(PAD), y + Px(22), MathMax(fillW, 1), Px(10), fillC, fillC);
   y += Px(38 + 8);

   //--- status badge
   color sc = C_GREEN;
   if(g_locked || StringFind(g_status, "LOSS") >= 0)
      sc = C_RED;
   else if(StringFind(g_status, "PROFIT") >= 0)
      sc = InpPanelColor;
   Rect("st_bg", x0 + Px(PAD), y, barW, Px(28), sc, sc);
   Text("st_t", x0 + W / 2, y + Px(14), g_status, clrWhite, 8, "Segoe UI Semibold", ANCHOR_CENTER);

   ChartRedraw();
  }
//+------------------------------------------------------------------+
void OnChartEvent(const int id, const long &lparam, const double &dparam, const string &sparam)
  {
   if(id == CHARTEVENT_CHART_CHANGE)
      DrawPanel(g_lastCount, g_lastFloat, g_lastPct);
  }
//+------------------------------------------------------------------+
