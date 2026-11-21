//+------------------------------------------------------------------+
//|                                            GoldenCross_Trend.mq5 |
//| Classic 50/200-day moving average "golden cross" trend filter.    |
//| In the market while the fast SMA of daily closes is above the     |
//| slow SMA, flat (or short, optional) otherwise. One decision per   |
//| completed daily bar, no stop-loss and no take-profit by design.   |
//+------------------------------------------------------------------+
#property copyright "Saad Ferdi"
#property version   "1.00"
#property description "Golden Cross / Death Cross trend filter on daily closes."
#property description "Buys when SMA(fast) > SMA(slow) on the last completed D1 bar and closes when it is not."
#property description "Optional short side. Position size as a % of balance (notional) or a fixed lot."

#include <Trade\Trade.mqh>

//--- input parameters
input int    InpFastPeriod  = 50;     // Fast SMA period (daily closes)
input int    InpSlowPeriod  = 200;    // Slow SMA period (daily closes)
input bool   InpAllowShort  = false;  // Also sell while fast SMA < slow SMA
input double InpNotionalPct = 50.0;   // Position value, % of balance (0 = use fixed lot)
input double InpFixedLot    = 0.10;   // Fixed lot when InpNotionalPct = 0
input long   InpMagic       = 205020; // Magic number
input int    InpDeviation   = 50;     // Max slippage, points

CTrade   m_trade;
int      g_fast = INVALID_HANDLE;
int      g_slow = INVALID_HANDLE;
datetime g_lastDay = 0;

//+------------------------------------------------------------------+
//| Expert initialization                                            |
//+------------------------------------------------------------------+
int OnInit()
  {
   if(InpFastPeriod < 1 || InpSlowPeriod <= InpFastPeriod)
     {
      Print("Slow period must be greater than fast period");
      return(INIT_PARAMETERS_INCORRECT);
     }
   g_fast = iMA(_Symbol, PERIOD_D1, InpFastPeriod, 0, MODE_SMA, PRICE_CLOSE);
   g_slow = iMA(_Symbol, PERIOD_D1, InpSlowPeriod, 0, MODE_SMA, PRICE_CLOSE);
   if(g_fast == INVALID_HANDLE || g_slow == INVALID_HANDLE)
      return(INIT_FAILED);
   m_trade.SetExpertMagicNumber(InpMagic);
   m_trade.SetDeviationInPoints(InpDeviation);
   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
//| Expert deinitialization                                          |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   IndicatorRelease(g_fast);
   IndicatorRelease(g_slow);
  }

//+------------------------------------------------------------------+
//| Expert tick: one decision per new daily bar                      |
//+------------------------------------------------------------------+
void OnTick()
  {
   datetime day = iTime(_Symbol, PERIOD_D1, 0);
   if(day == 0 || day == g_lastDay)
      return;

   //--- values of the last COMPLETED daily bar (shift 1), never the forming one
   double fast[1], slow[1];
   if(CopyBuffer(g_fast, 0, 1, 1, fast) != 1 || CopyBuffer(g_slow, 0, 1, 1, slow) != 1)
      return;   // not enough history yet, try again next tick

   int want = 0;                              // +1 long, -1 short, 0 flat
   if(fast[0] > slow[0])
      want = 1;
   else
      if(InpAllowShort && fast[0] < slow[0])
         want = -1;

   int have = CurrentDirection();
   if(have == want)
     {
      g_lastDay = day;                        // nothing to do today
      return;
     }

   //--- the new daily bar can open while the market is still closed
   //--- (e.g. index CFDs at midnight): wait for the session and retry
   if(!SessionOpen())
      return;

   //--- close the opposite / unwanted position first
   if(have != 0 && !CloseOurPositions())
      return;                                 // retry on the next tick
   if(want == 0)
     {
      g_lastDay = day;
      return;
     }

   double lot = LotSize();
   if(lot <= 0.0)
     {
      Print("Lot below the symbol minimum, no trade");
      g_lastDay = day;
      return;
     }
   bool ok = (want > 0) ? m_trade.Buy(lot, _Symbol, 0.0, 0.0, 0.0, "GoldenCross")
             : m_trade.Sell(lot, _Symbol, 0.0, 0.0, 0.0, "DeathCross");
   if(ok)
      g_lastDay = day;
   else
      PrintFormat("Order failed, retcode %u, will retry", m_trade.ResultRetcode());
  }

//+------------------------------------------------------------------+
//| True if the current server time is inside a trade session        |
//+------------------------------------------------------------------+
bool SessionOpen()
  {
   MqlDateTime now;
   TimeToStruct(TimeCurrent(), now);
   datetime sec = (datetime)(now.hour * 3600 + now.min * 60 + now.sec);
   datetime from, to;
   for(uint i = 0; SymbolInfoSessionTrade(_Symbol, (ENUM_DAY_OF_WEEK)now.day_of_week, i, from, to); i++)
      if(sec >= from && sec < to)
         return(true);
   return(false);
  }

//+------------------------------------------------------------------+
//| Direction of our open position: +1, -1 or 0                      |
//+------------------------------------------------------------------+
int CurrentDirection()
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0)
         continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol || PositionGetInteger(POSITION_MAGIC) != InpMagic)
         continue;
      return(PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY ? 1 : -1);
     }
   return(0);
  }

//+------------------------------------------------------------------+
//| Close every position of this EA on this symbol                   |
//+------------------------------------------------------------------+
bool CloseOurPositions()
  {
   bool allClosed = true;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0)
         continue;
      if(PositionGetString(POSITION_SYMBOL) == _Symbol && PositionGetInteger(POSITION_MAGIC) == InpMagic)
         if(!m_trade.PositionClose(ticket))
           {
            PrintFormat("Close failed, retcode %u, will retry", m_trade.ResultRetcode());
            allClosed = false;
           }
     }
   return(allClosed);
  }

//+------------------------------------------------------------------+
//| Lot from a notional % of balance, or the fixed lot               |
//+------------------------------------------------------------------+
double LotSize()
  {
   double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double vmin = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double vmax = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double lot  = InpFixedLot;
   if(InpNotionalPct > 0.0)
     {
      double price     = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      double tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
      double tickSize  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
      if(price <= 0.0 || tickValue <= 0.0 || tickSize <= 0.0)
         return(0.0);
      double perLot = price * tickValue / tickSize;   // account money per 1.0 lot of exposure
      lot = AccountInfoDouble(ACCOUNT_BALANCE) * InpNotionalPct / 100.0 / perLot;
     }
   lot = MathFloor(lot / step) * step;
   if(lot < vmin)
      return(0.0);
   return(MathMin(lot, vmax));
  }
//+------------------------------------------------------------------+
