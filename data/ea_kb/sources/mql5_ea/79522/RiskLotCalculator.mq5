//+------------------------------------------------------------------+
//| RiskLotCalculator.mq5                                            |
//| Risk Lot Calculator panel                                        |
//| Copyright 2026, Golden Sniper XAU                                |
//+------------------------------------------------------------------+
#property copyright   "Golden Sniper XAU"
#property version     "1.00"
#property description "Calculates lot size from a risk percent and a stop-loss in points."
#property description "The panel also shows tick value, required margin and money at risk."
#property description "Works on any symbol. This utility does not place orders."
//+------------------------------------------------------------------+
//| Defines                                                          |
//+------------------------------------------------------------------+
#define RLC_PREFIX "RLC_"
#define RLC_ROWS   16
//+------------------------------------------------------------------+
//| Input parameters                                                 |
//+------------------------------------------------------------------+
input group "Calculation"
input double InpRiskPercent = 1.0;  // Risk per trade, percent of the reference balance
input int    InpStopPoints  = 200;  // Stop-loss distance in points (symbol _Point units)
input bool   InpUseEquity   = true; // true = use equity, false = use balance
input double InpFixedMoney  = 0.0;  // If greater than 0, use this money risk instead of the percent

input group "Panel"
input bool   InpShowPanel   = true;           // Show the on-chart panel
input int    InpCorner      = 0;              // Panel corner: 0 left-upper, 1 left-lower, 2 right-upper, 3 right-lower
input int    InpOffsetX     = 12;             // Panel X offset, pixels
input int    InpOffsetY     = 20;             // Panel Y offset, pixels
input int    InpFontSize    = 9;              // Font size
input color  InpColorBack   = C'18,22,28';    // Panel background
input color  InpColorBorder = C'196,160,64';  // Panel border
input color  InpColorTitle  = C'232,214,160'; // Title color
input color  InpColorLabel  = C'180,186,194'; // Label color
input color  InpColorValue  = clrWhite;       // Value color
input color  InpColorWarn   = clrTomato;      // Warning color
//+------------------------------------------------------------------+
//| Timer flag                                                       |
//+------------------------------------------------------------------+
int g_timer_ok=0;
//+------------------------------------------------------------------+
//| Convert the corner input to a chart corner                       |
//+------------------------------------------------------------------+
ENUM_BASE_CORNER CornerFromInput()
  {
   switch(InpCorner)
     {
      case 1:  return(CORNER_LEFT_LOWER);
      case 2:  return(CORNER_RIGHT_UPPER);
      case 3:  return(CORNER_RIGHT_LOWER);
      default: return(CORNER_LEFT_UPPER);
     }
  }
//+------------------------------------------------------------------+
//| Delete panel objects                                             |
//+------------------------------------------------------------------+
void DeletePanel()
  {
   ObjectsDeleteAll(0,RLC_PREFIX);
   Comment("");
  }
//+------------------------------------------------------------------+
//| Create or update a label                                         |
//+------------------------------------------------------------------+
bool CreateLabel(const string name,const int x,const int y,const string text,
                 const color clr,const int font_size,const bool right_align)
  {
   if(ObjectFind(0,name)<0)
     {
      if(!ObjectCreate(0,name,OBJ_LABEL,0,0,0))
         return(false);
      ObjectSetInteger(0,name,OBJPROP_CORNER,CornerFromInput());
      ObjectSetInteger(0,name,OBJPROP_ANCHOR,
                       right_align ? (InpCorner==2 || InpCorner==3 ? ANCHOR_RIGHT_UPPER : ANCHOR_LEFT_UPPER)
                                   : (InpCorner==2 || InpCorner==3 ? ANCHOR_RIGHT_UPPER : ANCHOR_LEFT_UPPER));
      ObjectSetInteger(0,name,OBJPROP_SELECTABLE,false);
      ObjectSetInteger(0,name,OBJPROP_HIDDEN,true);
      ObjectSetInteger(0,name,OBJPROP_BACK,false);
      ObjectSetString(0,name,OBJPROP_FONT,"Consolas");
     }
   ObjectSetInteger(0,name,OBJPROP_XDISTANCE,x);
   ObjectSetInteger(0,name,OBJPROP_YDISTANCE,y);
   ObjectSetInteger(0,name,OBJPROP_FONTSIZE,font_size);
   ObjectSetInteger(0,name,OBJPROP_COLOR,clr);
   ObjectSetString(0,name,OBJPROP_TEXT,text);
   return(true);
  }
//+------------------------------------------------------------------+
//| Set one panel row (label and value)                              |
//+------------------------------------------------------------------+
void SetRow(const int row,const string label,const string value,const bool warn)
  {
   const int line_h=InpFontSize+6;
   const int y=InpOffsetY+10+(row+1)*line_h;
   const bool right=(InpCorner==2 || InpCorner==3);
   const int x_label=right ? InpOffsetX+268 : InpOffsetX+14;
   const int x_value=right ? InpOffsetX+12 : InpOffsetX+168;
   CreateLabel(RLC_PREFIX+"L"+IntegerToString(row),x_label,y,label,
               InpColorLabel,InpFontSize,right);
   CreateLabel(RLC_PREFIX+"V"+IntegerToString(row),x_value,y,value,
               warn ? InpColorWarn : InpColorValue,InpFontSize,right);
   if(right)
     {
      ObjectSetInteger(0,RLC_PREFIX+"L"+IntegerToString(row),OBJPROP_ANCHOR,ANCHOR_RIGHT_UPPER);
      ObjectSetInteger(0,RLC_PREFIX+"V"+IntegerToString(row),OBJPROP_ANCHOR,ANCHOR_RIGHT_UPPER);
     }
  }
//+------------------------------------------------------------------+
//| Round a lot down to the symbol volume step                       |
//+------------------------------------------------------------------+
double NormalizeLotDown(const double lot,const double vmin,const double vmax,const double step)
  {
   if(step<=0.0)
      return(0.0);
   double x=MathFloor((lot+1.0e-12)/step)*step;
   const int dg=(int)MathMax(0.0,MathCeil(-MathLog10(step)));
   x=NormalizeDouble(x,dg);
   if(x<vmin-1.0e-12)
      return(0.0);
   if(x>vmax)
      x=MathFloor(vmax/step)*step;
   return(NormalizeDouble(x,dg));
  }
//+------------------------------------------------------------------+
//| Recalculate the lot and redraw the panel                         |
//+------------------------------------------------------------------+
void RefreshPanel()
  {
   if(!InpShowPanel)
     {
      DeletePanel();
      return;
     }
//--- account and symbol data
   const double balance =AccountInfoDouble(ACCOUNT_BALANCE);
   const double equity  =AccountInfoDouble(ACCOUNT_EQUITY);
   const double free_mg =AccountInfoDouble(ACCOUNT_MARGIN_FREE);
   const string acc_ccy =AccountInfoString(ACCOUNT_CURRENCY);
   const double point   =SymbolInfoDouble(_Symbol,SYMBOL_POINT);
   const double tick_sz =SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_SIZE);
   const double tick_vl =SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_VALUE);
   const double vmin    =SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MIN);
   const double vmax    =SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MAX);
   const double vstep   =SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_STEP);
   const int    stops   =(int)SymbolInfoInteger(_Symbol,SYMBOL_TRADE_STOPS_LEVEL);
   const int    digits  =(int)SymbolInfoInteger(_Symbol,SYMBOL_DIGITS);
   const double contract=SymbolInfoDouble(_Symbol,SYMBOL_TRADE_CONTRACT_SIZE);
   const double ask     =SymbolInfoDouble(_Symbol,SYMBOL_ASK);

   const int sl_points=InpStopPoints;
   bool   warn=false;
   string warn_text="";

   if(sl_points<=0 || point<=0.0 || tick_sz<=0.0 || tick_vl<=0.0)
     {
      warn=true;
      warn_text="Invalid stop or tick data";
     }
   else
      if(sl_points<stops)
        {
         warn=true;
         warn_text="Stop is below broker StopsLevel";
        }
//--- risk money and stop distance
   const double ref_money=InpUseEquity ? equity : balance;
   double risk_money=(InpFixedMoney>0.0) ? InpFixedMoney : (ref_money*InpRiskPercent/100.0);
   if(risk_money<0.0)
      risk_money=0.0;

   const double sl_price=sl_points*point;
   const double ticks=(tick_sz>0.0 ? sl_price/tick_sz : 0.0);
   const double loss_per_lot=ticks*tick_vl;

   double raw_lot=0.0;
   if(loss_per_lot>0.0)
      raw_lot=risk_money/loss_per_lot;
   const double lot=NormalizeLotDown(raw_lot,vmin,vmax,vstep);
   if(raw_lot>0.0 && lot<=0.0)
     {
      warn=true;
      warn_text="Risk is below the minimum lot";
     }
   else
      if(lot+vstep<raw_lot-1.0e-12 && lot>=vmax-1.0e-12)
        {
         warn=true;
         warn_text="Lot was capped at the symbol maximum";
        }

   const double money_at_risk=lot*loss_per_lot;
   double margin_lot=0.0;
   if(!OrderCalcMargin(ORDER_TYPE_BUY,_Symbol,1.0,ask,margin_lot))
      margin_lot=0.0;
   const double margin_needed=margin_lot*lot;
   if(lot>0.0 && margin_needed>free_mg)
     {
      warn=true;
      warn_text="Not enough free margin for this lot";
     }
//--- background
   const int line_h=InpFontSize+6;
   const int width=280;
   const int height=16+(RLC_ROWS+2)*line_h;
   const string bg=RLC_PREFIX+"bg";
   if(ObjectFind(0,bg)<0)
     {
      ObjectCreate(0,bg,OBJ_RECTANGLE_LABEL,0,0,0);
      ObjectSetInteger(0,bg,OBJPROP_CORNER,CornerFromInput());
      ObjectSetInteger(0,bg,OBJPROP_BGCOLOR,InpColorBack);
      ObjectSetInteger(0,bg,OBJPROP_BORDER_TYPE,BORDER_FLAT);
      ObjectSetInteger(0,bg,OBJPROP_COLOR,InpColorBorder);
      ObjectSetInteger(0,bg,OBJPROP_WIDTH,1);
      ObjectSetInteger(0,bg,OBJPROP_SELECTABLE,false);
      ObjectSetInteger(0,bg,OBJPROP_HIDDEN,true);
      ObjectSetInteger(0,bg,OBJPROP_BACK,false);
      ObjectSetInteger(0,bg,OBJPROP_ZORDER,-1);
     }
   ObjectSetInteger(0,bg,OBJPROP_XDISTANCE,InpOffsetX);
   ObjectSetInteger(0,bg,OBJPROP_YDISTANCE,InpOffsetY);
   ObjectSetInteger(0,bg,OBJPROP_XSIZE,width);
   ObjectSetInteger(0,bg,OBJPROP_YSIZE,height);

   const bool right=(InpCorner==2 || InpCorner==3);
   const int x_title=right ? InpOffsetX+12 : InpOffsetX+14;
   CreateLabel(RLC_PREFIX+"title",x_title,InpOffsetY+8,"Risk Lot Calculator",
               InpColorTitle,InpFontSize+1,right);
   if(right)
      ObjectSetInteger(0,RLC_PREFIX+"title",OBJPROP_ANCHOR,ANCHOR_RIGHT_UPPER);
//--- rows
   int r=0;
   SetRow(r++,"Symbol",_Symbol+" "+EnumToString((ENUM_TIMEFRAMES)_Period),false);
   SetRow(r++,"Reference",InpUseEquity ? "Equity" : "Balance",false);
   SetRow(r++,"Equity",DoubleToString(equity,2)+" "+acc_ccy,false);
   SetRow(r++,"Balance",DoubleToString(balance,2)+" "+acc_ccy,false);
   SetRow(r++,"Risk setting",
          InpFixedMoney>0.0
          ? ("Fixed "+DoubleToString(InpFixedMoney,2)+" "+acc_ccy)
          : (DoubleToString(InpRiskPercent,2)+" %"),
          false);
   SetRow(r++,"Stop-loss",IntegerToString(sl_points)+" points  ("+DoubleToString(sl_price,digits)+")",
          sl_points<stops);
   SetRow(r++,"Tick size / value",
          DoubleToString(tick_sz,digits)+"  /  "+DoubleToString(tick_vl,5)+" "+acc_ccy,
          false);
   SetRow(r++,"Point / contract",
          DoubleToString(point,digits)+"  /  "+DoubleToString(contract,0),
          false);
   SetRow(r++,"Lot min / max / step",
          DoubleToString(vmin,2)+"  /  "+DoubleToString(vmax,2)+"  /  "+DoubleToString(vstep,2),
          false);
   SetRow(r++,"StopsLevel",IntegerToString(stops)+" points",false);
   SetRow(r++,"Loss per 1.00 lot",
          loss_per_lot>0.0 ? DoubleToString(loss_per_lot,2)+" "+acc_ccy : "n/a",
          loss_per_lot<=0.0);
   SetRow(r++,"Calculated lot",lot>0.0 ? DoubleToString(lot,2) : "n/a",lot<=0.0);
   SetRow(r++,"Money at risk",
          lot>0.0 ? DoubleToString(money_at_risk,2)+" "+acc_ccy : "n/a",
          false);
   SetRow(r++,"Margin per 1.00 lot",
          margin_lot>0.0 ? DoubleToString(margin_lot,2)+" "+acc_ccy : "n/a",
          false);
   SetRow(r++,"Margin for this lot",
          lot>0.0 && margin_lot>0.0 ? DoubleToString(margin_needed,2)+" "+acc_ccy : "n/a",
          lot>0.0 && margin_needed>free_mg);
   SetRow(r++,"Free margin",DoubleToString(free_mg,2)+" "+acc_ccy,
          lot>0.0 && margin_needed>free_mg);

   const string foot=(warn_text!="" ? warn_text : "This utility does not place orders.");
   const int y_foot=InpOffsetY+10+(r+1)*line_h+4;
   CreateLabel(RLC_PREFIX+"foot",x_title,y_foot,foot,
               warn ? InpColorWarn : InpColorLabel,InpFontSize,right);
   if(right)
      ObjectSetInteger(0,RLC_PREFIX+"foot",OBJPROP_ANCHOR,ANCHOR_RIGHT_UPPER);

   ChartRedraw(0);
  }
//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
  {
   if(InpRiskPercent<0.0 || InpRiskPercent>100.0)
      return(INIT_PARAMETERS_INCORRECT);
   if(InpStopPoints<0 || InpStopPoints>1000000)
      return(INIT_PARAMETERS_INCORRECT);
   if(InpFixedMoney<0.0)
      return(INIT_PARAMETERS_INCORRECT);
   if(InpFontSize<7 || InpFontSize>16)
      return(INIT_PARAMETERS_INCORRECT);
   if(InpCorner<0 || InpCorner>3)
      return(INIT_PARAMETERS_INCORRECT);

   if(!EventSetMillisecondTimer(500))
     {
      Print("Risk Lot Calculator: millisecond timer was not accepted, using a 1-second timer.");
      EventSetTimer(1);
     }
   g_timer_ok=1;
   RefreshPanel();
   return(INIT_SUCCEEDED);
  }
//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   EventKillTimer();
   DeletePanel();
  }
//+------------------------------------------------------------------+
//| Tick                                                             |
//+------------------------------------------------------------------+
void OnTick()
  {
   RefreshPanel();
  }
//+------------------------------------------------------------------+
//| Timer                                                            |
//+------------------------------------------------------------------+
void OnTimer()
  {
   RefreshPanel();
  }
//+------------------------------------------------------------------+
//| Chart event                                                      |
//+------------------------------------------------------------------+
void OnChartEvent(const int id,const long &lparam,const double &dparam,const string &sparam)
  {
   if(id==CHARTEVENT_CHART_CHANGE)
      RefreshPanel();
  }
//+------------------------------------------------------------------+
