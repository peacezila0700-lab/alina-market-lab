//+------------------------------------------------------------------+
//|                                       MZ_Smart_Trail_Manager.mq5 |
//|                                     Copyright 2026, Mazin Haqi   |
//|                          https://www.mql5.com/en/users/mazin55   |
//+------------------------------------------------------------------+
#property copyright   "Copyright 2026, Mazin Haqi"
#property link        "https://www.mql5.com/en/users/mazin55"
#property version     "1.40"
#property description "Smart trade manager: Break-even + Stepped trailing stop + Progressive profit lock."
#property description "Manages manual trades or trades of any EA (magic filter). It NEVER opens trades."
#property description "Bilingual on-chart panel: English / Arabic."

#include <Trade\Trade.mqh>

//--- enums
enum ENUM_MZ_FILTER
  {
   MZ_ALL    = 0, // All positions on this symbol
   MZ_MANUAL = 1, // Manual positions only (magic = 0)
   MZ_MAGIC  = 2  // Only the magic number below
  };
enum ENUM_MZ_LANG
  {
   MZ_EN   = 0, // English
   MZ_AR   = 1, // Arabic
   MZ_BOTH = 2  // English + Arabic
  };

enum ENUM_MZ_UNITS
  {
   MZ_UNITS_ATR   = 0, // ATR multiples (works on every symbol)
   MZ_UNITS_PRICE = 1  // Price units (1.0 on XAUUSD = 1$, 0.0010 on EURUSD = 10 pips)
  };

//--- inputs
input group "=== Distance units | وحدة المسافات ==="
input ENUM_MZ_UNITS   InpUnits     = MZ_UNITS_ATR; // Distances below are in
input ENUM_TIMEFRAMES InpATRTF     = PERIOD_M15;   // ATR timeframe
input int             InpATRPeriod = 14;           // ATR period

input group "=== Positions to manage | الصفقات المُدارة ==="
input ENUM_MZ_FILTER InpFilter = MZ_ALL;   // Positions to manage
input long           InpMagic  = 0;        // Magic number (when filter = magic)

input group "=== Initial stop loss | الستوب الأولي ==="
input bool   InpSetInitialSL = false;      // Add SL to positions that have none
input double InpInitialSL    = 1.5;        // Initial SL distance

input group "=== Break-even | نقطة التعادل ==="
input bool   InpUseBE     = true;          // Use break-even
input double InpBETrigger = 0.5;           // Trigger: profit distance
input double InpBEOffset  = 0.05;          // SL = entry + offset

input group "=== Stepped trailing stop | الستوب المتحرك المتدرج ==="
input bool   InpUseTrail   = true;         // Use trailing stop
input double InpTrailStart = 0.8;          // Start after profit distance
input double InpTrailDist  = 0.5;          // Distance behind best price
input double InpTrailStep  = 0.1;          // Move SL only in steps of

input group "=== Progressive profit lock | حجز ربح متصاعد (account currency) ==="
input bool   InpUseLock = true;            // Lock a growing % of the best profit
input double InpLvl1    = 10.0;            // Level 1: best profit reaches (money)
input double InpKeep1   = 40.0;            // Level 1: keep %
input double InpLvl2    = 30.0;            // Level 2: best profit reaches (money)
input double InpKeep2   = 60.0;            // Level 2: keep %
input double InpLvl3    = 60.0;            // Level 3: best profit reaches (money)
input double InpKeep3   = 75.0;            // Level 3: keep %
input double InpLvl4    = 100.0;           // Level 4: best profit reaches (0 = off)
input double InpKeep4   = 85.0;            // Level 4: keep %

input group "=== Strategy Tester demo | تجربة في التستر ==="
input bool   InpTesterDemo = true;         // In Strategy Tester only: open demo trades to show the manager
input double InpDemoLot    = 0.01;         // Demo trade lot (tester only)

input group "=== Panel | اللوحة ==="
input bool         InpShowPanel = true;    // Show panel
input ENUM_MZ_LANG InpLang      = MZ_BOTH; // Panel language
input int          InpPanelX    = 10;      // Panel X (px)
input int          InpPanelY    = 30;      // Panel Y (px)
input int          InpFontSize  = 9;       // Font size

//--- state
CTrade   trade;
bool     gEnabled   = true;
bool     gShowPanel = false;
ulong    gTk[];
double   gBest[];
datetime gModifyPause = 0;   // no SL modifications before this time (after a rejection)
string   PFX        = "MZSTM_";
int      gManaged   = 0;
double   gFloat     = 0.0;
double   gLocked    = 0.0;
int      gAtrHandle = INVALID_HANDLE;
double   gUnit      = 0.0;   // price value of 1.0 input unit (ATR or 1.0)

//+------------------------------------------------------------------+
//| Refresh distance unit: ATR value or 1.0 (price mode)            |
//+------------------------------------------------------------------+
bool UpdateUnit()
  {
   if(InpUnits==MZ_UNITS_PRICE)
     {
      gUnit=1.0;
      return true;
     }
   double b[1];
   if(gAtrHandle!=INVALID_HANDLE && CopyBuffer(gAtrHandle,0,1,1,b)==1 && b[0]>0)
      gUnit=b[0];
   return (gUnit>0);
  }

//+------------------------------------------------------------------+
//| Convert an input distance to price                              |
//+------------------------------------------------------------------+
double U(const double x)
  {
   return x*gUnit;
  }

//+------------------------------------------------------------------+
//| Helpers                                                          |
//+------------------------------------------------------------------+
string T(const string en,const string ar)
  {
   if(InpLang==MZ_EN) return en;
   if(InpLang==MZ_AR) return ar;
   return en+" | "+ar;
  }

//+------------------------------------------------------------------+
//| Panel value text in the selected language                       |
//+------------------------------------------------------------------+
string V(const string en,const string ar)
  {
   return (InpLang==MZ_AR ? ar : en);
  }

//+------------------------------------------------------------------+
//| Normalize a price to symbol digits                              |
//+------------------------------------------------------------------+
double NormPrice(const double p)
  {
   return NormalizeDouble(p,_Digits);
  }

//+------------------------------------------------------------------+
//| Price distance as text without trailing zeros                   |
//+------------------------------------------------------------------+
string Px(const double v)
  {
   string s=DoubleToString(v,_Digits);
   if(StringFind(s,".")<0) return s;
   int n=StringLen(s);
   while(n>1 && StringGetCharacter(s,n-1)=='0') n--;
   if(StringGetCharacter(s,n-1)=='.') n--;
   return StringSubstr(s,0,n);
  }

//+------------------------------------------------------------------+
//| Money value as text with sign and currency                      |
//+------------------------------------------------------------------+
string Money(const double v)
  {
   return (v>=0 ? "+" : "")+DoubleToString(v,2)+" "+AccountInfoString(ACCOUNT_CURRENCY);
  }

//+------------------------------------------------------------------+
//| Minimum SL distance allowed by the broker                       |
//+------------------------------------------------------------------+
double MinDist()
  {
   long a=SymbolInfoInteger(_Symbol,SYMBOL_TRADE_STOPS_LEVEL);
   long b=SymbolInfoInteger(_Symbol,SYMBOL_TRADE_FREEZE_LEVEL);
   long lv=(a>b ? a : b);
   return (double)(lv+1)*_Point;
  }

//+------------------------------------------------------------------+
//| Trade session open now, at least edgeSec away from its edges     |
//+------------------------------------------------------------------+
bool SessionCheck(const int edgeSec)
  {
   MqlDateTime t;
   TimeToStruct(TimeCurrent(),t);
   int sec=t.hour*3600+t.min*60+t.sec;

   datetime from=0,to=0;
   bool found=false;
   for(uint i=0;i<10;i++)
     {
      if(!SymbolInfoSessionTrade(_Symbol,(ENUM_DAY_OF_WEEK)t.day_of_week,i,from,to)) break;
      found=true;
      int f=(int)(from%86400);
      int e=(int)(to%86400);
      if(e==0) e=86400;                     // session ends at 24:00
      if(sec>=f+edgeSec && sec<=e-edgeSec) return true;
     }
   //--- no session table available: assume open
   return !found;
  }

//+------------------------------------------------------------------+
//| Check if the selected position must be managed                  |
//+------------------------------------------------------------------+
bool IsMine()
  {
   if(PositionGetString(POSITION_SYMBOL)!=_Symbol) return false;
   long mg=PositionGetInteger(POSITION_MAGIC);
   if(InpFilter==MZ_MANUAL) return (mg==0);
   if(InpFilter==MZ_MAGIC)  return (mg==InpMagic);
   return true;
  }

//+------------------------------------------------------------------+
//| Index of a ticket in the best-profit memory                     |
//+------------------------------------------------------------------+
int Slot(const ulong tk)
  {
   int n=ArraySize(gTk);
   for(int i=0;i<n;i++)
      if(gTk[i]==tk) return i;
   ArrayResize(gTk,n+1);
   ArrayResize(gBest,n+1);
   gTk[n]=tk;
   gBest[n]=0.0;
   return n;
  }

//+------------------------------------------------------------------+
//| Remove closed positions from the memory                         |
//+------------------------------------------------------------------+
void CleanSlots()
  {
   for(int i=ArraySize(gTk)-1;i>=0;i--)
     {
      if(PositionSelectByTicket(gTk[i])) continue;
      int last=ArraySize(gTk)-1;
      gTk[i]=gTk[last];
      gBest[i]=gBest[last];
      ArrayResize(gTk,last);
      ArrayResize(gBest,last);
     }
  }

//+------------------------------------------------------------------+
//| Percent of best profit to lock for a money level                |
//+------------------------------------------------------------------+
double KeepPct(const double bestMoney)
  {
   double k=0.0;
   if(InpLvl1>0 && bestMoney>=InpLvl1) k=InpKeep1;
   if(InpLvl2>0 && bestMoney>=InpLvl2) k=InpKeep2;
   if(InpLvl3>0 && bestMoney>=InpLvl3) k=InpKeep3;
   if(InpLvl4>0 && bestMoney>=InpLvl4) k=InpKeep4;
   return MathMin(k,99.0);
  }

//+------------------------------------------------------------------+
//| Core: manage stop loss of every matching position                |
//+------------------------------------------------------------------+
void ManageAll()
  {
   double bid=SymbolInfoDouble(_Symbol,SYMBOL_BID);
   double ask=SymbolInfoDouble(_Symbol,SYMBOL_ASK);
   if(bid<=0 || ask<=0) return;

   double tv=SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_VALUE);
   double ts=SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_SIZE);
   double minD=MinDist();
   bool   unitOK=UpdateUnit();   // false only while ATR data is still loading
   bool   canModify=(TimeCurrent()>=gModifyPause) && SessionCheck(300)
                    && SymbolInfoInteger(_Symbol,SYMBOL_TRADE_MODE)!=SYMBOL_TRADE_MODE_DISABLED;

   gManaged=0;
   gFloat=0.0;
   gLocked=0.0;

   for(int i=PositionsTotal()-1;i>=0;i--)
     {
      ulong tk=PositionGetTicket(i);
      if(tk==0 || !IsMine()) continue;
      gManaged++;

      bool   buy=(PositionGetInteger(POSITION_TYPE)==POSITION_TYPE_BUY);
      double op =PositionGetDouble(POSITION_PRICE_OPEN);
      double sl =PositionGetDouble(POSITION_SL);
      double tp =PositionGetDouble(POSITION_TP);
      double vol=PositionGetDouble(POSITION_VOLUME);
      double mpp=(ts>0 ? vol*tv/ts : 0.0);           // money per 1.0 price move

      gFloat+=PositionGetDouble(POSITION_PROFIT)+PositionGetDouble(POSITION_SWAP);
      if(sl>0) gLocked+=(buy ? sl-op : op-sl)*mpp;

      if(!gEnabled) continue;

      //--- best profit reached (price distance)
      double prof=(buy ? bid-op : op-ask);
      int s=Slot(tk);
      if(prof>gBest[s]) gBest[s]=prof;
      double best=gBest[s];

      bool   has=false;
      double want=0.0;                               // wanted SL distance from entry (profit side)

      //--- 1) break-even
      if(unitOK && InpUseBE && InpBETrigger>0 && best>=U(InpBETrigger))
        {
         want=U(InpBEOffset);
         has=true;
        }

      //--- 2) stepped trailing stop
      if(unitOK && InpUseTrail && InpTrailDist>0 && best>=U(InpTrailStart))
        {
         double raw=best-U(InpTrailDist);
         double st=U(InpTrailStep);
         if(st>0) raw=MathFloor(raw/st+1e-9)*st;
         if(!has || raw>want)
           {
            want=raw;
            has=true;
           }
        }

      //--- 3) progressive profit lock
      if(InpUseLock && mpp>0)
        {
         double k=KeepPct(best*mpp);
         if(k>0)
           {
            double lk=best*k/100.0;
            if(!has || lk>want)
              {
               want=lk;
               has=true;
              }
           }
        }

      //--- build the new stop
      double newSL=0.0;
      if(has)
         newSL=(buy ? op+want : op-want);
      else if(unitOK && sl==0 && InpSetInitialSL && InpInitialSL>0)
         newSL=(buy ? op-U(InpInitialSL) : op+U(InpInitialSL));
      if(newSL<=0) continue;

      //--- respect broker stop / freeze level
      if(buy  && newSL>bid-minD) newSL=bid-minD;
      if(!buy && newSL<ask+minD) newSL=ask+minD;
      newSL=NormPrice(newSL);

      //--- only ever move the stop in the trader's favour
      bool better=(sl==0) || (buy ? newSL>sl+_Point : newSL<sl-_Point);
      if(!better) continue;

      //--- market closed / near session edges, or paused after a rejection
      if(!canModify) continue;

      if(!trade.PositionModify(tk,newSL,tp))
        {
         gModifyPause=TimeCurrent()+60;      // wait 1 minute before trying again
         PrintFormat("MZ Trail: modify #%I64u failed: %u %s - retry in 60 s",
                     tk,trade.ResultRetcode(),trade.ResultRetcodeDescription());
         canModify=false;
        }
     }
  }

//+------------------------------------------------------------------+
//| Panel                                                            |
//+------------------------------------------------------------------+
void Rect(const string name,const int x,const int y,const int w,const int h,const color bg,const color border)
  {
   string nm=PFX+name;
   if(ObjectFind(0,nm)<0)
     {
      ObjectCreate(0,nm,OBJ_RECTANGLE_LABEL,0,0,0);
      ObjectSetInteger(0,nm,OBJPROP_CORNER,CORNER_LEFT_UPPER);
      ObjectSetInteger(0,nm,OBJPROP_BORDER_TYPE,BORDER_FLAT);
      ObjectSetInteger(0,nm,OBJPROP_SELECTABLE,false);
      ObjectSetInteger(0,nm,OBJPROP_HIDDEN,true);
      ObjectSetInteger(0,nm,OBJPROP_BACK,false);
     }
   ObjectSetInteger(0,nm,OBJPROP_XDISTANCE,x);
   ObjectSetInteger(0,nm,OBJPROP_YDISTANCE,y);
   ObjectSetInteger(0,nm,OBJPROP_XSIZE,w);
   ObjectSetInteger(0,nm,OBJPROP_YSIZE,h);
   ObjectSetInteger(0,nm,OBJPROP_BGCOLOR,bg);
   ObjectSetInteger(0,nm,OBJPROP_COLOR,border);
  }

//+------------------------------------------------------------------+
//| Create / update a text label                                    |
//+------------------------------------------------------------------+
void Label(const string name,const int x,const int y,const string text,const color clr,
           const int size,const bool bold,const ENUM_ANCHOR_POINT anchor)
  {
   string nm=PFX+name;
   if(ObjectFind(0,nm)<0)
     {
      ObjectCreate(0,nm,OBJ_LABEL,0,0,0);
      ObjectSetInteger(0,nm,OBJPROP_CORNER,CORNER_LEFT_UPPER);
      ObjectSetInteger(0,nm,OBJPROP_SELECTABLE,false);
      ObjectSetInteger(0,nm,OBJPROP_HIDDEN,true);
     }
   ObjectSetInteger(0,nm,OBJPROP_ANCHOR,anchor);
   ObjectSetInteger(0,nm,OBJPROP_XDISTANCE,x);
   ObjectSetInteger(0,nm,OBJPROP_YDISTANCE,y);
   ObjectSetString(0,nm,OBJPROP_TEXT,text);
   ObjectSetString(0,nm,OBJPROP_FONT,(bold ? "Arial Bold" : "Arial"));
   ObjectSetInteger(0,nm,OBJPROP_FONTSIZE,size);
   ObjectSetInteger(0,nm,OBJPROP_COLOR,clr);
  }

//+------------------------------------------------------------------+
//| Create / update a button                                        |
//+------------------------------------------------------------------+
void Button(const string name,const int x,const int y,const int w,const int h,const string text,const color bg)
  {
   string nm=PFX+name;
   if(ObjectFind(0,nm)<0)
     {
      ObjectCreate(0,nm,OBJ_BUTTON,0,0,0);
      ObjectSetInteger(0,nm,OBJPROP_CORNER,CORNER_LEFT_UPPER);
      ObjectSetInteger(0,nm,OBJPROP_SELECTABLE,false);
      ObjectSetInteger(0,nm,OBJPROP_HIDDEN,true);
      ObjectSetString(0,nm,OBJPROP_FONT,"Arial Bold");
      ObjectSetInteger(0,nm,OBJPROP_COLOR,clrWhite);
      ObjectSetInteger(0,nm,OBJPROP_BORDER_COLOR,clrSilver);
     }
   ObjectSetInteger(0,nm,OBJPROP_XDISTANCE,x);
   ObjectSetInteger(0,nm,OBJPROP_YDISTANCE,y);
   ObjectSetInteger(0,nm,OBJPROP_XSIZE,w);
   ObjectSetInteger(0,nm,OBJPROP_YSIZE,h);
   ObjectSetInteger(0,nm,OBJPROP_FONTSIZE,InpFontSize);
   ObjectSetInteger(0,nm,OBJPROP_BGCOLOR,bg);
   ObjectSetString(0,nm,OBJPROP_TEXT,text);
   ObjectSetInteger(0,nm,OBJPROP_STATE,false);
  }

//+------------------------------------------------------------------+
//| One panel row: label on the left, value on the right            |
//+------------------------------------------------------------------+
void Row(const int idx,const int x,const int y,const int w,const int pad,
         const string lab,const string val,const color vc)
  {
   color lc=C'150,160,185';
   Label("l"+IntegerToString(idx),x+pad,y,lab,lc,InpFontSize,false,ANCHOR_LEFT_UPPER);
   Label("v"+IntegerToString(idx),x+w-pad,y,val,vc,InpFontSize,true,ANCHOR_RIGHT_UPPER);
  }

//+------------------------------------------------------------------+
//| Draw the on-chart panel                                         |
//+------------------------------------------------------------------+
void DrawPanel()
  {
   if(!gShowPanel) return;

   //--- fonts are in points but positions are in pixels: scale pixels by screen DPI
   double S=MathMax(1.0,TerminalInfoInteger(TERMINAL_SCREEN_DPI)/96.0);
   int fs =MathMax(6,InpFontSize);
   int lh =(int)MathRound(fs*2.2*S);
   int pad=(int)MathRound(10*S);
   int W  =(int)MathRound((InpLang==MZ_BOTH ? 430 : 290)*S);
   int X  =InpPanelX;
   int Y  =InpPanelY;
   int rows=9;
   int H  =lh*(rows+1)+(int)(lh*1.3)+pad*2;

   color bg  =C'16,20,30';
   color head=C'110,80,10';
   color acc =C'255,196,40';
   color txt =C'235,240,250';
   color grn =C'0,220,120';
   color red =C'255,80,80';

   Rect("bg",X,Y,W,H,bg,acc);
   Rect("hd",X+1,Y+1,W-2,lh,head,head);
   Label("title",X+W/2,Y+(lh-fs*2)/2,"MZ  SMART  TRAIL",acc,fs+1,true,ANCHOR_UPPER);

   int y=Y+lh+pad/2;
   int r=0;

   Row(r++,X,y,W,pad,T("Status","الحالة"),
       (gEnabled ? V("ACTIVE","يعمل") : V("PAUSED","متوقف")),(gEnabled ? grn : red));          y+=lh;
   Row(r++,X,y,W,pad,T("Positions","الصفقات"),IntegerToString(gManaged),txt);                  y+=lh;
   Row(r++,X,y,W,pad,T("Floating P/L","الربح العائم"),Money(gFloat),(gFloat>=0 ? grn : red));  y+=lh;
   Row(r++,X,y,W,pad,T("Locked by SL","مضمون بالستوب"),
       (gManaged>0 ? Money(gLocked) : "-"),(gLocked>=0 ? grn : red));                          y+=lh;
   Row(r++,X,y,W,pad,T("Unit","الوحدة"),
       (InpUnits==MZ_UNITS_ATR ? "ATR "+Px(gUnit) : V("Price","سعر")),txt);                   y+=lh;
   Row(r++,X,y,W,pad,T("Break-even","التعادل"),
       (InpUseBE ? Px(U(InpBETrigger))+" > +"+Px(U(InpBEOffset)) : V("OFF","إيقاف")),txt);     y+=lh;
   Row(r++,X,y,W,pad,T("Trailing","الستوب المتحرك"),
       (InpUseTrail ? Px(U(InpTrailStart))+" / "+Px(U(InpTrailDist))+" / "+Px(U(InpTrailStep)) : V("OFF","إيقاف")),txt); y+=lh;
   Row(r++,X,y,W,pad,T("Profit lock","حجز الربح"),
       (InpUseLock ? V("ON","تشغيل") : V("OFF","إيقاف")),txt);                                 y+=lh;
   string flt=(InpFilter==MZ_ALL ? V("All","الكل") :
               InpFilter==MZ_MANUAL ? V("Manual","يدوية") : "Magic "+IntegerToString(InpMagic));
   Row(r++,X,y,W,pad,T("Filter","الفلتر"),flt,txt);                                            y+=lh;

   y+=pad/2;
   Button("btn",X+pad,y,W-2*pad,(int)(lh*1.1),
          (gEnabled ? T("PAUSE","إيقاف مؤقت") : T("START","تشغيل")),
          (gEnabled ? C'150,50,60' : C'20,130,70'));
   ChartRedraw(0);
  }

//+------------------------------------------------------------------+
//| Events                                                           |
//+------------------------------------------------------------------+
int OnInit()
  {
   if(InpInitialSL<0 || InpBETrigger<0 || InpTrailStart<0 || InpTrailDist<0 || InpTrailStep<0)
     {
      Print("MZ Trail: negative distances are not allowed");
      return INIT_PARAMETERS_INCORRECT;
     }
   trade.SetDeviationInPoints(20);
   if(InpUnits==MZ_UNITS_ATR)
     {
      gAtrHandle=iATR(_Symbol,InpATRTF,MathMax(1,InpATRPeriod));
      if(gAtrHandle==INVALID_HANDLE)
        {
         Print("MZ Trail: cannot create ATR indicator");
         return INIT_FAILED;
        }
     }
   bool visual=!(MQLInfoInteger(MQL_TESTER) && !MQLInfoInteger(MQL_VISUAL_MODE));
   gShowPanel=(InpShowPanel && visual);
   EventSetTimer(1);
   ManageAll();
   DrawPanel();
   return INIT_SUCCEEDED;
  }

//+------------------------------------------------------------------+
//| Expert deinitialization function                                |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   EventKillTimer();
   if(gAtrHandle!=INVALID_HANDLE) IndicatorRelease(gAtrHandle);
   ObjectsDeleteAll(0,PFX);
   ChartRedraw(0);
  }

double NormalizeLot(const double wanted);
bool   CheckMoney(const double lot,const bool buy,const double price);

//+------------------------------------------------------------------+
//| Trade session open now, away from session edges and midnight     |
//+------------------------------------------------------------------+
bool SessionOpen()
  {
   MqlDateTime t;
   TimeToStruct(TimeCurrent(),t);
   //--- rollover hour: brokers often close or widen spreads around midnight
   if(t.hour==23 || t.hour==0) return false;
   return SessionCheck(600);
  }

//+------------------------------------------------------------------+
//| Strategy Tester only: open demo trades to manage                |
//+------------------------------------------------------------------+
void TesterDemo()
  {
   if(!InpTesterDemo || !MQLInfoInteger(MQL_TESTER)) return;
   static datetime lastBar=0;
   datetime bar=iTime(_Symbol,PERIOD_M15,0);
   if(bar==0 || bar==lastBar) return;
   lastBar=bar;
   if(gManaged>0 || !UpdateUnit()) return;

   //--- trading allowed on this symbol and the session open?
   long mode=SymbolInfoInteger(_Symbol,SYMBOL_TRADE_MODE);
   if(mode!=SYMBOL_TRADE_MODE_FULL) return;
   if(!SessionOpen()) return;

   //--- skip rollover / wide spread moments
   double spread=SymbolInfoDouble(_Symbol,SYMBOL_ASK)-SymbolInfoDouble(_Symbol,SYMBOL_BID);
   if(gUnit>0 && spread>gUnit*0.5) return;

   bool   buy=(iClose(_Symbol,PERIOD_M15,1)>=iOpen(_Symbol,PERIOD_M15,1));
   double lot=NormalizeLot(InpDemoLot);
   if(lot<=0) return;

   double price=(buy ? SymbolInfoDouble(_Symbol,SYMBOL_ASK) : SymbolInfoDouble(_Symbol,SYMBOL_BID));
   if(price<=0) return;
   if(!CheckMoney(lot,buy,price)) return;

   //--- stop loss: ATR based, never closer than broker stop level
   double sld=MathMax(U(InpInitialSL>0 ? InpInitialSL : 1.5),MinDist()*2.0);
   double sl =NormPrice(buy ? price-sld : price+sld);

   if(buy) trade.Buy(lot,_Symbol,price,sl,0,"MZ demo");
   else    trade.Sell(lot,_Symbol,price,sl,0,"MZ demo");
  }

//+------------------------------------------------------------------+
//| Lot normalized to symbol min / max / step (0 = cannot trade)     |
//+------------------------------------------------------------------+
double NormalizeLot(const double wanted)
  {
   double mn=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MIN);
   double mx=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MAX);
   double st=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_STEP);
   if(mn<=0 || st<=0) return 0.0;
   double lot=MathMax(mn,wanted);
   lot=MathFloor(lot/st+1e-9)*st;
   if(lot<mn) lot=mn;
   if(mx>0 && lot>mx) lot=mx;
   //--- respect the total volume limit of the symbol, if any
   double lim=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_LIMIT);
   if(lim>0 && lot>lim) return 0.0;
   int digits=(int)MathMax(0,MathCeil(-MathLog10(st)));
   return NormalizeDouble(lot,digits);
  }

//+------------------------------------------------------------------+
//| Enough free margin for this lot?                                 |
//+------------------------------------------------------------------+
bool CheckMoney(const double lot,const bool buy,const double price)
  {
   double margin=0.0;
   ENUM_ORDER_TYPE type=(buy ? ORDER_TYPE_BUY : ORDER_TYPE_SELL);
   if(!OrderCalcMargin(type,_Symbol,lot,price,margin)) return false;
   return (margin<AccountInfoDouble(ACCOUNT_MARGIN_FREE));
  }

//+------------------------------------------------------------------+
//| Expert tick function                                            |
//+------------------------------------------------------------------+
void OnTick()
  {
   ManageAll();
   TesterDemo();
  }

//+------------------------------------------------------------------+
//| Timer function: cleanup, manage, redraw panel                   |
//+------------------------------------------------------------------+
void OnTimer()
  {
   CleanSlots();
   ManageAll();
   DrawPanel();
  }

//+------------------------------------------------------------------+
//| Chart event function: PAUSE / START button                      |
//+------------------------------------------------------------------+
void OnChartEvent(const int id,const long &lparam,const double &dparam,const string &sparam)
  {
   if(id==CHARTEVENT_OBJECT_CLICK && sparam==PFX+"btn")
     {
      gEnabled=!gEnabled;
      PrintFormat("MZ Trail: %s",(gEnabled ? "started" : "paused"));
      DrawPanel();
     }
  }
//+------------------------------------------------------------------+