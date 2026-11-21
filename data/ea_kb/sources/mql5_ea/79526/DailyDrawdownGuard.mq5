//+------------------------------------------------------------------+
//| DailyDrawdownGuard.mq5                                           |
//| Daily Drawdown Guard                                             |
//| Copyright 2026, Golden Sniper XAU                                |
//+------------------------------------------------------------------+
#property copyright   "Golden Sniper XAU"
#property version     "1.00"
#property description "Watches daily equity drawdown and daily loss from the start of the day."
#property description "Raises a warning or a critical alert when a chosen limit is reached."
#property description "This utility does not place, modify or close orders."
//+------------------------------------------------------------------+
//| Defines                                                          |
//+------------------------------------------------------------------+
#define DDG_PREFIX  "DDG_"
#define DDG_ROWS    14
#define DDG_GV      "GSX_DDG_"
//+------------------------------------------------------------------+
//| Alert mode                                                       |
//+------------------------------------------------------------------+
enum ENUM_DDG_MODE
  {
   DDG_FROM_START=0, // Daily loss from the start of the day
   DDG_FROM_PEAK =1, // Drawdown from the intraday equity peak
   DDG_EITHER    =2  // Whichever of the two is larger
  };
//+------------------------------------------------------------------+
//| Input parameters                                                 |
//+------------------------------------------------------------------+
input group "Limits"
input ENUM_DDG_MODE InpAlertMode    = DDG_FROM_START; // Value that is compared with the limits
input double InpWarnPercent  = 3.0;  // Warning level, percent
input double InpCritPercent  = 5.0;  // Critical level, percent
input double InpWarnMoney    = 0.0;  // Extra warning in money (0 = do not use)
input double InpCritMoney    = 0.0;  // Extra critical in money (0 = do not use)

input group "Day"
input int    InpResetHour    = 0;    // Hour when the trading day starts, server time
input int    InpResetMinute  = 0;    // Minute when the trading day starts, server time

input group "Alerts"
input bool   InpAlertPopup   = true;           // Terminal alert window
input bool   InpAlertSound   = true;           // Play a sound
input string InpSoundName    = "alert.wav";    // Sound file
input bool   InpAlertPush    = false;          // Push notification (MetaQuotes ID)

input group "Panel"
input bool   InpShowPanel    = true;           // Show the on-chart panel
input int    InpCorner       = 0;              // Panel corner: 0 left-upper, 1 left-lower, 2 right-upper, 3 right-lower
input int    InpOffsetX      = 12;             // Panel X offset, pixels
input int    InpOffsetY      = 20;             // Panel Y offset, pixels
input int    InpFontSize     = 9;              // Font size
input color  InpColorBack    = C'18,22,28';    // Panel background
input color  InpColorBorder  = C'196,160,64';  // Panel border
input color  InpColorTitle   = C'232,214,160'; // Title color
input color  InpColorLabel   = C'180,186,194'; // Label color
input color  InpColorValue   = clrWhite;       // Value color
input color  InpColorWarn    = clrOrange;      // Warning color
input color  InpColorCrit    = clrTomato;      // Critical color
input color  InpColorOk      = C'80,180,150';  // OK color
//+------------------------------------------------------------------+
//| Daily state                                                      |
//+------------------------------------------------------------------+
datetime g_day_start=0;
double   g_start_equity=0.0;
double   g_start_balance=0.0;
double   g_peak_equity=0.0;
int      g_warned=0;
int      g_critical=0;
int      g_timer_ok=0;
//+------------------------------------------------------------------+
//| Global variable name for this account                            |
//+------------------------------------------------------------------+
string GvName(const string key)
  {
   return(DDG_GV+IntegerToString(AccountInfoInteger(ACCOUNT_LOGIN))+"_"+key);
  }
//+------------------------------------------------------------------+
//| Save daily state                                                 |
//+------------------------------------------------------------------+
void SaveState()
  {
   GlobalVariableSet(GvName("day"),(double)g_day_start);
   GlobalVariableSet(GvName("seq"),g_start_equity);
   GlobalVariableSet(GvName("sba"),g_start_balance);
   GlobalVariableSet(GvName("peak"),g_peak_equity);
   GlobalVariableSet(GvName("wrn"),(double)g_warned);
   GlobalVariableSet(GvName("crt"),(double)g_critical);
  }
//+------------------------------------------------------------------+
//| Load daily state, return false if nothing is stored              |
//+------------------------------------------------------------------+
bool LoadState()
  {
   const string n_day=GvName("day");
   if(!GlobalVariableCheck(n_day))
      return(false);
   g_day_start=(datetime)GlobalVariableGet(n_day);
   g_start_equity=GlobalVariableGet(GvName("seq"));
   g_start_balance=GlobalVariableGet(GvName("sba"));
   g_peak_equity=GlobalVariableGet(GvName("peak"));
   g_warned=(int)GlobalVariableGet(GvName("wrn"));
   g_critical=(int)GlobalVariableGet(GvName("crt"));
   return(g_day_start>0 && g_start_equity>0.0);
  }
//+------------------------------------------------------------------+
//| Start of the current trading day in server time                  |
//+------------------------------------------------------------------+
datetime TradingDayStart(const datetime now)
  {
   MqlDateTime dt;
   TimeToStruct(now,dt);
   dt.hour=InpResetHour;
   dt.min=InpResetMinute;
   dt.sec=0;
   datetime start=StructToTime(dt);
   if(now<start)
      start-=PeriodSeconds(PERIOD_D1);
   return(start);
  }
//+------------------------------------------------------------------+
//| Open a new trading day                                           |
//+------------------------------------------------------------------+
void ResetDay(const datetime start,const double equity,const double balance)
  {
   g_day_start=start;
   g_start_equity=equity;
   g_start_balance=balance;
   g_peak_equity=equity;
   g_warned=0;
   g_critical=0;
   SaveState();
  }
//+------------------------------------------------------------------+
//| Delete panel objects                                             |
//+------------------------------------------------------------------+
void DeletePanel()
  {
   ObjectsDeleteAll(0,DDG_PREFIX);
   Comment("");
  }
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
//| Create or update a label                                         |
//+------------------------------------------------------------------+
bool CreateLabel(const string name,const int x,const int y,const string text,
                 const color clr,const int font_size)
  {
   if(ObjectFind(0,name)<0)
     {
      if(!ObjectCreate(0,name,OBJ_LABEL,0,0,0))
         return(false);
      ObjectSetInteger(0,name,OBJPROP_CORNER,CornerFromInput());
      ObjectSetInteger(0,name,OBJPROP_ANCHOR,
                       (InpCorner==2 || InpCorner==3) ? ANCHOR_RIGHT_UPPER : ANCHOR_LEFT_UPPER);
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
//| Pixel width of a Consolas string (matches OBJ_LABEL font size)   |
//+------------------------------------------------------------------+
int TextPx(const string text,const int font_size)
  {
   // TextGetSize units differ across terminal builds (a *10 size made the
   // panel fill the chart; a pixel size made it narrower than the text).
   // Size the panel from a generous Consolas estimate instead.
   int cw=8;
   if(font_size<=8)
      cw=7;
   else
      if(font_size==10)
         cw=9;
      else
         if(font_size>=11)
            cw=font_size-1;
   return((int)StringLen(text)*cw+8);
  }
//+------------------------------------------------------------------+
//| Approximate text height in pixels                                |
//+------------------------------------------------------------------+
int TextPxH(const string text,const int font_size)
  {
   if(text=="")
      return(font_size+4);
   return(font_size+4);
  }
//+------------------------------------------------------------------+
//| Set one panel row                                                |
//+------------------------------------------------------------------+
void SetRow(const int row,const string label,const string value,const color vclr,
            const int x_label,const int x_value,const int line_h)
  {
   const int y=InpOffsetY+10+(row+1)*line_h;
   CreateLabel(DDG_PREFIX+"L"+IntegerToString(row),x_label,y,label,InpColorLabel,InpFontSize);
   CreateLabel(DDG_PREFIX+"V"+IntegerToString(row),x_value,y,value,vclr,InpFontSize);
  }
//+------------------------------------------------------------------+
//| Mode name                                                        |
//+------------------------------------------------------------------+
string ModeName()
  {
   if(InpAlertMode==DDG_FROM_PEAK)
      return("From intraday peak");
   if(InpAlertMode==DDG_EITHER)
      return("Whichever is larger");
   return("From start of day");
  }
//+------------------------------------------------------------------+
//| Fire one alert, once                                             |
//+------------------------------------------------------------------+
void FireAlert(const string level,const double pct,const double money,
               const string acc_ccy)
  {
   const string msg="Daily Drawdown Guard: "+level+
                    "  "+DoubleToString(pct,2)+" %   "+
                    DoubleToString(money,2)+" "+acc_ccy+
                    "  ("+ModeName()+")";
   if(InpAlertPopup)
      Alert(msg);
   else
      Print(msg);
   if(InpAlertSound && InpSoundName!="")
      PlaySound(InpSoundName);
   if(InpAlertPush)
      SendNotification(msg);
  }
//+------------------------------------------------------------------+
//| Recalculate and redraw                                           |
//+------------------------------------------------------------------+
void Refresh()
  {
   const double equity =AccountInfoDouble(ACCOUNT_EQUITY);
   const double balance=AccountInfoDouble(ACCOUNT_BALANCE);
   const double credit =AccountInfoDouble(ACCOUNT_CREDIT);
   const string acc_ccy=AccountInfoString(ACCOUNT_CURRENCY);
   const datetime now=(TimeTradeServer()>0 ? TimeTradeServer() : TimeCurrent());
   const datetime day=TradingDayStart(now);

   if(g_day_start!=day || g_start_equity<=0.0)
      ResetDay(day,equity,balance);

   if(equity>g_peak_equity)
     {
      g_peak_equity=equity;
      SaveState();
     }

   const double pl_money=equity-g_start_equity;
   const double loss_from_start=(g_start_equity>equity ? g_start_equity-equity : 0.0);
   const double dd_from_peak=(g_peak_equity>equity ? g_peak_equity-equity : 0.0);
   const double pct_from_start=(g_start_equity>0.0 ? 100.0*loss_from_start/g_start_equity : 0.0);
   const double pct_from_peak =(g_peak_equity>0.0 ? 100.0*dd_from_peak/g_peak_equity : 0.0);

   double use_pct=pct_from_start;
   double use_money=loss_from_start;
   if(InpAlertMode==DDG_FROM_PEAK)
     {
      use_pct=pct_from_peak;
      use_money=dd_from_peak;
     }
   else
      if(InpAlertMode==DDG_EITHER)
        {
         if(pct_from_peak>pct_from_start)
           {
            use_pct=pct_from_peak;
            use_money=dd_from_peak;
           }
        }

   const bool money_warn=(InpWarnMoney>0.0 && use_money>=InpWarnMoney);
   const bool money_crit=(InpCritMoney>0.0 && use_money>=InpCritMoney);
   const bool pct_warn=(InpWarnPercent>0.0 && use_pct>=InpWarnPercent);
   const bool pct_crit=(InpCritPercent>0.0 && use_pct>=InpCritPercent);
   const bool is_crit=(pct_crit || money_crit);
   const bool is_warn=(!is_crit && (pct_warn || money_warn));

   if(is_crit && g_critical==0)
     {
      FireAlert("CRITICAL",use_pct,use_money,acc_ccy);
      g_critical=1;
      g_warned=1;
      SaveState();
     }
   else
      if(is_warn && g_warned==0)
        {
         FireAlert("WARNING",use_pct,use_money,acc_ccy);
         g_warned=1;
         SaveState();
        }

   if(!InpShowPanel)
     {
      DeletePanel();
      return;
     }

   string status="OK";
   color  st_clr=InpColorOk;
   if(is_crit)
     {
      status="CRITICAL";
      st_clr=InpColorCrit;
     }
   else
      if(is_warn || g_warned==1)
        {
         status=(g_critical==1 ? "CRITICAL" : "WARNING");
         st_clr=(g_critical==1 ? InpColorCrit : InpColorWarn);
        }

   const color pl_clr=(pl_money<0.0 ? InpColorCrit : (pl_money>0.0 ? InpColorOk : InpColorValue));
   const color dd_start_clr=(pct_from_start>=InpCritPercent && InpCritPercent>0.0 ? InpColorCrit :
                             (pct_from_start>=InpWarnPercent && InpWarnPercent>0.0 ? InpColorWarn : InpColorValue));
   const color dd_peak_clr=(pct_from_peak>=InpCritPercent && InpCritPercent>0.0 ? InpColorCrit :
                            (pct_from_peak>=InpWarnPercent && InpWarnPercent>0.0 ? InpColorWarn : InpColorValue));

   string row_lab[DDG_ROWS];
   string row_val[DDG_ROWS];
   color  row_clr[DDG_ROWS];
   int r=0;
   row_lab[r]="Status";            row_val[r]=status;                                            row_clr[r]=st_clr; r++;
   row_lab[r]="Day start";         row_val[r]=TimeToString(g_day_start,TIME_DATE|TIME_MINUTES);   row_clr[r]=InpColorValue; r++;
   row_lab[r]="Alert mode";        row_val[r]=ModeName();                                        row_clr[r]=InpColorValue; r++;
   row_lab[r]="Equity";            row_val[r]=DoubleToString(equity,2)+" "+acc_ccy;               row_clr[r]=InpColorValue; r++;
   row_lab[r]="Balance";           row_val[r]=DoubleToString(balance,2)+" "+acc_ccy;              row_clr[r]=InpColorValue; r++;
   row_lab[r]="Credit";            row_val[r]=DoubleToString(credit,2)+" "+acc_ccy;
   row_clr[r]=(credit>0.0 ? InpColorWarn : InpColorValue); r++;
   row_lab[r]="Start equity";      row_val[r]=DoubleToString(g_start_equity,2)+" "+acc_ccy;       row_clr[r]=InpColorValue; r++;
   row_lab[r]="Peak equity";       row_val[r]=DoubleToString(g_peak_equity,2)+" "+acc_ccy;        row_clr[r]=InpColorValue; r++;
   row_lab[r]="Daily P/L";
   row_val[r]=DoubleToString(pl_money,2)+" "+acc_ccy+"   "+
              (g_start_equity>0.0 ? DoubleToString(100.0*pl_money/g_start_equity,2)+" %" : "n/a");
   row_clr[r]=pl_clr; r++;
   row_lab[r]="Loss from start";
   row_val[r]=DoubleToString(loss_from_start,2)+" "+acc_ccy+"   "+DoubleToString(pct_from_start,2)+" %";
   row_clr[r]=dd_start_clr; r++;
   row_lab[r]="DD from peak";
   row_val[r]=DoubleToString(dd_from_peak,2)+" "+acc_ccy+"   "+DoubleToString(pct_from_peak,2)+" %";
   row_clr[r]=dd_peak_clr; r++;
   row_lab[r]="Warning at";
   row_val[r]=DoubleToString(InpWarnPercent,2)+" %"+
              (InpWarnMoney>0.0 ? "  or  "+DoubleToString(InpWarnMoney,2)+" "+acc_ccy : "");
   row_clr[r]=InpColorValue; r++;
   row_lab[r]="Critical at";
   row_val[r]=DoubleToString(InpCritPercent,2)+" %"+
              (InpCritMoney>0.0 ? "  or  "+DoubleToString(InpCritMoney,2)+" "+acc_ccy : "");
   row_clr[r]=InpColorValue; r++;
   row_lab[r]="Used for alerts";
   row_val[r]=DoubleToString(use_pct,2)+" %   "+DoubleToString(use_money,2)+" "+acc_ccy;
   row_clr[r]=st_clr; r++;

   const string title="Daily Drawdown Guard";
   const string foot="This utility does not place, modify or close orders.";
   const int pad=16;
   const int gap=16;
   int label_w=0,value_w=0,line_h=InpFontSize+6;
   for(int i=0;i<r;i++)
     {
      const int lw=TextPx(row_lab[i],InpFontSize);
      const int vw=TextPx(row_val[i],InpFontSize);
      if(lw>label_w)
         label_w=lw;
      if(vw>value_w)
         value_w=vw;
     }
   int inner=label_w+gap+value_w;
   const int title_w=TextPx(title,InpFontSize+1);
   const int foot_w=TextPx(foot,InpFontSize);
   if(title_w>inner)
      inner=title_w;
   if(foot_w>inner)
      inner=foot_w;
   int width=pad+inner+pad;
   if(width<420)
      width=420;
   const int y_foot=InpOffsetY+10+(r+1)*line_h+4;
   const int foot_h=TextPxH(foot,InpFontSize);
   const int height=(y_foot-InpOffsetY)+foot_h+10;

   const string bg=DDG_PREFIX+"bg";
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
   int x_title,x_label,x_value;
   if(right)
     {
      x_title=InpOffsetX+pad;
      x_value=InpOffsetX+pad;
      x_label=InpOffsetX+pad+value_w+gap;
     }
   else
     {
      x_title=InpOffsetX+pad;
      x_label=InpOffsetX+pad;
      x_value=InpOffsetX+pad+label_w+gap;
     }
   CreateLabel(DDG_PREFIX+"title",x_title,InpOffsetY+8,title,InpColorTitle,InpFontSize+1);

   for(int i=0;i<r;i++)
      SetRow(i,row_lab[i],row_val[i],row_clr[i],x_label,x_value,line_h);

   CreateLabel(DDG_PREFIX+"foot",x_title,y_foot,foot,InpColorLabel,InpFontSize);

   ChartRedraw(0);
  }
//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
  {
   if(InpWarnPercent<0.0 || InpWarnPercent>100.0)
      return(INIT_PARAMETERS_INCORRECT);
   if(InpCritPercent<0.0 || InpCritPercent>100.0)
      return(INIT_PARAMETERS_INCORRECT);
   if(InpWarnMoney<0.0 || InpCritMoney<0.0)
      return(INIT_PARAMETERS_INCORRECT);
   if(InpResetHour<0 || InpResetHour>23 || InpResetMinute<0 || InpResetMinute>59)
      return(INIT_PARAMETERS_INCORRECT);
   if(InpFontSize<7 || InpFontSize>16)
      return(INIT_PARAMETERS_INCORRECT);
   if(InpCorner<0 || InpCorner>3)
      return(INIT_PARAMETERS_INCORRECT);
   if(InpCritPercent>0.0 && InpWarnPercent>InpCritPercent)
      return(INIT_PARAMETERS_INCORRECT);
   if(InpCritMoney>0.0 && InpWarnMoney>InpCritMoney)
      return(INIT_PARAMETERS_INCORRECT);

   LoadState();
   if(!EventSetMillisecondTimer(500))
     {
      Print("Daily Drawdown Guard: millisecond timer was not accepted, using a 1-second timer.");
      EventSetTimer(1);
     }
   g_timer_ok=1;
   Refresh();
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
   Refresh();
  }
//+------------------------------------------------------------------+
//| Timer                                                            |
//+------------------------------------------------------------------+
void OnTimer()
  {
   Refresh();
  }
//+------------------------------------------------------------------+
//| Chart event                                                      |
//+------------------------------------------------------------------+
void OnChartEvent(const int id,const long &lparam,const double &dparam,const string &sparam)
  {
   if(id==CHARTEVENT_CHART_CHANGE && lparam>=0 && dparam>=0.0 && sparam!="~")
      Refresh();
  }
//+------------------------------------------------------------------+
