//+------------------------------------------------------------------+
//|                                   SmartBreakEvenPartialClose.mq5 |
//|                                   Copyright 2026, Deepanshu Goyal |
//|                 https://www.mql5.com/en/users/deepanshugoyal99   |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, Deepanshu Goyal"
#property link      "https://www.mql5.com/en/users/deepanshugoyal99"
#property version   "1.00"
#property description "Smart Break-Even & Partial Close manager for manual trades and other EAs."
#property description "Moves the stop to break-even at a chosen R multiple, closes part of the"
#property description "position at a second target, then trails in steps. Stops are modified only"
#property description "when they actually improve, which keeps server requests low (prop firm safe)."

#include <Trade/Trade.mqh>

//--- inputs
input long   InpMagicFilter       = -1;    // Magic number to manage (-1 = all, 0 = manual trades only)
input bool   InpAllSymbols        = true;  // Manage all symbols (false = this chart's symbol only)
input group  "Break-even"
input double InpBreakEvenAtR      = 1.0;   // Move SL to break-even at this R multiple (0 = off)
input int    InpBreakEvenPoints   = 0;     // ...or at this profit in points, for trades without an SL (0 = off)
input int    InpBreakEvenOffset   = 20;    // Points beyond entry to cover spread and commission
input group  "Partial close"
input double InpPartialAtR        = 2.0;   // Close part of the position at this R multiple (0 = off)
input double InpPartialPercent    = 50.0;  // Percent of the volume to close
input group  "Trailing stop"
input double InpTrailStartR       = 2.0;   // Start trailing at this R multiple (0 = off)
input int    InpTrailDistance     = 300;   // Trailing distance in points
input int    InpTrailStep         = 100;   // Move the SL only in steps of this many points

CTrade trade;

//+------------------------------------------------------------------+
//| Per-position memory kept in terminal global variables, so a      |
//| restart does not forget the original risk or a partial close.    |
//+------------------------------------------------------------------+
string Key(const ulong ticket, const string field) { return "SBEPC_" + IntegerToString((long)ticket) + "_" + field; }

int OnInit()
  {
   if(InpPartialPercent <= 0 || InpPartialPercent >= 100 || InpTrailDistance < 0 || InpTrailStep < 0 ||
      InpBreakEvenOffset < 0 || InpBreakEvenAtR < 0 || InpPartialAtR < 0 || InpTrailStartR < 0)
     {
      Print("Invalid inputs: partial percent must be between 0 and 100 and the other values >= 0.");
      return INIT_PARAMETERS_INCORRECT;
     }
   trade.SetDeviationInPoints(30);
   EventSetTimer(1);
   return INIT_SUCCEEDED;
  }

void OnDeinit(const int reason) { EventKillTimer(); }
void OnTick()  { ManageAll(); }

void OnTimer()
  {
   ManageAll();
   static datetime lastCleanup = 0;
   if(TimeCurrent() - lastCleanup >= 60)
     {
      lastCleanup = TimeCurrent();
      CleanupClosed();
     }
  }

//+------------------------------------------------------------------+
void ManageAll()
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0)
         continue;
      long magic = PositionGetInteger(POSITION_MAGIC);
      if(InpMagicFilter >= 0 && magic != InpMagicFilter)
         continue;
      string symbol = PositionGetString(POSITION_SYMBOL);
      if(!InpAllSymbols && symbol != _Symbol)
         continue;
      Manage(ticket, symbol);
     }
  }

//+------------------------------------------------------------------+
void Manage(const ulong ticket, const string symbol)
  {
   if(!PositionSelectByTicket(ticket))
      return;
   bool   isBuy  = PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY;
   double open   = PositionGetDouble(POSITION_PRICE_OPEN);
   double sl     = PositionGetDouble(POSITION_SL);
   double tp     = PositionGetDouble(POSITION_TP);
   double volume = PositionGetDouble(POSITION_VOLUME);
   double point  = SymbolInfoDouble(symbol, SYMBOL_POINT);
   double bid    = SymbolInfoDouble(symbol, SYMBOL_BID);
   double ask    = SymbolInfoDouble(symbol, SYMBOL_ASK);
   if(point <= 0 || bid <= 0 || ask <= 0)
      return;
   double price  = isBuy ? bid : ask;
   double profit = isBuy ? bid - open : open - ask;   // distance in price, not money

   //--- remember the original risk (1R) the first time a stop loss is seen
   string riskKey = Key(ticket, "risk");
   double risk = GlobalVariableCheck(riskKey) ? GlobalVariableGet(riskKey) : 0;
   if(risk <= 0 && sl > 0)
     {
      double dist = MathAbs(open - sl);
      if(dist > 0 && (isBuy ? sl < open : sl > open))
        {
         risk = dist;
         GlobalVariableSet(riskKey, risk);
        }
     }

   //--- 1. partial close
   string partialKey = Key(ticket, "partial");
   if(risk > 0 && InpPartialAtR > 0 && !GlobalVariableCheck(partialKey) && profit >= risk * InpPartialAtR)
     {
      double closeVol = NormalizeVolume(symbol, volume * InpPartialPercent / 100.0);
      double minVol   = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN);
      if(closeVol >= minVol && volume - closeVol >= minVol - 1e-9)
        {
         trade.SetTypeFillingBySymbol(symbol);
         bool hedging = AccountInfoInteger(ACCOUNT_MARGIN_MODE) == ACCOUNT_MARGIN_MODE_RETAIL_HEDGING;
         bool done = hedging ? trade.PositionClosePartial(ticket, closeVol)
                             : trade.PositionClosePartial(symbol, closeVol);   // netting: one position per symbol
         if(done)
            GlobalVariableSet(partialKey, 1);
         else
            PrintFormat("Partial close failed for %I64u: retcode %u", ticket, trade.ResultRetcode());
         return;   // re-read the position on the next pass
        }
      GlobalVariableSet(partialKey, 1); // volume too small to split: skip partial for this trade
     }

   //--- 2. break-even
   double newSl = sl;
   double beTrigger = 0;
   if(risk > 0 && InpBreakEvenAtR > 0)
      beTrigger = risk * InpBreakEvenAtR;
   else if(InpBreakEvenPoints > 0)
      beTrigger = InpBreakEvenPoints * point;
   if(beTrigger > 0 && profit >= beTrigger)
     {
      double be = isBuy ? open + InpBreakEvenOffset * point : open - InpBreakEvenOffset * point;
      if(IsBetter(isBuy, be, newSl))
         newSl = be;
     }

   //--- 3. step trailing
   if(InpTrailStartR > 0 && InpTrailDistance > 0)
     {
      double start = risk > 0 ? risk * InpTrailStartR : InpTrailDistance * point;
      if(profit >= start)
        {
         double trail = isBuy ? price - InpTrailDistance * point : price + InpTrailDistance * point;
         if(IsBetter(isBuy, trail, newSl) && (newSl == 0 || MathAbs(trail - newSl) >= InpTrailStep * point))
            newSl = trail;
        }
     }

   if(newSl != sl)
      ModifyStop(ticket, symbol, isBuy, newSl, tp);
  }

//+------------------------------------------------------------------+
bool IsBetter(const bool isBuy, const double candidate, const double current)
  {
   if(current == 0)
      return true;
   return isBuy ? candidate > current : candidate < current;
  }

double NormalizeVolume(const string symbol, const double volume)
  {
   double step = SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP);
   if(step <= 0)
      return volume;
   double v = MathFloor(volume / step + 1e-9) * step;
   int digits = (int)MathMax(0, MathCeil(-MathLog10(step)));
   return NormalizeDouble(v, digits);
  }

//+------------------------------------------------------------------+
//| Sends one modification, respecting the broker's minimum stop      |
//| distance and tick size.                                           |
//+------------------------------------------------------------------+
void ModifyStop(const ulong ticket, const string symbol, const bool isBuy, double newSl, const double tp)
  {
   double point    = SymbolInfoDouble(symbol, SYMBOL_POINT);
   double tickSize = SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_SIZE);
   int    digits   = (int)SymbolInfoInteger(symbol, SYMBOL_DIGITS);
   double minDist  = (double)SymbolInfoInteger(symbol, SYMBOL_TRADE_STOPS_LEVEL) * point;
   double bid      = SymbolInfoDouble(symbol, SYMBOL_BID);
   double ask      = SymbolInfoDouble(symbol, SYMBOL_ASK);

   if(isBuy && newSl > bid - minDist)
      return;   // too close to price for this broker; try again later
   if(!isBuy && newSl < ask + minDist)
      return;

   if(tickSize > 0)
      newSl = MathRound(newSl / tickSize) * tickSize;
   newSl = NormalizeDouble(newSl, digits);

   if(!trade.PositionModify(ticket, newSl, tp))
      PrintFormat("Stop update failed for %I64u: retcode %u", ticket, trade.ResultRetcode());
  }

//+------------------------------------------------------------------+
//| Removes memory of positions that are no longer open.             |
//+------------------------------------------------------------------+
void CleanupClosed()
  {
   for(int i = GlobalVariablesTotal() - 1; i >= 0; i--)
     {
      string name = GlobalVariableName(i);
      if(StringFind(name, "SBEPC_") != 0)
         continue;
      string parts[];
      if(StringSplit(name, '_', parts) < 3)
         continue;
      ulong ticket = (ulong)StringToInteger(parts[1]);
      if(!PositionSelectByTicket(ticket))
         GlobalVariableDel(name);
     }
  }
//+------------------------------------------------------------------+
