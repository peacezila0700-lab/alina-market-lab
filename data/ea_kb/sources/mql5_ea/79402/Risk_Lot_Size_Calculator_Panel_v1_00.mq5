//+------------------------------------------------------------------+
//| Risk Lot Size Calculator Panel                   XPro by Xander  |
//| Version 1.0  |  2026-11-02  |  MetaTrader 5                      |
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
// v1.0 - 2026-11-02 - Initial release
//                     Lot size from risk in percent of balance, percent
//                     of equity or fixed money and the stop in points
//                     Loss per lot from OrderCalcProfit (right on gold,
//                     indices and crosses), rounded down to volume step
//                     Buy and Sell buttons with stop, target, margin check
//+------------------------------------------------------------------+
#property copyright   "Copyright 2026, Cristhian Gaibor (Xander)"
#property link        "https://www.mql5.com/en/users/09151993a"
#property version     "1.00"
#property description "XPro by Xander. Tested code, compiles clean, ready for demo and live accounts."
#property description "Type your risk and your stop in points, the panel gives the lot and opens the trade with one click."
#property description "More tools on my profile. Updates first on my MQL5 channel: mql5.com/en/channels/xander"

#include <Trade\Trade.mqh>

enum ENUM_XP_RISKMODE
  {
   XP_RISK_BALANCE = 0,   // Percent of balance
   XP_RISK_EQUITY  = 1,   // Percent of equity
   XP_RISK_MONEY   = 2    // Fixed money (account currency)
  };

//+------------------------------------------------------------------+
//| INPUTS                                                           |
//+------------------------------------------------------------------+
input string sep0               = "★ Risk Lot Size Calculator Panel"; // ══ XPro by Xander ══
input string sep1               = "══════ STRATEGY ══════";          // ─────────────────────
input ENUM_XP_RISKMODE InpRiskMode = XP_RISK_BALANCE; // Risk mode (can be changed on the panel)
input double InpRiskValue       = 1.0;     // Risk per trade (percent or money, by mode)
input int    InpStopPoints      = 300;     // Stop loss distance (points)
input int    InpTakePoints      = 600;     // Take profit distance (points, 0 = none)

input string sep2               = "══════ LOT SETTINGS ══════";      // ─────────────────────
input bool   InpUseMinLot       = false;   // If the lot is below the broker minimum, use the minimum
input double InpMaxLot          = 5.0;     // Never send more than this lot

input string sep3               = "══════ RISK PROTECTION ══════";   // ─────────────────────
input double InpMaxRiskPercent  = 5.0;     // Refuse a trade that risks more than this percent of balance

input string sep4               = "══════ EXPERT SETTINGS ══════";   // ─────────────────────
input ulong  InpMagic           = 7301;    // Magic number of the trades it opens
input int    InpSlippage        = 30;      // Max deviation (points)
input string InpComment         = "XPro RiskLot"; // Order comment
input int    InpPanelX          = 12;      // Panel X offset (pixels)
input int    InpPanelY          = 30;      // Panel Y offset (pixels)
input int    InpFontSize        = 9;       // Panel font size

//+------------------------------------------------------------------+
//| GLOBALS                                                          |
//+------------------------------------------------------------------+
#define XP_NAME   "Risk Lot Size Calculator Panel"
#define XP_PFX    "XP_RLC_"

CTrade           XP_trade;
ENUM_XP_RISKMODE XP_mode;
double           XP_risk;
int              XP_sl;
int              XP_tp;
string           XP_status="";

double           XP_lot=0.0;          // lot after rounding and limits
double           XP_riskMoney=0.0;    // money the user wants to risk
double           XP_lossPerLot=0.0;   // loss of 1.00 lot at the stop
double           XP_realRisk=0.0;     // money really at risk with XP_lot

//+------------------------------------------------------------------+
int OnInit()
  {
   if(InpStopPoints<1 || InpRiskValue<=0.0)
     {
      Print("[",XP_NAME,"] Stop loss must be 1 point or more and risk must be above 0.");
      return(INIT_PARAMETERS_INCORRECT);
     }
   XP_mode=InpRiskMode;
   XP_risk=InpRiskValue;
   XP_sl=InpStopPoints;
   XP_tp=MathMax(InpTakePoints,0);

   XP_trade.SetExpertMagicNumber(InpMagic);
   XP_trade.SetDeviationInPoints(InpSlippage);
   XP_trade.SetTypeFillingBySymbol(_Symbol);

   XP_BuildPanel();
   XP_Recalc();
   EventSetTimer(1);   // keeps the numbers fresh on quiet markets and weekends
   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   EventKillTimer();
   ObjectsDeleteAll(0,XP_PFX);
   ChartRedraw();
  }

void OnTick()  { XP_Recalc(); }
void OnTimer() { XP_Recalc(); }

//+------------------------------------------------------------------+
//| Money at risk for 1.00 lot, worst of buy and sell                |
//+------------------------------------------------------------------+
double XP_LossPerLot()
  {
   MqlTick tk;
   if(!SymbolInfoTick(_Symbol,tk) || tk.ask<=0.0 || tk.bid<=0.0)
      return(0.0);
   double dist=XP_sl*_Point;
   double pBuy=0.0,pSell=0.0;
   bool okB=OrderCalcProfit(ORDER_TYPE_BUY,_Symbol,1.0,tk.ask,tk.ask-dist,pBuy);
   bool okS=OrderCalcProfit(ORDER_TYPE_SELL,_Symbol,1.0,tk.bid,tk.bid+dist,pSell);
   if(!okB && !okS)
      return(0.0);
   return(MathMax(MathAbs(pBuy),MathAbs(pSell)));
  }

//+------------------------------------------------------------------+
//| Lot from risk, rounded down to the broker volume step            |
//+------------------------------------------------------------------+
void XP_Recalc()
  {
   double bal=AccountInfoDouble(ACCOUNT_BALANCE);
   double eq =AccountInfoDouble(ACCOUNT_EQUITY);
   if(XP_mode==XP_RISK_BALANCE)     XP_riskMoney=bal*XP_risk/100.0;
   else if(XP_mode==XP_RISK_EQUITY) XP_riskMoney=eq*XP_risk/100.0;
   else                             XP_riskMoney=XP_risk;

   XP_lossPerLot=XP_LossPerLot();
   double vMin =SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MIN);
   double vMax =SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MAX);
   double vStep=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_STEP);
   if(vStep<=0.0) vStep=0.01;

   XP_lot=0.0;
   string note="";
   if(XP_lossPerLot>0.0)
     {
      double raw=XP_riskMoney/XP_lossPerLot;
      double lot=MathFloor(raw/vStep+1e-9)*vStep;
      lot=MathMin(lot,MathMin(vMax,InpMaxLot));
      if(lot<vMin)
        {
         if(InpUseMinLot)
           {
            lot=vMin;
            note="Below the broker minimum, using "+DoubleToString(vMin,2);
           }
         else
           {
            lot=0.0;
            note="Risk too small for the minimum lot "+DoubleToString(vMin,2);
           }
        }
      XP_lot=NormalizeDouble(lot,XP_VolumeDigits(vStep));
     }
   else
      note="Waiting for prices";

   XP_realRisk=XP_lot*XP_lossPerLot;
   if(note!="")
      XP_status=note;
   XP_UpdatePanel();
  }

//+------------------------------------------------------------------+
int XP_VolumeDigits(const double step)
  {
   int d=0;
   double s=step;
   while(d<8 && MathAbs(s-MathRound(s))>1e-9)
     {
      s*=10.0;
      d++;
     }
   return(d);
  }

//+------------------------------------------------------------------+
//| Send a market order with stop and target in points               |
//+------------------------------------------------------------------+
void XP_Send(const bool buy)
  {
   XP_Recalc();
   if(XP_lot<=0.0)
     {
      XP_status="No trade: lot is 0 ("+XP_status+")";
      XP_UpdatePanel();
      return;
     }
   double bal=AccountInfoDouble(ACCOUNT_BALANCE);
   if(bal>0.0 && XP_realRisk/bal*100.0>InpMaxRiskPercent)
     {
      XP_status=StringFormat("No trade: risk %.2f%% is above your limit %.2f%%",XP_realRisk/bal*100.0,InpMaxRiskPercent);
      XP_UpdatePanel();
      return;
     }
   long stopsLevel=SymbolInfoInteger(_Symbol,SYMBOL_TRADE_STOPS_LEVEL);
   if(XP_sl<stopsLevel || (XP_tp>0 && XP_tp<stopsLevel))
     {
      XP_status="No trade: broker minimum stop distance is "+IntegerToString(stopsLevel)+" points";
      XP_UpdatePanel();
      return;
     }

   MqlTick tk;
   if(!SymbolInfoTick(_Symbol,tk))
     {
      XP_status="No trade: no price";
      XP_UpdatePanel();
      return;
     }
   double price=buy ? tk.ask : tk.bid;

   //--- margin check before every order
   double margin=0.0;
   if(!OrderCalcMargin(buy ? ORDER_TYPE_BUY : ORDER_TYPE_SELL,_Symbol,XP_lot,price,margin) ||
      margin>AccountInfoDouble(ACCOUNT_MARGIN_FREE))
     {
      XP_status="No trade: not enough free margin for "+DoubleToString(XP_lot,2)+" lots";
      XP_UpdatePanel();
      return;
     }

   double sl=buy ? price-XP_sl*_Point : price+XP_sl*_Point;
   double tp=0.0;
   if(XP_tp>0)
      tp=buy ? price+XP_tp*_Point : price-XP_tp*_Point;
   sl=NormalizeDouble(sl,_Digits);
   tp=NormalizeDouble(tp,_Digits);

   bool ok=buy ? XP_trade.Buy(XP_lot,_Symbol,0.0,sl,tp,InpComment)
                : XP_trade.Sell(XP_lot,_Symbol,0.0,sl,tp,InpComment);
   uint rc=XP_trade.ResultRetcode();
   if(ok && (rc==TRADE_RETCODE_DONE || rc==TRADE_RETCODE_PLACED))
     {
      XP_status=StringFormat("%s %.2f opened, risk %.2f %s",buy ? "Buy" : "Sell",XP_lot,
                             XP_realRisk,AccountInfoString(ACCOUNT_CURRENCY));
      Print("[",XP_NAME,"] ",XP_status);
     }
   else
     {
      XP_status="Order rejected: "+XP_trade.ResultRetcodeDescription();
      Print("[",XP_NAME,"] ",XP_status," (",rc,")");
     }
   XP_UpdatePanel();
  }

//+------------------------------------------------------------------+
//| Panel events                                                     |
//+------------------------------------------------------------------+
void OnChartEvent(const int id,const long &lparam,const double &dparam,const string &sparam)
  {
   if(id==CHARTEVENT_OBJECT_CLICK)
     {
      if(sparam==XP_PFX+"Mode")
        {
         XP_mode=(ENUM_XP_RISKMODE)(((int)XP_mode+1)%3);
         XP_status="";
         XP_Recalc();
        }
      else if(sparam==XP_PFX+"Buy")
         XP_Send(true);
      else if(sparam==XP_PFX+"Sell")
         XP_Send(false);
      ObjectSetInteger(0,sparam,OBJPROP_STATE,false);
      ChartRedraw();
     }
   if(id==CHARTEVENT_OBJECT_ENDEDIT)
     {
      string txt=ObjectGetString(0,sparam,OBJPROP_TEXT);
      StringReplace(txt,",",".");
      double v=StringToDouble(txt);
      if(sparam==XP_PFX+"Risk")
        {
         if(v>0.0) XP_risk=v;
        }
      else if(sparam==XP_PFX+"SL")
        {
         if(v>=1.0) XP_sl=(int)MathRound(v);
        }
      else if(sparam==XP_PFX+"TP")
        {
         if(v>=0.0) XP_tp=(int)MathRound(v);
        }
      //--- write back the value really used (edits are not touched while typing)
      ObjectSetString(0,XP_PFX+"Risk",OBJPROP_TEXT,DoubleToString(XP_risk,2));
      ObjectSetString(0,XP_PFX+"SL",OBJPROP_TEXT,IntegerToString(XP_sl));
      ObjectSetString(0,XP_PFX+"TP",OBJPROP_TEXT,IntegerToString(XP_tp));
      XP_status="";
      XP_Recalc();
     }
  }

//+------------------------------------------------------------------+
//| Plain panel: rectangle label, labels, edits and buttons          |
//+------------------------------------------------------------------+
#define XP_W 260
int XP_RowH() { return(InpFontSize*2+8); }

void XP_Label(const string name,const int x,const int y,const string text,const color clr)
  {
   string id=XP_PFX+name;
   if(ObjectFind(0,id)<0)
     {
      ObjectCreate(0,id,OBJ_LABEL,0,0,0);
      ObjectSetInteger(0,id,OBJPROP_CORNER,CORNER_LEFT_UPPER);
      ObjectSetString(0,id,OBJPROP_FONT,"Arial");
      ObjectSetInteger(0,id,OBJPROP_FONTSIZE,InpFontSize);
      ObjectSetInteger(0,id,OBJPROP_SELECTABLE,false);
      ObjectSetInteger(0,id,OBJPROP_HIDDEN,true);
     }
   ObjectSetInteger(0,id,OBJPROP_XDISTANCE,x);
   ObjectSetInteger(0,id,OBJPROP_YDISTANCE,y);
   ObjectSetInteger(0,id,OBJPROP_COLOR,clr);
   ObjectSetString(0,id,OBJPROP_TEXT,text);
  }

void XP_Box(const string name,const ENUM_OBJECT type,const int x,const int y,const int w,
            const int h,const string text,const color bg,const color fg)
  {
   string id=XP_PFX+name;
   if(ObjectFind(0,id)<0)
     {
      ObjectCreate(0,id,type,0,0,0);
      ObjectSetInteger(0,id,OBJPROP_CORNER,CORNER_LEFT_UPPER);
      ObjectSetString(0,id,OBJPROP_FONT,"Arial");
      ObjectSetInteger(0,id,OBJPROP_FONTSIZE,InpFontSize);
      ObjectSetInteger(0,id,OBJPROP_SELECTABLE,false);
      ObjectSetInteger(0,id,OBJPROP_HIDDEN,true);
     }
   ObjectSetInteger(0,id,OBJPROP_XDISTANCE,x);
   ObjectSetInteger(0,id,OBJPROP_YDISTANCE,y);
   ObjectSetInteger(0,id,OBJPROP_XSIZE,w);
   ObjectSetInteger(0,id,OBJPROP_YSIZE,h);
   ObjectSetInteger(0,id,OBJPROP_BGCOLOR,bg);
   ObjectSetInteger(0,id,OBJPROP_COLOR,fg);
   ObjectSetInteger(0,id,OBJPROP_BORDER_COLOR,C'90,90,90');
   if(type!=OBJ_RECTANGLE_LABEL)
      ObjectSetString(0,id,OBJPROP_TEXT,text);
  }

void XP_BuildPanel()
  {
   int r=XP_RowH();
   string bgId=XP_PFX+"Bg";
   if(ObjectFind(0,bgId)<0)
     {
      ObjectCreate(0,bgId,OBJ_RECTANGLE_LABEL,0,0,0);
      ObjectSetInteger(0,bgId,OBJPROP_CORNER,CORNER_LEFT_UPPER);
      ObjectSetInteger(0,bgId,OBJPROP_BORDER_TYPE,BORDER_FLAT);
      ObjectSetInteger(0,bgId,OBJPROP_SELECTABLE,false);
      ObjectSetInteger(0,bgId,OBJPROP_HIDDEN,true);
     }
   ObjectSetInteger(0,bgId,OBJPROP_XDISTANCE,InpPanelX);
   ObjectSetInteger(0,bgId,OBJPROP_YDISTANCE,InpPanelY);
   ObjectSetInteger(0,bgId,OBJPROP_XSIZE,XP_W);
   ObjectSetInteger(0,bgId,OBJPROP_YSIZE,r*12+10);
   ObjectSetInteger(0,bgId,OBJPROP_BGCOLOR,C'24,28,34');
   ObjectSetInteger(0,bgId,OBJPROP_COLOR,C'70,70,70');

   int x=InpPanelX+10,y=InpPanelY+8,xv=InpPanelX+150,wv=XP_W-160;
   XP_Label("Title",x,y,XP_NAME,clrWhite);                    y+=r+2;
   XP_Label("LMode",x,y+3,"Risk mode",clrSilver);
   XP_Box("Mode",OBJ_BUTTON,xv,y,wv,r,"",C'45,52,62',clrWhite);         y+=r+2;
   XP_Label("LRisk",x,y+3,"Risk",clrSilver);
   XP_Box("Risk",OBJ_EDIT,xv,y,wv,r,DoubleToString(XP_risk,2),C'15,18,22',clrWhite); y+=r+2;
   XP_Label("LSL",x,y+3,"Stop loss (points)",clrSilver);
   XP_Box("SL",OBJ_EDIT,xv,y,wv,r,IntegerToString(XP_sl),C'15,18,22',clrWhite);       y+=r+2;
   XP_Label("LTP",x,y+3,"Take profit (points)",clrSilver);
   XP_Box("TP",OBJ_EDIT,xv,y,wv,r,IntegerToString(XP_tp),C'15,18,22',clrWhite);       y+=r+6;
   XP_Label("Lot",x,y,"",clrGold);              y+=r;
   XP_Label("Money",x,y,"",clrSilver);          y+=r;
   XP_Label("PerLot",x,y,"",clrSilver);         y+=r;
   XP_Label("Spread",x,y,"",clrSilver);         y+=r+4;
   int bw=(XP_W-30)/2;
   XP_Box("Buy",OBJ_BUTTON,x,y,bw,r+4,"BUY",C'20,110,80',clrWhite);
   XP_Box("Sell",OBJ_BUTTON,x+bw+10,y,bw,r+4,"SELL",C'150,40,40',clrWhite); y+=r+10;
   XP_Label("Status",x,y,"",clrOrange);
   ChartRedraw();
  }

void XP_UpdatePanel()
  {
   string cur=AccountInfoString(ACCOUNT_CURRENCY);
   string modeTxt=(XP_mode==XP_RISK_BALANCE) ? "% of balance" : (XP_mode==XP_RISK_EQUITY ? "% of equity" : "Money ("+cur+")");
   ObjectSetString(0,XP_PFX+"Mode",OBJPROP_TEXT,modeTxt);

   ObjectSetString(0,XP_PFX+"Lot",OBJPROP_TEXT,"Lot: "+DoubleToString(XP_lot,2));
   ObjectSetString(0,XP_PFX+"Money",OBJPROP_TEXT,StringFormat("Risk: %.2f %s (at this lot %.2f)",XP_riskMoney,cur,XP_realRisk));
   ObjectSetString(0,XP_PFX+"PerLot",OBJPROP_TEXT,StringFormat("Loss of 1.00 lot at the stop: %.2f %s",XP_lossPerLot,cur));
   ObjectSetString(0,XP_PFX+"Spread",OBJPROP_TEXT,"Spread: "+IntegerToString(SymbolInfoInteger(_Symbol,SYMBOL_SPREAD))+" points");
   ObjectSetString(0,XP_PFX+"Buy",OBJPROP_TEXT,"BUY "+DoubleToString(XP_lot,2));
   ObjectSetString(0,XP_PFX+"Sell",OBJPROP_TEXT,"SELL "+DoubleToString(XP_lot,2));
   ObjectSetString(0,XP_PFX+"Status",OBJPROP_TEXT,XP_status);
   ChartRedraw();
  }
//+------------------------------------------------------------------+
