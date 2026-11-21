//+------------------------------------------------------------------+
//|                                       Lab_Trailing_BreakEven.mq5 |
//|  Manages the stop loss of positions that are already open:       |
//|  break-even (with optional locked profit) and trailing stop      |
//|  in fixed points or as a multiple of ATR. It never opens trades. |
//|  Free utility. Not financial advice.                             |
//+------------------------------------------------------------------+
#property copyright "Strategy Lab"
#property version   "1.00"
#property description "Break-even and trailing stop manager for positions you already have open."
#property description "Trailing in fixed points or ATR multiple. Filters: all symbols or this symbol, any magic or one magic."
#property description "It only moves stops in your favour and never opens trades."

#include <Trade\Trade.mqh>

enum ENUM_SCOPE
  {
   SCOPE_ALL_SYMBOLS = 0,   // All symbols
   SCOPE_THIS_SYMBOL = 1    // Only this chart's symbol
  };

enum ENUM_TRAIL_MODE
  {
   TRAIL_OFF    = 0,        // Off (break-even only)
   TRAIL_POINTS = 1,        // Fixed distance in points
   TRAIL_ATR    = 2         // ATR multiple
  };

input group "Break-even"
input double          InpBeTrigger   = 200;          // Move to break-even after profit of (points, 0 = off)
input double          InpBeLock      = 20;           // Lock this many points of profit at break-even

input group "Trailing stop"
input ENUM_TRAIL_MODE InpTrailMode   = TRAIL_POINTS; // Trailing mode
input double          InpTrailStart  = 300;          // Start trailing after profit of (points)
input double          InpTrailDist   = 200;          // Trailing distance (points, fixed mode)
input double          InpAtrMult     = 2.0;          // ATR multiple (ATR mode)
input int             InpAtrPeriod   = 14;           // ATR period (ATR mode)
input ENUM_TIMEFRAMES InpAtrTf       = PERIOD_CURRENT; // ATR timeframe (ATR mode)
input double          InpStepPts     = 20;           // Move the stop only if it improves by at least (points)

input group "Filters"
input ENUM_SCOPE      InpScope       = SCOPE_THIS_SYMBOL; // Positions to manage
input long            InpMagic       = -1;           // Magic number (-1 = any, 0 = manual trades only)
input bool            InpShowPanel   = true;         // Show status on the chart

CTrade trade;
int    g_atr[];        // one ATR handle per symbol seen
string g_atrSym[];
int    g_moves = 0;
datetime g_pauseUntil = 0;   // after a failed modify (e.g. market closed) wait before retrying

//+------------------------------------------------------------------+
bool Selected(const string sym, const long magic)
  {
   if(InpScope == SCOPE_THIS_SYMBOL && sym != _Symbol) return false;
   if(InpMagic >= 0 && magic != InpMagic)              return false;
   return true;
  }

//+------------------------------------------------------------------+
//| ATR in price for a symbol (handle created on first use)          |
//+------------------------------------------------------------------+
double AtrPrice(const string sym)
  {
   int idx = -1;
   for(int i = 0; i < ArraySize(g_atrSym); i++)
      if(g_atrSym[i] == sym) { idx = i; break; }
   if(idx < 0)
     {
      int h = iATR(sym, InpAtrTf, InpAtrPeriod);
      if(h == INVALID_HANDLE) return 0;
      idx = ArraySize(g_atrSym);
      ArrayResize(g_atrSym, idx + 1);
      ArrayResize(g_atr, idx + 1);
      g_atrSym[idx] = sym;
      g_atr[idx] = h;
     }
   double b[];
   if(CopyBuffer(g_atr[idx], 0, 1, 1, b) != 1) return 0;   // last closed bar
   return b[0];
  }

//+------------------------------------------------------------------+
//| Manage every selected position                                   |
//+------------------------------------------------------------------+
int ManagePositions(void)
  {
   int managed = 0;
   bool paused = (TimeCurrent() < g_pauseUntil);
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      string sym = PositionGetString(POSITION_SYMBOL);
      if(!Selected(sym, PositionGetInteger(POSITION_MAGIC))) continue;
      managed++;

      double point  = SymbolInfoDouble(sym, SYMBOL_POINT);
      int    digits = (int)SymbolInfoInteger(sym, SYMBOL_DIGITS);
      double minDist = (double)SymbolInfoInteger(sym, SYMBOL_TRADE_STOPS_LEVEL) * point;
      long   type   = PositionGetInteger(POSITION_TYPE);
      double open   = PositionGetDouble(POSITION_PRICE_OPEN);
      double sl     = PositionGetDouble(POSITION_SL);
      double tp     = PositionGetDouble(POSITION_TP);
      bool   isBuy  = (type == POSITION_TYPE_BUY);
      double price  = isBuy ? SymbolInfoDouble(sym, SYMBOL_BID) : SymbolInfoDouble(sym, SYMBOL_ASK);
      if(point <= 0 || price <= 0) continue;
      double gainPts = isBuy ? (price - open) / point : (open - price) / point;

      double newSl = sl;

      // 1) Break-even
      if(InpBeTrigger > 0 && gainPts >= InpBeTrigger)
        {
         double be = isBuy ? open + InpBeLock * point : open - InpBeLock * point;
         if(isBuy  && (newSl == 0 || be > newSl)) newSl = be;
         if(!isBuy && (newSl == 0 || be < newSl)) newSl = be;
        }

      // 2) Trailing stop
      if(InpTrailMode != TRAIL_OFF && gainPts >= InpTrailStart)
        {
         double dist = (InpTrailMode == TRAIL_POINTS) ? InpTrailDist * point : AtrPrice(sym) * InpAtrMult;
         if(dist > 0)
           {
            double tr = isBuy ? price - dist : price + dist;
            if(isBuy  && (newSl == 0 || tr > newSl)) newSl = tr;
            if(!isBuy && (newSl == 0 || tr < newSl)) newSl = tr;
           }
        }

      newSl = NormalizeDouble(newSl, digits);
      if(newSl == 0 || newSl == sl || paused) continue;

      // only in our favour, by at least one step, and respecting the broker's minimum distance
      if(sl != 0 && MathAbs(newSl - sl) < InpStepPts * point) continue;
      if(isBuy  && price - newSl < minDist) continue;
      if(!isBuy && newSl - price < minDist) continue;

      if(trade.PositionModify(ticket, newSl, tp))
        {
         g_moves++;
         PrintFormat("Stop moved #%I64u %s: %s -> %s", ticket, sym,
                     sl == 0 ? "none" : DoubleToString(sl, digits), DoubleToString(newSl, digits));
        }
      else
        {
         PrintFormat("Could not move stop #%I64u: %d %s (retrying in 60 s)", ticket, trade.ResultRetcode(), trade.ResultRetcodeDescription());
         g_pauseUntil = TimeCurrent() + 60;
         paused = true;
        }
     }
   return managed;
  }

//+------------------------------------------------------------------+
void ShowStatus(const int managed)
  {
   if(!InpShowPanel) return;
   string trail = (InpTrailMode == TRAIL_OFF) ? "off" :
                  (InpTrailMode == TRAIL_POINTS) ? StringFormat("%.0f pts after %.0f pts", InpTrailDist, InpTrailStart) :
                  StringFormat("%.1f x ATR(%d) after %.0f pts", InpAtrMult, InpAtrPeriod, InpTrailStart);
   string be = (InpBeTrigger > 0) ? StringFormat("after %.0f pts, lock %.0f pts", InpBeTrigger, InpBeLock) : "off";
   Comment(StringFormat("Lab Trailing & Break-even  |  positions managed: %d  |  stops moved: %d\nBreak-even: %s\nTrailing: %s",
                        managed, g_moves, be, trail));
  }

//+------------------------------------------------------------------+
int OnInit()
  {
   if(InpBeTrigger <= 0 && InpTrailMode == TRAIL_OFF)
     {
      Alert("Lab Trailing: enable break-even and/or a trailing mode.");
      return INIT_PARAMETERS_INCORRECT;
     }
   if(InpBeTrigger > 0 && InpBeLock >= InpBeTrigger)
     {
      Alert("Lab Trailing: the locked profit must be smaller than the break-even trigger.");
      return INIT_PARAMETERS_INCORRECT;
     }
   if(InpTrailMode == TRAIL_POINTS && InpTrailDist <= 0)
     {
      Alert("Lab Trailing: trailing distance must be greater than 0.");
      return INIT_PARAMETERS_INCORRECT;
     }
   if(InpTrailMode == TRAIL_ATR && (InpAtrPeriod < 1 || InpAtrMult <= 0))
     {
      Alert("Lab Trailing: check ATR period and multiple.");
      return INIT_PARAMETERS_INCORRECT;
     }
   trade.SetAsyncMode(false);
   EventSetTimer(1);
   return INIT_SUCCEEDED;
  }

void OnDeinit(const int reason)
  {
   EventKillTimer();
   for(int i = 0; i < ArraySize(g_atr); i++)
      if(g_atr[i] != INVALID_HANDLE) IndicatorRelease(g_atr[i]);
   Comment("");
  }

void OnTick()  { ShowStatus(ManagePositions()); }
void OnTimer() { ShowStatus(ManagePositions()); }
//+------------------------------------------------------------------+
