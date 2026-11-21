//+------------------------------------------------------------------+
//|                                             Prop_Risk_Guard.mq5   |
//|  Account protection for prop-firm challenges and personal         |
//|  accounts: daily loss limit, max drawdown, profit-target lock.   |
//|  On a breach it closes all positions, deletes pending orders and |
//|  keeps closing new trades until the lock resets.                 |
//|  It never opens trades itself (except demo trades in the         |
//|  Strategy Tester, when Demo mode is on).                         |
//+------------------------------------------------------------------+
#property copyright   "Desmond Obafemi"
#property link        "https://www.mql5.com/en/users/478847"
#property version     "1.00"
#property description "Protects your account: daily loss limit, max drawdown and profit-target lock."
#property description "On a breach it closes everything and blocks new trades until the lock resets."
#property description "Attach to ONE chart. Watches the whole account (or one symbol / magic number)."

#include <Trade\Trade.mqh>
#include <Canvas\Canvas.mqh>

enum ENUM_LIMIT_MODE { LIMIT_PERCENT = 0, LIMIT_MONEY = 1 };                          // limit given as
enum ENUM_DAY_BASE   { BASE_BALANCE = 0, BASE_EQUITY = 1, BASE_HIGHER = 2 };           // daily reference
enum ENUM_DD_MODE    { DD_STATIC = 0, DD_TRAILING = 1 };                               // max drawdown type
enum ENUM_SCOPE      { SCOPE_ACCOUNT = 0, SCOPE_SYMBOL = 1, SCOPE_MAGIC = 2 };         // what is protected

input group "=== Daily loss limit ==="
input bool            InpUseDaily      = true;            // Use a daily loss limit
input ENUM_LIMIT_MODE InpDailyMode     = LIMIT_PERCENT;   // Daily limit given as
input double          InpDailyValue    = 5.0;             // Daily limit (% or money)
input ENUM_DAY_BASE   InpDayBase       = BASE_BALANCE;    // Measured from the day's starting
input int             InpResetHour     = 0;               // Day starts at (server hour, 0-23)

input group "=== Max drawdown ==="
input bool            InpUseMaxDD      = true;            // Use a max drawdown limit
input ENUM_LIMIT_MODE InpDDMode        = LIMIT_PERCENT;   // Max drawdown given as
input double          InpDDValue       = 10.0;            // Max drawdown (% or money)
input ENUM_DD_MODE    InpDDType        = DD_STATIC;       // Static (from start) or trailing (from peak)
input double          InpStartBalance  = 0;               // Account starting balance (0 = balance when attached)

input group "=== Profit target ==="
input bool            InpUseTarget     = false;           // Lock the account when the target is reached
input ENUM_LIMIT_MODE InpTargetMode    = LIMIT_PERCENT;   // Target given as
input double          InpTargetValue   = 10.0;            // Profit target (% or money)

input group "=== Protection ==="
input ENUM_SCOPE      InpScope         = SCOPE_ACCOUNT;   // Protect
input long            InpMagic         = 0;               // Magic number (when protecting one magic)
input double          InpWarnPercent   = 80.0;            // Warn when this % of a limit is used
input double          InpBufferPercent = 0.0;             // Safety buffer: act this % of the limit early
input int             InpSlippage      = 30;              // Max slippage when closing (points)

input group "=== Panel and alerts ==="
input bool             InpShowPanel    = true;              // Show panel
input ENUM_BASE_CORNER InpCorner       = CORNER_RIGHT_UPPER; // Panel corner
input int              InpPanelX       = 12;                // Panel X offset (px)
input int              InpPanelY       = 28;                // Panel Y offset (px)
input bool             InpAlertPopup   = true;              // Popup alerts
input bool             InpAlertPush    = false;             // Push notifications

input group "=== Strategy Tester ==="
input bool            InpDemoTrades    = true;            // Demo mode: open random trades (tester only)

//--- state kept in terminal global variables (survives restarts)
string   GVP;                 // prefix
double   g_startBal = 0;      // account starting balance for max DD
double   g_peak = 0;          // peak equity for trailing DD
double   g_dayBase = 0;       // reference for today's loss
datetime g_dayStart = 0;      // start of the current guard day
bool     g_lockDay = false, g_lockAll = false, g_lockTarget = false;
bool     g_warnDaySent = false, g_warnDDSent = false;
string   g_lastEvent = "";

CTrade   g_trade;
CCanvas  g_cv;
bool     g_cvOk = false, g_compact = false;
double   g_s = 1.0;
string   PFX;
uint     g_lastDraw = 0;

//+------------------------------------------------------------------+
double GV(const string k, const double def)
{
   const string n = GVP + k;
   return(GlobalVariableCheck(n) ? GlobalVariableGet(n) : def);
}
void GVSet(const string k, const double v) { GlobalVariableSet(GVP + k, v); }

double Equity()  { return(AccountInfoDouble(ACCOUNT_EQUITY)); }
double Balance() { return(AccountInfoDouble(ACCOUNT_BALANCE)); }

bool InScope(const string sym, const long magic)
{
   if(InpScope == SCOPE_SYMBOL) return(sym == _Symbol);
   if(InpScope == SCOPE_MAGIC)  return(magic == InpMagic);
   return(true);
}

double ScopedFloating()     // floating P/L of the protected positions
{
   double f = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      const ulong tk = PositionGetTicket(i);
      if(tk == 0) continue;
      if(!InScope(PositionGetString(POSITION_SYMBOL), PositionGetInteger(POSITION_MAGIC))) continue;
      f += PositionGetDouble(POSITION_PROFIT) + PositionGetDouble(POSITION_SWAP);
   }
   return(f);
}

double ScopedClosedSince(const datetime from)   // closed P/L of protected deals since 'from'
{
   if(!HistorySelect(from, TimeCurrent() + 60)) return(0);
   double p = 0;
   for(int i = HistoryDealsTotal() - 1; i >= 0; i--)
   {
      const ulong d = HistoryDealGetTicket(i);
      if(d == 0) continue;
      const long type = HistoryDealGetInteger(d, DEAL_TYPE);
      if(type != DEAL_TYPE_BUY && type != DEAL_TYPE_SELL) continue;
      if(!InScope(HistoryDealGetString(d, DEAL_SYMBOL), HistoryDealGetInteger(d, DEAL_MAGIC))) continue;
      p += HistoryDealGetDouble(d, DEAL_PROFIT) + HistoryDealGetDouble(d, DEAL_SWAP) + HistoryDealGetDouble(d, DEAL_COMMISSION);
   }
   return(p);
}

datetime DayStartFor(const datetime t)
{
   const int h = MathMax(0, MathMin(23, InpResetHour));
   datetime d = t - (t % 86400) + h * 3600;
   if(d > t) d -= 86400;
   return(d);
}

double LimitMoney(const ENUM_LIMIT_MODE mode, const double value, const double base)
{
   return(mode == LIMIT_PERCENT ? base * value / 100.0 : value);
}

//+------------------------------------------------------------------+
int OnInit()
{
   GVP = StringFormat("PRG_%I64d_%d_", AccountInfoInteger(ACCOUNT_LOGIN), (int)InpScope);
   if(MQLInfoInteger(MQL_TESTER)) GVP = "PRGT_";          // tester runs never touch live state
   PFX = "PRG" + IntegerToString((long)(GetMicrosecondCount() % 1000000)) + "_";
   g_s = MathMax(1.0, MathMin(2.0, TerminalInfoInteger(TERMINAL_SCREEN_DPI) / 96.0));
   g_trade.SetDeviationInPoints(InpSlippage);
   g_trade.SetAsyncMode(false);

   if(MQLInfoInteger(MQL_TESTER))
   {
      // fresh state for every test; same demo trades in visual and normal runs
      GlobalVariablesDeleteAll("PRGT_");
      MathSrand(20260901);
      if(InpDemoTrades) ChartSetInteger(0, CHART_SHOW_TRADE_HISTORY, false);   // keep the demo chart clean
   }
   g_startBal = InpStartBalance > 0 ? InpStartBalance : GV("start", Balance());
   GVSet("start", g_startBal);
   g_peak     = GV("peak", MathMax(g_startBal, Equity()));
   g_dayStart = (datetime)GV("daystart", 0);
   g_dayBase  = GV("daybase", 0);
   g_lockDay  = GV("lockday", 0) > 0;
   g_lockAll  = GV("lockall", 0) > 0;
   g_lockTarget = GV("locktarget", 0) > 0;
   if(InpStartBalance > 0 && GV("lastinput", 0) != InpStartBalance)
   {
      // a new starting balance typed in by the user = a new challenge: clear the permanent locks
      g_lockAll = false; g_lockTarget = false; g_peak = MathMax(g_startBal, Equity());
      GVSet("lockall", 0); GVSet("locktarget", 0); GVSet("peak", g_peak);
   }
   GVSet("lastinput", InpStartBalance);
   CheckNewDay();
   EventSetMillisecondTimer(250);
   Evaluate();
   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason)
{
   EventKillTimer();
   if(g_cvOk) { g_cv.Destroy(); g_cvOk = false; }
   ObjectsDeleteAll(0, PFX);
   ChartRedraw();
}

void OnTick()  { Evaluate(); if(MQLInfoInteger(MQL_TESTER) && InpDemoTrades) DemoTrades(); }
void OnTimer() { Evaluate(); }

void OnTradeTransaction(const MqlTradeTransaction &t, const MqlTradeRequest &r, const MqlTradeResult &res)
{
   // a locked account: close anything new straight away
   if(t.type == TRADE_TRANSACTION_DEAL_ADD && (g_lockDay || g_lockAll || g_lockTarget)) CloseAll("new trade while locked");
}

void OnChartEvent(const int id, const long &l, const double &d, const string &s)
{
   if(id == CHARTEVENT_OBJECT_CLICK && s == PFX + "panel") { g_compact = !g_compact; DrawPanel(); }
   else if(id == CHARTEVENT_CHART_CHANGE) DrawPanel();
}

//+------------------------------------------------------------------+
void CheckNewDay()
{
   const datetime ds = DayStartFor(TimeCurrent());
   if(ds == g_dayStart && g_dayBase > 0) return;
   g_dayStart = ds;
   // the day's reference: balance at the day start = balance now minus what closed since then
   const double balAtStart = Balance() - ScopedClosedSince(ds);
   const double eqNow = Equity();
   g_dayBase = (InpDayBase == BASE_BALANCE) ? balAtStart : (InpDayBase == BASE_EQUITY) ? eqNow : MathMax(balAtStart, eqNow);
   g_lockDay = false; g_warnDaySent = false;
   GVSet("daystart", (double)g_dayStart); GVSet("daybase", g_dayBase); GVSet("lockday", 0);
}

double DayLoss()      // today's loss in money (positive = losing), protected trades only
{
   return(-(ScopedClosedSince(g_dayStart) + ScopedFloating()));
}

void Evaluate()
{
   CheckNewDay();
   const double eq = Equity();
   if(eq > g_peak) { g_peak = eq; GVSet("peak", g_peak); }
   const double early = 1.0 - MathMax(0, MathMin(50, InpBufferPercent)) / 100.0;

   //--- daily loss
   if(InpUseDaily && !g_lockDay)
   {
      const double lim = LimitMoney(InpDailyMode, InpDailyValue, g_dayBase) * early;
      const double loss = DayLoss();
      if(lim > 0 && loss >= lim)
      {
         g_lockDay = true; GVSet("lockday", 1);
         Event(StringFormat("Daily loss limit reached (%.2f of %.2f). Closing all and locking until the next day.", loss, lim / early));
         CloseAll("daily limit");
      }
      else if(lim > 0 && !g_warnDaySent && loss >= lim * InpWarnPercent / 100.0)
      {
         g_warnDaySent = true;
         Event(StringFormat("Warning: %.0f%% of today's loss limit used (%.2f of %.2f).", 100.0 * loss / (lim / early), loss, lim / early));
      }
   }
   //--- max drawdown
   if(InpUseMaxDD && !g_lockAll)
   {
      const double ref = (InpDDType == DD_TRAILING) ? g_peak : g_startBal;
      const double lim = LimitMoney(InpDDMode, InpDDValue, InpDDType == DD_TRAILING ? g_startBal : g_startBal) * early;
      const double dd = ref - eq;
      if(lim > 0 && dd >= lim)
      {
         g_lockAll = true; GVSet("lockall", 1);
         Event(StringFormat("Max drawdown reached (%.2f of %.2f). Closing all and locking the account.", dd, lim / early));
         CloseAll("max drawdown");
      }
      else if(lim > 0 && !g_warnDDSent && dd >= lim * InpWarnPercent / 100.0)
      {
         g_warnDDSent = true;
         Event(StringFormat("Warning: %.0f%% of the max drawdown used (%.2f of %.2f).", 100.0 * dd / (lim / early), dd, lim / early));
      }
   }
   //--- profit target
   if(InpUseTarget && !g_lockTarget)
   {
      const double tgt = LimitMoney(InpTargetMode, InpTargetValue, g_startBal);
      if(tgt > 0 && eq - g_startBal >= tgt)
      {
         g_lockTarget = true; GVSet("locktarget", 1);
         Event(StringFormat("Profit target reached (+%.2f). Closing all and locking to protect it.", eq - g_startBal));
         CloseAll("profit target");
      }
   }
   //--- keep a locked account flat
   if((g_lockDay || g_lockAll || g_lockTarget) && (CountScoped() > 0)) CloseAll("locked");

   const uint now = GetTickCount();
   if(now - g_lastDraw > 400) { g_lastDraw = now; DrawPanel(); }
}

int CountScoped()
{
   int n = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      const ulong tk = PositionGetTicket(i);
      if(tk > 0 && InScope(PositionGetString(POSITION_SYMBOL), PositionGetInteger(POSITION_MAGIC))) n++;
   }
   for(int i = OrdersTotal() - 1; i >= 0; i--)
   {
      const ulong tk = OrderGetTicket(i);
      if(tk > 0 && InScope(OrderGetString(ORDER_SYMBOL), OrderGetInteger(ORDER_MAGIC))) n++;
   }
   return(n);
}

void CloseAll(const string why)
{
   for(int pass = 0; pass < 3; pass++)
   {
      for(int i = PositionsTotal() - 1; i >= 0; i--)
      {
         const ulong tk = PositionGetTicket(i);
         if(tk == 0) continue;
         if(!InScope(PositionGetString(POSITION_SYMBOL), PositionGetInteger(POSITION_MAGIC))) continue;
         if(!g_trade.PositionClose(tk))
            PrintFormat("Prop Risk Guard: could not close #%I64u (%s): %d %s", tk, why, g_trade.ResultRetcode(), g_trade.ResultRetcodeDescription());
      }
      for(int i = OrdersTotal() - 1; i >= 0; i--)
      {
         const ulong tk = OrderGetTicket(i);
         if(tk == 0) continue;
         if(!InScope(OrderGetString(ORDER_SYMBOL), OrderGetInteger(ORDER_MAGIC))) continue;
         g_trade.OrderDelete(tk);
      }
      if(CountScoped() == 0) break;
   }
}

void Event(const string msg)
{
   g_lastEvent = TimeToString(TimeCurrent(), TIME_MINUTES) + "  " + msg;
   Print("Prop Risk Guard: ", msg);
   if(MQLInfoInteger(MQL_TESTER)) return;
   if(InpAlertPopup) Alert("Prop Risk Guard: ", msg);
   if(InpAlertPush) SendNotification("Prop Risk Guard: " + msg);
}

//+------------------------------------------------------------------+
//| Tester demo: random small trades so the guard can be seen working |
//+------------------------------------------------------------------+
void DemoTrades()
{
   static datetime lastBar = 0;
   const datetime b = iTime(_Symbol, _Period, 0);
   if(b == lastBar) return;
   lastBar = b;
   // keep the visual demo readable: remove the tester's own trade arrows ("#..." objects)
   if(MQLInfoInteger(MQL_VISUAL_MODE)) ObjectsDeleteAll(0, "#");
   if(g_lockDay || g_lockAll || g_lockTarget) return;
   // close a demo position now and then, so the account keeps trading
   if(PositionsTotal() > 0 && MathRand() % 5 == 0)
   {
      const ulong tk = PositionGetTicket(MathRand() % PositionsTotal());
      if(tk > 0 && PositionGetInteger(POSITION_MAGIC) == 777) g_trade.PositionClose(tk);
   }
   if(PositionsTotal() >= 3 || MathRand() % 4 != 0) return;
   if(SymbolInfoInteger(_Symbol, SYMBOL_TRADE_MODE) != SYMBOL_TRADE_MODE_FULL) return;
   const double minLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   const double maxLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   const double step   = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   if(minLot <= 0 || step <= 0) return;
   double lot = MathFloor(Balance() / 10000.0 / step) * step;                   // aggressive on purpose
   lot = MathMax(minLot, MathMin(maxLot, lot));
   lot = NormalizeDouble(MathRound(lot / step) * step, 8);
   const bool buy = (MathRand() % 2 == 0);
   const ENUM_ORDER_TYPE type = buy ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
   const double price = buy ? SymbolInfoDouble(_Symbol, SYMBOL_ASK) : SymbolInfoDouble(_Symbol, SYMBOL_BID);
   // only trade what the account can afford (the tester may use a tiny deposit)
   double margin = 0;
   if(!OrderCalcMargin(type, _Symbol, lot, price, margin)) return;
   if(margin <= 0 || margin > AccountInfoDouble(ACCOUNT_MARGIN_FREE) * 0.5) return;
   g_trade.SetExpertMagicNumber(777);
   if(buy) g_trade.Buy(lot, _Symbol); else g_trade.Sell(lot, _Symbol);
}

//+------------------------------------------------------------------+
//| Panel                                                            |
//+------------------------------------------------------------------+
uint Clr(const color c, const uchar a) { return(ColorToARGB(c, a)); }
int  S(const double v) { return((int)MathRound(v * g_s)); }

bool IsDark()
{
   const color bg = (color)ChartGetInteger(0, CHART_COLOR_BACKGROUND);
   const double lum = 0.299 * (bg & 0xFF) + 0.587 * ((bg >> 8) & 0xFF) + 0.114 * ((bg >> 16) & 0xFF);
   return(lum < 128);
}

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

uint UseColor(const double f)
{
   if(f >= 1.0)  return(Clr(C'235,77,75', 255));
   if(f >= InpWarnPercent / 100.0) return(Clr(C'245,140,40', 255));
   if(f >= 0.5)  return(Clr(C'242,196,15', 255));
   return(Clr(C'38,194,129', 255));
}

// one limit row: title, used / limit, bar
int Row(int y, const int pad, const int W, const string title, const double used, const double limit,
        const uint cText, const uint cDim, const uint cTrack, const string right = "")
{
   const string cur = AccountInfoString(ACCOUNT_CURRENCY);
   const double f = limit > 0 ? MathMax(0, used) / limit : 0;
   Txt(pad, y, title, cDim, 70, true);
   Txt(W - pad, y, right != "" ? right : StringFormat("%.0f%% used", 100 * f), UseColor(f), 75, true, TA_RIGHT | TA_TOP);
   y += S(16);
   Txt(pad, y, StringFormat("%s %s", DoubleToString(MathMax(0, used), 2), cur), cText, 105, true);
   Txt(W - pad, y + S(3), StringFormat("limit %s", DoubleToString(limit, 2)), cDim, 75, false, TA_RIGHT | TA_TOP);
   y += S(22);
   const int bh = S(8);
   RRect(pad, y, W - pad, y + bh, S(4), cTrack);
   const int fx = pad + (int)MathRound((W - 2 * pad) * MathMin(1.0, f));
   if(fx > pad + S(4)) RRect(pad, y, fx, y + bh, S(4), UseColor(f));
   return(y + bh + S(14));
}

void DrawPanel()
{
   if(!InpShowPanel) return;
   const bool dark = IsDark();
   const uint cBg     = dark ? Clr(C'21,24,31', 255)  : Clr(C'252,252,253', 255);
   const uint cBorder = dark ? Clr(C'52,58,70', 255)  : Clr(C'214,218,226', 255);
   const uint cText   = dark ? Clr(C'236,239,244', 255) : Clr(C'28,32,40', 255);
   const uint cDim    = dark ? Clr(C'138,146,160', 255) : Clr(C'110,118,132', 255);
   const uint cTrack  = dark ? Clr(C'46,52,64', 255)  : Clr(C'228,231,237', 255);
   const uint cCard   = dark ? Clr(C'30,34,43', 255)  : Clr(C'243,245,248', 255);

   //--- status
   string status; color sc;
   const double dayLim = LimitMoney(InpDailyMode, InpDailyValue, g_dayBase);
   const double ddRef  = (InpDDType == DD_TRAILING) ? g_peak : g_startBal;
   const double ddLim  = LimitMoney(InpDDMode, InpDDValue, g_startBal);
   const double dayUse = DayLoss();
   const double ddUse  = ddRef - Equity();
   const double worst  = MathMax(InpUseDaily && dayLim > 0 ? dayUse / dayLim : 0, InpUseMaxDD && ddLim > 0 ? ddUse / ddLim : 0);
   if(g_lockAll)         { status = "LOCKED - MAX DRAWDOWN"; sc = C'235,77,75'; }
   else if(g_lockTarget) { status = "LOCKED - TARGET HIT";   sc = C'52,152,219'; }
   else if(g_lockDay)    { status = "LOCKED FOR TODAY";      sc = C'235,77,75'; }
   else if(worst >= InpWarnPercent / 100.0) { status = "WARNING"; sc = C'245,140,40'; }
   else                  { status = "PROTECTED";             sc = C'38,194,129'; }

   const int W = S(300), pad = S(14);
   int H = g_compact ? S(78) : S(150);
   if(!g_compact)
   {
      if(InpUseDaily) H += S(70);
      if(InpUseMaxDD) H += S(62);
      if(InpUseTarget) H += S(62);
      if(g_lastEvent != "") H += S(52);
   }
   const string nm = PFX + "panel";
   if(!g_cvOk)
   {
      if(!g_cv.CreateBitmapLabel(0, 0, nm, 0, 0, W, H, COLOR_FORMAT_ARGB_NORMALIZE)) return;
      g_cvOk = true;
      ObjectSetInteger(0, nm, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, nm, OBJPROP_HIDDEN, true);
      ObjectSetString(0, nm, OBJPROP_TOOLTIP, "Prop Risk Guard - click to collapse / expand");
   }
   else if(g_cv.Width() != W || g_cv.Height() != H) g_cv.Resize(W, H);
   const bool right = (InpCorner == CORNER_RIGHT_UPPER || InpCorner == CORNER_RIGHT_LOWER);
   const bool lower = (InpCorner == CORNER_LEFT_LOWER || InpCorner == CORNER_RIGHT_LOWER);
   ObjectSetInteger(0, nm, OBJPROP_CORNER, InpCorner);
   ObjectSetInteger(0, nm, OBJPROP_ANCHOR, right ? (lower ? ANCHOR_RIGHT_LOWER : ANCHOR_RIGHT_UPPER)
                                                 : (lower ? ANCHOR_LEFT_LOWER : ANCHOR_LEFT_UPPER));
   ObjectSetInteger(0, nm, OBJPROP_XDISTANCE, InpPanelX);
   ObjectSetInteger(0, nm, OBJPROP_YDISTANCE, InpPanelY);

   g_cv.Erase(0);
   RRect(0, 0, W - 1, H - 1, S(10), cBorder);
   RRect(1, 1, W - 2, H - 2, S(9), cBg);
   RRect(1, 1, S(5), H - 2, S(2), Clr(sc, 255));

   int y = S(12);
   Txt(pad, y, "Prop Risk Guard", cText, 100, true);
   Txt(W - pad, y + S(1), AccountInfoString(ACCOUNT_CURRENCY) + "  \x00B7  #" + IntegerToString(AccountInfoInteger(ACCOUNT_LOGIN)),
       cDim, 80, false, TA_RIGHT | TA_TOP);
   y += S(26);
   const string icon = (g_lockDay || g_lockAll || g_lockTarget) ? "\x25A0" : (status == "WARNING" ? "\x25B2" : "\x25CF");
   const string badge = icon + "  " + status;
   const int bw = TW(badge, 95, true) + S(24);
   RRect(pad, y, pad + bw, y + S(26), S(13), Clr(sc, 255));
   Txt(pad + bw / 2, y + S(13), badge, Clr(clrWhite, 255), 95, true, TA_CENTER | TA_VCENTER);
   if(g_compact) { g_cv.Update(); return; }
   y += S(36);

   //--- equity line
   const double dayPL = -dayUse;
   Txt(pad, y, "EQUITY", cDim, 70, true);
   Txt(W - pad, y, "TODAY", cDim, 70, true, TA_RIGHT | TA_TOP);
   y += S(16);
   Txt(pad, y, DoubleToString(Equity(), 2), cText, 130, true);
   Txt(W - pad, y, (dayPL >= 0 ? "+" : "") + DoubleToString(dayPL, 2), dayPL >= 0 ? Clr(C'38,194,129', 255) : Clr(C'235,77,75', 255),
       130, true, TA_RIGHT | TA_TOP);
   y += S(30);
   g_cv.FillRectangle(pad, y, W - pad, y, cTrack);
   y += S(12);

   if(InpUseDaily)
   {
      const datetime nxt = g_dayStart + 86400;
      const int secs = (int)MathMax(0, nxt - TimeCurrent());
      const string reset = StringFormat("resets in %dh %02dm", secs / 3600, (secs % 3600) / 60);
      y = Row(y, pad, W, "TODAY'S LOSS", dayUse, dayLim, cText, cDim, cTrack, g_lockDay ? reset : "");
      if(!g_lockDay) { Txt(pad, y - S(9), reset, cDim, 70); y += S(12); }
   }
   if(InpUseMaxDD)
      y = Row(y, pad, W, InpDDType == DD_TRAILING ? "TRAILING DRAWDOWN" : "MAX DRAWDOWN", ddUse, ddLim, cText, cDim, cTrack);
   if(InpUseTarget)
   {
      const double tgt = LimitMoney(InpTargetMode, InpTargetValue, g_startBal);
      const double got = Equity() - g_startBal;
      const double f = tgt > 0 ? MathMax(0, got) / tgt : 0;
      Txt(pad, y, "PROFIT TARGET", cDim, 70, true);
      Txt(W - pad, y, StringFormat("%.0f%% reached", 100 * f), Clr(C'52,152,219', 255), 75, true, TA_RIGHT | TA_TOP);
      y += S(16);
      Txt(pad, y, StringFormat("%s %s", DoubleToString(got, 2), AccountInfoString(ACCOUNT_CURRENCY)), cText, 105, true);
      Txt(W - pad, y + S(3), StringFormat("target %s", DoubleToString(tgt, 2)), cDim, 75, false, TA_RIGHT | TA_TOP);
      y += S(22);
      RRect(pad, y, W - pad, y + S(8), S(4), cTrack);
      const int fx = pad + (int)MathRound((W - 2 * pad) * MathMin(1.0, f));
      if(fx > pad + S(4)) RRect(pad, y, fx, y + S(8), S(4), Clr(C'52,152,219', 255));
      y += S(22);
   }
   if(g_lastEvent != "")
   {
      RRect(pad, y, W - pad, y + S(42), S(8), cCard);
      Txt(pad + S(10), y + S(6), "LAST EVENT", cDim, 65, true);
      string ev = g_lastEvent;
      if(StringLen(ev) > 52) ev = StringSubstr(ev, 0, 50) + "...";
      Txt(pad + S(10), y + S(21), ev, cText, 75);
      y += S(52);
   }
   g_cv.Update();
}
//+------------------------------------------------------------------+
