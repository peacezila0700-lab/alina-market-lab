//+------------------------------------------------------------------+
//|                                          TrailingStopManager.mq5 |
//|                                         Muhammad Muqeem Korejo   |
//|                                                                  |
//| Trails the stop loss of open positions with one of seven methods |
//| (fixed, ATR, Chandelier exit, swing low/high, previous candle,   |
//| Parabolic SAR, moving average) plus a break-even that includes   |
//| the commission. It is built to be gentle with the trade server:  |
//| it modifies only when the stop improves by at least one step,    |
//| never moves a stop back, respects the stop and freeze levels of  |
//| the broker (buy stops against Bid, sell stops against Ask), waits|
//| between modifications and backs off after a "too many requests". |
//| It keeps no state of its own, so a restart changes nothing.      |
//+------------------------------------------------------------------+
#property copyright "Muhammad Muqeem Korejo"
#property version   "1.00"
#property description "Trailing stop and break-even manager: fixed, ATR, Chandelier, swing, candle, SAR or moving average."
#property description "Modifies only on a real improvement, never loosens a stop, respects stop and freeze levels,"
#property description "break-even includes the commission, works on hedging and netting accounts, survives restarts."

enum ENUM_TSM_METHOD
  {
   TSM_NONE       = 0, // Break-even only (no trailing)
   TSM_FIXED      = 1, // Fixed distance from price
   TSM_ATR        = 2, // ATR distance from price
   TSM_CHANDELIER = 3, // Chandelier exit (extreme since entry - ATR x k)
   TSM_SWING      = 4, // Last swing low / high - buffer
   TSM_CANDLE     = 5, // Previous candle low / high - buffer
   TSM_SAR        = 6, // Parabolic SAR
   TSM_MA         = 7  // Moving average - buffer
  };

enum ENUM_TSM_SCOPE
  {
   TSM_MANUAL = 0, // Manual trades only (magic number 0)
   TSM_MAGIC  = 1, // One magic number
   TSM_ALL    = 2  // All positions
  };

enum ENUM_TSM_UNITS
  {
   TSM_POINTS = 0, // Points
   TSM_ATRX   = 1  // Multiples of ATR
  };

input group "Which positions"
input ENUM_TSM_SCOPE  InpScope        = TSM_ALL;        // Positions to manage
input long            InpMagic        = 0;              // Magic number (for "One magic number")
input bool            InpAllSymbols   = false;          // All symbols (false = this chart's symbol only)

input group "Trailing"
input ENUM_TSM_METHOD InpMethod       = TSM_ATR;        // Method
input ENUM_TIMEFRAMES InpTimeframe    = PERIOD_CURRENT; // Timeframe of ATR, candles, SAR, MA
input ENUM_TSM_UNITS  InpUnits        = TSM_ATRX;       // Units of all distances below
input double          InpDistance     = 2.5;            // Distance (fixed and ATR methods)
input double          InpBuffer       = 0.5;            // Buffer beyond swing / candle / MA
input double          InpStart        = 1.0;            // Start trailing at this profit (0 = at once)
input double          InpStep         = 0.1;            // Minimum improvement for a new stop
input int             InpAtrPeriod    = 14;             // ATR period
input int             InpChandBars    = 22;             // Chandelier: ATR period
input double          InpChandMult    = 3.0;            // Chandelier: ATR multiple
input int             InpSwingStrength= 3;              // Swing: bars on each side of a swing point
input int             InpSwingLookback= 100;            // Swing: bars to search
input double          InpSarStep      = 0.02;           // SAR: step
input double          InpSarMax       = 0.2;            // SAR: maximum
input int             InpMaPeriod     = 20;             // MA: period
input ENUM_MA_METHOD  InpMaMethod     = MODE_EMA;       // MA: method

input group "Break-even"
input bool            InpBreakEven    = true;           // Use break-even
input double          InpBETrigger    = 1.0;            // Move to break-even at this profit
input double          InpBELock       = 0.1;            // Lock this much profit above entry
input bool            InpBECosts      = true;           // Add commission and swap of the position

input group "Safety"
input int             InpMinSeconds   = 5;              // Seconds between two changes of one position
input int             InpMaxPerDay    = 500;            // Maximum modifications per day (0 = no limit)
input double          InpSpreadGuard  = 3.0;            // Skip when spread > x times its average (0 = off)
input int             InpExtraPoints  = 2;              // Extra points kept beyond stop / freeze level
input bool            InpShowPanel    = true;           // Show the status panel
input bool            InpTesterDemo   = true;           // Strategy Tester only: open demo trades to show the trailing

//--- per symbol data
struct SymData
  {
   string            name;
   int               atr;
   int               chandAtr;
   int               sar;
   int               ma;
   double            avgSpread;
  };
SymData   g_sym[];
ulong     g_tickets[];
datetime  g_lastMod[];
datetime  g_backoffUntil = 0;
datetime  g_day = 0;
int       g_modsToday = 0;
bool      g_capWarned = false;
bool      g_algoWarned = false;
string    g_last = "waiting";
bool      g_tester = false;

//+------------------------------------------------------------------+
int OnInit()
  {
   g_tester = (bool)MQLInfoInteger(MQL_TESTER);
   if(InpDistance < 0 || InpBuffer < 0 || InpStep < 0 || InpStart < 0 || InpBETrigger < 0 || InpBELock < 0)
     {
      Print("Trailing Stop Manager: distances must not be negative");
      return INIT_PARAMETERS_INCORRECT;
     }
   if(InpAtrPeriod < 1 || InpChandBars < 1 || InpSwingStrength < 1 || InpSwingLookback < 3 || InpMaPeriod < 1)
     {
      Print("Trailing Stop Manager: periods must be at least 1");
      return INIT_PARAMETERS_INCORRECT;
     }
   if(Sym(_Symbol) < 0)
      return INIT_FAILED;
   EventSetTimer(1);
   Print(StringFormat("Trailing Stop Manager started: %s, %s, distances in %s",
                      EnumToString(InpMethod), EnumToString(InpScope), InpUnits == TSM_POINTS ? "points" : "ATR multiples"));
   return INIT_SUCCEEDED;
  }

void OnDeinit(const int reason)
  {
   EventKillTimer();
   for(int i = 0; i < ArraySize(g_sym); i++)
     {
      IndicatorRelease(g_sym[i].atr);
      if(g_sym[i].chandAtr != INVALID_HANDLE) IndicatorRelease(g_sym[i].chandAtr);
      if(g_sym[i].sar != INVALID_HANDLE) IndicatorRelease(g_sym[i].sar);
      if(g_sym[i].ma != INVALID_HANDLE) IndicatorRelease(g_sym[i].ma);
     }
   Comment("");
  }

void OnTick()  { if(g_tester && InpTesterDemo) TesterDemo(); Manage(); }
void OnTimer() { Manage(); }   // positions of other symbols are managed even when this chart is quiet

//+------------------------------------------------------------------+
//| Indicator handles for a symbol, created once                     |
//+------------------------------------------------------------------+
int Sym(const string s)
  {
   for(int i = 0; i < ArraySize(g_sym); i++)
      if(g_sym[i].name == s)
         return i;
   SymData d;
   d.name = s;
   d.atr = iATR(s, InpTimeframe, InpAtrPeriod);
   d.chandAtr = InpMethod == TSM_CHANDELIER ? iATR(s, InpTimeframe, InpChandBars) : INVALID_HANDLE;
   d.sar = InpMethod == TSM_SAR ? iSAR(s, InpTimeframe, InpSarStep, InpSarMax) : INVALID_HANDLE;
   d.ma = InpMethod == TSM_MA ? iMA(s, InpTimeframe, InpMaPeriod, 0, InpMaMethod, PRICE_CLOSE) : INVALID_HANDLE;
   d.avgSpread = 0;
   if(d.atr == INVALID_HANDLE || (InpMethod == TSM_CHANDELIER && d.chandAtr == INVALID_HANDLE) ||
      (InpMethod == TSM_SAR && d.sar == INVALID_HANDLE) || (InpMethod == TSM_MA && d.ma == INVALID_HANDLE))
     {
      Print("Trailing Stop Manager: cannot create the indicators for ", s, ", error ", GetLastError());
      return -1;
     }
   int n = ArraySize(g_sym);
   ArrayResize(g_sym, n + 1);
   g_sym[n] = d;
   return n;
  }

double Value(const int handle, const int shift)
  {
   double v[1];
   if(handle == INVALID_HANDLE || CopyBuffer(handle, 0, shift, 1, v) != 1 || v[0] == EMPTY_VALUE || v[0] <= 0)
      return 0;
   return v[0];
  }

//+------------------------------------------------------------------+
//| Main loop over the positions                                     |
//+------------------------------------------------------------------+
void Manage()
  {
   datetime now = TimeCurrent();
   datetime day = now - now % 86400;
   if(day != g_day)
     {
      g_day = day;
      g_modsToday = 0;
      g_capWarned = false;
     }
   if(!TerminalInfoInteger(TERMINAL_TRADE_ALLOWED) || !MQLInfoInteger(MQL_TRADE_ALLOWED))
     {
      if(!g_algoWarned && !g_tester)
         Print("Trailing Stop Manager: Algo Trading is off, nothing is changed");
      g_algoWarned = true;
      g_last = "Algo Trading is off";
      Panel(0);
      return;
     }
   g_algoWarned = false;
   int managed = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0 || !PositionSelectByTicket(ticket))
         continue;
      string s = PositionGetString(POSITION_SYMBOL);
      long magic = PositionGetInteger(POSITION_MAGIC);
      if(!InpAllSymbols && s != _Symbol)
         continue;
      if(InpScope == TSM_MANUAL && magic != 0)
         continue;
      if(InpScope == TSM_MAGIC && magic != InpMagic)
         continue;
      managed++;
      ManageOne(ticket, s);
     }
   Panel(managed);
  }

//+------------------------------------------------------------------+
//| One position: compute the best allowed stop and send it          |
//+------------------------------------------------------------------+
void ManageOne(const ulong ticket, const string s)
  {
   if(!PositionSelectByTicket(ticket))
      return;
   int k = Sym(s);
   if(k < 0)
      return;
   bool buy = PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY;
   double open = PositionGetDouble(POSITION_PRICE_OPEN);
   double sl = PositionGetDouble(POSITION_SL);
   double tp = PositionGetDouble(POSITION_TP);
   double volume = PositionGetDouble(POSITION_VOLUME);
   datetime opened = (datetime)PositionGetInteger(POSITION_TIME);
   MqlTick tick;
   if(!SymbolInfoTick(s, tick) || tick.bid <= 0 || tick.ask <= 0)
      return;
   if(!TradeOpen(s))
      return;                          // weekend, daily break: the server would answer "market closed"
   double point = SymbolInfoDouble(s, SYMBOL_POINT);
   double tickSize = SymbolInfoDouble(s, SYMBOL_TRADE_TICK_SIZE);
   if(tickSize <= 0) tickSize = point;
   int digits = (int)SymbolInfoInteger(s, SYMBOL_DIGITS);

   //--- spread guard: an average spread of this symbol, kept per tick
   double spread = tick.ask - tick.bid;
   g_sym[k].avgSpread = g_sym[k].avgSpread <= 0 ? spread : g_sym[k].avgSpread * 0.99 + spread * 0.01;
   if(InpSpreadGuard > 0 && spread > InpSpreadGuard * g_sym[k].avgSpread && g_sym[k].avgSpread > 0)
     {
      g_last = s + ": spread too wide, waiting";
      return;
     }

   double atr = Value(g_sym[k].atr, 1);
   if(InpUnits == TSM_ATRX && atr <= 0)
      return;                          // no ATR yet (history still loading)
   double unit = InpUnits == TSM_POINTS ? point : atr;
   double price = buy ? tick.bid : tick.ask;            // the price a stop of this position is triggered by
   double profit = buy ? price - open : open - price;

   //--- 1. trailing candidate
   double cand = 0;
   if(InpMethod != TSM_NONE && profit >= InpStart * unit)
      cand = Trail(k, s, buy, price, opened, unit);
   //--- 2. break-even candidate
   if(InpBreakEven && profit >= InpBETrigger * unit && InpBETrigger > 0)
     {
      double lock = InpBELock * unit;
      if(InpBECosts)
         lock += CostDistance(ticket, s, volume);
      double be = buy ? open + lock : open - lock;
      if(cand == 0 || (buy ? be > cand : be < cand))
         cand = be;
     }
   if(cand <= 0)
      return;

   //--- 3. round to the tick size, on the safe side
   cand = buy ? MathFloor(cand / tickSize + 1e-9) * tickSize : MathCeil(cand / tickSize - 1e-9) * tickSize;
   cand = NormalizeDouble(cand, digits);

   //--- 4. never loosen, and only a real improvement
   double step = MathMax(InpStep * unit, tickSize);
   if(sl > 0 && (buy ? cand < sl + step - 1e-10 : cand > sl - step + 1e-10))
      return;

   //--- 5. broker limits: stop level against the trigger side, freeze level against both levels
   double stopsLevel = (SymbolInfoInteger(s, SYMBOL_TRADE_STOPS_LEVEL) + InpExtraPoints) * point;
   double freezeLevel = (SymbolInfoInteger(s, SYMBOL_TRADE_FREEZE_LEVEL) + InpExtraPoints) * point;
   if(buy ? cand > tick.bid - stopsLevel : cand < tick.ask + stopsLevel)
     {
      // too close: move it as far as allowed, still only if that is an improvement
      cand = buy ? MathFloor((tick.bid - stopsLevel) / tickSize) * tickSize : MathCeil((tick.ask + stopsLevel) / tickSize) * tickSize;
      cand = NormalizeDouble(cand, digits);
      if(sl > 0 && (buy ? cand < sl + step - 1e-10 : cand > sl - step + 1e-10))
         return;
     }
   if(sl > 0 && (buy ? tick.bid - sl <= freezeLevel : sl - tick.ask <= freezeLevel))
      return;                          // the stop is frozen: the server would refuse
   if(tp > 0 && (buy ? tp - tick.bid <= freezeLevel : tick.ask - tp <= freezeLevel))
      return;

   //--- 6. pace: one change per position every few seconds, a global back-off, a daily cap
   datetime now = TimeCurrent();
   if(now < g_backoffUntil)
      return;
   int slot = Slot(ticket);
   if(InpMinSeconds > 0 && now - g_lastMod[slot] < InpMinSeconds)
      return;
   if(InpMaxPerDay > 0 && g_modsToday >= InpMaxPerDay)
     {
      if(!g_capWarned)
         Print("Trailing Stop Manager: daily limit of ", InpMaxPerDay, " modifications reached, paused until tomorrow");
      g_capWarned = true;
      g_last = "daily limit reached";
      return;
     }

   //--- 7. send
   MqlTradeRequest req;
   MqlTradeResult res;
   ZeroMemory(req);
   ZeroMemory(res);
   req.action = TRADE_ACTION_SLTP;
   req.position = ticket;
   req.symbol = s;
   req.sl = cand;
   req.tp = tp;
   g_lastMod[slot] = now;
   g_modsToday++;
   bool sent = OrderSend(req, res);
   if(sent && (res.retcode == TRADE_RETCODE_DONE || res.retcode == TRADE_RETCODE_PLACED))
     {
      g_last = StringFormat("#%I64u %s %s SL %s -> %s", ticket, buy ? "buy" : "sell", s,
                            sl > 0 ? DoubleToString(sl, digits) : "none", DoubleToString(cand, digits));
      Print("Trailing Stop Manager: ", g_last, " (", MethodName(), ")");
      return;
     }
   uint rc = res.retcode;
   g_last = StringFormat("#%I64u modify refused, code %u", ticket, rc);
   if(rc == TRADE_RETCODE_MARKET_CLOSED)
      g_lastMod[slot] = now + 60;      // try this position again in a minute
   else
   if(rc == TRADE_RETCODE_TOO_MANY_REQUESTS)
     {
      g_backoffUntil = now + 60;
      Print("Trailing Stop Manager: server says too many requests, pausing 60 seconds");
     }
   else
      if(rc == TRADE_RETCODE_CLIENT_DISABLES_AT || rc == TRADE_RETCODE_SERVER_DISABLES_AT)
        {
         g_backoffUntil = now + 300;
         Print("Trailing Stop Manager: Algo Trading is disabled (code ", rc, "), pausing 5 minutes");
        }
      else
         if(rc != TRADE_RETCODE_MARKET_CLOSED && rc != TRADE_RETCODE_INVALID_STOPS && rc != TRADE_RETCODE_FROZEN && rc != TRADE_RETCODE_REQUOTE &&
            rc != TRADE_RETCODE_PRICE_OFF && rc != TRADE_RETCODE_PRICE_CHANGED)
            Print("Trailing Stop Manager: ", g_last, ", ", res.comment);
   // invalid stops / frozen / requote / no prices: the next tick computes again with fresh levels
  }

//+------------------------------------------------------------------+
//| Trailing stop of one method (0 = none)                           |
//+------------------------------------------------------------------+
double Trail(const int k, const string s, const bool buy, const double price, const datetime opened, const double unit)
  {
   switch(InpMethod)
     {
      case TSM_FIXED:
      case TSM_ATR:
        {
         double dist = InpMethod == TSM_ATR && InpUnits == TSM_POINTS ? InpDistance * Value(g_sym[k].atr, 1) : InpDistance * unit;
         if(dist <= 0) return 0;
         return buy ? price - dist : price + dist;
        }
      case TSM_CHANDELIER:
        {
         // extreme since the entry (closed bars and the current bar) minus ATR x k: restart-safe, no memory needed
         double atr = Value(g_sym[k].chandAtr, 1);
         if(atr <= 0) return 0;
         int shift = iBarShift(s, InpTimeframe, opened, false);
         if(shift < 0) return 0;
         double ext = 0;
         if(buy)
           {
            int idx = iHighest(s, InpTimeframe, MODE_HIGH, shift + 1, 0);
            if(idx < 0) return 0;
            ext = iHigh(s, InpTimeframe, idx);
            return ext - InpChandMult * atr;
           }
         int idx = iLowest(s, InpTimeframe, MODE_LOW, shift + 1, 0);
         if(idx < 0) return 0;
         ext = iLow(s, InpTimeframe, idx);
         return ext + InpChandMult * atr;
        }
      case TSM_SWING:
        {
         double lvl = Swing(s, buy, price);
         if(lvl <= 0) return 0;
         return buy ? lvl - InpBuffer * unit : lvl + InpBuffer * unit;
        }
      case TSM_CANDLE:
        {
         double lvl = buy ? iLow(s, InpTimeframe, 1) : iHigh(s, InpTimeframe, 1);
         if(lvl <= 0) return 0;
         return buy ? lvl - InpBuffer * unit : lvl + InpBuffer * unit;
        }
      case TSM_SAR:
        {
         double v = Value(g_sym[k].sar, 1);
         if(v <= 0 || (buy ? v >= price : v <= price)) return 0;   // SAR on the wrong side: the trend has turned
         return v;
        }
      case TSM_MA:
        {
         double v = Value(g_sym[k].ma, 1);
         if(v <= 0) return 0;
         v = buy ? v - InpBuffer * unit : v + InpBuffer * unit;
         if(buy ? v >= price : v <= price) return 0;
         return v;
        }
     }
   return 0;
  }

//+------------------------------------------------------------------+
//| Most recent confirmed swing low (buy) / high (sell) beyond price |
//+------------------------------------------------------------------+
double Swing(const string s, const bool buy, const double price)
  {
   int n = InpSwingStrength;
   int bars = MathMin(InpSwingLookback, iBars(s, InpTimeframe) - n - 1);
   for(int i = n + 1; i <= bars; i++)
     {
      double v = buy ? iLow(s, InpTimeframe, i) : iHigh(s, InpTimeframe, i);
      if(v <= 0) return 0;
      bool pivot = true;
      for(int j = 1; j <= n && pivot; j++)
        {
         double a = buy ? iLow(s, InpTimeframe, i - j) : iHigh(s, InpTimeframe, i - j);
         double b = buy ? iLow(s, InpTimeframe, i + j) : iHigh(s, InpTimeframe, i + j);
         if(buy ? (a < v || b <= v) : (a > v || b >= v))
            pivot = false;
        }
      if(pivot && (buy ? v < price : v > price))
         return v;
     }
   return 0;
  }

//+------------------------------------------------------------------+
//| Commission and swap of the position as a price distance          |
//+------------------------------------------------------------------+
double CostDistance(const ulong ticket, const string s, const double volume)
  {
   double money = PositionGetDouble(POSITION_SWAP);       // negative = a cost
   long posId = PositionGetInteger(POSITION_IDENTIFIER);
   if(HistorySelectByPosition(posId))
      for(int i = HistoryDealsTotal() - 1; i >= 0; i--)
        {
         ulong d = HistoryDealGetTicket(i);
         if(d > 0 && HistoryDealGetInteger(d, DEAL_ENTRY) == DEAL_ENTRY_IN)
            money += 2.0 * HistoryDealGetDouble(d, DEAL_COMMISSION) * MathMin(1.0, volume / MathMax(HistoryDealGetDouble(d, DEAL_VOLUME), 1e-12));
        }
   PositionSelectByTicket(ticket);                        // HistorySelect does not change it, but stay safe
   if(money >= 0)
      return 0;                                           // no cost to cover
   double tv = SymbolInfoDouble(s, SYMBOL_TRADE_TICK_VALUE_LOSS);
   double ts = SymbolInfoDouble(s, SYMBOL_TRADE_TICK_SIZE);
   if(tv <= 0 || ts <= 0 || volume <= 0)
      return 0;
   return -money / (tv * volume) * ts;                    // price distance that earns the cost back
  }

//+------------------------------------------------------------------+
//| Is the symbol inside one of its trade sessions now (server time)?|
//+------------------------------------------------------------------+
bool TradeOpen(const string s)
  {
   if(SymbolInfoInteger(s, SYMBOL_TRADE_MODE) == SYMBOL_TRADE_MODE_DISABLED)
      return false;
   MqlDateTime t;
   TimeToStruct(TimeCurrent(), t);
   long sec = t.hour * 3600 + t.min * 60 + t.sec;
   datetime from, to;
   for(uint i = 0; SymbolInfoSessionTrade(s, (ENUM_DAY_OF_WEEK)t.day_of_week, i, from, to); i++)
      if(sec >= (long)from && sec < (long)to)
         return true;
   //--- no session table at all for this symbol: do not block it
   for(int d = 0; d < 7; d++)
      if(SymbolInfoSessionTrade(s, (ENUM_DAY_OF_WEEK)d, 0, from, to))
         return false;
   return true;
  }

int Slot(const ulong ticket)
  {
   int n = ArraySize(g_tickets);
   for(int i = 0; i < n; i++)
      if(g_tickets[i] == ticket)
         return i;
   if(n >= 200)                                           // forget the oldest slots
     {
      ArrayRemove(g_tickets, 0, 100);
      ArrayRemove(g_lastMod, 0, 100);
      n = ArraySize(g_tickets);
     }
   ArrayResize(g_tickets, n + 1);
   ArrayResize(g_lastMod, n + 1);
   g_tickets[n] = ticket;
   g_lastMod[n] = 0;
   return n;
  }

string MethodName()
  {
   switch(InpMethod)
     {
      case TSM_NONE:       return "break-even only";
      case TSM_FIXED:      return "fixed distance";
      case TSM_ATR:        return "ATR distance";
      case TSM_CHANDELIER: return "Chandelier exit";
      case TSM_SWING:      return "swing";
      case TSM_CANDLE:     return "previous candle";
      case TSM_SAR:        return "Parabolic SAR";
      case TSM_MA:         return "moving average";
     }
   return "";
  }

void Panel(const int managed)
  {
   if(!InpShowPanel || (g_tester && !MQLInfoInteger(MQL_VISUAL_MODE)))
      return;
   Comment(StringFormat("Trailing Stop Manager | %s | %s\nPositions managed: %d | changes today: %d%s\nLast: %s",
                        MethodName(), InpBreakEven ? "break-even on" : "break-even off", managed, g_modsToday,
                        InpMaxPerDay > 0 ? " of " + IntegerToString(InpMaxPerDay) : "", g_last));
  }

//+------------------------------------------------------------------+
//| Strategy Tester only: a few demo trades so the trailing can be   |
//| seen and tested. Never runs on a live or demo chart.             |
//+------------------------------------------------------------------+
void TesterDemo()
  {
   static datetime lastBar = 0;
   static int count = 0;
   datetime bar = iTime(_Symbol, InpTimeframe, 0);
   if(bar == lastBar || bar == 0 || !TradeOpen(_Symbol))
      return;
   lastBar = bar;
   count++;
   //--- close demo positions older than 60 bars that the trailing stop did not close
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong t = PositionGetTicket(i);
      if(t == 0 || PositionGetInteger(POSITION_MAGIC) != 777000 || PositionGetString(POSITION_SYMBOL) != _Symbol)
         continue;
      if(iBarShift(_Symbol, InpTimeframe, (datetime)PositionGetInteger(POSITION_TIME)) < 60)
         return;                                          // one demo position at a time
      MqlTradeRequest rq; MqlTradeResult rs; ZeroMemory(rq); ZeroMemory(rs);
      bool isBuy = PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY;
      rq.action = TRADE_ACTION_DEAL; rq.position = t; rq.symbol = _Symbol;
      rq.volume = PositionGetDouble(POSITION_VOLUME);
      rq.type = isBuy ? ORDER_TYPE_SELL : ORDER_TYPE_BUY;
      rq.price = isBuy ? SymbolInfoDouble(_Symbol, SYMBOL_BID) : SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      rq.deviation = 50; rq.magic = 777000; rq.type_filling = Filling();
      if(!OrderSend(rq, rs)) Print("demo close failed ", rs.retcode);
      return;
     }
   if(count % 10 != 0)
      return;
   //--- direction from a 50-bar moving average slope, so the demo trades usually run in the trend
   double c0 = iClose(_Symbol, InpTimeframe, 1), c50 = iClose(_Symbol, InpTimeframe, 50);
   if(c0 <= 0 || c50 <= 0)
      return;
   bool buy = c0 > c50;
   double vol = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double margin = 0;
   double price = buy ? SymbolInfoDouble(_Symbol, SYMBOL_ASK) : SymbolInfoDouble(_Symbol, SYMBOL_BID);
   if(!OrderCalcMargin(buy ? ORDER_TYPE_BUY : ORDER_TYPE_SELL, _Symbol, vol, price, margin) ||
      margin > AccountInfoDouble(ACCOUNT_MARGIN_FREE) * 0.5)
      return;
   MqlTradeRequest rq; MqlTradeResult rs; ZeroMemory(rq); ZeroMemory(rs);
   rq.action = TRADE_ACTION_DEAL; rq.symbol = _Symbol; rq.volume = vol;
   rq.type = buy ? ORDER_TYPE_BUY : ORDER_TYPE_SELL; rq.price = price;
   rq.deviation = 50; rq.magic = 777000; rq.type_filling = Filling(); rq.comment = "TSM demo";
   if(!OrderSend(rq, rs)) Print("demo trade failed ", rs.retcode);
  }

ENUM_ORDER_TYPE_FILLING Filling()
  {
   long f = SymbolInfoInteger(_Symbol, SYMBOL_FILLING_MODE);
   if((f & SYMBOL_FILLING_FOK) != 0) return ORDER_FILLING_FOK;
   if((f & SYMBOL_FILLING_IOC) != 0) return ORDER_FILLING_IOC;
   return ORDER_FILLING_RETURN;
  }
//+------------------------------------------------------------------+
