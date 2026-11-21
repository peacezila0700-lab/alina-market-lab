//+------------------------------------------------------------------+
//|  Bollinger Bands Bounce / Breakout EA               © Eye Algo   |
//+------------------------------------------------------------------+
#property copyright   "Eye Algo"
#property version     "1.00"
#property description "Bollinger Bands in Bounce or Breakout mode. Exit at the middle band, the opposite band, or by SL/TP (Risk:Reward)."

#define EA_NAME  "Bollinger EA"
#define EA_MAGIC 26010104

enum ENUM_BB_MODE
  {
   BB_BOUNCE   = 0, // Bounce
   BB_BREAKOUT = 1  // Breakout
  };

enum ENUM_BB_TP
  {
   BB_TP_MIDDLE   = 0, // Middle band
   BB_TP_OPPOSITE = 1, // Opposite band
   BB_TP_RR       = 2  // Risk:Reward
  };

enum ENUM_BB_SL
  {
   BB_SL_ATR     = 0, // ATR
   BB_SL_POINTS  = 1, // Fixed points
   BB_SL_PERCENT = 2, // Percent of price
   BB_SL_CANDLE  = 3  // Signal candle + ATR buffer
  };

input group "Bollinger Bands"
input ENUM_BB_MODE InpMode = BB_BOUNCE; // Entry mode
input int    InpBBLen  = 20;   // Period
input double InpBBDev  = 2.0;  // Deviation

input group "Exit"
input ENUM_BB_TP InpTpMode = BB_TP_MIDDLE; // Take profit

input group "Stop loss"
input ENUM_BB_SL InpSlType = BB_SL_ATR; // Stop loss type
input int    InpSlAtrLen = 14;   // ATR length
input double InpSlAtrMul = 1.5;  // ATR multiplier
input int    InpSlPoints = 300;  // Fixed stop (points)
input double InpSlPct    = 1.0;  // Stop (%)

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


int g_hBB = INVALID_HANDLE;

int OnInit()
  {
   g_hBB = iBands(_Symbol, _Period, InpBBLen, 0, InpBBDev, PRICE_CLOSE);
   if(g_hBB == INVALID_HANDLE) return INIT_FAILED;
   EngineInit();
   return INIT_SUCCEEDED;
  }

void OnDeinit(const int reason)
  {
   IndicatorRelease(g_hBB);
   EngineDeinit();
  }

void OnTick()
  {
   ManageTrades();
   if(!IsNewBar()) return;

   double mid1 = Buf(g_hBB, 0, 1), up1 = Buf(g_hBB, 1, 1), lo1 = Buf(g_hBB, 2, 1);
   double mid2 = Buf(g_hBB, 0, 2), up2 = Buf(g_hBB, 1, 2), lo2 = Buf(g_hBB, 2, 2);
   if(mid1 == EMPTY_VALUE || mid2 == EMPTY_VALUE || up1 == EMPTY_VALUE || lo1 == EMPTY_VALUE || up2 == EMPTY_VALUE || lo2 == EMPTY_VALUE) return;

   double c1 = iClose(_Symbol, _Period, 1), c2 = iClose(_Symbol, _Period, 2);
   double h1 = iHigh(_Symbol, _Period, 1),  h2 = iHigh(_Symbol, _Period, 2);
   double l1 = iLow(_Symbol, _Period, 1),   l2 = iLow(_Symbol, _Period, 2);

   bool bounceL = (c2 < lo2 || l1 < lo1) && c1 > lo1 && c1 < mid1;
   bool bounceS = (c2 > up2 || h1 > up1) && c1 < up1 && c1 > mid1;
   bool breakL  = c1 > up1 && c2 <= up2;
   bool breakS  = c1 < lo1 && c2 >= lo2;
   bool buyOk   = InpMode == BB_BOUNCE ? bounceL : breakL;
   bool sellOk  = InpMode == BB_BOUNCE ? bounceS : breakS;

   // Bounce: target is the middle / opposite band. Breakout: exit when price falls back to the middle / opposite band.
   bool bo = InpMode == BB_BREAKOUT;
   bool exitL = InpTpMode == BB_TP_MIDDLE ? (bo ? (c1 <= mid1 && c2 > mid2) : (c1 >= mid1 && c2 < mid2))
              : InpTpMode == BB_TP_OPPOSITE ? (bo ? c1 <= lo1 : c1 >= up1) : false;
   bool exitS = InpTpMode == BB_TP_MIDDLE ? (bo ? (c1 >= mid1 && c2 < mid2) : (c1 <= mid1 && c2 > mid2))
              : InpTpMode == BB_TP_OPPOSITE ? (bo ? c1 >= up1 : c1 <= lo1) : false;
   double tpMode = InpTpMode == BB_TP_RR ? 0 : -1;

   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK), bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double atr = AtrTV(InpSlAtrLen);
   double slB = 0, slS = 0;
   if(InpSlType == BB_SL_CANDLE)
     {
      slB = MathMin(l1, l2) - atr * 0.5;
      slS = MathMax(h1, h2) + atr * 0.5;
     }
   else
     {
      double dist = BasicSlDist((int)InpSlType, atr, InpSlAtrMul, InpSlPoints, InpSlPct, c1);
      slB = ask - dist;
      slS = bid + dist;
     }

   ProcessSignals(buyOk, sellOk, exitL, exitS, EnumToString(InpTpMode), slB, slS, tpMode, tpMode, "BB Buy", "BB Sell");
   CleanGV();
   ShowPanel(StringFormat("Upper %s  Mid %s  Lower %s", DoubleToString(up1, _Digits), DoubleToString(mid1, _Digits), DoubleToString(lo1, _Digits)));
  }

double CustomTrail(int dir) { return 0; }
