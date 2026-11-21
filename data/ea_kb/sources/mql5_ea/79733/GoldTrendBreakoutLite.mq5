//+------------------------------------------------------------------+
//|                                      GoldTrendBreakoutLite.mq5   |
//|   Educational XAUUSD trend-breakout EA (Lite)                    |
//|   H1 Donchian breakout in the direction of the D1 EMA slope,     |
//|   ATR stop, break-even at +1R. Fixed lot. No grid/martingale.    |
//|                          https://www.mql5.com/en/users/sgupta30  |
//+------------------------------------------------------------------+
#property copyright   "Shipra Gupta (SGupta30)"
#property link        "https://www.mql5.com/en/users/sgupta30"
#property version     "1.00"
#property description "Gold Trend Breakout Lite: the multi-day trend-persistence edge of XAUUSD in ~250 lines."
#property description "Entry: H1 close beyond the N-bar Donchian channel, only with the D1 EMA slope."
#property description "Exit: ATR stop, moved to break-even +0.1R once price reaches +1R."
#property description "Fixed lot. Hard stop on every trade. Use as a learning base for your own EA."

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


input group "Signal"
input int             InpDonchian   = 120;        // Donchian length (H1 bars)
input int             InpTrendEMA   = 100;        // D1 EMA period
input int             InpSlopeBars  = 3;          // D1 EMA slope lookback
input bool            InpAllowShort = true;       // Allow short trades
input group "Risk"
input double          InpLots       = 0.01;       // Fixed lot
input double          InpATRMult    = 3.0;        // Stop = ATR(14,H1) x
input double          InpBE_R       = 1.0;        // Break-even trigger, R
input double          InpLock_R     = 0.1;        // Locked profit, R
input double          InpMaxSpreadPts = 0;        // Max spread, points (0 = off)
input group "General"
input long            InpMagic      = 30120001;   // Magic number
input string          InpComment    = "GTB Lite"; // Order comment

CTrade   trade;
int      hEMA=INVALID_HANDLE,hATR=INVALID_HANDLE;
datetime g_last_bar=0;
datetime g_last_fail=0;
const ENUM_TIMEFRAMES TF=PERIOD_H1;

//+------------------------------------------------------------------+
int OnInit()
  {
   if(InpDonchian<5 || InpDonchian>1000 || InpTrendEMA<2 || InpSlopeBars<1 ||
      InpLots<=0.0 || InpATRMult<=0.0 || InpBE_R<=0.0 || InpLock_R<0.0 || InpLock_R>=InpBE_R)
      return(INIT_PARAMETERS_INCORRECT);
   hEMA=iMA(_Symbol,PERIOD_D1,InpTrendEMA,0,MODE_EMA,PRICE_CLOSE);
   hATR=iATR(_Symbol,TF,14);
   if(hEMA==INVALID_HANDLE || hATR==INVALID_HANDLE)
      return(INIT_FAILED);
   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(50);
   trade.SetTypeFillingBySymbol(_Symbol);
   trade.LogLevel(LOG_LEVEL_ERRORS);
   if(StringFind(_Symbol,"XAU")<0 && StringFind(_Symbol,"GOLD")<0)
      Print("GoldTrendBreakoutLite: designed for XAUUSD, running on ",_Symbol);
   return(INIT_SUCCEEDED);
  }

void OnDeinit(const int reason)
  {
   if(hEMA!=INVALID_HANDLE) IndicatorRelease(hEMA);
   if(hATR!=INVALID_HANDLE) IndicatorRelease(hATR);
  }

//+------------------------------------------------------------------+
//| +1 / -1 / 0 from the last COMPLETED D1 bars                      |
//+------------------------------------------------------------------+
int TrendD1()
  {
   double e[];
   if(CopyBuffer(hEMA,0,1,InpSlopeBars+1,e)!=InpSlopeBars+1)
      return(0);
   if(e[InpSlopeBars]>e[0]) return(1);
   if(e[InpSlopeBars]<e[0]) return(-1);
   return(0);
  }

//+------------------------------------------------------------------+
//| Find our position (one per magic/symbol)                         |
//+------------------------------------------------------------------+
bool MyPosition(ulong &ticket)
  {
   for(int i=PositionsTotal()-1;i>=0;i--)
     {
      ulong t=PositionGetTicket(i);
      if(t>0 && PositionGetString(POSITION_SYMBOL)==_Symbol && PositionGetInteger(POSITION_MAGIC)==InpMagic)
        { ticket=t; return(true); }
     }
   return(false);
  }

//+------------------------------------------------------------------+
//| Break-even on bar close. R = |open - original SL|, stored once   |
//| per ticket in a terminal global variable.                        |
//+------------------------------------------------------------------+
void ManageBE(const ulong tk)
  {
   if(!PositionSelectByTicket(tk))
      return;
   string gv="GTBL_R_"+(string)tk;
   double open=PositionGetDouble(POSITION_PRICE_OPEN);
   double sl  =PositionGetDouble(POSITION_SL);
   double tp  =PositionGetDouble(POSITION_TP);
   if(!GlobalVariableCheck(gv))
     {
      if(sl<=0.0) return;
      GlobalVariableSet(gv,MathAbs(open-sl));
     }
   double R=GlobalVariableGet(gv);
   if(R<=0.0)
      return;
   bool   is_buy=(PositionGetInteger(POSITION_TYPE)==POSITION_TYPE_BUY);
   double c1=iClose(_Symbol,TF,1);
   double gain=(is_buy?c1-open:open-c1)/R;
   if(gain<InpBE_R)
      return;
   double be=TH_NormalizePrice(_Symbol,is_buy?open+InpLock_R*R:open-InpLock_R*R);
   bool better=is_buy?(be>sl):(sl<=0.0 || be<sl);
   if(!better || !TH_PriceChanged(_Symbol,be,sl))
      return;
   if(TH_StopsLevelOK(_Symbol,is_buy,be,tp) && TH_FreezeLevelOK(_Symbol,is_buy,sl,tp))
      trade.PositionModify(tk,be,tp);
  }

//+------------------------------------------------------------------+
void TryEntry()
  {
   int need=InpDonchian+2;
   double hi[],lo[],cl[];
   if(CopyHigh(_Symbol,TF,2,InpDonchian,hi)!=InpDonchian) return;   // bars 2..N+1
   if(CopyLow(_Symbol,TF,2,InpDonchian,lo)!=InpDonchian)  return;
   if(CopyClose(_Symbol,TF,1,1,cl)!=1)                    return;   // signal bar = bar 1
   if(Bars(_Symbol,TF)<need) return;
   double hh=hi[ArrayMaximum(hi)];
   double ll=lo[ArrayMinimum(lo)];
   int tr=TrendD1();
   int dir=0;
   if(cl[0]>hh && tr>0) dir=1;
   else if(InpAllowShort && cl[0]<ll && tr<0) dir=-1;
   if(dir==0)
      return;

   if(InpMaxSpreadPts>0 && SymbolInfoInteger(_Symbol,SYMBOL_SPREAD)>InpMaxSpreadPts)
      return;
   double atr[];
   if(CopyBuffer(hATR,0,1,1,atr)!=1 || atr[0]<=0.0)
      return;
   if(TimeCurrent()-g_last_fail<60)
      return;

   ENUM_ORDER_TYPE type=(dir>0)?ORDER_TYPE_BUY:ORDER_TYPE_SELL;
   double px=(dir>0)?SymbolInfoDouble(_Symbol,SYMBOL_ASK):SymbolInfoDouble(_Symbol,SYMBOL_BID);
   double sl=px-dir*InpATRMult*atr[0];
   double tp=0.0;
   string why;
   double lots=TH_PrepareOrder(_Symbol,type,InpLots,sl,tp,why);
   if(lots<=0.0)
     {
      Print("GTB Lite: entry skipped, ",why);
      return;
     }
   bool ok=(dir>0)?trade.Buy(lots,_Symbol,0.0,sl,tp,InpComment):trade.Sell(lots,_Symbol,0.0,sl,tp,InpComment);
   if(!ok || (trade.ResultRetcode()!=TRADE_RETCODE_DONE && trade.ResultRetcode()!=TRADE_RETCODE_PLACED))
     {
      g_last_fail=TimeCurrent();
      PrintFormat("GTB Lite: order failed, retcode %u",trade.ResultRetcode());
     }
  }

//+------------------------------------------------------------------+
void OnTick()
  {
   datetime b=iTime(_Symbol,TF,0);
   if(b==0 || b==g_last_bar)
      return;
   g_last_bar=b;
   ulong tk;
   if(MyPosition(tk))
      ManageBE(tk);
   else
      TryEntry();
  }

//+------------------------------------------------------------------+
double OnTester()
  {
   double dd=TesterStatistics(STAT_BALANCE_DDREL_PERCENT);
   double np=TesterStatistics(STAT_PROFIT);
   return(dd>0.0?np/dd:np);
  }
//+------------------------------------------------------------------+
