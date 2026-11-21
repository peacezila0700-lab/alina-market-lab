//+------------------------------------------------------------------+
//|  Supertrend (TradingView style) for MT5             © Eye Algo   |
//+------------------------------------------------------------------+
#property copyright   "Eye Algo"
#property version     "1.00"
#property description "Supertrend with the same calculation, colours and Buy/Sell labels as the classic TradingView Supertrend. ATR period, multiplier, source, RMA/SMA ATR, trend highlight, popup / sound / push alerts on bar close."
#property indicator_chart_window
#property indicator_buffers 10
#property indicator_plots   5

#property indicator_label1  "Highlight"
#property indicator_type1   DRAW_FILLING
#property indicator_color1  C'70,22,22',C'14,62,38'

#property indicator_label2  "Up trend"
#property indicator_type2   DRAW_LINE
#property indicator_color2  clrLime
#property indicator_width2  2

#property indicator_label3  "Down trend"
#property indicator_type3   DRAW_LINE
#property indicator_color3  clrRed
#property indicator_width3  2

#property indicator_label4  "Buy"
#property indicator_type4   DRAW_ARROW
#property indicator_color4  clrLime
#property indicator_width4  1

#property indicator_label5  "Sell"
#property indicator_type5   DRAW_ARROW
#property indicator_color5  clrRed
#property indicator_width5  1

enum ENUM_ST_SRC
  {
   SRC_HL2   = 0, // hl2
   SRC_CLOSE = 1, // close
   SRC_HLC3  = 2, // hlc3
   SRC_OHLC4 = 3  // ohlc4
  };

input int         InpAtrPeriod = 10;      // ATR period
input ENUM_ST_SRC InpSource    = SRC_HL2; // Source
input double      InpMult      = 3.0;     // ATR multiplier
input bool        InpRma       = true;    // Change ATR calculation method (RMA)
input bool        InpShowSig   = true;    // Show Buy/Sell labels
input bool        InpHighlight = true;    // Highlight trend
input bool        InpAlertPopup = true;   // Popup alert
input bool        InpAlertSound = false;  // Sound alert
input string      InpSoundFile  = "alert.wav"; // Sound file
input bool        InpAlertPush  = false;  // Push notification

double bFillA[], bFillB[], bUp[], bDn[], bBuy[], bSell[];
double cTrend[], cUpBand[], cDnBand[], cAtr[];
datetime g_lastAlert = 0;
string   g_pre = "EASTI_";

int OnInit()
  {
   SetIndexBuffer(0, bFillA, INDICATOR_DATA);
   SetIndexBuffer(1, bFillB, INDICATOR_DATA);
   SetIndexBuffer(2, bUp, INDICATOR_DATA);
   SetIndexBuffer(3, bDn, INDICATOR_DATA);
   SetIndexBuffer(4, bBuy, INDICATOR_DATA);
   SetIndexBuffer(5, bSell, INDICATOR_DATA);
   SetIndexBuffer(6, cTrend, INDICATOR_CALCULATIONS);
   SetIndexBuffer(7, cUpBand, INDICATOR_CALCULATIONS);
   SetIndexBuffer(8, cDnBand, INDICATOR_CALCULATIONS);
   SetIndexBuffer(9, cAtr, INDICATOR_CALCULATIONS);
   for(int p = 0; p < 5; p++) PlotIndexSetDouble(p, PLOT_EMPTY_VALUE, EMPTY_VALUE);
   PlotIndexSetInteger(3, PLOT_ARROW, 233);
   PlotIndexSetInteger(4, PLOT_ARROW, 234);
   PlotIndexSetInteger(3, PLOT_ARROW_SHIFT, 10);
   PlotIndexSetInteger(4, PLOT_ARROW_SHIFT, -10);
   g_pre = "EASTI_" + IntegerToString(InpAtrPeriod) + "_" + DoubleToString(InpMult, 1) + "_";
   IndicatorSetString(INDICATOR_SHORTNAME, StringFormat("Supertrend (%d, %.1f)", InpAtrPeriod, InpMult));
   IndicatorSetInteger(INDICATOR_DIGITS, _Digits);
   return INIT_SUCCEEDED;
  }

void OnDeinit(const int reason) { ObjectsDeleteAll(0, g_pre); }

double Src(int i, const double &o[], const double &h[], const double &l[], const double &c[])
  {
   switch(InpSource)
     {
      case SRC_CLOSE: return c[i];
      case SRC_HLC3:  return (h[i] + l[i] + c[i]) / 3.0;
      case SRC_OHLC4: return (o[i] + h[i] + l[i] + c[i]) / 4.0;
     }
   return (h[i] + l[i]) / 2.0;
  }

void Label(int i, bool buy, const datetime &t[], double price)
  {
   string nm = g_pre + (string)(long)t[i];
   if(ObjectFind(0, nm) >= 0) return;
   ObjectCreate(0, nm, OBJ_TEXT, 0, t[i], price);
   ObjectSetString(0, nm, OBJPROP_TEXT, buy ? "Buy" : "Sell");
   ObjectSetString(0, nm, OBJPROP_FONT, "Arial Bold");
   ObjectSetInteger(0, nm, OBJPROP_FONTSIZE, 8);
   ObjectSetInteger(0, nm, OBJPROP_COLOR, buy ? clrLime : clrRed);
   ObjectSetInteger(0, nm, OBJPROP_ANCHOR, buy ? ANCHOR_UPPER : ANCHOR_LOWER);
   ObjectSetInteger(0, nm, OBJPROP_SELECTABLE, false);
  }

int OnCalculate(const int rates_total, const int prev_calculated, const datetime &time[], const double &open[],
                const double &high[], const double &low[], const double &close[], const long &tick_volume[],
                const long &volume[], const int &spread[])
  {
   if(rates_total < InpAtrPeriod + 2) return 0;
   ArraySetAsSeries(time, false);
   ArraySetAsSeries(open, false);
   ArraySetAsSeries(high, false);
   ArraySetAsSeries(low, false);
   ArraySetAsSeries(close, false);

   int start = prev_calculated > 1 ? prev_calculated - 1 : 0;
   if(start == 0) ObjectsDeleteAll(0, g_pre);

   for(int i = start; i < rates_total; i++)
     {
      // ATR
      double tr = high[i] - low[i];
      if(i > 0) tr = MathMax(tr, MathMax(MathAbs(high[i] - close[i - 1]), MathAbs(low[i] - close[i - 1])));
      if(InpRma)
        {
         if(i < InpAtrPeriod)
           {
            double s = 0;
            for(int k = 0; k <= i; k++)
              {
               double t2 = high[k] - low[k];
               if(k > 0) t2 = MathMax(t2, MathMax(MathAbs(high[k] - close[k - 1]), MathAbs(low[k] - close[k - 1])));
               s += t2;
              }
            cAtr[i] = s / (i + 1);
           }
         else
            cAtr[i] = (cAtr[i - 1] * (InpAtrPeriod - 1) + tr) / InpAtrPeriod;
        }
      else
        {
         double s = 0;
         int cnt = 0;
         for(int k = i; k >= 0 && k > i - InpAtrPeriod; k--)
           {
            double t2 = high[k] - low[k];
            if(k > 0) t2 = MathMax(t2, MathMax(MathAbs(high[k] - close[k - 1]), MathAbs(low[k] - close[k - 1])));
            s += t2;
            cnt++;
           }
         cAtr[i] = s / cnt;
        }

      // bands
      double src = Src(i, open, high, low, close);
      double up  = src - InpMult * cAtr[i];
      double dn  = src + InpMult * cAtr[i];
      double up1 = i > 0 ? cUpBand[i - 1] : up;
      double dn1 = i > 0 ? cDnBand[i - 1] : dn;
      double c1  = i > 0 ? close[i - 1] : close[i];
      if(c1 > up1) up = MathMax(up, up1);
      if(c1 < dn1) dn = MathMin(dn, dn1);
      cUpBand[i] = up;
      cDnBand[i] = dn;

      // trend
      double prevT = i > 0 ? cTrend[i - 1] : 1;
      double t = prevT;
      if(prevT == -1 && close[i] > dn1) t = 1;
      else if(prevT == 1 && close[i] < up1) t = -1;
      cTrend[i] = t;

      bUp[i] = t == 1 ? up : EMPTY_VALUE;
      bDn[i] = t == -1 ? dn : EMPTY_VALUE;
      double mid = (open[i] + high[i] + low[i] + close[i]) / 4.0;
      bFillA[i] = InpHighlight ? (t == 1 ? up : dn) : EMPTY_VALUE;
      bFillB[i] = InpHighlight ? mid : EMPTY_VALUE;

      bool buy  = i > 0 && t == 1 && prevT == -1;
      bool sell = i > 0 && t == -1 && prevT == 1;
      bBuy[i]  = InpShowSig && buy ? up : EMPTY_VALUE;
      bSell[i] = InpShowSig && sell ? dn : EMPTY_VALUE;
      if(InpShowSig && i < rates_total - 1)
        {
         if(buy)  Label(i, true, time, up);
         if(sell) Label(i, false, time, dn);
        }
     }

   // alerts on the last closed bar
   int last = rates_total - 2;
   if(prev_calculated == 0 && last > 0) g_lastAlert = time[last];   // no alert for old history
   if(last > 0 && time[last] != g_lastAlert)
     {
      bool buy  = cTrend[last] == 1 && cTrend[last - 1] == -1;
      bool sell = cTrend[last] == -1 && cTrend[last - 1] == 1;
      if(buy || sell)
        {
         string msg = StringFormat("Supertrend %s on %s %s @ %s", buy ? "BUY" : "SELL", _Symbol, EnumToString(_Period), DoubleToString(close[last], _Digits));
         if(InpAlertPopup) Alert(msg);
         if(InpAlertSound) PlaySound(InpSoundFile);
         if(InpAlertPush) SendNotification(msg);
        }
      g_lastAlert = time[last];
     }
   return rates_total;
  }
