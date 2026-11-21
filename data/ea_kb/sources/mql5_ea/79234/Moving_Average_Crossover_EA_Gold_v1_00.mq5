//+------------------------------------------------------------------+
//| Moving Average Crossover EA Gold                 XPro by Xander  |
//| Version 1.0  |  2026-10-25  |  MetaTrader 5                      |
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
// v1.0 - 2026-10-25 - Initial release
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

//+------------------------------------------------------------------+
//| Inputs                                                           |
//+------------------------------------------------------------------+
input string sep0              = "★ Moving Average Crossover EA Gold"; // ══ XPro by Xander ══
input string sep1              = "══════ STRATEGY ══════";           // ─────────────────────
input int    InpFastPeriod     = 20;     // Fast moving average period
input int    InpSlowPeriod     = 50;     // Slow moving average period
input ENUM_MA_METHOD InpMAMethod = MODE_EMA; // Moving average method
input ENUM_APPLIED_PRICE InpMAPrice = PRICE_CLOSE; // Applied price
input bool   InpReverse        = false;  // Reverse signals
input bool   InpCloseOnCross   = true;   // Close the position on the opposite cross

input string sep2              = "══════ LOT SETTINGS ══════";       // ─────────────────────
input ENUM_XP_LOT_MODE InpLotMode = XP_LOT_FIXED; // Lot mode
input double InpFixedLot       = 0.01;   // Fixed lot (when lot mode is fixed)
input double InpRiskPercent    = 1.0;    // Risk percent per trade (needs a stop loss)

input string sep3              = "══════ CLOSE / EXIT ══════";       // ─────────────────────
input int    InpTakeProfit     = 600;    // Take profit (points, 0 = none)
input bool   InpUseStopLoss    = true;   // Use a stop loss
input int    InpStopLoss       = 300;    // Stop loss (points)

input string sep4              = "══════ RISK PROTECTION ══════";    // ─────────────────────
input int    InpMaxPositions   = 1;      // Maximum positions of this EA at the same time
input bool   InpUseBreakeven   = false;  // Move the stop to breakeven
input int    InpBreakevenStart = 300;    // Breakeven starts at this profit (points)
input int    InpBreakevenOffset= 20;     // Breakeven offset above or below entry (points)

input string sep5              = "══════ FILTERS ══════";            // ─────────────────────
input bool   InpUseTimeFilter  = false;  // Use the time filter
input int    InpStartHour      = 8;      // Start hour (server time, 0 to 23)
input int    InpEndHour        = 20;     // End hour (server time, 0 to 23)

input string sep6              = "══════ EXPERT SETTINGS ══════";    // ─────────────────────
input long   InpMagic          = 2610252; // Magic number
input string InpComment        = "MACrossGold"; // Order comment
input int    InpSlippage       = 30;     // Max slippage (points)
input bool   InpShowInfo       = true;   // Show status on chart

//+------------------------------------------------------------------+
//| Globals                                                          |
//+------------------------------------------------------------------+
#define XP_NAME "Moving Average Crossover EA Gold"

CTrade   XP_trade;
int      XP_fastHandle = INVALID_HANDLE;
int      XP_slowHandle = INVALID_HANDLE;
datetime XP_lastBar    = 0;

//+------------------------------------------------------------------+
//| Init                                                             |
//+------------------------------------------------------------------+
int OnInit()
  {
   if(InpFastPeriod<1 || InpSlowPeriod<1)
     {
      Print("[", XP_NAME, "] Both moving average periods must be above zero.");
      return(INIT_PARAMETERS_INCORRECT);
     }
   if(InpFastPeriod>=InpSlowPeriod)
     {
      Print("[", XP_NAME, "] The fast period must be smaller than the slow period.");
      return(INIT_PARAMETERS_INCORRECT);
     }
   if(InpLotMode!=XP_LOT_FIXED && !InpUseStopLoss)
     {
      Print("[", XP_NAME, "] Risk percent needs a stop loss. Turn the stop loss on or use a fixed lot.");
      return(INIT_PARAMETERS_INCORRECT);
     }

   XP_fastHandle=iMA(_Symbol,_Period,InpFastPeriod,0,InpMAMethod,InpMAPrice);
   XP_slowHandle=iMA(_Symbol,_Period,InpSlowPeriod,0,InpMAMethod,InpMAPrice);
   if(XP_fastHandle==INVALID_HANDLE || XP_slowHandle==INVALID_HANDLE)
     {
      Print("[", XP_NAME, "] Moving average handles could not be created.");
      return(INIT_FAILED);
     }

   XP_trade.SetExpertMagicNumber((ulong)InpMagic);
   XP_trade.SetDeviationInPoints(InpSlippage);
   XP_trade.SetAsyncMode(false);

   Print("[", XP_NAME, "] Started on ", _Symbol, " ", EnumToString(_Period), ". MA ",
         InpFastPeriod, " and ", InpSlowPeriod, ", magic ", InpMagic);
   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
//| Deinit                                                           |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   if(XP_fastHandle!=INVALID_HANDLE) IndicatorRelease(XP_fastHandle);
   if(XP_slowHandle!=INVALID_HANDLE) IndicatorRelease(XP_slowHandle);
   Comment("");
  }

//+------------------------------------------------------------------+
//| Main cycle: decisions on closed bars only                        |
//+------------------------------------------------------------------+
void OnTick()
  {
   if(InpUseBreakeven) XP_Breakeven();

   if(XP_IsNewBar())
     {
      int signal=XP_Signal();
      if(signal!=0)
        {
         if(InpCloseOnCross) XP_CloseOpposite(signal);
         XP_TryOpen(signal);
        }
     }
   if(InpShowInfo) XP_ShowInfo();
  }

//+------------------------------------------------------------------+
//| New bar detector                                                 |
//+------------------------------------------------------------------+
bool XP_IsNewBar()
  {
   datetime t=iTime(_Symbol,_Period,0);
   if(t==0 || t==XP_lastBar) return(false);
   XP_lastBar=t;
   return(true);
  }

//+------------------------------------------------------------------+
//| Cross on the bar that just closed: 1 buy, -1 sell, 0 nothing     |
//+------------------------------------------------------------------+
int XP_Signal()
  {
   double fast[],slow[];
   ArraySetAsSeries(fast,true);
   ArraySetAsSeries(slow,true);
   if(CopyBuffer(XP_fastHandle,0,1,2,fast)!=2) return(0);
   if(CopyBuffer(XP_slowHandle,0,1,2,slow)!=2) return(0);

   int signal=0;
   if(fast[1]<=slow[1] && fast[0]>slow[0]) signal=1;
   if(fast[1]>=slow[1] && fast[0]<slow[0]) signal=-1;
   if(signal!=0 && InpReverse) signal=-signal;
   return(signal);
  }

//+------------------------------------------------------------------+
//| Close the positions that go against the new signal               |
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
      if(XP_trade.PositionClose(ticket,InpSlippage))
         Print("[", XP_NAME, "] closed #", ticket, " on the opposite cross");
     }
  }

//+------------------------------------------------------------------+
//| Open one position if the filters allow it                        |
//+------------------------------------------------------------------+
void XP_TryOpen(const int signal)
  {
   if(!XP_TimeAllowed()) return;
   if(XP_CountMine()>=InpMaxPositions) return;

   double point=SymbolInfoDouble(_Symbol,SYMBOL_POINT);
   int    digits=(int)SymbolInfoInteger(_Symbol,SYMBOL_DIGITS);
   double ask=SymbolInfoDouble(_Symbol,SYMBOL_ASK);
   double bid=SymbolInfoDouble(_Symbol,SYMBOL_BID);
   double price=(signal>0 ? ask : bid);

   double sl=0.0,tp=0.0;
   if(InpUseStopLoss && InpStopLoss>0)
      sl=NormalizeDouble((signal>0 ? price-InpStopLoss*point : price+InpStopLoss*point),digits);
   if(InpTakeProfit>0)
      tp=NormalizeDouble((signal>0 ? price+InpTakeProfit*point : price-InpTakeProfit*point),digits);

   double lot=XP_Lot(point);
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
//+------------------------------------------------------------------+
double XP_Lot(const double point)
  {
   double lot=InpFixedLot;
   if(InpLotMode!=XP_LOT_FIXED && InpStopLoss>0)
     {
      double money=(InpLotMode==XP_LOT_BALANCE) ? AccountInfoDouble(ACCOUNT_BALANCE)
                                                : AccountInfoDouble(ACCOUNT_EQUITY);
      double risk=money*InpRiskPercent/100.0;
      double tickValue=SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_VALUE);
      double tickSize=SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_SIZE);
      if(tickValue>0.0 && tickSize>0.0)
        {
         double lossPerLot=InpStopLoss*point/tickSize*tickValue;
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
//| Breakeven on the EA own positions                                |
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
      double profit=(type==POSITION_TYPE_BUY) ? (bid-open)/point : (open-ask)/point;
      if(profit<InpBreakevenStart) continue;

      double target=NormalizeDouble((type==POSITION_TYPE_BUY) ? open+InpBreakevenOffset*point
                                                              : open-InpBreakevenOffset*point,digits);
      if(type==POSITION_TYPE_BUY  && sl>0.0 && sl>=target) continue;
      if(type==POSITION_TYPE_SELL && sl>0.0 && sl<=target) continue;
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
   double fast[],slow[];
   ArraySetAsSeries(fast,true);
   ArraySetAsSeries(slow,true);
   string bias="waiting data";
   if(CopyBuffer(XP_fastHandle,0,1,1,fast)==1 && CopyBuffer(XP_slowHandle,0,1,1,slow)==1)
      bias=(fast[0]>slow[0] ? "fast above slow" : "fast below slow");

   string txt=XP_NAME+"  |  XPro by Xander\n";
   txt+=_Symbol+" "+EnumToString(_Period)+"   MA "+IntegerToString(InpFastPeriod)+" / "+
        IntegerToString(InpSlowPeriod)+"   "+bias+"\n";
   txt+="Open positions: "+IntegerToString(XP_CountMine())+" of "+IntegerToString(InpMaxPositions)+
        "   Stop: "+(InpUseStopLoss ? IntegerToString(InpStopLoss)+" pts" : "off")+
        "   Target: "+(InpTakeProfit>0 ? IntegerToString(InpTakeProfit)+" pts" : "off")+"\n";
   txt+="Trading window: "+(InpUseTimeFilter ? IntegerToString(InpStartHour)+"h to "+
        IntegerToString(InpEndHour)+"h "+(XP_TimeAllowed() ? "(open)" : "(closed)") : "always open");
   Comment(txt);
  }
//+------------------------------------------------------------------+
