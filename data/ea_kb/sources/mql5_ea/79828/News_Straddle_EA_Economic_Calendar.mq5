//+------------------------------------------------------------------+
//| News Straddle EA Economic Calendar               XPro by Xander  |
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
#property description "Buy Stop and Sell Stop around the news of the MT5 economic calendar. The calendar does not run in the tester."
#property description "More tools on my profile. Updates first on my MQL5 channel: mql5.com/en/channels/xander"

#include <Trade/Trade.mqh>

//--- inputs
input string sep0               = "★ News Straddle EA Economic Calendar"; // ══ XPro by Xander ══
input string sep1               = "══════ STRATEGY (NEWS) ══════";   // ─────────────────────
input string InpNewsCurrency    = "CAD,AUD,NZD,GBP,USD"; // News currencies (only those of the chart symbol are used)
input int    InpStartBeforeSec  = 30;    // Place the orders this many seconds before the news
input int    InpStopAfterSec    = 60;    // Delete unfilled orders this many seconds after the news
input bool   InpHighImpact      = true;  // High impact news
input bool   InpMediumImpact    = true;  // Medium impact news
input bool   InpLowImpact       = false; // Low impact news
input int    InpPendingDistance = 100;   // Pending order distance from the price (points)
input bool   InpOCO             = true;  // One cancels the other when a side is filled

input string sep2               = "══════ LOT SETTINGS ══════";       // ─────────────────────
input double InpLotSize         = 0.01;  // Lot size

input string sep3               = "══════ CLOSE / EXIT ══════";       // ─────────────────────
input int    InpTakeProfit      = 300;   // Take profit (points, 0 = off)
input int    InpStopLoss        = 200;   // Stop loss (points, 0 = off)
input int    InpTrailStop       = 100;   // Trailing stop distance (points, 0 = off)
input int    InpTrailStart      = 150;   // Trailing starts at this profit (points)
input int    InpTrailStep       = 20;    // Trailing step (points)

input string sep4               = "══════ EXPERT SETTINGS ══════";    // ─────────────────────
input long   InpMagic           = 20261102; // Magic number
input string InpComment         = "News EA"; // Order comment
input int    InpSlippage        = 30;    // Max slippage (points)
input bool   InpDrawLines       = true;  // Draw vertical lines on the coming news
input color  InpHighColor       = clrRed;    // High impact line colour
input color  InpMediumColor     = clrOrange; // Medium impact line colour
input color  InpLowColor        = clrGold;   // Low impact line colour
input ENUM_LINE_STYLE InpLineStyle = STYLE_DASH; // Line style

#define XP_NAME "News Straddle EA Economic Calendar"

//--- types
struct NewsItem
  {
   ulong             value_id;
   datetime          time;
   int               importance;   // 1 low, 2 medium, 3 high
   string            currency;
   string            name;
  };

struct NewsSet
  {
   ulong             value_id;
   datetime          expire;
   ulong             buy_ticket;
   ulong             sell_ticket;
  };

//--- globals
CTrade   g_trade;
NewsItem g_news[];
NewsSet  g_sets[];
ulong    g_done[];
string   g_cur1 = "";
string   g_cur2 = "";
bool     g_cur1_ok = false;
bool     g_cur2_ok = false;
datetime g_last_load = 0;
const string PREFIX = "XPNEWS_";

//+------------------------------------------------------------------+
int OnInit()
  {
   if(InpLotSize <= 0.0 || InpPendingDistance <= 0 || InpStartBeforeSec < 0 || InpStopAfterSec < 0)
     {
      Print("[", XP_NAME, "] Lot size and pending distance must be above 0, seconds cannot be negative.");
      return(INIT_PARAMETERS_INCORRECT);
     }

   g_trade.SetExpertMagicNumber(InpMagic);
   g_trade.SetDeviationInPoints(InpSlippage);
   g_trade.SetTypeFillingBySymbol(_Symbol);

   g_cur1 = SymbolInfoString(_Symbol, SYMBOL_CURRENCY_BASE);
   g_cur2 = SymbolInfoString(_Symbol, SYMBOL_CURRENCY_PROFIT);
   StringToUpper(g_cur1);
   StringToUpper(g_cur2);
   g_cur1_ok = InList(g_cur1);
   g_cur2_ok = (g_cur2 != g_cur1) && InList(g_cur2);

   if(!g_cur1_ok && !g_cur2_ok)
      Print("[", XP_NAME, "] none of the currencies of ", _Symbol, " (", g_cur1, ", ", g_cur2,
            ") is in News Currency. The EA will not place orders on this chart.");
   else
      Print("[", XP_NAME, "] on ", _Symbol, ". Watching news of: ",
            (g_cur1_ok ? g_cur1 + " " : ""), (g_cur2_ok ? g_cur2 : ""));

   if(MQLInfoInteger(MQL_TESTER))
      Print("[", XP_NAME, "] the economic calendar does not run in the Strategy Tester, so no orders are placed there. Test it on a demo account.");

   LoadNews();
   AdoptExistingOrders();
   EventSetTimer(1);
   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   EventKillTimer();
   ObjectsDeleteAll(0, PREFIX);
   ChartRedraw();
  }

//+------------------------------------------------------------------+
void OnTick()
  {
   ManageSets(TimeTradeServer());
   Trailing();
  }

//+------------------------------------------------------------------+
void OnTimer()
  {
   datetime now = TimeTradeServer();

   if(now - g_last_load >= 300)
      LoadNews();

   for(int i = 0; i < ArraySize(g_news); i++)
     {
      datetime t = g_news[i].time;
      if(now < t - InpStartBeforeSec)
         continue;                 // too early
      if(now >= t)
         continue;                 // news already out, do not chase it
      if(IsDone(g_news[i].value_id))
         continue;
      MarkDone(g_news[i].value_id);
      PlaceSet(g_news[i]);
     }

   ManageSets(now);
   Trailing();
  }

//+------------------------------------------------------------------+
//| News currency list                                               |
//+------------------------------------------------------------------+
bool InList(const string cur)
  {
   if(cur == "")
      return(false);
   string parts[];
   int n = StringSplit(InpNewsCurrency, ',', parts);
   for(int i = 0; i < n; i++)
     {
      string p = parts[i];
      StringTrimLeft(p);
      StringTrimRight(p);
      StringToUpper(p);
      if(p == cur)
         return(true);
     }
   return(false);
  }

//+------------------------------------------------------------------+
bool ImportanceAllowed(const ENUM_CALENDAR_EVENT_IMPORTANCE imp)
  {
   if(imp == CALENDAR_IMPORTANCE_HIGH)
      return(InpHighImpact);
   if(imp == CALENDAR_IMPORTANCE_MODERATE)
      return(InpMediumImpact);
   if(imp == CALENDAR_IMPORTANCE_LOW)
      return(InpLowImpact);
   return(false);
  }

//+------------------------------------------------------------------+
//| Load the calendar for the currencies of the chart symbol        |
//+------------------------------------------------------------------+
void LoadNews()
  {
   ArrayResize(g_news, 0);
   datetime now  = TimeTradeServer();
   datetime from = now - InpStopAfterSec - 3600;
   datetime to   = now + 2 * 86400;

   if(g_cur1_ok)
      LoadCurrency(g_cur1, from, to);
   if(g_cur2_ok)
      LoadCurrency(g_cur2, from, to);

   g_last_load = now;
   if(InpDrawLines)
      DrawLines();
  }

//+------------------------------------------------------------------+
void LoadCurrency(const string cur, const datetime from, const datetime to)
  {
   MqlCalendarValue values[];
   ResetLastError();
   if(!CalendarValueHistory(values, from, to, NULL, cur))
     {
      int err = GetLastError();
      if(err != 0)
         Print("[", XP_NAME, "] calendar error ", err, " while loading ", cur, " news");
      return;
     }

   int n = ArraySize(values);
   for(int i = 0; i < n; i++)
     {
      MqlCalendarEvent ev;
      if(!CalendarEventById(values[i].event_id, ev))
         continue;
      if(!ImportanceAllowed(ev.importance))
         continue;
      if(ev.time_mode != CALENDAR_TIMEMODE_DATETIME)
         continue;                 // skip all day and tentative events

      int k = ArraySize(g_news);
      ArrayResize(g_news, k + 1);
      g_news[k].value_id   = values[i].id;
      g_news[k].time       = values[i].time;
      g_news[k].importance = (int)ev.importance;
      g_news[k].currency   = cur;
      g_news[k].name       = ev.name;
     }
  }

//+------------------------------------------------------------------+
//| Processed news                                                   |
//+------------------------------------------------------------------+
bool IsDone(const ulong id)
  {
   for(int i = 0; i < ArraySize(g_done); i++)
      if(g_done[i] == id)
         return(true);
   return(false);
  }

void MarkDone(const ulong id)
  {
   int k = ArraySize(g_done);
   ArrayResize(g_done, k + 1);
   g_done[k] = id;
  }

//+------------------------------------------------------------------+
//| Lot and price helpers                                            |
//+------------------------------------------------------------------+
double NormalizeLot(double lot)
  {
   double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double mn   = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double mx   = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   if(step <= 0.0)
      step = 0.01;
   lot = MathFloor(lot / step + 1e-9) * step;
   lot = MathMax(mn, MathMin(mx, lot));
   int d = (int)MathMax(0.0, MathCeil(-MathLog10(step)));
   return(NormalizeDouble(lot, d));
  }

int MinStopPoints()
  {
   int stops  = (int)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
   int freeze = (int)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_FREEZE_LEVEL);
   return(MathMax(stops, freeze) + 1);
  }

//+------------------------------------------------------------------+
//| Place the Buy Stop and the Sell Stop for one news                |
//+------------------------------------------------------------------+
void PlaceSet(const NewsItem &nw)
  {
   MqlTick tick;
   if(!SymbolInfoTick(_Symbol, tick))
      return;

   double pt     = _Point;
   int    digits = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   int    minPts = MinStopPoints();
   int    dist   = MathMax(InpPendingDistance, minPts);
   int    slPts  = (InpStopLoss   > 0 ? MathMax(InpStopLoss,   minPts) : 0);
   int    tpPts  = (InpTakeProfit > 0 ? MathMax(InpTakeProfit, minPts) : 0);
   double lot    = NormalizeLot(InpLotSize);

   double buyPrice  = NormalizeDouble(tick.ask + dist * pt, digits);
   double sellPrice = NormalizeDouble(tick.bid - dist * pt, digits);
   double buySL  = (slPts > 0 ? NormalizeDouble(buyPrice  - slPts * pt, digits) : 0.0);
   double buyTP  = (tpPts > 0 ? NormalizeDouble(buyPrice  + tpPts * pt, digits) : 0.0);
   double sellSL = (slPts > 0 ? NormalizeDouble(sellPrice + slPts * pt, digits) : 0.0);
   double sellTP = (tpPts > 0 ? NormalizeDouble(sellPrice - tpPts * pt, digits) : 0.0);

   NewsSet s;
   s.value_id    = nw.value_id;
   s.expire      = nw.time + InpStopAfterSec;
   s.buy_ticket  = 0;
   s.sell_ticket = 0;

   //--- free margin for both sides, checked before sending anything
   double mBuy = 0.0, mSell = 0.0;
   if(!OrderCalcMargin(ORDER_TYPE_BUY, _Symbol, lot, buyPrice, mBuy) ||
      !OrderCalcMargin(ORDER_TYPE_SELL, _Symbol, lot, sellPrice, mSell) ||
      mBuy + mSell >= AccountInfoDouble(ACCOUNT_MARGIN_FREE))
     {
      Print("[", XP_NAME, "] not enough free margin for ", DoubleToString(lot, 2), " lots on both sides. News skipped.");
      return;
     }

   if(g_trade.BuyStop(lot, buyPrice, _Symbol, buySL, buyTP, ORDER_TIME_GTC, 0, InpComment))
      s.buy_ticket = g_trade.ResultOrder();
   else
      Print("[", XP_NAME, "] Buy Stop failed: ", g_trade.ResultRetcode(), " ", g_trade.ResultRetcodeDescription());

   if(g_trade.SellStop(lot, sellPrice, _Symbol, sellSL, sellTP, ORDER_TIME_GTC, 0, InpComment))
      s.sell_ticket = g_trade.ResultOrder();
   else
      Print("[", XP_NAME, "] Sell Stop failed: ", g_trade.ResultRetcode(), " ", g_trade.ResultRetcodeDescription());

   if(s.buy_ticket == 0 && s.sell_ticket == 0)
      return;

   int k = ArraySize(g_sets);
   ArrayResize(g_sets, k + 1);
   g_sets[k] = s;

   Print("[", XP_NAME, "] news ", nw.currency, " | ", nw.name, " | ", TimeToString(nw.time, TIME_DATE | TIME_SECONDS),
         " | Buy Stop ", DoubleToString(buyPrice, digits), " | Sell Stop ", DoubleToString(sellPrice, digits));
  }

//+------------------------------------------------------------------+
//| Order state helpers                                              |
//+------------------------------------------------------------------+
bool IsPending(const ulong ticket)
  {
   return(ticket > 0 && OrderSelect(ticket));
  }

bool WasFilled(const ulong ticket)
  {
   if(ticket == 0)
      return(false);
   if(!HistoryOrderSelect(ticket))
      return(false);
   return(HistoryOrderGetInteger(ticket, ORDER_STATE) == ORDER_STATE_FILLED);
  }

//+------------------------------------------------------------------+
//| OCO and deletion of the pending orders after the news            |
//+------------------------------------------------------------------+
void ManageSets(const datetime now)
  {
   for(int i = ArraySize(g_sets) - 1; i >= 0; i--)
     {
      bool buyPend  = IsPending(g_sets[i].buy_ticket);
      bool sellPend = IsPending(g_sets[i].sell_ticket);

      if(InpOCO)
        {
         if(buyPend && !sellPend && WasFilled(g_sets[i].sell_ticket))
           {
            if(g_trade.OrderDelete(g_sets[i].buy_ticket))
               buyPend = false;
           }
         if(sellPend && !buyPend && WasFilled(g_sets[i].buy_ticket))
           {
            if(g_trade.OrderDelete(g_sets[i].sell_ticket))
               sellPend = false;
           }
        }

      if(now >= g_sets[i].expire)
        {
         if(buyPend && g_trade.OrderDelete(g_sets[i].buy_ticket))
            buyPend = false;
         if(sellPend && g_trade.OrderDelete(g_sets[i].sell_ticket))
            sellPend = false;
        }

      if(!buyPend && !sellPend)
        {
         int last = ArraySize(g_sets) - 1;
         if(i != last)
            g_sets[i] = g_sets[last];
         ArrayResize(g_sets, last);
        }
     }
  }

//+------------------------------------------------------------------+
//| After a restart: keep control of our pending orders              |
//+------------------------------------------------------------------+
void AdoptExistingOrders()
  {
   datetime now    = TimeTradeServer();
   int      window = InpStartBeforeSec + InpStopAfterSec;

   for(int i = OrdersTotal() - 1; i >= 0; i--)
     {
      ulong t = OrderGetTicket(i);
      if(t == 0)
         continue;
      if(OrderGetString(ORDER_SYMBOL) != _Symbol || OrderGetInteger(ORDER_MAGIC) != InpMagic)
         continue;

      datetime setup = (datetime)OrderGetInteger(ORDER_TIME_SETUP);
      if(now - setup > window)
        {
         g_trade.OrderDelete(t);   // old pending order left from a previous run
         continue;
        }

      NewsSet s;
      s.value_id    = 0;
      s.expire      = setup + window;
      s.buy_ticket  = 0;
      s.sell_ticket = 0;
      if((ENUM_ORDER_TYPE)OrderGetInteger(ORDER_TYPE) == ORDER_TYPE_BUY_STOP)
         s.buy_ticket = t;
      else
         s.sell_ticket = t;
      int k = ArraySize(g_sets);
      ArrayResize(g_sets, k + 1);
      g_sets[k] = s;
     }

//--- do not place a second set for a news already in progress
   for(int i = 0; i < ArraySize(g_news); i++)
     {
      datetime t0 = g_news[i].time - InpStartBeforeSec;
      if(now < t0 || now >= g_news[i].time)
         continue;
      if(HasActivitySince(t0 - 5))
         MarkDone(g_news[i].value_id);
     }
  }

bool HasActivitySince(const datetime since)
  {
   for(int i = OrdersTotal() - 1; i >= 0; i--)
     {
      ulong t = OrderGetTicket(i);
      if(t == 0)
         continue;
      if(OrderGetString(ORDER_SYMBOL) == _Symbol && OrderGetInteger(ORDER_MAGIC) == InpMagic &&
         (datetime)OrderGetInteger(ORDER_TIME_SETUP) >= since)
         return(true);
     }
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong p = PositionGetTicket(i);
      if(p == 0)
         continue;
      if(PositionGetString(POSITION_SYMBOL) == _Symbol && PositionGetInteger(POSITION_MAGIC) == InpMagic &&
         (datetime)PositionGetInteger(POSITION_TIME) >= since)
         return(true);
     }
   return(false);
  }

//+------------------------------------------------------------------+
//| Trailing stop                                                    |
//+------------------------------------------------------------------+
void Trailing()
  {
   if(InpTrailStop <= 0)
      return;

   double pt     = _Point;
   int    digits = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   int    trail  = MathMax(InpTrailStop, MinStopPoints());
   double step   = MathMax(InpTrailStep, 1) * pt;
   double bid    = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask    = SymbolInfoDouble(_Symbol, SYMBOL_ASK);

   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong tk = PositionGetTicket(i);
      if(tk == 0)
         continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol || PositionGetInteger(POSITION_MAGIC) != InpMagic)
         continue;

      double open = PositionGetDouble(POSITION_PRICE_OPEN);
      double sl   = PositionGetDouble(POSITION_SL);
      double tp   = PositionGetDouble(POSITION_TP);

      if((ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY)
        {
         if((bid - open) / pt < InpTrailStart)
            continue;
         double newSL = NormalizeDouble(bid - trail * pt, digits);
         if(sl == 0.0 || newSL - sl >= step)
            g_trade.PositionModify(tk, newSL, tp);
        }
      else
        {
         if((open - ask) / pt < InpTrailStart)
            continue;
         double newSL = NormalizeDouble(ask + trail * pt, digits);
         if(sl == 0.0 || sl - newSL >= step)
            g_trade.PositionModify(tk, newSL, tp);
        }
     }
  }

//+------------------------------------------------------------------+
//| Vertical lines on the coming news                                |
//+------------------------------------------------------------------+
void DrawLines()
  {
   ObjectsDeleteAll(0, PREFIX);
   datetime now = TimeTradeServer();

   for(int i = 0; i < ArraySize(g_news); i++)
     {
      if(g_news[i].time < now)
         continue;

      string name = PREFIX + (string)g_news[i].value_id;
      color  c    = InpLowColor;
      if(g_news[i].importance == (int)CALENDAR_IMPORTANCE_HIGH)
         c = InpHighColor;
      else
         if(g_news[i].importance == (int)CALENDAR_IMPORTANCE_MODERATE)
            c = InpMediumColor;

      if(!ObjectCreate(0, name, OBJ_VLINE, 0, g_news[i].time, 0))
         continue;
      ObjectSetInteger(0, name, OBJPROP_COLOR, c);
      ObjectSetInteger(0, name, OBJPROP_STYLE, InpLineStyle);
      ObjectSetInteger(0, name, OBJPROP_BACK, true);
      ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
      ObjectSetString(0, name, OBJPROP_TOOLTIP,
                      g_news[i].currency + " | " + g_news[i].name + " | " +
                      TimeToString(g_news[i].time, TIME_DATE | TIME_MINUTES));
     }
   ChartRedraw();
  }
//+------------------------------------------------------------------+
