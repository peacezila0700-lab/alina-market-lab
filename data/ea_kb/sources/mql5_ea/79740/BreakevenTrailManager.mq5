//+------------------------------------------------------------------+
//|                                       BreakevenTrailManager.mq5  |
//|   Trade manager: break-even at +X R and an R-multiple trailing   |
//|   stop for manual trades or any EA (filter by magic)             |
//|                          https://www.mql5.com/en/users/sgupta30  |
//+------------------------------------------------------------------+
#property copyright   "Shipra Gupta (SGupta30)"
#property link        "https://www.mql5.com/en/users/sgupta30"
#property version     "1.00"
#property description "Moves the stop to break-even (+lock) once a trade reaches +BE R,"
#property description "then trails it N R behind price. R = the stop distance seen when the"
#property description "manager first meets the position (stored in global variables)."
#property description "Never opens trades. Never widens a stop."

#include <Trade\Trade.mqh>
//=== inlined helpers (single-file build) ==========================
//+------------------------------------------------------------------+
//|                                                TradeHygiene.mqh  |
//|   Pre-trade checks that the MQL5 Market validator expects        |
//|                          https://www.mql5.com/en/users/sgupta30  |
//+------------------------------------------------------------------+

//+------------------------------------------------------------------+
//| 1. Is trading allowed at every level?                            |
//+------------------------------------------------------------------+
bool TH_TradeAllowed(const string symbol,string &why)
  {
   why="";
   if(!TerminalInfoInteger(TERMINAL_CONNECTED))
     { why="terminal not connected"; return(false); }
   if(!TerminalInfoInteger(TERMINAL_TRADE_ALLOWED))
     { why="AutoTrading disabled in terminal"; return(false); }
   if(!MQLInfoInteger(MQL_TRADE_ALLOWED))
     { why="Algo trading disabled for this program"; return(false); }
   if(!AccountInfoInteger(ACCOUNT_TRADE_ALLOWED))
     { why="trading disabled for this account"; return(false); }
   if(!AccountInfoInteger(ACCOUNT_TRADE_EXPERT))
     { why="expert trading disabled by broker"; return(false); }
   long mode=SymbolInfoInteger(symbol,SYMBOL_TRADE_MODE);
   if(mode==SYMBOL_TRADE_MODE_DISABLED || mode==SYMBOL_TRADE_MODE_CLOSEONLY)
     { why="symbol not open for new trades"; return(false); }
   return(true);
  }

//+------------------------------------------------------------------+
//| 2. Volume: round down to step, clamp to min/max                  |
//+------------------------------------------------------------------+
double TH_NormalizeVolume(const string symbol,double lots)
  {
   double vmin =SymbolInfoDouble(symbol,SYMBOL_VOLUME_MIN);
   double vmax =SymbolInfoDouble(symbol,SYMBOL_VOLUME_MAX);
   double vstep=SymbolInfoDouble(symbol,SYMBOL_VOLUME_STEP);
   if(vstep<=0.0)
      vstep=0.01;
   lots=MathFloor(lots/vstep+1e-9)*vstep;
   if(lots<vmin-1e-12)
      return(0.0);
   if(lots>vmax)
      lots=vmax;
   int digits=(int)MathMax(0,MathCeil(-MathLog10(vstep)-1e-9));
   return(NormalizeDouble(lots,digits));
  }

//+------------------------------------------------------------------+
//| 3. SYMBOL_VOLUME_LIMIT: total open + pending volume per symbol   |
//+------------------------------------------------------------------+
bool TH_VolumeLimitOK(const string symbol,const double add_lots)
  {
   double limit=SymbolInfoDouble(symbol,SYMBOL_VOLUME_LIMIT);
   if(limit<=0.0)
      return(true);
   double used=0.0;
   for(int i=PositionsTotal()-1;i>=0;i--)
      if(PositionGetSymbol(i)==symbol)
         used+=PositionGetDouble(POSITION_VOLUME);
   for(int i=OrdersTotal()-1;i>=0;i--)
     {
      ulong t=OrderGetTicket(i);
      if(t>0 && OrderGetString(ORDER_SYMBOL)==symbol)
         used+=OrderGetDouble(ORDER_VOLUME_CURRENT);
     }
   return(used+add_lots<=limit+1e-9);
  }

//+------------------------------------------------------------------+
//| 4. Price normalisation to tick size (not just digits)            |
//+------------------------------------------------------------------+
double TH_NormalizePrice(const string symbol,const double price)
  {
   double ts=SymbolInfoDouble(symbol,SYMBOL_TRADE_TICK_SIZE);
   int    dg=(int)SymbolInfoInteger(symbol,SYMBOL_DIGITS);
   if(ts<=0.0)
      return(NormalizeDouble(price,dg));
   return(NormalizeDouble(MathRound(price/ts)*ts,dg));
  }

//+------------------------------------------------------------------+
//| 5. Stops level: SL/TP must be far enough from the current price  |
//|    is_buy refers to the position direction.                      |
//+------------------------------------------------------------------+
bool TH_StopsLevelOK(const string symbol,const bool is_buy,const double sl,const double tp)
  {
   MqlTick tk;
   if(!SymbolInfoTick(symbol,tk))
      return(false);
   double pt  =SymbolInfoDouble(symbol,SYMBOL_POINT);
   double minD=(double)SymbolInfoInteger(symbol,SYMBOL_TRADE_STOPS_LEVEL)*pt;
   //--- buy closes at bid, sell closes at ask
   double ref=is_buy?tk.bid:tk.ask;
   if(sl>0.0)
     {
      if(is_buy && ref-sl<minD) return(false);
      if(!is_buy && sl-ref<minD) return(false);
     }
   if(tp>0.0)
     {
      if(is_buy && tp-ref<minD) return(false);
      if(!is_buy && ref-tp<minD) return(false);
     }
   return(true);
  }

//+------------------------------------------------------------------+
//| 6. Freeze level: existing SL/TP too close to price can't change  |
//+------------------------------------------------------------------+
bool TH_FreezeLevelOK(const string symbol,const bool is_buy,const double cur_sl,const double cur_tp)
  {
   MqlTick tk;
   if(!SymbolInfoTick(symbol,tk))
      return(false);
   double fz=(double)SymbolInfoInteger(symbol,SYMBOL_TRADE_FREEZE_LEVEL)*SymbolInfoDouble(symbol,SYMBOL_POINT);
   if(fz<=0.0)
      return(true);
   double ref=is_buy?tk.bid:tk.ask;
   if(cur_sl>0.0 && MathAbs(ref-cur_sl)<=fz) return(false);
   if(cur_tp>0.0 && MathAbs(ref-cur_tp)<=fz) return(false);
   return(true);
  }

//+------------------------------------------------------------------+
//| 7. Free margin: reduce the volume until it fits, or return 0     |
//+------------------------------------------------------------------+
double TH_FitToMargin(const string symbol,const ENUM_ORDER_TYPE type,double lots,const double reserve_pct=10.0)
  {
   double price=(type==ORDER_TYPE_BUY)?SymbolInfoDouble(symbol,SYMBOL_ASK):SymbolInfoDouble(symbol,SYMBOL_BID);
   double free =AccountInfoDouble(ACCOUNT_MARGIN_FREE)*(1.0-reserve_pct/100.0);
   double vstep=SymbolInfoDouble(symbol,SYMBOL_VOLUME_STEP);
   if(vstep<=0.0)
      vstep=0.01;
   lots=TH_NormalizeVolume(symbol,lots);
   for(int guard=0;guard<1000 && lots>0.0;guard++)
     {
      double m=0.0;
      if(!OrderCalcMargin(type,symbol,lots,price,m))
         return(0.0);
      if(m<=free)
         return(lots);
      lots=TH_NormalizeVolume(symbol,lots-vstep);
     }
   return(0.0);
  }

//+------------------------------------------------------------------+
//| 8. Has the SL really changed? (avoids error 10025 "no changes")  |
//+------------------------------------------------------------------+
bool TH_PriceChanged(const string symbol,const double a,const double b)
  {
   double ts=SymbolInfoDouble(symbol,SYMBOL_TRADE_TICK_SIZE);
   if(ts<=0.0)
      ts=SymbolInfoDouble(symbol,SYMBOL_POINT);
   return(MathAbs(a-b)>=ts*0.5);
  }

//+------------------------------------------------------------------+
//| 9. Simple request throttle: one attempt per key every N seconds  |
//+------------------------------------------------------------------+
bool TH_Throttle(datetime &last_attempt,const int seconds)
  {
   datetime now=TimeCurrent();
   if(now-last_attempt<seconds)
      return(false);
   last_attempt=now;
   return(true);
  }

//+------------------------------------------------------------------+
//| 10. Account is hedging?                                          |
//+------------------------------------------------------------------+
bool TH_IsHedging()
  {
   return((ENUM_ACCOUNT_MARGIN_MODE)AccountInfoInteger(ACCOUNT_MARGIN_MODE)==ACCOUNT_MARGIN_MODE_RETAIL_HEDGING);
  }

//+------------------------------------------------------------------+
//| All-in-one gate for a new market order                           |
//| Returns the volume to send (0 = do not send) and the reason.     |
//+------------------------------------------------------------------+
double TH_PrepareOrder(const string symbol,const ENUM_ORDER_TYPE type,const double lots_wanted,
                       double &sl,double &tp,string &why)
  {
   if(!TH_TradeAllowed(symbol,why))
      return(0.0);
   bool is_buy=(type==ORDER_TYPE_BUY);
   sl=(sl>0.0)?TH_NormalizePrice(symbol,sl):0.0;
   tp=(tp>0.0)?TH_NormalizePrice(symbol,tp):0.0;
   if(!TH_StopsLevelOK(symbol,is_buy,sl,tp))
     { why="SL/TP inside stops level"; return(0.0); }
   double lots=TH_NormalizeVolume(symbol,lots_wanted);
   if(lots<=0.0)
     { why="volume below minimum"; return(0.0); }
   lots=TH_FitToMargin(symbol,type,lots);
   if(lots<=0.0)
     { why="not enough free margin"; return(0.0); }
   if(!TH_VolumeLimitOK(symbol,lots))
     { why="SYMBOL_VOLUME_LIMIT reached"; return(0.0); }
   why="OK";
   return(lots);
  }
//+------------------------------------------------------------------+


input long            InpMagic       = -1;        // Magic filter (-1 = all, 0 = manual only)
input bool            InpThisSymbol  = true;      // Only the chart symbol
input double          InpBE_R        = 1.0;       // Break-even trigger, R
input double          InpLock_R      = 0.1;       // Locked profit at break-even, R
input double          InpTrailStartR = 2.0;       // Start trailing at, R (0 = no trail)
input double          InpTrail_R     = 2.0;       // Trail distance, R
input bool            InpOnBarClose  = true;      // Evaluate on closed bars only
input ENUM_TIMEFRAMES InpBarTF       = PERIOD_H1; // Bar timeframe for evaluation
input bool            InpVerbose     = false;     // Journal messages

CTrade   trade;
datetime g_last_bar=0;
datetime g_last_try=0;

//+------------------------------------------------------------------+
int OnInit()
  {
   if(InpBE_R<=0.0 || InpLock_R<0.0 || InpLock_R>=InpBE_R || InpTrail_R<=0.0 || InpTrailStartR<0.0)
      return(INIT_PARAMETERS_INCORRECT);
   trade.SetExpertMagicNumber(0);
   trade.LogLevel(LOG_LEVEL_ERRORS);
   EventSetTimer(30);
   return(INIT_SUCCEEDED);
  }

void OnDeinit(const int reason)
  {
   EventKillTimer();
   Comment("");
  }

//+------------------------------------------------------------------+
string GVName(const ulong ticket) { return("BETM_R_"+(string)ticket); }

//--- initial risk in price units; stored once per ticket
double InitialRisk(const ulong ticket,const double open,const double sl)
  {
   string n=GVName(ticket);
   if(GlobalVariableCheck(n))
      return(GlobalVariableGet(n));
   if(sl<=0.0)
      return(0.0);
   double r=MathAbs(open-sl);
   GlobalVariableSet(n,r);
   return(r);
  }

//--- delete globals of positions that no longer exist
void CleanGlobals()
  {
   for(int i=GlobalVariablesTotal()-1;i>=0;i--)
     {
      string n=GlobalVariableName(i);
      if(StringFind(n,"BETM_R_")!=0)
         continue;
      ulong t=(ulong)StringToInteger(StringSubstr(n,7));
      if(!PositionSelectByTicket(t))
         GlobalVariableDel(n);
     }
  }

//+------------------------------------------------------------------+
void Manage()
  {
   for(int i=PositionsTotal()-1;i>=0;i--)
     {
      ulong tk=PositionGetTicket(i);
      if(tk==0)
         continue;
      string sym=PositionGetString(POSITION_SYMBOL);
      if(InpThisSymbol && sym!=_Symbol)
         continue;
      long mg=PositionGetInteger(POSITION_MAGIC);
      if(InpMagic>=0 && mg!=InpMagic)
         continue;

      bool   is_buy=(PositionGetInteger(POSITION_TYPE)==POSITION_TYPE_BUY);
      double open =PositionGetDouble(POSITION_PRICE_OPEN);
      double sl   =PositionGetDouble(POSITION_SL);
      double tp   =PositionGetDouble(POSITION_TP);
      double R    =InitialRisk(tk,open,sl);
      if(R<=0.0)
         continue;

      //--- reference price: last closed bar close, or live bid/ask
      double px;
      if(InpOnBarClose)
         px=iClose(sym,InpBarTF,1);
      else
         px=is_buy?SymbolInfoDouble(sym,SYMBOL_BID):SymbolInfoDouble(sym,SYMBOL_ASK);
      if(px<=0.0)
         continue;
      double gainR=(is_buy?px-open:open-px)/R;

      double new_sl=sl;
      if(gainR>=InpBE_R)
        {
         double be=is_buy?open+InpLock_R*R:open-InpLock_R*R;
         if(sl<=0.0 || (is_buy && be>new_sl) || (!is_buy && be<new_sl))
            new_sl=be;
        }
      if(InpTrailStartR>0.0 && gainR>=InpTrailStartR)
        {
         double tr=is_buy?px-InpTrail_R*R:px+InpTrail_R*R;
         if((is_buy && tr>new_sl) || (!is_buy && tr<new_sl))
            new_sl=tr;
        }
      new_sl=TH_NormalizePrice(sym,new_sl);
      if(!TH_PriceChanged(sym,new_sl,sl))
         continue;
      if(!TH_StopsLevelOK(sym,is_buy,new_sl,0.0) || !TH_FreezeLevelOK(sym,is_buy,sl,tp))
         continue;
      if(trade.PositionModify(tk,new_sl,tp))
        {
         if(InpVerbose)
            PrintFormat("BETM #%I64u %s SL %s -> %s (%.2f R)",tk,sym,DoubleToString(sl,_Digits),
                        DoubleToString(new_sl,_Digits),gainR);
        }
     }
  }

//+------------------------------------------------------------------+
void OnTick()
  {
   if(InpOnBarClose)
     {
      datetime b=iTime(_Symbol,InpBarTF,0);
      if(b==g_last_bar)
         return;
      g_last_bar=b;
     }
   else if(!TH_Throttle(g_last_try,1))
      return;
   Manage();
  }

void OnTimer()
  {
   CleanGlobals();
   Comment(StringFormat("BreakevenTrailManager  BE %.1fR (+%.1fR)  trail %.1fR from %.1fR  %s",
                        InpBE_R,InpLock_R,InpTrail_R,InpTrailStartR,InpOnBarClose?"bar close":"live"));
  }
//+------------------------------------------------------------------+
