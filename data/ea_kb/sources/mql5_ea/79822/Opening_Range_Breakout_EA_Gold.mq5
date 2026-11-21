//+------------------------------------------------------------------+
//| Opening Range Breakout EA Gold                   XPro by Xander  |
//| Version 1.0  |  2026-11-20  |  MetaTrader 5                      |
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
// v1.0 - 2026-11-20 - Initial release
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
   XP_STOP_OTHER_SIDE = 0, // Other side of the range
   XP_STOP_MIDDLE     = 1  // Middle of the range
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
input string sep0              = "★ Opening Range Breakout EA Gold"; // ══ XPro by Xander ══
input string sep1              = "══════ STRATEGY ══════";           // ─────────────────────
input string InpSessionStart   = "10:00"; // Range start (HH:MM, server time)
input int    InpRangeMinutes   = 30;     // Range length (minutes)
input int    InpTradeMinutes   = 180;    // Minutes after the range in which a breakout is taken
input int    InpBufferPoints   = 0;      // Breakout buffer beyond the range (points)
input ENUM_XP_DIRECTION InpDirection = XP_DIR_BOTH; // Allowed direction
input int    InpMaxTradesDay   = 1;      // Maximum trades per day

input string sep2              = "══════ LOT SETTINGS ══════";       // ─────────────────────
input ENUM_XP_LOT_MODE InpLotMode = XP_LOT_BALANCE; // Lot mode
input double InpFixedLot       = 0.01;   // Fixed lot (when lot mode is fixed)
input double InpRiskPercent    = 1.0;    // Risk percent per trade (by stop distance)

input string sep3              = "══════ CLOSE / EXIT ══════";       // ─────────────────────
input ENUM_XP_STOP_MODE InpStopMode = XP_STOP_OTHER_SIDE; // Stop loss placement
input double InpTargetR        = 1.5;    // Take profit as a multiple of the stop distance (0 = none)
input bool   InpCloseEndOfDay  = true;   // Close open positions at the end time
input string InpCloseTime      = "22:00"; // End time (HH:MM, server time)

input string sep4              = "══════ RISK PROTECTION ══════";    // ─────────────────────
input int    InpMinRangePoints = 0;      // Minimum range height (points, 0 = no limit)
input int    InpMaxRangePoints = 0;      // Maximum range height (points, 0 = no limit)
input int    InpMaxSpread      = 0;      // Maximum spread to open (points, 0 = no limit)

input string sep5              = "══════ FILTERS ══════";            // ─────────────────────
input bool   InpTradeMonday    = true;   // Trade on Monday
input bool   InpTradeFriday    = true;   // Trade on Friday

input string sep6              = "══════ EXPERT SETTINGS ══════";    // ─────────────────────
input long   InpMagic          = 2611201; // Magic number
input string InpComment        = "ORB EA"; // Order comment
input int    InpSlippage       = 30;     // Max slippage (points)
input bool   InpShowInfo       = true;   // Show status and range box on chart

//+------------------------------------------------------------------+
//| Globals                                                          |
//+------------------------------------------------------------------+
#define XP_NAME   "Opening Range Breakout EA Gold"
#define XP_PREFIX "XPORBEA_"
#define XP_DAY    86400

CTrade   XP_trade;
int      XP_startMin   = 0;     // range start, minutes from midnight
int      XP_closeMin   = 0;     // end time, minutes from midnight
datetime XP_lastBar    = 0;
datetime XP_dayStart   = 0;     // midnight of the day being tracked
double   XP_hi         = 0.0;   // range high
double   XP_lo         = 0.0;   // range low
bool     XP_rangeReady = false; // range window finished with data
bool     XP_rangeBad   = false; // range outside the min or max height
int      XP_tradesDay  = 0;     // trades opened today
bool     XP_tfOk       = true;  // timeframe fits inside the range

//+------------------------------------------------------------------+
//| Reads HH:MM into minutes from midnight                           |
//+------------------------------------------------------------------+
bool XP_ParseTime(const string text,int &minutes)
  {
   string parts[];
   if(StringSplit(text,StringGetCharacter(":",0),parts)!=2) return(false);
   int h=(int)StringToInteger(parts[0]);
   int m=(int)StringToInteger(parts[1]);
   if(h<0 || h>23 || m<0 || m>59) return(false);
   minutes=h*60+m;
   return(true);
  }

//+------------------------------------------------------------------+
//| Init                                                             |
//+------------------------------------------------------------------+
int OnInit()
  {
   if(!XP_ParseTime(InpSessionStart,XP_startMin) || !XP_ParseTime(InpCloseTime,XP_closeMin))
     {
      Print("[", XP_NAME, "] The start and end times must be written as HH:MM.");
      return(INIT_PARAMETERS_INCORRECT);
     }
   if(InpRangeMinutes<1 || InpTradeMinutes<1 || XP_startMin+InpRangeMinutes>=1440)
     {
      Print("[", XP_NAME, "] The range and trade window must be at least 1 minute and the range must end before midnight.");
      return(INIT_PARAMETERS_INCORRECT);
     }
   XP_tfOk=(PeriodSeconds()<=InpRangeMinutes*60);
   if(!XP_tfOk)
      Print("[", XP_NAME, "] The chart timeframe is higher than the range length. The EA waits and does not trade. Use M1 to M30 for a 30 minute range.");
   if(InpBufferPoints<0 || InpTargetR<0.0 || InpMinRangePoints<0 || InpMaxRangePoints<0 || InpMaxSpread<0 || InpMaxTradesDay<1)
     {
      Print("[", XP_NAME, "] Buffer, target, range limits and spread cannot be negative, and at least 1 trade per day.");
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

   XP_trade.SetExpertMagicNumber((ulong)InpMagic);
   XP_trade.SetDeviationInPoints((ulong)InpSlippage);
   XP_trade.SetTypeFillingBySymbol(_Symbol);
   XP_trade.SetAsyncMode(false);

   XP_ResetDay(0);
   Print("[", XP_NAME, "] Started on ", _Symbol, " ", EnumToString(_Period), ". Range ", InpSessionStart,
         " for ", InpRangeMinutes, " min, magic ", InpMagic);
   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
//| Deinit                                                           |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   ObjectsDeleteAll(0,XP_PREFIX);
   Comment("");
  }

//+------------------------------------------------------------------+
//| New day: forget the old range                                    |
//+------------------------------------------------------------------+
void XP_ResetDay(const datetime midnight)
  {
   XP_dayStart=midnight;
   XP_hi=0.0;
   XP_lo=0.0;
   XP_rangeReady=false;
   XP_rangeBad=false;
   XP_tradesDay=0;
  }

//+------------------------------------------------------------------+
//| Main cycle: decisions on closed bars only                        |
//+------------------------------------------------------------------+
void OnTick()
  {
   datetime now=TimeCurrent();
   datetime midnight=now-(now%XP_DAY);
   if(midnight!=XP_dayStart) XP_ResetDay(midnight);

   //--- end of day close
   int nowMin=(int)((now-midnight)/60);
   if(InpCloseEndOfDay && nowMin>=XP_closeMin && XP_CountMine()>0)
      XP_CloseAll("end time");

   datetime bar=iTime(_Symbol,_Period,0);
   if(XP_tfOk && bar!=0 && bar!=XP_lastBar)
     {
      XP_lastBar=bar;
      XP_OnNewBar(midnight);
     }
   if(InpShowInfo) XP_ShowInfo();
  }

//+------------------------------------------------------------------+
//| Builds the range and checks the last closed candle                |
//+------------------------------------------------------------------+
void XP_OnNewBar(const datetime midnight)
  {
   datetime rStart=midnight+XP_startMin*60;
   datetime rEnd=rStart+InpRangeMinutes*60;
   datetime tEnd=rEnd+InpTradeMinutes*60;

   //--- the range is read once, after its window has closed
   if(!XP_rangeReady && TimeCurrent()>=rEnd)
     {
      MqlRates r[];
      int got=CopyRates(_Symbol,_Period,rStart,rEnd-1,r);
      if(got>0)
        {
         XP_hi=r[0].high;
         XP_lo=r[0].low;
         for(int k=1;k<got;k++)
           {
            if(r[k].high>XP_hi) XP_hi=r[k].high;
            if(r[k].low<XP_lo)  XP_lo=r[k].low;
           }
         XP_rangeReady=true;
         double pts=(XP_hi-XP_lo)/_Point;
         XP_rangeBad=((InpMinRangePoints>0 && pts<InpMinRangePoints) ||
                      (InpMaxRangePoints>0 && pts>InpMaxRangePoints));
         if(XP_rangeBad)
            Print("[", XP_NAME, "] range of ", DoubleToString(pts,0), " points is outside the limits. No trade today.");
         if(InpShowInfo) XP_DrawRange(rStart,tEnd);
        }
     }

   if(!XP_rangeReady || XP_rangeBad) return;
   if(XP_tradesDay>=InpMaxTradesDay) return;
   if(XP_CountMine()>0) return;
   if(!XP_DayAllowed()) return;

   //--- last closed candle must close inside the trade window
   MqlRates c[];
   if(CopyRates(_Symbol,_Period,1,1,c)!=1) return;
   datetime closeTime=c[0].time+PeriodSeconds();
   if(c[0].time<rEnd || closeTime>tEnd) return;

   double buf=InpBufferPoints*_Point;
   int signal=0;
   if(c[0].close>XP_hi+buf) signal=1;
   if(c[0].close<XP_lo-buf) signal=-1;
   if(signal==0) return;
   if(InpDirection==XP_DIR_BUY  && signal<0) return;
   if(InpDirection==XP_DIR_SELL && signal>0) return;

   XP_Open(signal);
  }

//+------------------------------------------------------------------+
//| Opens one market position after a breakout close                 |
//+------------------------------------------------------------------+
void XP_Open(const int signal)
  {
   double point=_Point;
   int    digits=_Digits;
   double ask=SymbolInfoDouble(_Symbol,SYMBOL_ASK);
   double bid=SymbolInfoDouble(_Symbol,SYMBOL_BID);
   if(ask<=0.0 || bid<=0.0) return;

   double spread=ask-bid;
   if(InpMaxSpread>0 && spread>InpMaxSpread*point)
     {
      Print("[", XP_NAME, "] spread of ", DoubleToString(spread/point,0), " points is above the limit. Breakout skipped.");
      return;
     }

   double price=(signal>0 ? ask : bid);
   double stopPrice;
   if(InpStopMode==XP_STOP_OTHER_SIDE) stopPrice=(signal>0 ? XP_lo : XP_hi);
   else                                stopPrice=(XP_hi+XP_lo)/2.0;
   double dist=(signal>0 ? price-stopPrice : stopPrice-price);

   //--- never closer than the broker minimum distance plus the spread
   double minDist=(double)SymbolInfoInteger(_Symbol,SYMBOL_TRADE_STOPS_LEVEL)*point+spread;
   if(dist<minDist) dist=minDist;

   double sl=NormalizeDouble((signal>0 ? price-dist : price+dist),digits);
   double tp=0.0;
   if(InpTargetR>0.0)
     {
      double tpDist=MathMax(dist*InpTargetR,minDist);
      tp=NormalizeDouble((signal>0 ? price+tpDist : price-tpDist),digits);
     }

   double lot=XP_Lot(dist);
   if(lot<=0.0) return;
   ENUM_ORDER_TYPE type=(signal>0 ? ORDER_TYPE_BUY : ORDER_TYPE_SELL);
   if(!XP_MarginOk(type,lot,price)) return;

   bool ok=(signal>0 ? XP_trade.Buy(lot,_Symbol,0.0,sl,tp,InpComment)
                     : XP_trade.Sell(lot,_Symbol,0.0,sl,tp,InpComment));
   if(ok)
     {
      XP_tradesDay++;
      Print("[", XP_NAME, "] ", (signal>0 ? "buy" : "sell"), " breakout, ", DoubleToString(lot,2),
            " lots, stop ", DoubleToString(sl,digits), ", target ", DoubleToString(tp,digits));
     }
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

void XP_CloseAll(const string why)
  {
   for(int i=PositionsTotal()-1;i>=0;i--)
     {
      ulong ticket=PositionGetTicket(i);
      if(ticket==0 || !PositionSelectByTicket(ticket)) continue;
      if(!XP_Mine()) continue;
      if(XP_trade.PositionClose(ticket,(ulong)InpSlippage))
         Print("[", XP_NAME, "] closed #", ticket, " at the ", why);
     }
  }

bool XP_DayAllowed()
  {
   MqlDateTime t;
   TimeToStruct(TimeCurrent(),t);
   if(t.day_of_week==1 && !InpTradeMonday) return(false);
   if(t.day_of_week==5 && !InpTradeFriday) return(false);
   return(true);
  }

//+------------------------------------------------------------------+
//| Range box and levels with standard objects (no canvas)           |
//+------------------------------------------------------------------+
void XP_DrawRange(const datetime rStart,const datetime tEnd)
  {
   string box=XP_PREFIX+"box_"+TimeToString(rStart,TIME_DATE);
   ObjectDelete(0,box);
   if(ObjectCreate(0,box,OBJ_RECTANGLE,0,rStart,XP_hi,tEnd,XP_lo))
     {
      ObjectSetInteger(0,box,OBJPROP_COLOR,C'35,55,90');
      ObjectSetInteger(0,box,OBJPROP_FILL,true);
      ObjectSetInteger(0,box,OBJPROP_BACK,true);
      ObjectSetInteger(0,box,OBJPROP_SELECTABLE,false);
      ObjectSetInteger(0,box,OBJPROP_HIDDEN,true);
     }
  }

//+------------------------------------------------------------------+
//| Plain text status on the chart                                   |
//+------------------------------------------------------------------+
void XP_ShowInfo()
  {
   string range="waiting for "+InpSessionStart;
   if(XP_rangeReady)
      range=DoubleToString(XP_lo,_Digits)+" - "+DoubleToString(XP_hi,_Digits)+" ("+
            DoubleToString((XP_hi-XP_lo)/_Point,0)+" pts)"+(XP_rangeBad ? " skipped" : "");
   string lots=(InpLotMode==XP_LOT_FIXED) ? DoubleToString(InpFixedLot,2)+" fixed"
                                          : DoubleToString(InpRiskPercent,2)+"% risk";
   string txt=XP_NAME+"  |  XPro by Xander\n";
   txt+=_Symbol+" "+EnumToString(_Period)+"   Range "+InpSessionStart+" + "+IntegerToString(InpRangeMinutes)+
        " min: "+range+"\n";
   txt+="Trades today: "+IntegerToString(XP_tradesDay)+" of "+IntegerToString(InpMaxTradesDay)+
        "   Open: "+IntegerToString(XP_CountMine())+"   Lot: "+lots+"   Target: "+
        (InpTargetR>0.0 ? DoubleToString(InpTargetR,1)+" x stop" : "off")+"\n";
   txt+="End time close: "+(InpCloseEndOfDay ? InpCloseTime : "off");
   Comment(txt);
  }
//+------------------------------------------------------------------+
