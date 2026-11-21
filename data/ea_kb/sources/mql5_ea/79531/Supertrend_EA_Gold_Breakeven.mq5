//+------------------------------------------------------------------+
//| Supertrend EA Gold Breakeven                     XPro by Xander  |
//| Version 1.0  |  2026-11-14  |  MetaTrader 5                      |
//| Developer: Cristhian Gaibor (Xander)                             |
//| Profile:   https://www.mql5.com/en/users/09151993a               |
//+------------------------------------------------------------------+
// XPro by Xander. Tested code, compiles clean and runs on demo and
// live accounts as it is. Built from more than 10 years of trading
// and coding experience, so you can use it today or take it as the
// base for your own EA or indicator. You will find more tools like
// this one on my profile. If something is not clear, ask in the
// comments and I will answer. Results depend on your settings, your
// broker and your risk management, so test your configuration first.
// Provided as is, use at your own risk.
// Updates and new tools first on my MQL5 channel:
// https://www.mql5.com/en/channels/xander
//+------------------------------------------------------------------+
// CHANGELOG
// v1.0 - 2026-11-14 - Initial release
//+------------------------------------------------------------------+
#property copyright   "Copyright 2026, Cristhian Gaibor (Xander)"
#property link        "https://www.mql5.com/en/users/09151993a"
#property version     "1.00"
#property description "XPro by Xander. Tested code, compiles clean, ready for demo and live accounts."
#property description "Use it as it is or as the base for your own EA or indicator. 10+ years of experience behind it."
#property description "More tools on my profile. Updates first on my MQL5 channel: mql5.com/en/channels/xander"

#include <Trade\Trade.mqh>

//--- enums
enum ENUM_XP_LOT_MODE
  {
   XP_LOT_FIXED   = 0,  // Fixed lot
   XP_LOT_BALANCE = 1,  // Risk percent of balance
   XP_LOT_EQUITY  = 2   // Risk percent of equity
  };

enum ENUM_XP_STOP_MODE
  {
   XP_STOP_LINE  = 0,   // At the Supertrend line
   XP_STOP_FIXED = 1    // Fixed distance in points
  };

enum ENUM_XP_DIRECTION
  {
   XP_DIR_BOTH = 0,     // Buy and sell
   XP_DIR_BUY  = 1,     // Buy only
   XP_DIR_SELL = 2      // Sell only
  };

//+------------------------------------------------------------------+
//| Inputs                                                           |
//+------------------------------------------------------------------+
input string sep0              = "★ Supertrend EA Gold Breakeven";   // ══ XPro by Xander ══
input string sep1              = "══════ STRATEGY ══════";           // ─────────────────────
input int    InpAtrPeriod      = 10;     // ATR period (bars)
input double InpMultiplier     = 3.0;    // ATR multiplier
input int    InpCalcBars       = 300;    // Closed bars used to build the Supertrend
input ENUM_XP_DIRECTION InpDirection = XP_DIR_BOTH; // Allowed direction
input bool   InpCloseOnFlip    = true;   // Close the position on the opposite flip

input string sep2              = "══════ LOT SETTINGS ══════";       // ─────────────────────
input ENUM_XP_LOT_MODE InpLotMode = XP_LOT_BALANCE; // Lot mode
input double InpFixedLot       = 0.01;   // Fixed lot (when lot mode is fixed)
input double InpRiskPercent    = 1.0;    // Risk percent per trade (by stop distance)

input string sep3              = "══════ CLOSE / EXIT ══════";       // ─────────────────────
input ENUM_XP_STOP_MODE InpStopMode = XP_STOP_LINE; // Stop loss mode
input int    InpStopBuffer     = 50;     // Extra distance beyond the Supertrend line (points)
input int    InpStopLoss       = 500;    // Fixed stop loss (points, fixed mode only)
input double InpTargetR        = 2.0;    // Take profit as a multiple of the stop distance (0 = none)

input string sep4              = "══════ RISK PROTECTION ══════";    // ─────────────────────
input bool   InpUseBreakeven   = true;   // Move the stop to breakeven
input double InpBreakevenR     = 1.0;    // Breakeven starts at this multiple of the stop distance
input int    InpBreakevenOffset= 20;     // Breakeven offset beyond the entry price (points)
input int    InpMaxSpread      = 0;      // Maximum spread to open (points, 0 = no limit)

input string sep5              = "══════ FILTERS ══════";            // ─────────────────────
input bool   InpUseTimeFilter  = false;  // Use the time filter
input int    InpStartHour      = 8;      // Start hour (server time, 0 to 23)
input int    InpEndHour        = 20;     // End hour (server time, 0 to 23)

input string sep6              = "══════ EXPERT SETTINGS ══════";    // ─────────────────────
input long   InpMagic          = 2611143; // Magic number
input string InpComment        = "SupertrendBE"; // Order comment
input int    InpSlippage       = 30;     // Max slippage (points)
input bool   InpShowInfo       = true;   // Show status on chart

//+------------------------------------------------------------------+
//| Globals                                                          |
//+------------------------------------------------------------------+
#define XP_NAME "Supertrend EA Gold Breakeven"

CTrade   XP_trade;
int      XP_atrHandle = INVALID_HANDLE;
datetime XP_lastBar   = 0;
int      XP_trend     = 0;
double   XP_line      = 0.0;

//+------------------------------------------------------------------+
//| Init                                                             |
//+------------------------------------------------------------------+
int OnInit()
  {
   if(InpAtrPeriod<1 || InpMultiplier<=0.0)
     {
      Print("[", XP_NAME, "] The ATR period must be 1 or more and the multiplier above zero.");
      return(INIT_PARAMETERS_INCORRECT);
     }
   if(InpCalcBars<InpAtrPeriod+20)
     {
      Print("[", XP_NAME, "] Closed bars for the Supertrend must be at least the ATR period plus 20.");
      return(INIT_PARAMETERS_INCORRECT);
     }
   if(InpStopMode==XP_STOP_FIXED && InpStopLoss<=0)
     {
      Print("[", XP_NAME, "] The fixed stop loss must be above zero.");
      return(INIT_PARAMETERS_INCORRECT);
     }
   if(InpStopBuffer<0 || InpTargetR<0.0 || InpBreakevenOffset<0 || InpMaxSpread<0)
     {
      Print("[", XP_NAME, "] Stop buffer, target multiple, breakeven offset and maximum spread cannot be negative.");
      return(INIT_PARAMETERS_INCORRECT);
     }
   if(InpUseBreakeven && InpBreakevenR<=0.0)
     {
      Print("[", XP_NAME, "] The breakeven multiple must be above zero.");
      return(INIT_PARAMETERS_INCORRECT);
     }
   if(InpLotMode==XP_LOT_FIXED && InpFixedLot<=0.0)
     {
      Print("[", XP_NAME, "] The fixed lot must be above zero.");
      return(INIT_PARAMETERS_INCORRECT);
     }
   if(InpLotMode!=XP_LOT_FIXED && InpRiskPercent<=0.0)
     {
      Print("[", XP_NAME, "] The risk percent must be above zero.");
      return(INIT_PARAMETERS_INCORRECT);
     }

   XP_atrHandle=iATR(_Symbol,_Period,InpAtrPeriod);
   if(XP_atrHandle==INVALID_HANDLE)
     {
      Print("[", XP_NAME, "] The ATR handle could not be created.");
      return(INIT_FAILED);
     }

   XP_trade.SetExpertMagicNumber((ulong)InpMagic);
   XP_trade.SetDeviationInPoints((ulong)InpSlippage);
   XP_trade.SetTypeFillingBySymbol(_Symbol);
   XP_trade.SetAsyncMode(false);

   XP_lastBar=0;
   XP_trend=0;
   XP_line=0.0;

   Print("[", XP_NAME, "] Started on ", _Symbol, " ", EnumToString(_Period), ". Supertrend ATR ",
         InpAtrPeriod, " x ", DoubleToString(InpMultiplier,1), ", magic ", InpMagic);
   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
//| Deinit                                                           |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   if(XP_atrHandle!=INVALID_HANDLE) IndicatorRelease(XP_atrHandle);
   Comment("");
  }

//+------------------------------------------------------------------+
//| Main cycle: decisions on closed bars only                        |
//+------------------------------------------------------------------+
void OnTick()
  {
   if(InpUseBreakeven) XP_Breakeven();

   datetime t=iTime(_Symbol,_Period,0);
   if(t!=0 && t!=XP_lastBar)
     {
      int    trendNow=0,trendPrev=0;
      double lineNow=0.0;
      if(XP_Supertrend(trendNow,trendPrev,lineNow))
        {
         XP_lastBar=t;
         XP_trend=trendNow;
         XP_line=lineNow;
         if(trendNow!=trendPrev)
           {
            if(InpCloseOnFlip) XP_CloseOpposite(trendNow);
            XP_TryOpen(trendNow,lineNow);
           }
        }
     }
   if(InpShowInfo) XP_ShowInfo();
  }

//+------------------------------------------------------------------+
//| Supertrend on closed bars. trendNow is the last closed bar,      |
//| trendPrev the bar before it. 1 = up, -1 = down                   |
//+------------------------------------------------------------------+
bool XP_Supertrend(int &trendNow,int &trendPrev,double &lineNow)
  {
   int bars=Bars(_Symbol,_Period);
   int n=MathMin(InpCalcBars,bars-1);
   if(n<InpAtrPeriod+5) return(false);
   if(BarsCalculated(XP_atrHandle)<n+1) return(false);

   MqlRates rates[];
   double   atr[];
   ArraySetAsSeries(rates,false);
   ArraySetAsSeries(atr,false);
   if(CopyRates(_Symbol,_Period,1,n,rates)!=n) return(false);
   if(CopyBuffer(XP_atrHandle,0,1,n,atr)!=n) return(false);

   //--- first bar with a valid ATR value
   int first=-1;
   for(int k=0;k<n;k++)
     {
      if(atr[k]>0.0 && atr[k]!=EMPTY_VALUE)
        {
         first=k;
         break;
        }
     }
   if(first<0 || n-first<5) return(false);

   double mid=(rates[first].high+rates[first].low)/2.0;
   double upper=mid+InpMultiplier*atr[first];
   double lower=mid-InpMultiplier*atr[first];
   int    trend=1;
   int    prev=1;

   for(int i=first+1;i<n;i++)
     {
      if(atr[i]<=0.0 || atr[i]==EMPTY_VALUE) return(false);
      mid=(rates[i].high+rates[i].low)/2.0;
      double up=mid+InpMultiplier*atr[i];
      double dn=mid-InpMultiplier*atr[i];
      double lastClose=rates[i-1].close;

      //--- bands only move in favour of the trend
      if(up<upper || lastClose>upper) upper=up;
      if(dn>lower || lastClose<lower) lower=dn;

      //--- trend flips when the close crosses the active band
      prev=trend;
      if(trend>0 && rates[i].close<lower)
         trend=-1;
      else
         if(trend<0 && rates[i].close>upper)
            trend=1;
     }

   trendNow=trend;
   trendPrev=prev;
   lineNow=(trend>0 ? lower : upper);
   return(true);
  }

//+------------------------------------------------------------------+
//| Close the positions that go against the new trend                |
//+------------------------------------------------------------------+
void XP_CloseOpposite(const int signal)
  {
   ENUM_POSITION_TYPE kill=(signal>0 ? POSITION_TYPE_SELL : POSITION_TYPE_BUY);
   for(int i=PositionsTotal()-1;i>=0;i--)
     {
      ulong ticket=PositionGetTicket(i);
      if(ticket==0 || !PositionSelectByTicket(ticket)) continue;
      if(!XP_Mine()) continue;
      if((ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE)!=kill) continue;
      if(XP_trade.PositionClose(ticket,(ulong)InpSlippage))
         Print("[", XP_NAME, "] closed #", ticket, " on the opposite flip");
     }
  }

//+------------------------------------------------------------------+
//| Open one position on the flip if the filters allow it            |
//+------------------------------------------------------------------+
void XP_TryOpen(const int signal,const double line)
  {
   if(InpDirection==XP_DIR_BUY  && signal<0) return;
   if(InpDirection==XP_DIR_SELL && signal>0) return;
   if(!XP_TimeAllowed()) return;
   if(XP_CountMine()>0) return;

   double point=SymbolInfoDouble(_Symbol,SYMBOL_POINT);
   int    digits=(int)SymbolInfoInteger(_Symbol,SYMBOL_DIGITS);
   double ask=SymbolInfoDouble(_Symbol,SYMBOL_ASK);
   double bid=SymbolInfoDouble(_Symbol,SYMBOL_BID);
   if(point<=0.0 || ask<=0.0 || bid<=0.0) return;

   double spread=ask-bid;
   if(InpMaxSpread>0 && spread>InpMaxSpread*point)
     {
      Print("[", XP_NAME, "] spread of ", DoubleToString(spread/point,0), " points is above the limit. Signal skipped.");
      return;
     }

   double price=(signal>0 ? ask : bid);

   //--- stop distance: Supertrend line plus buffer, or fixed points
   double dist;
   if(InpStopMode==XP_STOP_LINE)
      dist=(signal>0 ? price-(line-InpStopBuffer*point) : (line+InpStopBuffer*point)-price);
   else
      dist=InpStopLoss*point;

   //--- never closer than the broker minimum distance plus the spread
   double minDist=(double)SymbolInfoInteger(_Symbol,SYMBOL_TRADE_STOPS_LEVEL)*point+spread;
   if(dist<minDist) dist=minDist;
   if(dist<=0.0)
     {
      Print("[", XP_NAME, "] the stop distance is zero. Signal skipped.");
      return;
     }

   double sl=NormalizeDouble((signal>0 ? price-dist : price+dist),digits);
   double tp=0.0;
   if(InpTargetR>0.0)
     {
      double tpDist=MathMax(dist*InpTargetR,minDist);
      tp=NormalizeDouble((signal>0 ? price+tpDist : price-tpDist),digits);
     }

   double lot=XP_Lot(dist);
   if(lot<=0.0) return;
   if(!XP_MarginOk((signal>0 ? ORDER_TYPE_BUY : ORDER_TYPE_SELL),lot,price)) return;

   bool ok;
   if(signal>0) ok=XP_trade.Buy(lot,_Symbol,0.0,sl,tp,InpComment);
   else         ok=XP_trade.Sell(lot,_Symbol,0.0,sl,tp,InpComment);

   if(ok)
      Print("[", XP_NAME, "] ", (signal>0 ? "buy" : "sell"), " ", DoubleToString(lot,2),
            " lots, stop ", DoubleToString(sl,digits), ", target ", DoubleToString(tp,digits));
   else
      Print("[", XP_NAME, "] open failed. Retcode ", XP_trade.ResultRetcode(), " ",
            XP_trade.ResultRetcodeDescription());
  }

//+------------------------------------------------------------------+
//| Free margin check before every order, warns once per bar         |
//+------------------------------------------------------------------+
bool XP_MarginOk(const ENUM_ORDER_TYPE type,const double lot,const double price)
  {
   static datetime warned=0;
   double margin=0.0;
   if(OrderCalcMargin(type,_Symbol,lot,price,margin) && margin<AccountInfoDouble(ACCOUNT_MARGIN_FREE))
      return(true);
   datetime bar=iTime(_Symbol,_Period,0);
   if(bar!=warned)
     {
      warned=bar;
      Print("[", XP_NAME, "] not enough free margin for ", DoubleToString(lot,2), " lots. Order skipped.");
     }
   return(false);
  }

//+------------------------------------------------------------------+
//| Lot: fixed, or the size that risks the chosen percent            |
//| stopDistance is a price distance                                 |
//+------------------------------------------------------------------+
double XP_Lot(const double stopDistance)
  {
   double lot=InpFixedLot;
   if(InpLotMode!=XP_LOT_FIXED && stopDistance>0.0)
     {
      double money=(InpLotMode==XP_LOT_BALANCE) ? AccountInfoDouble(ACCOUNT_BALANCE)
                                                : AccountInfoDouble(ACCOUNT_EQUITY);
      double risk=money*InpRiskPercent/100.0;
      double tickValue=SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_VALUE);
      double tickSize=SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_SIZE);
      if(tickValue>0.0 && tickSize>0.0)
        {
         double lossPerLot=stopDistance/tickSize*tickValue;
         if(lossPerLot>0.0) lot=risk/lossPerLot;
        }
     }

   double minLot=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MIN);
   double maxLot=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MAX);
   double stepLot=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_STEP);
   if(stepLot<=0.0) stepLot=minLot;
   if(stepLot<=0.0) return(0.0);

   lot=MathFloor(lot/stepLot+0.0000001)*stepLot;
   if(lot<minLot) lot=minLot;
   if(lot>maxLot) lot=maxLot;
   return(NormalizeDouble(lot,8));
  }

//+------------------------------------------------------------------+
//| Breakeven on the EA own positions. The trigger is a multiple of  |
//| the distance between the entry and the stop still at risk        |
//+------------------------------------------------------------------+
void XP_Breakeven()
  {
   double point=SymbolInfoDouble(_Symbol,SYMBOL_POINT);
   int    digits=(int)SymbolInfoInteger(_Symbol,SYMBOL_DIGITS);
   double stops=(double)SymbolInfoInteger(_Symbol,SYMBOL_TRADE_STOPS_LEVEL)*point;

   for(int i=PositionsTotal()-1;i>=0;i--)
     {
      ulong ticket=PositionGetTicket(i);
      if(ticket==0 || !PositionSelectByTicket(ticket)) continue;
      if(!XP_Mine()) continue;

      ENUM_POSITION_TYPE type=(ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
      double open=PositionGetDouble(POSITION_PRICE_OPEN);
      double sl=PositionGetDouble(POSITION_SL);
      double tp=PositionGetDouble(POSITION_TP);
      double bid=SymbolInfoDouble(_Symbol,SYMBOL_BID);
      double ask=SymbolInfoDouble(_Symbol,SYMBOL_ASK);
      if(sl<=0.0) continue;

      //--- distance still at risk. Zero or negative means the stop was already moved
      double risk=(type==POSITION_TYPE_BUY) ? open-sl : sl-open;
      if(risk<=0.0) continue;

      double profit=(type==POSITION_TYPE_BUY) ? bid-open : open-ask;
      if(profit<risk*InpBreakevenR) continue;

      double target=NormalizeDouble((type==POSITION_TYPE_BUY) ? open+InpBreakevenOffset*point
                                                              : open-InpBreakevenOffset*point,digits);
      if(type==POSITION_TYPE_BUY  && bid-target<stops) continue;
      if(type==POSITION_TYPE_SELL && target-ask<stops) continue;

      if(XP_trade.PositionModify(ticket,target,tp))
         Print("[", XP_NAME, "] #", ticket, " stop at breakeven ", DoubleToString(target,digits));
     }
  }

//+------------------------------------------------------------------+
//| Helpers                                                          |
//+------------------------------------------------------------------+
bool XP_Mine()
  {
   return(PositionGetString(POSITION_SYMBOL)==_Symbol &&
          PositionGetInteger(POSITION_MAGIC)==InpMagic);
  }

int XP_CountMine()
  {
   int count=0;
   for(int i=PositionsTotal()-1;i>=0;i--)
     {
      ulong ticket=PositionGetTicket(i);
      if(ticket==0 || !PositionSelectByTicket(ticket)) continue;
      if(XP_Mine()) count++;
     }
   return(count);
  }

bool XP_TimeAllowed()
  {
   if(!InpUseTimeFilter) return(true);
   MqlDateTime t;
   TimeToStruct(TimeCurrent(),t);
   if(InpStartHour==InpEndHour) return(true);
   if(InpStartHour<InpEndHour)  return(t.hour>=InpStartHour && t.hour<InpEndHour);
   return(t.hour>=InpStartHour || t.hour<InpEndHour);
  }

//+------------------------------------------------------------------+
//| Plain text status on the chart                                   |
//+------------------------------------------------------------------+
void XP_ShowInfo()
  {
   int    digits=(int)SymbolInfoInteger(_Symbol,SYMBOL_DIGITS);
   string bias="waiting data";
   if(XP_trend>0) bias="up, line "+DoubleToString(XP_line,digits);
   if(XP_trend<0) bias="down, line "+DoubleToString(XP_line,digits);

   string stop=(InpStopMode==XP_STOP_LINE) ? "Supertrend line + "+IntegerToString(InpStopBuffer)+" pts"
                                           : IntegerToString(InpStopLoss)+" pts";
   string lots=(InpLotMode==XP_LOT_FIXED) ? DoubleToString(InpFixedLot,2)+" fixed"
                                          : DoubleToString(InpRiskPercent,2)+"% risk";

   string txt=XP_NAME+"  |  XPro by Xander\n";
   txt+=_Symbol+" "+EnumToString(_Period)+"   Supertrend "+IntegerToString(InpAtrPeriod)+" x "+
        DoubleToString(InpMultiplier,1)+"   "+bias+"\n";
   txt+="Open positions: "+IntegerToString(XP_CountMine())+"   Lot: "+lots+"   Stop: "+stop+
        "   Target: "+(InpTargetR>0.0 ? DoubleToString(InpTargetR,1)+" x stop" : "off")+"\n";
   txt+="Breakeven: "+(InpUseBreakeven ? "at "+DoubleToString(InpBreakevenR,1)+" x stop, offset "+
        IntegerToString(InpBreakevenOffset)+" pts" : "off")+
        "   Trading window: "+(InpUseTimeFilter ? IntegerToString(InpStartHour)+"h to "+
        IntegerToString(InpEndHour)+"h "+(XP_TimeAllowed() ? "(open)" : "(closed)") : "always open");
   Comment(txt);
  }
//+------------------------------------------------------------------+
