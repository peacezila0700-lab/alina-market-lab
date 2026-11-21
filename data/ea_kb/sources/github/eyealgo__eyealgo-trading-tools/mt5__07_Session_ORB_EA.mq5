//+------------------------------------------------------------------+
//|  Session Opening Range Breakout EA                  © Eye Algo   |
//+------------------------------------------------------------------+
#property copyright   "Eye Algo"
#property version     "1.00"
#property description "Tokyo / London / New York opening range breakout. Entry on candle close or touch, reverse after SL, SL opposite side / middle / fixed / ATR, TP R:R or fixed, partial + trailing, session-end exit, daily & monthly P/L limits, range boxes and session dashboard."

#define EA_NAME  "Session ORB EA"
#define EA_MAGIC 26010107

enum ENUM_ORB_ENTRY
  {
   ORB_CLOSE = 0, // Candle close beyond range
   ORB_TOUCH = 1  // Touch (stop orders)
  };

enum ENUM_ORB_SL
  {
   ORB_SL_OPP    = 0, // Opposite side of range
   ORB_SL_MID    = 1, // Middle of range
   ORB_SL_POINTS = 2, // Fixed points
   ORB_SL_ATR    = 3  // ATR
  };

enum ENUM_ORB_TP
  {
   ORB_TP_RR     = 0, // Risk:Reward
   ORB_TP_POINTS = 1, // Fixed points
   ORB_TP_NONE   = 2  // None (session end)
  };

input group "Time"
input int InpTimeOffset = 0; // Hours added to server time (session times below use the result)

input group "Tokyo"
input bool   InpTkOn    = true;    // Enabled
input string InpTkStart = "00:00"; // Range start (HH:MM)
input int    InpTkDur   = 60;      // Range duration (minutes)
input string InpTkEnd   = "06:00"; // Session end (HH:MM)
input int    InpTkMax   = 1;       // Max trades
input color  InpTkCol   = C'110,123,242'; // Box colour

input group "London"
input bool   InpLdOn    = true;    // Enabled
input string InpLdStart = "07:00"; // Range start (HH:MM)
input int    InpLdDur   = 60;      // Range duration (minutes)
input string InpLdEnd   = "11:00"; // Session end (HH:MM)
input int    InpLdMax   = 2;       // Max trades
input color  InpLdCol   = C'34,176,125'; // Box colour

input group "New York"
input bool   InpNyOn    = true;    // Enabled
input string InpNyStart = "13:30"; // Range start (HH:MM)
input int    InpNyDur   = 30;      // Range duration (minutes)
input string InpNyEnd   = "17:00"; // Session end (HH:MM)
input int    InpNyMax   = 2;       // Max trades
input color  InpNyCol   = C'240,136,62'; // Box colour

input group "Entry"
input ENUM_ORB_ENTRY InpEntryMode = ORB_CLOSE; // Entry on
input bool   InpReverseSL = false;  // Reverse after stop loss
input bool   InpExitEnd   = true;   // Close trade at session end
input int    InpMinRange  = 0;      // Min range (points, 0 = off)
input int    InpMaxRange  = 0;      // Max range (points, 0 = off)

input group "Stop loss & take profit"
input ENUM_ORB_SL InpSlType = ORB_SL_OPP; // Stop loss
input int    InpSlPoints = 200;  // Fixed stop (points)
input int    InpSlAtrLen = 14;   // ATR length
input double InpSlAtrMul = 1.5;  // ATR multiplier
input ENUM_ORB_TP InpTpType = ORB_TP_RR; // Take profit (R:R value is in Trade management)
input int    InpTpPoints = 400;  // Fixed TP (points)

input group "Days & limits"
input bool   InpMon = true;   // Monday
input bool   InpTue = true;   // Tuesday
input bool   InpWed = true;   // Wednesday
input bool   InpThu = true;   // Thursday
input bool   InpFri = true;   // Friday
input bool   InpSat = false;  // Saturday
input bool   InpSun = false;  // Sunday
input double InpDayLoss = 0;  // Daily loss limit (%, 0 = off)
input double InpDayGain = 0;  // Daily profit target (%, 0 = off)
input double InpMonLoss = 0;  // Monthly loss limit (%, 0 = off)
input double InpMonGain = 0;  // Monthly profit target (%, 0 = off)
input bool   InpShowBoxes = true; // Draw range boxes

//+------------------------------------------------------------------+
//|  SHARED EYE ALGO TRADE ENGINE – inputs                           |
//+------------------------------------------------------------------+
enum ENUM_EA_DIR
  {
   DIR_BOTH  = 0, // Both
   DIR_LONG  = 1, // Long only
   DIR_SHORT = 2  // Short only
  };

enum ENUM_LOT_MODE
  {
   LOT_FIXED = 0, // Fixed lot
   LOT_RISK  = 1  // % risk of equity
  };

input group "Trade management"
input ENUM_EA_DIR   InpDirection    = DIR_BOTH;  // Trade direction
input double        InpRR           = 2.0;       // Take profit (Risk:Reward)
input bool          InpUsePartial   = true;      // Partial close at 1R
input double        InpPartialPct   = 50;        // Partial close (%)
input bool          InpUseBE        = true;      // Move SL to break-even after partial
input bool          InpUseTrail     = false;     // ATR trailing stop
input int           InpTrailATRLen  = 14;        // Trailing ATR length
input double        InpTrailATRMult = 2.0;       // Trailing ATR multiplier

input group "Position size"
input ENUM_LOT_MODE InpLotMode      = LOT_FIXED; // Lot mode
input double        InpLot          = 0.10;      // Fixed lot
input double        InpRiskPct      = 1.0;       // Risk per trade (% of equity)

//+------------------------------------------------------------------+
//|  EYE ALGO CORE HELPERS                                           |
//+------------------------------------------------------------------+
#include <Trade\Trade.mqh>

input group "General"
input ulong  InpMagic      = EA_MAGIC;  // Magic number
input int    InpMaxSpread  = 0;         // Max spread in points (0 = off)
input bool   InpAlerts     = false;     // Popup alert on new trade
input bool   InpPush       = false;     // Push notification on new trade
input bool   InpShowPanel  = true;      // Show info panel
input bool   InpShowArrows = true;      // Draw signal arrows

CTrade   g_trade;
datetime g_lastBar = 0;

//--- price / volume -------------------------------------------------
double NP(double p)
  {
   double ts = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(ts > 0) p = MathRound(p / ts) * ts;
   return NormalizeDouble(p, _Digits);
  }

double VolStep() { double s = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP); return s > 0 ? s : 0.01; }

double NormLot(double lot)
  {
   double step = VolStep();
   double mn   = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double mx   = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   lot = MathFloor(lot / step + 1e-9) * step;
   lot = MathMax(mn, MathMin(mx, lot));
   return NormalizeDouble(lot, 8);
  }

double StopsMin() { return (double)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL) * _Point; }

bool SpreadOk()
  {
   if(InpMaxSpread > 0 && SymbolInfoInteger(_Symbol, SYMBOL_SPREAD) > InpMaxSpread)
     {
      Print(EA_NAME, ": spread too high, signal skipped");
      return false;
     }
   return true;
  }

// distance helper: mode 0 = ATR, 1 = fixed points, 2 = percent of price
double BasicSlDist(int mode, double atr, double atrMul, int points, double pct, double price)
  {
   if(mode == 0) return atr * atrMul;
   if(mode == 1) return points * _Point;
   return price * pct / 100.0;
  }

//--- bars / data ----------------------------------------------------
bool IsNewBar()
  {
   datetime t = iTime(_Symbol, _Period, 0);
   if(t == 0 || t == g_lastBar) return false;
   g_lastBar = t;
   return true;
  }

double Buf(int handle, int buffer, int shift)
  {
   double v[1];
   if(CopyBuffer(handle, buffer, shift, 1, v) != 1) return EMPTY_VALUE;
   return v[0];
  }

// closed bars only, oldest first: r[n-1] is bar #1 of that timeframe
int GetRatesTF(ENUM_TIMEFRAMES tf, int count, MqlRates &r[])
  {
   ArraySetAsSeries(r, false);
   return CopyRates(_Symbol, tf, 1, count, r);
  }

int GetRates(int count, MqlRates &r[]) { return GetRatesTF(_Period, count, r); }

// TradingView-style ATR (RMA smoothing), oldest first
void AtrRMA(const MqlRates &r[], int n, int len, double &out[])
  {
   ArrayResize(out, n);
   ArrayInitialize(out, 0.0);
   double sum = 0;
   for(int i = 0; i < n; i++)
     {
      double tr = r[i].high - r[i].low;
      if(i > 0)
         tr = MathMax(tr, MathMax(MathAbs(r[i].high - r[i - 1].close), MathAbs(r[i].low - r[i - 1].close)));
      if(i < len)
        {
         sum += tr;
         out[i] = sum / (i + 1);
        }
      else
         out[i] = (out[i - 1] * (len - 1) + tr) / len;
     }
  }

// TradingView-style EMA (SMA seed), oldest first
void EmaArr(const double &src[], int n, int len, double &out[])
  {
   ArrayResize(out, n);
   ArrayInitialize(out, 0.0);
   double a = 2.0 / (len + 1), sum = 0;
   for(int i = 0; i < n; i++)
     {
      if(i < len)
        {
         sum += src[i];
         out[i] = sum / (i + 1);
        }
      else
         out[i] = a * src[i] + (1 - a) * out[i - 1];
     }
  }

double AtrTV(int len, int shift = 1)
  {
   int cnt = MathMax(len * 10, 200);
   MqlRates r[];
   ArraySetAsSeries(r, false);
   int n = CopyRates(_Symbol, _Period, shift, cnt, r);
   if(n < len + 1) return 0;
   double out[];
   AtrRMA(r, n, len, out);
   return out[n - 1];
  }

// TradingView Supertrend (hl2 source, RMA ATR by default), oldest first.
// trend[i] = 1 up / -1 down, line[i] = active band
void SupertrendArr(const MqlRates &r[], int n, int len, double mult, bool rma, double &line[], int &trend[])
  {
   ArrayResize(line, n);
   ArrayResize(trend, n);
   double atr[];
   if(rma) AtrRMA(r, n, len, atr);
   else
     {
      ArrayResize(atr, n);
      double sum = 0;
      for(int i = 0; i < n; i++)
        {
         double tr = r[i].high - r[i].low;
         if(i > 0) tr = MathMax(tr, MathMax(MathAbs(r[i].high - r[i - 1].close), MathAbs(r[i].low - r[i - 1].close)));
         sum += tr;
         if(i >= len)
           {
            double old = r[i - len].high - r[i - len].low;
            if(i - len > 0) old = MathMax(old, MathMax(MathAbs(r[i - len].high - r[i - len - 1].close), MathAbs(r[i - len].low - r[i - len - 1].close)));
            sum -= old;
           }
         atr[i] = sum / MathMin(i + 1, len);
        }
     }
   double upPrev = 0, dnPrev = 0;
   int tr = 1;
   for(int i = 0; i < n; i++)
     {
      double src = (r[i].high + r[i].low) / 2.0;
      double up = src - mult * atr[i];
      double dn = src + mult * atr[i];
      double up1 = i == 0 ? up : upPrev;
      double dn1 = i == 0 ? dn : dnPrev;
      double c1  = i == 0 ? r[i].close : r[i - 1].close;
      if(c1 > up1) up = MathMax(up, up1);
      if(c1 < dn1) dn = MathMin(dn, dn1);
      if(tr == -1 && r[i].close > dn1) tr = 1;
      else if(tr == 1 && r[i].close < up1) tr = -1;
      trend[i] = tr;
      line[i]  = tr == 1 ? up : dn;
      upPrev = up;
      dnPrev = dn;
     }
  }

//--- positions ------------------------------------------------------
bool SelectMine(int i)
  {
   ulong t = PositionGetTicket(i);
   if(t == 0) return false;
   return PositionGetString(POSITION_SYMBOL) == _Symbol && (ulong)PositionGetInteger(POSITION_MAGIC) == InpMagic;
  }

int PosDirOfSelected() { return PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY ? 1 : -1; }

int PosDir()
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
      if(SelectMine(i)) return PosDirOfSelected();
   return 0;
  }

int CountPos(int dir)
  {
   int c = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
      if(SelectMine(i) && (dir == 0 || PosDirOfSelected() == dir)) c++;
   return c;
  }

void ClosePositions(int dir, string reason = "")
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      if(!SelectMine(i)) continue;
      if(dir != 0 && PosDirOfSelected() != dir) continue;
      ulong ticket = (ulong)PositionGetInteger(POSITION_TICKET);
      if(g_trade.PositionClose(ticket) && reason != "")
         Print(EA_NAME, ": closed #", ticket, " (", reason, ")");
     }
  }

// filter = "" deletes all pending orders of this EA, otherwise only those whose comment contains filter
void DeletePendings(string filter = "")
  {
   for(int i = OrdersTotal() - 1; i >= 0; i--)
     {
      ulong t = OrderGetTicket(i);
      if(t == 0) continue;
      if(OrderGetString(ORDER_SYMBOL) != _Symbol || (ulong)OrderGetInteger(ORDER_MAGIC) != InpMagic) continue;
      if(filter != "" && StringFind(OrderGetString(ORDER_COMMENT), filter) < 0) continue;
      g_trade.OrderDelete(t);
     }
  }

string GVKey(ulong posId, string k) { return "EA" + (string)InpMagic + "_" + (string)posId + "_" + k; }

void Notify(string msg)
  {
   if(InpAlerts) Alert(msg);
   if(InpPush) SendNotification(msg);
  }

void CleanGV()
  {
   string pre = "EA" + (string)InpMagic + "_";
   for(int g = GlobalVariablesTotal() - 1; g >= 0; g--)
     {
      string nm = GlobalVariableName(g);
      if(StringFind(nm, pre) != 0) continue;
      string rest = StringSubstr(nm, StringLen(pre));
      int u = StringFind(rest, "_");
      if(u < 0) continue;
      ulong id = (ulong)StringToInteger(StringSubstr(rest, 0, u));
      if(id == 0) continue;
      bool alive = false;
      for(int i = PositionsTotal() - 1; i >= 0; i--)
         if(SelectMine(i) && (ulong)PositionGetInteger(POSITION_IDENTIFIER) == id) { alive = true; break; }
      if(!alive) GlobalVariableDel(nm);
     }
  }

//--- visuals --------------------------------------------------------
string ObjPre() { return "EA" + (string)InpMagic + "_"; }

void MarkSignal(int dir, int shift = 1)
  {
   if(!InpShowArrows) return;
   datetime t = iTime(_Symbol, _Period, shift);
   string name = ObjPre() + "sig_" + (string)(long)t + (dir == 1 ? "_B" : "_S");
   double price = dir == 1 ? iLow(_Symbol, _Period, shift) : iHigh(_Symbol, _Period, shift);
   if(ObjectFind(0, name) >= 0) return;
   ObjectCreate(0, name, dir == 1 ? OBJ_ARROW_BUY : OBJ_ARROW_SELL, 0, t, price);
   ObjectSetInteger(0, name, OBJPROP_COLOR, dir == 1 ? clrLimeGreen : clrTomato);
   ObjectSetInteger(0, name, OBJPROP_WIDTH, 2);
   ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
  }

// simple dark info panel; first line is the title
void DrawPanel(string &lines[], int width = 440)
  {
   string pre = ObjPre() + "pnl_";
   int n = ArraySize(lines);
   string bg = pre + "bg";
   if(ObjectFind(0, bg) < 0)
     {
      ObjectCreate(0, bg, OBJ_RECTANGLE_LABEL, 0, 0, 0);
      ObjectSetInteger(0, bg, OBJPROP_CORNER, CORNER_LEFT_UPPER);
      ObjectSetInteger(0, bg, OBJPROP_XDISTANCE, 10);
      ObjectSetInteger(0, bg, OBJPROP_YDISTANCE, 25);
      ObjectSetInteger(0, bg, OBJPROP_BGCOLOR, C'15,17,21');
      ObjectSetInteger(0, bg, OBJPROP_BORDER_TYPE, BORDER_FLAT);
      ObjectSetInteger(0, bg, OBJPROP_COLOR, C'42,47,56');
      ObjectSetInteger(0, bg, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, bg, OBJPROP_BACK, false);
     }
   ObjectSetInteger(0, bg, OBJPROP_XSIZE, width);
   ObjectSetInteger(0, bg, OBJPROP_YSIZE, 18 * n + 12);
   for(int i = 0; i < 40; i++)
     {
      string nm = pre + IntegerToString(i);
      if(i >= n)
        {
         if(ObjectFind(0, nm) >= 0) ObjectDelete(0, nm);
         continue;
        }
      if(ObjectFind(0, nm) < 0)
        {
         ObjectCreate(0, nm, OBJ_LABEL, 0, 0, 0);
         ObjectSetInteger(0, nm, OBJPROP_CORNER, CORNER_LEFT_UPPER);
         ObjectSetInteger(0, nm, OBJPROP_XDISTANCE, 18);
         ObjectSetInteger(0, nm, OBJPROP_YDISTANCE, 31 + 18 * i);
         ObjectSetString(0, nm, OBJPROP_FONT, "Consolas");
         ObjectSetInteger(0, nm, OBJPROP_FONTSIZE, 9);
         ObjectSetInteger(0, nm, OBJPROP_SELECTABLE, false);
        }
      ObjectSetString(0, nm, OBJPROP_TEXT, lines[i]);
      ObjectSetInteger(0, nm, OBJPROP_COLOR, i == 0 ? C'240,136,62' : C'230,232,235');
     }
   ChartRedraw(0);
  }

void AddLine(string &lines[], string s)
  {
   int n = ArraySize(lines);
   ArrayResize(lines, n + 1);
   lines[n] = s;
  }

// closed-deal statistics for this EA; dir 0 = all, 1 = longs, -1 = shorts
void DealStats(int dir, int &n, int &w, double &net, double &gp, double &gl, double &today)
  {
   n = 0; w = 0; net = 0; gp = 0; gl = 0; today = 0;
   HistorySelect(0, TimeCurrent() + 86400);
   datetime dayStart = iTime(_Symbol, PERIOD_D1, 0);
   for(int i = HistoryDealsTotal() - 1; i >= 0; i--)
     {
      ulong d = HistoryDealGetTicket(i);
      if(d == 0) continue;
      if(HistoryDealGetString(d, DEAL_SYMBOL) != _Symbol || (ulong)HistoryDealGetInteger(d, DEAL_MAGIC) != InpMagic) continue;
      long e = HistoryDealGetInteger(d, DEAL_ENTRY);
      if(e != DEAL_ENTRY_OUT && e != DEAL_ENTRY_OUT_BY && e != DEAL_ENTRY_INOUT) continue;
      // a closing SELL deal closes a long position
      int posDir = HistoryDealGetInteger(d, DEAL_TYPE) == DEAL_TYPE_SELL ? 1 : -1;
      if(dir != 0 && posDir != dir) continue;
      double p = HistoryDealGetDouble(d, DEAL_PROFIT) + HistoryDealGetDouble(d, DEAL_SWAP) + HistoryDealGetDouble(d, DEAL_COMMISSION);
      n++;
      if(p > 0) { w++; gp += p; } else gl -= p;
      net += p;
      if((datetime)HistoryDealGetInteger(d, DEAL_TIME) >= dayStart) today += p;
     }
  }

string PFText(double gp, double gl) { return gl > 0 ? DoubleToString(gp / gl, 2) : (gp > 0 ? "inf" : "-"); }

void CoreDeinit()
  {
   ObjectsDeleteAll(0, ObjPre() + "pnl_");
   Comment("");
  }

//+------------------------------------------------------------------+
//|  SHARED EYE ALGO TRADE ENGINE – functions                        |
//+------------------------------------------------------------------+
double   g_trailAtr = 0;
datetime g_trailBar = 0;

double CustomTrail(int dir);   // implemented by each EA: return a stop price, or 0 for none

double CalcLot(double slDist)
  {
   if(InpLotMode == LOT_FIXED || slDist <= 0) return NormLot(InpLot);
   double tv = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double ts = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(tv <= 0 || ts <= 0) return NormLot(InpLot);
   double risk   = AccountInfoDouble(ACCOUNT_EQUITY) * InpRiskPct / 100.0;
   double perLot = slDist / ts * tv;
   if(perLot <= 0) return NormLot(InpLot);
   return NormLot(risk / perLot);
  }

// tp: -1 = no take profit, 0 = Risk:Reward, >0 = this price
bool OpenTrade(int dir, double sl, double tp, string cmt)
  {
   if(!SpreadOk()) return false;
   double price = dir == 1 ? SymbolInfoDouble(_Symbol, SYMBOL_ASK) : SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double dist  = dir == 1 ? price - sl : sl - price;
   if(sl <= 0 || dist <= 0) return false;
   double minD = StopsMin() + _Point;
   if(dist < minD)
     {
      dist = minD;
      sl = price - dir * dist;
     }
   if(tp == 0 && InpRR > 0) tp = price + dir * dist * InpRR;
   if(tp > 0 && dir * (tp - price) <= minD) tp = 0;
   if(tp < 0) tp = 0;
   double lot = CalcLot(dist);
   sl = NP(sl);
   if(tp > 0) tp = NP(tp);
   bool ok = dir == 1 ? g_trade.Buy(lot, _Symbol, 0, sl, tp, cmt) : g_trade.Sell(lot, _Symbol, 0, sl, tp, cmt);
   uint rc = g_trade.ResultRetcode();
   if(!ok || (rc != TRADE_RETCODE_DONE && rc != TRADE_RETCODE_PLACED))
     {
      Print(EA_NAME, ": order failed, retcode ", rc, " ", g_trade.ResultRetcodeDescription());
      return false;
     }
   GlobalVariableSet(GVKey(g_trade.ResultOrder(), "R"), dist);
   Notify(StringFormat("%s %s %s %.2f lots @ %s | SL %s", EA_NAME, _Symbol, dir == 1 ? "BUY" : "SELL", lot,
                       DoubleToString(price, _Digits), DoubleToString(sl, _Digits)));
   return true;
  }

double BetterSl(double cur, double cand, int dir)
  {
   if(cand <= 0) return cur;
   if(cur <= 0) return cand;
   return dir == 1 ? MathMax(cur, cand) : MathMin(cur, cand);
  }

// partial close at 1R, break-even, ATR trailing and the EA's own trailing hook
void ManageTrades()
  {
   if(InpUseTrail)
     {
      datetime b = iTime(_Symbol, _Period, 0);
      if(b != g_trailBar)
        {
         g_trailAtr = AtrTV(InpTrailATRLen);
         g_trailBar = b;
        }
     }
   double stopsMin = StopsMin();
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      if(!SelectMine(i)) continue;
      ulong  ticket = (ulong)PositionGetInteger(POSITION_TICKET);
      ulong  posId  = (ulong)PositionGetInteger(POSITION_IDENTIFIER);
      int    dir    = PosDirOfSelected();
      double open   = PositionGetDouble(POSITION_PRICE_OPEN);
      double sl     = PositionGetDouble(POSITION_SL);
      double tp     = PositionGetDouble(POSITION_TP);
      double vol    = PositionGetDouble(POSITION_VOLUME);
      double cur    = dir == 1 ? SymbolInfoDouble(_Symbol, SYMBOL_BID) : SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      string kR = GVKey(posId, "R"), kP = GVKey(posId, "P");
      if(!GlobalVariableCheck(kR) && sl > 0) GlobalVariableSet(kR, MathAbs(open - sl));   // e.g. filled pending order
      double R  = GlobalVariableCheck(kR) ? GlobalVariableGet(kR) : 0;
      bool partDone = GlobalVariableCheck(kP);

      if(InpUsePartial && !partDone && R > 0)
        {
         double tp1 = open + dir * R;
         if(tp > 0 && dir * (tp - tp1) <= 0)
           {
            GlobalVariableSet(kP, 1);
            partDone = true;
           }
         else if(dir * (cur - tp1) >= 0)
           {
            double step = VolStep();
            double mn   = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
            double cv   = NormalizeDouble(MathFloor(vol * InpPartialPct / 100.0 / step + 1e-9) * step, 8);
            if(cv >= mn && vol - cv >= mn - 1e-9)
              {
               if(g_trade.PositionClosePartial(ticket, cv))
                 {
                  GlobalVariableSet(kP, 1);
                  partDone = true;
                 }
              }
            else
              {
               GlobalVariableSet(kP, 1);   // volume too small to split
               partDone = true;
              }
           }
        }

      double newSl = sl;
      if(InpUseBE && partDone)
         newSl = BetterSl(newSl, open, dir);
      if(InpUseTrail && g_trailAtr > 0)
         newSl = BetterSl(newSl, cur - dir * g_trailAtr * InpTrailATRMult, dir);
      double ct = CustomTrail(dir);
      if(ct > 0 && dir * (cur - ct) > 0)
         newSl = BetterSl(newSl, ct, dir);

      newSl = NP(newSl);
      if(newSl <= 0) continue;
      bool improves = sl <= 0 || dir * (newSl - sl) >= _Point;
      bool valid    = dir * (cur - newSl) > stopsMin;
      if(improves && valid)
         g_trade.PositionModify(ticket, newSl, tp);
     }
  }

// common signal flow: one position at a time, reverse on opposite signal
// tp: -1 = none, 0 = Risk:Reward, >0 = price
void ProcessSignals(bool buySig, bool sellSig, bool exitBuy, bool exitSell, string exitTag,
                    double slBuy, double slSell, double tpBuy, double tpSell, string tagB, string tagS)
  {
   int side = PosDir();
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID), ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   bool allowL = InpDirection != DIR_SHORT, allowS = InpDirection != DIR_LONG;
   bool goL = buySig  && allowL && side != 1  && slBuy  > 0 && bid - slBuy > 0;
   bool goS = sellSig && allowS && side != -1 && slSell > 0 && slSell - ask > 0;
   if(goL && goS) goS = false;
   if(side == 1  && (exitBuy  || goS)) ClosePositions(1,  goS ? "reverse" : exitTag);
   if(side == -1 && (exitSell || goL)) ClosePositions(-1, goL ? "reverse" : exitTag);
   if(goL)
     {
      if(OpenTrade(1, slBuy, tpBuy, tagB)) MarkSignal(1);
     }
   else if(goS)
     {
      if(OpenTrade(-1, slSell, tpSell, tagS)) MarkSignal(-1);
     }
  }

// standard panel: EA name, position, stats, plus extra lines separated by "\n"
void ShowPanel(string extra = "")
  {
   if(!InpShowPanel) return;
   int n = 0, w = 0;
   double net = 0, gp = 0, gl = 0, today = 0;
   DealStats(0, n, w, net, gp, gl, today);
   string lines[];
   int side = PosDir();
   AddLine(lines, EA_NAME + "  |  Eye Algo");
   AddLine(lines, StringFormat("Position : %s (%d)", side == 1 ? "LONG" : side == -1 ? "SHORT" : "flat", CountPos(0)));
   AddLine(lines, StringFormat("Closed   : %d   Win %.1f%%   PF %s", n, n > 0 ? 100.0 * w / n : 0.0, PFText(gp, gl)));
   AddLine(lines, StringFormat("Net P/L  : %.2f   Today %.2f", net, today));
   if(extra != "")
     {
      string ex[];
      int k = StringSplit(extra, '\n', ex);
      for(int i = 0; i < k; i++) AddLine(lines, ex[i]);
     }
   DrawPanel(lines);
  }

bool EngineInit()
  {
   g_trade.SetExpertMagicNumber(InpMagic);
   g_trade.SetDeviationInPoints(20);
   g_trade.SetTypeFillingBySymbol(_Symbol);
   g_lastBar = iTime(_Symbol, _Period, 0);   // wait for the next closed bar before the first signal
   ShowPanel();
   return true;
  }

void EngineDeinit() { CoreDeinit(); }


struct Sess
  {
   string   name;
   bool     on;
   int      startMin;
   int      dur;
   int      endMin;
   int      maxTrades;
   color    col;
   double   hi;
   double   lo;
   int      state;      // 0 waiting, 1 building, 2 active, 3 done
   bool     filtered;
   int      trades;
   datetime rangeStart; // server time
   bool     pendingsPlaced;
  };

Sess   g_s[3];
ulong  g_memId[];    // position id -> owning session (backup for the global variable)
int    g_memOwn[];
int    g_revDir = 0, g_revOwner = -1;
bool   g_limitHit = false;
double g_dayPct = 0, g_monPct = 0;

int ToMin(string hhmm)
  {
   string p[];
   if(StringSplit(hhmm, ':', p) != 2) return -1;
   int h = (int)StringToInteger(p[0]), m = (int)StringToInteger(p[1]);
   if(h < 0 || h > 23 || m < 0 || m > 59) return -1;
   return h * 60 + m;
  }

void SetSess(int i, string name, bool on, string st, int dur, string en, int mx, color col)
  {
   g_s[i].name = name;
   g_s[i].on = on;
   g_s[i].startMin = ToMin(st);
   g_s[i].dur = MathMax(1, dur);
   g_s[i].endMin = ToMin(en);
   g_s[i].maxTrades = MathMax(1, mx);
   g_s[i].col = col;
   g_s[i].hi = 0;
   g_s[i].lo = 0;
   g_s[i].state = 0;
   g_s[i].filtered = false;
   g_s[i].trades = 0;
   g_s[i].rangeStart = 0;
   g_s[i].pendingsPlaced = false;
  }

bool DayOk(int dow)
  {
   switch(dow)
     {
      case 0: return InpSun;
      case 1: return InpMon;
      case 2: return InpTue;
      case 3: return InpWed;
      case 4: return InpThu;
      case 5: return InpFri;
      case 6: return InpSat;
     }
   return false;
  }

int OnInit()
  {
   SetSess(0, "Tokyo",    InpTkOn, InpTkStart, InpTkDur, InpTkEnd, InpTkMax, InpTkCol);
   SetSess(1, "London",   InpLdOn, InpLdStart, InpLdDur, InpLdEnd, InpLdMax, InpLdCol);
   SetSess(2, "New York", InpNyOn, InpNyStart, InpNyDur, InpNyEnd, InpNyMax, InpNyCol);
   for(int i = 0; i < 3; i++)
      if(g_s[i].on && (g_s[i].startMin < 0 || g_s[i].endMin < 0))
        {
         Print(EA_NAME, ": wrong time format for ", g_s[i].name, ", use HH:MM");
         return INIT_PARAMETERS_INCORRECT;
        }
   RestoreTradeCounts();
   EngineInit();
   UpdatePanel();
   return INIT_SUCCEEDED;
  }

// after a restart: count today's entries per session from the deal history
void RestoreTradeCounts()
  {
   MqlDateTime dt;
   TimeToStruct(TimeCurrent() + InpTimeOffset * 3600, dt);
   datetime dayStartSrv = TimeCurrent() - (dt.hour * 3600 + dt.min * 60 + dt.sec);
   HistorySelect(dayStartSrv, TimeCurrent() + 60);
   for(int i = HistoryDealsTotal() - 1; i >= 0; i--)
     {
      ulong d = HistoryDealGetTicket(i);
      if(d == 0 || (ulong)HistoryDealGetInteger(d, DEAL_MAGIC) != InpMagic || HistoryDealGetString(d, DEAL_SYMBOL) != _Symbol) continue;
      if(HistoryDealGetInteger(d, DEAL_ENTRY) != DEAL_ENTRY_IN) continue;
      int o = OwnerFromComment(HistoryDealGetString(d, DEAL_COMMENT));
      if(o >= 0) g_s[o].trades++;
     }
  }

void OnDeinit(const int reason)
  {
   EngineDeinit();
  }

//--- range from M1 data (independent of the chart timeframe) ---------
bool RangeHL(datetime from, datetime to, double &hi, double &lo)
  {
   MqlRates r[];
   int n = CopyRates(_Symbol, PERIOD_M1, from, to, r);
   if(n <= 0) return false;
   hi = r[0].high;
   lo = r[0].low;
   for(int i = 1; i < n; i++)
     {
      hi = MathMax(hi, r[i].high);
      lo = MathMin(lo, r[i].low);
     }
   return true;
  }

void DrawBox(int i, datetime right)
  {
   if(!InpShowBoxes || g_s[i].hi <= 0) return;
   string nm = ObjPre() + "box_" + IntegerToString(i) + "_" + (string)(long)g_s[i].rangeStart;
   if(ObjectFind(0, nm) < 0)
     {
      ObjectCreate(0, nm, OBJ_RECTANGLE, 0, g_s[i].rangeStart, g_s[i].hi, right, g_s[i].lo);
      ObjectSetInteger(0, nm, OBJPROP_COLOR, g_s[i].col);
      ObjectSetInteger(0, nm, OBJPROP_FILL, false);
      ObjectSetInteger(0, nm, OBJPROP_WIDTH, 1);
      ObjectSetInteger(0, nm, OBJPROP_BACK, true);
      ObjectSetInteger(0, nm, OBJPROP_SELECTABLE, false);
      ObjectSetString(0, nm, OBJPROP_TOOLTIP, g_s[i].name + " range");
     }
   ObjectMove(0, nm, 0, g_s[i].rangeStart, g_s[i].hi);
   ObjectMove(0, nm, 1, right, g_s[i].lo);
  }

//--- SL / TP ----------------------------------------------------------
double SlPrice(int dir, double entry, int i)
  {
   if(InpSlType == ORB_SL_OPP) return dir == 1 ? g_s[i].lo : g_s[i].hi;
   if(InpSlType == ORB_SL_MID) return (g_s[i].hi + g_s[i].lo) / 2.0;
   if(InpSlType == ORB_SL_POINTS) return entry - dir * InpSlPoints * _Point;
   return entry - dir * AtrTV(InpSlAtrLen) * InpSlAtrMul;
  }

double TpParam(int dir, double entry, double sl)
  {
   if(InpTpType == ORB_TP_NONE) return -1;
   if(InpTpType == ORB_TP_POINTS) return entry + dir * InpTpPoints * _Point;
   return 0;   // Risk:Reward from Trade management
  }

string SessTag(int i) { return "ORB " + g_s[i].name; }

int OwnerFromComment(string c)
  {
   for(int i = 0; i < 3; i++)
      if(StringFind(c, g_s[i].name) >= 0) return i;
   return -1;
  }

//--- daily / monthly limits ------------------------------------------
void CheckLimits(MqlDateTime &dt)
  {
   double eq = AccountInfoDouble(ACCOUNT_EQUITY);
   double dayKey = dt.year * 1000 + dt.day_of_year, monKey = dt.year * 100 + dt.mon;
   string kDK = GVKey(0, "DK"), kDE = GVKey(0, "DE"), kMK = GVKey(0, "MK"), kME = GVKey(0, "ME"), kBL = GVKey(0, "BL");
   if(!GlobalVariableCheck(kDK) || GlobalVariableGet(kDK) != dayKey)
     {
      GlobalVariableSet(kDK, dayKey);
      GlobalVariableSet(kDE, eq);
      GlobalVariableSet(kBL, 0);
     }
   if(!GlobalVariableCheck(kMK) || GlobalVariableGet(kMK) != monKey)
     {
      GlobalVariableSet(kMK, monKey);
      GlobalVariableSet(kME, eq);
     }
   double de = GlobalVariableGet(kDE), me = GlobalVariableGet(kME);
   g_dayPct = de > 0 ? (eq - de) / de * 100 : 0;
   g_monPct = me > 0 ? (eq - me) / me * 100 : 0;
   bool dayHit = (InpDayLoss > 0 && g_dayPct <= -InpDayLoss) || (InpDayGain > 0 && g_dayPct >= InpDayGain);
   bool monHit = (InpMonLoss > 0 && g_monPct <= -InpMonLoss) || (InpMonGain > 0 && g_monPct >= InpMonGain);
   if(dayHit || monHit) GlobalVariableSet(kBL, 1);
   g_limitHit = GlobalVariableGet(kBL) > 0 || monHit;
   if(g_limitHit && (CountPos(0) > 0 || OrdersTotal() > 0))
     {
      ClosePositions(0, "P/L limit");
      DeletePendings();
     }
  }

//--- trade events: count entries per session, detect SL for reverse --
void OnTradeTransaction(const MqlTradeTransaction &trans, const MqlTradeRequest &request, const MqlTradeResult &result)
  {
   if(trans.type != TRADE_TRANSACTION_DEAL_ADD) return;
   ulong d = trans.deal;
   if(!HistoryDealSelect(d)) return;
   if((ulong)HistoryDealGetInteger(d, DEAL_MAGIC) != InpMagic || HistoryDealGetString(d, DEAL_SYMBOL) != _Symbol) return;
   long entry = HistoryDealGetInteger(d, DEAL_ENTRY);
   ulong posId = (ulong)HistoryDealGetInteger(d, DEAL_POSITION_ID);
   if(entry == DEAL_ENTRY_IN)
     {
      int o = OwnerFromComment(HistoryDealGetString(d, DEAL_COMMENT));
      if(o >= 0)
        {
         g_s[o].trades++;
         GlobalVariableSet(GVKey(posId, "O"), o + 1);
         int k = ArraySize(g_memId);
         ArrayResize(g_memId, k + 1);
         ArrayResize(g_memOwn, k + 1);
         g_memId[k] = posId;
         g_memOwn[k] = o;
         DeletePendings(g_s[o].name);   // one-cancels-other for touch mode
        }
     }
   else if(entry == DEAL_ENTRY_OUT && InpReverseSL)
     {
      long reason = HistoryDealGetInteger(d, DEAL_REASON);
      double p = HistoryDealGetDouble(d, DEAL_PROFIT);
      string kO = GVKey(posId, "O");
      int owner = GlobalVariableCheck(kO) ? (int)GlobalVariableGet(kO) - 1 : -1;
      for(int k = ArraySize(g_memId) - 1; k >= 0 && owner < 0; k--)
         if(g_memId[k] == posId) owner = g_memOwn[k];
      if(reason == DEAL_REASON_SL && p < 0 && owner >= 0)
        {
         g_revOwner = owner;
         g_revDir = HistoryDealGetInteger(d, DEAL_TYPE) == DEAL_TYPE_SELL ? -1 : 1;   // closed a long → go short
        }
     }
  }

//--- per-session P/L from history -----------------------------------
void SessionPL(double &pl[], int &n[], int &w[])
  {
   ArrayResize(pl, 3); ArrayResize(n, 3); ArrayResize(w, 3);
   ArrayInitialize(pl, 0); ArrayInitialize(n, 0); ArrayInitialize(w, 0);
   HistorySelect(0, TimeCurrent() + 86400);
   int total = HistoryDealsTotal();
   ulong ids[];
   int   own[];
   for(int i = 0; i < total; i++)
     {
      ulong d = HistoryDealGetTicket(i);
      if(d == 0 || (ulong)HistoryDealGetInteger(d, DEAL_MAGIC) != InpMagic || HistoryDealGetString(d, DEAL_SYMBOL) != _Symbol) continue;
      if(HistoryDealGetInteger(d, DEAL_ENTRY) != DEAL_ENTRY_IN) continue;
      int k = ArraySize(ids);
      ArrayResize(ids, k + 1);
      ArrayResize(own, k + 1);
      ids[k] = (ulong)HistoryDealGetInteger(d, DEAL_POSITION_ID);
      own[k] = OwnerFromComment(HistoryDealGetString(d, DEAL_COMMENT));
     }
   for(int i = 0; i < total; i++)
     {
      ulong d = HistoryDealGetTicket(i);
      if(d == 0 || (ulong)HistoryDealGetInteger(d, DEAL_MAGIC) != InpMagic || HistoryDealGetString(d, DEAL_SYMBOL) != _Symbol) continue;
      long e = HistoryDealGetInteger(d, DEAL_ENTRY);
      if(e != DEAL_ENTRY_OUT && e != DEAL_ENTRY_OUT_BY) continue;
      ulong pid = (ulong)HistoryDealGetInteger(d, DEAL_POSITION_ID);
      int o = -1;
      for(int k = 0; k < ArraySize(ids); k++)
         if(ids[k] == pid) { o = own[k]; break; }
      if(o < 0) continue;
      double p = HistoryDealGetDouble(d, DEAL_PROFIT) + HistoryDealGetDouble(d, DEAL_SWAP) + HistoryDealGetDouble(d, DEAL_COMMISSION);
      pl[o] += p;
      n[o]++;
      if(p > 0) w[o]++;
     }
  }

void UpdatePanel()
  {
   if(!InpShowPanel) return;
   double pl[];
   int n[], w[];
   SessionPL(pl, n, w);
   string lines[];
   int side = PosDir();
   AddLine(lines, EA_NAME + "  |  Eye Algo");
   AddLine(lines, "Session   Status    Range   Trades   P/L     Win%");
   for(int i = 0; i < 3; i++)
     {
      string st = !g_s[i].on ? "Off" : g_s[i].filtered ? "Filtered" : g_s[i].state == 1 ? "Building" : g_s[i].state == 2 ? "Active" : g_s[i].state == 3 ? "Done" : "Waiting";
      string rg = g_s[i].hi > 0 ? IntegerToString((int)MathRound((g_s[i].hi - g_s[i].lo) / _Point)) : "-";
      AddLine(lines, StringFormat("%-9s %-9s %6s   %d/%d   %8.2f  %5s", g_s[i].name, st, rg, g_s[i].trades, g_s[i].maxTrades, pl[i],
                                  n[i] > 0 ? DoubleToString(100.0 * w[i] / n[i], 0) : "-"));
     }
   AddLine(lines, StringFormat("Position: %s%s", side == 1 ? "LONG" : side == -1 ? "SHORT" : "flat", g_limitHit ? "   P/L LIMIT HIT" : ""));
   AddLine(lines, StringFormat("Day P/L: %.2f%%   Month P/L: %.2f%%", g_dayPct, g_monPct));
   DrawPanel(lines, 440);
  }

//--- main --------------------------------------------------------------
void OnTick()
  {
   ManageTrades();

   datetime srv = TimeCurrent();
   datetime loc = srv + InpTimeOffset * 3600;
   MqlDateTime dt;
   TimeToStruct(loc, dt);
   int nowMin = dt.hour * 60 + dt.min;
   CheckLimits(dt);

   bool newBar = IsNewBar();
   int side = PosDir();
   bool hasPend = false;
   for(int k = OrdersTotal() - 1; k >= 0; k--)
     {
      ulong t = OrderGetTicket(k);
      if(t != 0 && OrderGetString(ORDER_SYMBOL) == _Symbol && (ulong)OrderGetInteger(ORDER_MAGIC) == InpMagic) hasPend = true;
     }

   for(int i = 0; i < 3; i++)
     {
      if(!g_s[i].on) continue;
      int rel    = (nowMin - g_s[i].startMin + 1440) % 1440;
      int endRel = (g_s[i].endMin - g_s[i].startMin + 1440) % 1440;
      if(endRel <= g_s[i].dur) endRel = 1440;
      datetime start = srv - rel * 60 - dt.sec;

      if(rel < g_s[i].dur)
        {
         if(g_s[i].state != 1)
           {
            if(g_s[i].state != 0) g_s[i].trades = 0;   // state 0 = EA just started, keep restored count
            g_s[i].state = 1;
            g_s[i].filtered = false;
            g_s[i].pendingsPlaced = false;
            g_s[i].rangeStart = start;
           }
         double h, l;
         if(RangeHL(g_s[i].rangeStart, srv, h, l))
           {
            g_s[i].hi = h;
            g_s[i].lo = l;
            DrawBox(i, srv);
           }
        }
      else if(rel < endRel)
        {
         if(g_s[i].state == 0 || g_s[i].state == 1)
           {
            // range complete (also rebuilds the range if the EA was started mid-session)
            if(g_s[i].state == 0) g_s[i].rangeStart = start;
            double h, l;
            if(!RangeHL(g_s[i].rangeStart, g_s[i].rangeStart + g_s[i].dur * 60 - 1, h, l)) continue;
            g_s[i].hi = h;
            g_s[i].lo = l;
            g_s[i].state = 2;
            double pts = (h - l) / _Point;
            if((InpMinRange > 0 && pts < InpMinRange) || (InpMaxRange > 0 && pts > InpMaxRange))
              {
               g_s[i].filtered = true;
               g_s[i].state = 3;
              }
           }
         if(g_s[i].state == 2) DrawBox(i, g_s[i].rangeStart + endRel * 60);
        }
      else
        {
         if(g_s[i].state == 1 || g_s[i].state == 2)
           {
            g_s[i].state = 3;
            if(InpExitEnd)
              {
               for(int p = PositionsTotal() - 1; p >= 0; p--)
                 {
                  if(!SelectMine(p)) continue;
                  string kO = GVKey((ulong)PositionGetInteger(POSITION_IDENTIFIER), "O");
                  if(GlobalVariableCheck(kO) && (int)GlobalVariableGet(kO) - 1 == i)
                     g_trade.PositionClose((ulong)PositionGetInteger(POSITION_TICKET));
                 }
              }
            DeletePendings(g_s[i].name);
            if(g_revOwner == i) g_revDir = 0;
           }
         continue;
        }

      // ---- entries -----------------------------------------------------
      bool ready = g_s[i].state == 2 && g_s[i].trades < g_s[i].maxTrades && DayOk(dt.day_of_week) && !g_limitHit && side == 0;
      if(!ready) continue;
      double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK), bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      bool allowL = InpDirection != DIR_SHORT, allowS = InpDirection != DIR_LONG;

      // reverse after a stop loss
      if(g_revDir != 0 && g_revOwner == i)
        {
         int d = g_revDir;
         g_revDir = 0;
         if((d == 1 && allowL) || (d == -1 && allowS))
           {
            double price = d == 1 ? ask : bid;
            double sl = SlPrice(d, price, i);
            if(d * (price - sl) > 0 && OpenTrade(d, sl, TpParam(d, price, sl), SessTag(i) + (d == 1 ? " Rev Long" : " Rev Short")))
              {
               MarkSignal(d, 0);
               side = d;
              }
           }
         continue;
        }

      if(InpEntryMode == ORB_CLOSE)
        {
         if(!newBar) continue;
         double c1 = iClose(_Symbol, _Period, 1), c2 = iClose(_Symbol, _Period, 2);
         datetime t1 = iTime(_Symbol, _Period, 1);
         if(t1 < g_s[i].rangeStart + g_s[i].dur * 60) continue;   // bar must close after the range is complete
         int d = (c1 > g_s[i].hi && c2 <= g_s[i].hi && allowL) ? 1 : (c1 < g_s[i].lo && c2 >= g_s[i].lo && allowS) ? -1 : 0;
         if(d == 0) continue;
         double price = d == 1 ? ask : bid;
         double sl = SlPrice(d, price, i);
         if(d * (price - sl) > 0 && OpenTrade(d, sl, TpParam(d, price, sl), SessTag(i) + (d == 1 ? " Long" : " Short")))
           {
            MarkSignal(d, 0);
            side = d;
           }
        }
      else if(!hasPend)
        {
         // touch mode: buy stop at the high, sell stop at the low
         if(!SpreadOk()) continue;
         double minD = StopsMin() + _Point;
         double hi = NP(g_s[i].hi), lo = NP(g_s[i].lo);
         bool placed = false;
         if(allowL && hi - ask > minD)
           {
            double sl = SlPrice(1, hi, i), tp = TpParam(1, hi, sl);
            double dist = hi - sl;
            if(dist > minD)
              {
               if(tp == 0 && InpRR > 0) tp = hi + dist * InpRR;
               if(g_trade.BuyStop(CalcLot(dist), hi, _Symbol, NP(sl), tp > 0 ? NP(tp) : 0, ORDER_TIME_GTC, 0, SessTag(i) + " Long"))
                  placed = true;
              }
           }
         if(allowS && bid - lo > minD)
           {
            double sl = SlPrice(-1, lo, i), tp = TpParam(-1, lo, sl);
            double dist = sl - lo;
            if(dist > minD)
              {
               if(tp == 0 && InpRR > 0) tp = lo - dist * InpRR;
               if(g_trade.SellStop(CalcLot(dist), lo, _Symbol, NP(sl), tp > 0 ? NP(tp) : 0, ORDER_TIME_GTC, 0, SessTag(i) + " Short"))
                  placed = true;
              }
           }
         if(placed)
           {
            g_s[i].pendingsPlaced = true;
            hasPend = true;
           }
        }
     }

   if(newBar)
     {
      CleanGV();
      UpdatePanel();
     }
  }

double CustomTrail(int dir) { return 0; }
